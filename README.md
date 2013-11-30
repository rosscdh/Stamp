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