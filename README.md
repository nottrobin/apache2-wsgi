Apache WSGI charm
==

This is a [Juju](https://juju.ubuntu.com/) [charm](https://juju.ubuntu.com/charms/) for setting up an [Apache](http://httpd.apache.org/) [mod_wsgi](http://modwsgi.readthedocs.org/en/latest/) server for a basic [Python](https://www.python.org/) [WSGI](http://wsgi.readthedocs.org/en/latest/) app.

Usage
---

Hopefully, this charm will eventually be included in the [Juju charm repository](https://jujucharms.com/), so you can use it with simply `juju deploy apache-wsgi`, but for now you'll need to clone it to use it:

### Cloning

Clone the charm into your `trusty` folder within your charms directory, with the name `django-legal`, e.g.:

``` bash
mkdir -p ~/charms/trusty && cd charms
git clone git@github.com:nottrobin/apache-wsgi-charm.git trusty/apache-wsgi
```

### Preparing

You'll need a link to a zipped tarball of your project, and then to include that in a charm config file along with the other options:


``` yaml
# example config.yaml

apache2-wsgi:
    app_tgz_url: "https://github.com/username/repo/archive/master.tar.gz"
    wsgi_file_path: "django-app/wsgi.py"
    download_dependencies: False
```

Then deploy this charm with the config file:

``` bash
juju deploy --config=config.yaml local:trusty/apache-wsgi
```

### Mongodb

If your app wants to make use of a [MongoDB](http://www.mongodb.org/) server, you can do that by adding a relation:

``` bash
juju deploy mongodb
juju add-relation apache-wsgi mongodb
``` 

Now the MongoDB URI for your application to use will be available in the environment variable `MONGODB_URI`.

### Configuring

For a full list of config options, see the default config options in [`config.yaml`](config.yaml).
