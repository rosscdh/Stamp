from __future__ import with_statement
from fabric.api import *
from fabric.contrib.console import confirm
from fabric.context_managers import settings
from fabric.contrib import files

from git import *

import os
import json
import getpass
import datetime
import time
import requests
from termcolor import colored
from pprint import pprint

debug = True

env.local_project_path = os.path.dirname(os.path.realpath(__file__))

env.repo = Repo(env.local_project_path)

env.project = 'stamp'
env.fixtures = None
env.SHA1_FILENAME = None
env.timestamp = time.time()
env.is_predeploy = False
env.local_user = getpass.getuser()
env.environment = 'local'

env.truthy = ['true','t','y','yes','1',1]
env.falsy = ['false','f','n','no','0',0]

@task
def production():
    env.environment = 'production'
    env.environment_class = 'production'

    env.remote_project_path = '/var/apps/toolkit/stamp/'
    env.deploy_archive_path = '/var/apps/'
    env.virtualenv_path = '/var/apps/.toolkit-live-venv/'

    # change from the default user to 'vagrant'
    env.user = 'ubuntu'
    env.application_user = 'app'
    # connect to the port-forwarded ssh
    env.hosts = ['ec2-184-169-191-190.us-west-1.compute.amazonaws.com', 'ec2-184-72-21-48.us-west-1.compute.amazonaws.com'] if not env.hosts else env.hosts

    env.key_filename = '%s/../lawpal-chef/chef-machines.pem' % env.local_project_path

    env.start_service = 'supervisorctl start puma-stamp-live'
    env.stop_service = 'supervisorctl stop puma-stamp-live'
    env.light_restart = "kill -HUP `cat /tmp/toolkit.pid`"

#
# Update the roles
#
env.roledefs.update({
    'db': ['ec2-50-18-97-221.us-west-1.compute.amazonaws.com'], # the actual db host
    'db-actor': ['ec2-54-241-224-100.us-west-1.compute.amazonaws.com'], # database action host
    'search': ['ec2-54-241-224-100.us-west-1.compute.amazonaws.com'], # elastic search action host
    'web': ['ec2-184-169-191-190.us-west-1.compute.amazonaws.com', 'ec2-184-72-21-48.us-west-1.compute.amazonaws.com'],
    'worker': ['ec2-54-241-224-100.us-west-1.compute.amazonaws.com'],
})


@task
def as_sudo(cmd, **kwargs):
    sudo("%s" % cmd)

@task
def virtualenv(cmd, **kwargs):
  # change to base dir
  #with cd(env.remote_project_path):
    if env.environment_class is 'webfaction':
        # webfaction
        run("source %sbin/activate; %s" % (env.virtualenv_path, cmd,), **kwargs)
    else:
        sudo("source %sbin/activate; %s" % (env.virtualenv_path, cmd,), user=env.application_user, **kwargs)

@task
def pip_install():
    virtualenv('pip install django --upgrade')

@task
def check_permissions():
    with cd(env.remote_project_path):
        virtualenv(cmd='python %s%s/manage.py check_permissions' % (env.remote_project_path, env.project))

@task
def clean_all():
    with cd(env.remote_project_path):
        virtualenv(cmd='python %s%s/manage.py clean_pyc' % (env.remote_project_path, env.project))
        virtualenv(cmd='python %s%s/manage.py cleanup' % (env.remote_project_path, env.project))
        virtualenv(cmd='python %s%s/manage.py clean_nonces' % (env.remote_project_path, env.project))
        virtualenv(cmd='python %s%s/manage.py clean_associations' % (env.remote_project_path, env.project))
        virtualenv(cmd='python %s%s/manage.py clear_cache' % (env.remote_project_path, env.project))
        virtualenv(cmd='python %s%s/manage.py clean_pyc' % (env.remote_project_path, env.project))
        virtualenv(cmd='python %s%s/manage.py compile_pyc' % (env.remote_project_path, env.project))

@task
def clear_cache():
    with cd(env.remote_project_path):
        virtualenv(cmd='python %s%s/manage.py clear_cache' % (env.remote_project_path, env.project))

@task
def clean_pyc():
    with cd(env.remote_project_path):
        virtualenv('python %s%s/manage.py clean_pyc' % (env.remote_project_path, env.project))

@task
def precompile_pyc():
    virtualenv(cmd='python %s%s/manage.py compile_pyc' % (env.remote_project_path, env.project))

@task
def manage(cmd='validate'):
    virtualenv('python %s%s/manage.py %s' % (env.remote_project_path, env.project, cmd))

def get_sha1():
  cd(env.local_project_path)
  return local('git rev-parse --short --verify HEAD', capture=True)

@task
def db_backup(db='toolkit_production'):
    db_backup_name = '%s.bak' % db
    sudo('pg_dump --no-owner --no-acl -Fc %s > /tmp/%s' % (db, db_backup_name,), user='postgres')
    local('scp -i %s %s@%s:/tmp/%s /tmp/' % (env.key_filename, env.user, env.host, db_backup_name,))

