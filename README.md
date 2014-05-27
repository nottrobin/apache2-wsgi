Apache WSGI charm
==

This is a [Juju](https://juju.ubuntu.com/) [charm](https://juju.ubuntu.com/charms/) for setting up an [Apache](http://httpd.apache.org/) [mod_wsgi](http://modwsgi.readthedocs.org/en/latest/) server for a basic [Python](https://www.python.org/) [WSGI](http://wsgi.readthedocs.org/en/latest/) app.

Usage
---

### Deploy the charm

``` bash
juju deploy ~nottrobin/trusty/apache2-wsgi
```

### Add a project

The charm will just show a basic Apache2 welcome page, until you give it a URL from which to download a correctly configured WSGI app:

```
juju set app_tgz_url=http://example.com/my-project.tgz
```

It will then download the project, extract it, and restart Apache, attempting to run it.

### Mongodb

If your app wants to make use of a [MongoDB](http://www.mongodb.org/) server, you can do that by adding a relation:

``` bash
juju deploy mongodb
juju add-relation apache-wsgi mongodb
``` 

Now the MongoDB URI for your application to use will be available in the environment variable `MONGODB_URI`.

### Configuring

By default, the WSGI file (`wsgi_file_path`) is expected to be at `[project]/app.py`, and the application name (`wsgi_app_name`) is expected to be `app`. This is in line with [Flask](http://flask.pocoo.org/) defaults.

Any required python modules should be listed in `[project]/requirements.txt` (`pip_requirements_path`) and if you want pip to install them from local files instead of from [PyPi](https://pypi.python.org/), include the local packages in `[project]/pip-cache` (`pip_cache_path`).

For a full list of configuration options, see [`config.yaml`](config.yaml).
