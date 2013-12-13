Stamp
=====

Simple Grape api to covert html to pdf

Get Started
-----------

```
bundle install
foreman start
```

Use it
------

```
curl -d '{"html": "<h2>Title</h2><p><b>para</b></p><p>This is a pretty good test</p>", "filename":"test.pdf"}' 'http://localhost:9292/v1/html/to/pdf' -H Content-Type:application/json -v > test.pdf
```

Set it up on remote
-------------------

```
fab production as_sudo:"rvm install 1.9.3"

fab production virtualenv:"rvm --default use 1.9.3"

fab production virtualenv:"rvm --default use 1.9.3;cd /var/apps/toolkit/stamp/stamp;gem install rake -v '10.1.0'"

fab production virtualenv:"rvm --default use 1.9.3;cd /var/apps/toolkit/stamp/stamp;bundle"

fab production virtualenv:"rvm --default use 1.9.3;cd /var/apps/toolkit/stamp/stamp;bundle exec puma -e production -d -b 'tcp://127.0.0.1:9292' -S /tmp/puma.state --control 'unix:///tmp/pumactl.sock'"
```