@task
def db_restore(db='toolkit_production', db_file=None):
    with settings(warn_only=True): # only warning as we will often have errors importing
        if db_file is None:
            db_file = '/tmp/%s.bak' % db
            if not os.path.exists(db_file):
                print(colored('Database Backup %s does not exist...' % db_file, 'red'))
            else:
                go = prompt(colored('Restore "%s" DB from a file entitled: "%s" in the "%s" environment: Proceed? (y,n)' % (db, db_file, env.environment,), 'yellow'))
                if go in env.truthy:
                    local('echo "DROP DATABASE %s;" | psql -h localhost -U %s' % (db, env.local_user,))
                    local('echo "CREATE DATABASE %s WITH OWNER %s ENCODING \'UTF8\';" | psql -h localhost -U %s' % (db, env.local_user, env.local_user,))
                    local('pg_restore -U %s -h localhost -d %s -Fc %s' % (env.local_user, db, db_file,))

@task
def git_tags():
    """ returns list of tags """
    tags = env.repo.tags
    return tags

@task
def git_previous_tag():
    # last tag in list
    previous = git_tags()[-1]
    return previous

@task
def git_suggest_tag():
    """ split into parts v1.0.0 drops v converts to ints and increaments and reassembles v1.0.1"""
    previous = git_previous_tag().name.split('.')
    mapped = map(int, previous[1:]) # convert all digits to int but exclude the first one as it starts with v and cant be an int
    next = [int(previous[0].replace('v',''))] + mapped #remove string v and append mapped list
    next_rev = next[2] = mapped[-1] + 1 # increment the last digit
    return {
        'next': 'v%s' % '.'.join(map(str,next)), 
        'previous': '.'.join(previous)
    }

@task
@runs_once
def git_set_tag():
    proceed = prompt(colored('Do you want to tag this realease?', 'red'), default='y')
    if proceed in env.truthy:
        suggested = git_suggest_tag()
        tag = prompt(colored('Please enter a tag: previous: %s suggested: %s' % (suggested['previous'], suggested['next']), 'yellow'), default=suggested['next'])
        if tag:
            tag = 'v%s' % tag if tag[0] != 'v' else tag # ensure we start with a "v"

            #message = env.deploy_desc if 'deploy_desc' in env else prompt(colored('Please enter a tag comment', 'green'))
            env.repo.create_tag(tag)
#            local('git tag -a %s -m "%s"' % (tag, comment))
#            local('git push origin %s' % tag)

@task
def git_export(branch='master'):
  env.SHA1_FILENAME = get_sha1()
  if not os.path.exists('/tmp/%s.zip' % env.SHA1_FILENAME):
      local('git archive --format zip --output /tmp/%s.zip --prefix=%s/ %s' % (env.SHA1_FILENAME, env.SHA1_FILENAME, branch,), capture=False)

@task
@runs_once
def current_version_sha():
    current = '%s%s' % (env.remote_project_path, env.project)
    realpath = run('ls -al %s' % current)
    current_sha = realpath.split('/')[-1]
    return current_sha

@task
@runs_once
def diff_outgoing_with_current():
    diff = local('git diff %s %s' % (get_sha1(), current_version_sha(),), capture=True)
    print(diff)

@task
@roles('worker')
def celery_restart():
    with settings(warn_only=True): # only warning as we will often have errors importing
        sudo('supervisorctl restart %s' % env.celery_name )

@task
@roles('worker')
def celery_start(loglevel='info'):
    with settings(warn_only=True): # only warning as we will often have errors importing
        sudo('supervisorctl start %s' % env.celery_name )

@task
@roles('worker')
def celery_stop():
    with settings(warn_only=True): # only warning as we will often have errors importing
        sudo('supervisorctl stop %s' % env.celery_name )

@task
@roles('worker')
def celery_log():
    with settings(warn_only=True): # only warning as we will often have errors importing
        sudo('supervisorctl fg %s' % env.celery_name )

@task
def prepare_deploy():
    git_export()

@task
@runs_once
def update_index():
    with settings(host_string=env.db_host):
        #for i in ['default lawyer', 'firms firm']:
        for i in ['default lawyer',]:
            virtualenv('python %s%s/manage.py update_index -a 100000 -u %s' % (env.remote_project_path, env.project, i))

@task
@runs_once
@roles('db-actor')
def migrate():
    with settings():
        virtualenv('python %s%s/manage.py migrate' % (env.remote_project_path, env.project))

@task
@runs_once
@roles('db-actor')
def syncdb():
    with settings():
        virtualenv('python %s%s/manage.py syncdb' % (env.remote_project_path, env.project))

@task
def clean_versions():
    current_version = get_sha1()
    versions_path = '%sversions' % env.remote_project_path
    cmd = 'cd %s; ls %s/ | grep -v %s | xargs rm -R' % (versions_path, versions_path ,current_version,)
    if env.environment_class is 'webfaction':
        virtualenv(cmd)
    else:
        virtualenv(cmd)

# ------ RESTARTERS ------#
@task
def supervisord_restart():
    with settings(warn_only=True):
        if env.environment_class is 'webfaction':
            restart_service()
        else:
            sudo('supervisorctl restart uwsgi')

