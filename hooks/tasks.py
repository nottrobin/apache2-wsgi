#!/usr/bin/env python

import sys
import json
from urllib import urlretrieve
from os import path, getcwd, chdir
from datetime import datetime
from base64 import b64decode

# Add ./lib to path
lib_dir = path.join(path.dirname(__file__), 'lib')
sys.path.append(lib_dir)

import sh
from jinja2 import Environment, FileSystemLoader
from helpers import (
    create_dir, install_packages, can_connect, parent_dir, run
)
from charmhelpers.core.host import service_restart, service_stop
from charmhelpers.core.hookenv import config
from charmhelpers.core.host import log
from charmhelpers.contrib.openstack.utils import save_script_rc


# Settings
install_parent = "/srv"
live_link_name = "current"
live_link_path = path.join(install_parent, live_link_name)
charm_dir = parent_dir(__file__)
timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
apache_dir = "/etc/apache2"
sites_enabled_dir = path.join(apache_dir, "sites-enabled")
sites_enabled_path = path.join(sites_enabled_dir, "wsgi-app.conf")
sites_available_dir = path.join(apache_dir, "sites-available")


def install():
    timestamp = extract_app_files()

    install_dependencies(timestamp)

    setup_apache_wsgi(timestamp)

    set_current(timestamp)


def extract_app_files():
    """
    Extract the app zip file
    into an install directory (specified in config)
    """

    url = config('app_tgz_url')

    install_path = path.join(install_parent, timestamp)
    tempfile_path = '/tmp/wsgi-app-package.tgz'

    create_dir(install_path)

    log(
        "Extracting '{url}' to '{dir}'".format(
            url=url, dir=install_path
        )
    )

    run(sh.rm, tempfile_path, f=True)

    urlretrieve(url, tempfile_path)

    # Extract files into install dir
    run(
        sh.tar,
        file=tempfile_path,
        directory=install_path,
        strip="1", z=True, x=True
    )

    return timestamp


def install_dependencies(timestamp):
    """
    Install pip and gem dependencies for the app

    TODO: test for pip connectivity?
    """

    app_path = path.join(install_parent, timestamp)

    install_packages(config('apt_dependencies'))
    pip_dependencies(app_path)
    gem_dependencies(app_path)


def pip_dependencies(app_path):
    """
    Install pip dependencies from requirements file
    and from the dependencies directory
    """

    # Read paths from config
    requirements_file = config('pip_requirements_path')
    dependencies_directory = config('pip_dependencies_path')
    download_dependencies = config('download_dependencies')
    requirements_path = path.join(app_path, requirements_file)
    dependencies_path = path.join(app_path, dependencies_directory)

    install_requirements = (
        requirements_file and
        download_dependencies and
        path.exists(requirements_path) and
        can_connect('http://pypi.python.org')
    )
    install_dependencies = (
        dependencies_directory and
        path.exists(dependencies_path)
    )

    # Install pip if needed
    if install_requirements or install_dependencies:
        install_packages('python-pip')

    # Install from requirements file if possible
    if install_requirements:
        log(
            "Installing pip requirements from {0}".format(
                requirements_path
            )
        )

        run(sh.pip.install, r=requirements_path)

    # Install dependencies in dependencies directory
    if install_dependencies:
        log("Installing pip dependencies from {0}".format(dependencies_path))
        packages = sh.glob(path.join(dependencies_path, '*'))
        run(sh.pip.install, packages, upgrade=True)


def gem_dependencies(app_path):
    """
    Install gem dependencies from Gemfile
    or from the dependencies directory
    """

    # Read paths from config
    dependencies_directory = config('gem_dependencies_path')
    gemfile_path = path.join(app_path, "Gemfile")
    download_dependencies = config('download_dependencies')
    dependencies_path = path.join(app_path, dependencies_directory)

    install_dependencies = (
        dependencies_directory and
        path.exists(dependencies_path)
    )
    update_bundler = (
        download_dependencies and
        path.exists(gemfile_path) and
        can_connect('http://rubygems.org')
    )

    if install_dependencies or update_bundler:
        install_packages('ruby-dev')

    # Install from requirements file if possible
    if update_bundler:
        install_packages('bundler')

        log("Updating bundle")

        cwd = getcwd()
        chdir(app_path)
        run(sh.bundle.update)
        chdir(cwd)

    # Install gem dependencies in dependencies directory
    if install_dependencies:
        log("Installing gem dependencies from {0}".format(dependencies_path))
        packages = sh.glob(path.join(dependencies_path, '*'))
        run(sh.gem.install, packages)