@task
def restart_lite():
    with settings(warn_only=True):
        sudo(env.light_restart)

@task
def stop_nginx():
    with settings(warn_only=True):
        sudo('service nginx stop')

@task
def start_nginx():
    with settings(warn_only=True):
        sudo('service nginx start')

@task
def restart_nginx():
    with settings(warn_only=True):
        sudo('service nginx restart')

@task
def restart_service(heavy_handed=False):
    with settings(warn_only=True):
        if env.environment_class not in ['celery']: # dont restart celery nginx services
            if env.environment_class == 'webfaction':
                stop_service()
                start_service()
            else:
                if not heavy_handed:
                    restart_lite()
                else:
                    supervisord_restart()

# ------ END-RESTARTERS ------#


def env_run(cmd):
    return sudo(cmd) if env.environment_class in ['production', 'celery'] else run(cmd)

@task
def deploy_archive_file():
    filename = env.get('SHA1_FILENAME', None)
    if filename is None:
        filename = env.SHA1_FILENAME = get_sha1()
    file_name = '%s.zip' % filename
    if not files.exists('%s/%s' % (env.deploy_archive_path, file_name)):
        as_sudo = env.environment_class in ['production', 'celery']
        put('/tmp/%s' % file_name, env.deploy_archive_path, use_sudo=as_sudo)
        env_run('chown %s:%s %s' % (env.application_user, env.application_user, env.deploy_archive_path) )


def clean_zip():
    file_name = '%s.zip' % env.SHA1_FILENAME
    if files.exists('%s%s' % (env.deploy_archive_path, file_name)):
        env_run('rm %s%s' % (env.deploy_archive_path, file_name,))

@task
def relink():
    if not env.SHA1_FILENAME:
        env.SHA1_FILENAME = get_sha1()

    version_path = '%sversions' % env.remote_project_path
    full_version_path = '%s/%s' % (version_path, env.SHA1_FILENAME)
    project_path = '%s%s' % (env.remote_project_path, env.project,)

    if not env.is_predeploy:
        if files.exists('%s/%s' % (version_path, env.SHA1_FILENAME)): # check the sha1 dir exists
            #if files.exists(project_path, use_sudo=True): # unlink the glynt dir
            if files.exists('%s/%s' % (env.remote_project_path, env.project)): # check the current glynt dir exists
                virtualenv('unlink %s' % project_path)
            virtualenv('ln -s %s/%s %s' % (version_path, env.SHA1_FILENAME, project_path,)) # relink

@task
def clean_start():
    stop_service()
    clean_pyc()
    clear_cache()
    clean_pyc()
    #precompile_pyc()
    start_service()
    clean_zip()

@task
def do_deploy():
    if env.SHA1_FILENAME is None:
        env.SHA1_FILENAME = get_sha1()

    version_path = '%sversions' % env.remote_project_path
    full_version_path = '%s/%s' % (version_path, env.SHA1_FILENAME)
    project_path = '%s%s' % (env.remote_project_path, env.project,)

    if env.environment_class in ['production', 'celery']:
        if not files.exists(version_path):
            env_run('mkdir -p %s' % version_path )
        sudo('chown -R %s:%s %s' % (env.application_user, env.application_user, env.remote_project_path) )

    deploy_archive_file()

    # extract project zip file:into a staging area and link it in
    if not files.exists('%s/manage.py'%full_version_path):
        unzip_archive()


@task
def update_env_conf():
    if env.SHA1_FILENAME is None:
        env.SHA1_FILENAME = get_sha1()

    version_path = '%sversions' % env.remote_project_path
    full_version_path = '%s/%s' % (version_path, env.SHA1_FILENAME)
    project_path = '%s%s' % (env.remote_project_path, env.project,)

    if not env.is_predeploy:
        # copy the live local_settings
        with cd(project_path):
            virtualenv('cp %s/conf/%s.local_settings.py %s/%s/local_settings.py' % (full_version_path, env.environment, full_version_path, env.project))
            virtualenv('cp %s/conf/%s.wsgi.py %s/%s/wsgi.py' % (full_version_path, env.environment, full_version_path, env.project))
            #virtualenv('cp %s/conf/%s.newrelic.ini %s/%s/newrelic.ini' % (full_version_path, env.environment, full_version_path, env.project))

@task
def unzip_archive():
    version_path = '%sversions' % env.remote_project_path
    with cd('%s' % version_path):
        virtualenv('unzip %s%s.zip -d %s' % (env.deploy_archive_path, env.SHA1_FILENAME, version_path,))

@task
def start_service():
    env_run(env.start_service)

@task
def stop_service():
    env_run(env.stop_service)

@task
def deploy(is_predeploy='False',full='False',db='False',search='False'):
    """
    :is_predeploy=True - will deploy the latest MASTER SHA but not link it in: this allows for assets collection
    and requirements update etc...
    """
    env.is_predeploy = is_predeploy.lower() in env.truthy
    full = full.lower() in env.truthy
    db = db.lower() in env.truthy
    search = search.lower() in env.truthy

    prepare_deploy()
    do_deploy()
    relink()