def setup_apache_wsgi(timestamp):
    install_packages('apache2 libapache2-mod-wsgi')

    run(sh.a2enmod, "ssl", "proxy_http")

    available_path = path.join(sites_available_dir, timestamp)

    (keyfile_path, certificate_path) = copy_ssl_certificates(timestamp)

    template_dir = path.join(charm_dir, 'templates')
    jinja_env = Environment(loader=FileSystemLoader(template_dir))
    conf_template = jinja_env.get_template('wsgi-app.conf')

    wsgi_path = path.join(live_link_path, config('wsgi_file_path'))

    conf_content = conf_template.render({
        'wsgi_path': wsgi_path,
        'wsgi_dir': path.dirname(wsgi_path),
        'wsgi_file': path.basename(wsgi_path),
        'static_url_path': config('static_url_path'),
        'static_path': path.join(live_link_path, config('static_path')),
        'keyfile_path': keyfile_path,
        'certificate_path': certificate_path
    })

    # Save it to sites-available
    with open(available_path, 'w') as conf:
        conf.write(conf_content)

    # Add line to bottom of envvars to source scriptrc
    apache_env_file = path.join(apache_dir, 'envvars')
    source_file_path = path.join(charm_dir, 'scripts/scriptrc')
    source_command = '. {0}'.format(source_file_path)
    with open(apache_env_file, 'a') as env_file:
        env_file.write('# Added by apache2-wsgi charm:\n')
        env_file.write(source_command)


def copy_ssl_certificates(timestamp):
    """
    Copy either the default self-signed certificate
    or the provided custom ones
    into /etc/ssl/certs/wsgi-app.*
    Return the locations of the created files
    """

    certs_dir = '/etc/ssl/certs'
    app_path = path.join(install_parent, timestamp)
    keyfile_path = path.join(certs_dir, 'wsgi-app.key')
    certificate_path = path.join(certs_dir, 'wsgi-app.crt')
    config_path = path.join(charm_dir, 'ssl/wsgi-app.conf')

    custom_keyfile = config('ssl_keyfile')
    custom_certificate = config('ssl_certificate')

    create_dir(certs_dir)

    log('Saving certificate files')

    if custom_keyfile and custom_certificate:
        keyfile_content = b64decode(path.join(app_path, custom_keyfile))
        certificate_content = b64decode(path.join(app_path, custom_certificate))

        with open(keyfile_path, 'w') as keyfile:
            keyfile.write(keyfile_content)

        with open(certificate_path, 'w') as certificate:
            certificate.write(certificate_content)
    else:
        run(
            sh.openssl.req,
            "-new", "-nodes", "-x509", "-newkey", "rsa:2048", "-days",
            "365", "-keyout", keyfile_path, "-out", certificate_path,
            "-config", config_path
        )

    return (keyfile_path, certificate_path)


def set_current(timestamp):
    """
    Set an app directory to the currently live app
    by creating a symlink as specified in config
    """

    app_path = path.join(install_parent, timestamp)

    log(
        "Linking live path '{live}' to app dir: {app_dir}".format(
            app_dir=app_path, live=live_link_path
        )
    )

    run(sh.rm, live_link_path, force=True)
    run(sh.ln, app_path, live_link_path, symbolic=True)

    site_to_enable = path.join(sites_available_dir, timestamp)

    site_links = sh.glob(path.join(sites_enabled_dir, '*'))

    # Delete existing site links
    run(sh.rm, site_links, f=True)

    # Add our link into sites-enabled
    run(sh.ln, site_to_enable, sites_enabled_path, s=True)


def restart():
    service_restart("apache2")
    log('Restarted apache')


def stop():
    service_stop("apache2")


def setup_mongo_relation():
    log('setting up relation: mongodb')

    # Get relation details
    host = sh.unit_get('public-address')
    port = sh.config_get('port') or '27017'

    # Set the relation in this juju instance
    sh.relation_set('hostname={0}'.format(host))
    sh.relation_set('port={0}'.format(port))

    # Compile into mongo URI
    mongo_uri = 'mongodb://{host}:{port}/'.format(
        host=str(host).rstrip(),
        port=str(port).rstrip()
    )

    # Setup environment variable
    env = {'MONGODB_URI': mongo_uri}

    log('setting environment variable: {0}'.format(json.dumps(env)))

    # Save into scripts/scriptrc
    save_script_rc(**env)

    restart()
