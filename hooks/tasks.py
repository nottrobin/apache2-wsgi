#!/usr/bin/env python

import sys
from urllib import urlretrieve
from os import path, listdir, remove
from base64 import b64decode
from datetime import datetime

# Add ./lib to path
lib_dir = path.join(path.dirname(__file__), 'lib')
sys.path.append(lib_dir)

import sh
from jinja2 import Environment, FileSystemLoader
from helpers import create_dir, install_packages, parent_dir, run
from charmhelpers.core.host import service_restart, service_stop
from charmhelpers.core.hookenv import config
from charmhelpers.core.host import log


# Settings
install_parent = "/srv"
live_link_name = "current"
live_link_path = path.join(install_parent, live_link_name)
charm_dir = parent_dir(__file__)
scriptrc_path = path.join(charm_dir, 'scripts/scriptrc')
apache_dir = "/etc/apache2"
sites_enabled_dir = path.join(apache_dir, "sites-enabled")
sites_enabled_path = path.join(sites_enabled_dir, "wsgi-app.conf")
sites_available_dir = path.join(apache_dir, "sites-available")
timefile_name = '.timestamp.txt'


def install():
    # Install charm dependencies
    install_packages('apache2 python-pip libapache2-mod-wsgi')

    # Make sure extra packages are installed
    install_packages(config('apt_dependencies'))


def config_changed():
    # Make sure required packages are installed
    install_packages(config('apt_dependencies'))

    app_tgz_url = config('app_tgz_url')

    if app_tgz_url:
        timestamp = get_timestamp()

        extract_app_files(app_tgz_url, timestamp)

        install_dependencies(timestamp)

        save_environment_variables_string(config('environment_variables'))

        setup_apache_wsgi(timestamp)

        set_current(timestamp)


def get_timestamp():
    """
    Generate a timestamp and save it in a file
    which can be removed with remove_timestamp
    In case the install fails at any point, it can continue where it left off
    """

    # Generate timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

    if path.exists(timefile_name):
        # Read existing timestamp
        with open(timefile_name, 'r') as timefile:
            timestamp = timefile.read().rstrip()
    else:
        # Save generate timestamp into file
        with open(timefile_name, 'w') as timefile:
            timefile.write(timestamp)

    return timestamp


def remove_timestamp():
    remove(timefile_name)


def extract_app_files(url, timestamp):
    """
    Extract the app zip file
    into an install directory (specified in config)
    """

    install_path = path.join(install_parent, timestamp)

    # Unless install dir already exists, extract it
    if not (path.exists(install_path) and listdir(install_path)):
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


def install_dependencies(timestamp):
    """
    Install pip and gem dependencies for the app

    TODO: test for pip connectivity?
    """

    app_path = path.join(install_parent, timestamp)

    pip_dependencies(app_path)


def pip_dependencies(app_path):
    """
    Install pip dependencies from requirements file
    and from the dependencies directory
    """

    # Read paths from config
    requirements_path = path.join(app_path, config('pip_requirements_path'))
    dependencies_path = path.join(app_path, config('pip_dependencies_path'))

    if path.isfile(requirements_path):
        # Install from requirements file if possible
        log("Installing pip requirements from {0}".format(requirements_path))

        # Install dependencies in dependencies directory
        run(
            sh.pip.install,
            r=requirements_path,
            find_links=dependencies_path,  # Path to local package files
            no_index=config('pip_no_index')  # Use PyPi?
        )


def setup_apache_wsgi(timestamp):
    run(sh.a2enmod, "ssl", "proxy_http")

    available_path = path.join(sites_available_dir, timestamp)

    (keyfile_path, certificate_path) = copy_ssl_certificates(timestamp)

    template_dir = path.join(charm_dir, 'templates')
    jinja_env = Environment(loader=FileSystemLoader(template_dir))
    conf_template = jinja_env.get_template('wsgi-app.conf')

    wsgi_path = path.join(live_link_path, config('wsgi_file_path'))

    conf_content = conf_template.render({
        'wsgi_path': wsgi_path,
        'wsgi_app_name': config('wsgi_app_name'),
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

    comment = '# scriptrc link added by apache2-wsgi charm:'

    comment_exists = False

    with open(apache_env_file) as env_file_read:
        comment_exists = comment in env_file_read.read()

    if not comment_exists:
        with open(apache_env_file, 'a') as env_file:
            env_file.write(comment + '\n')
            env_file.write(source_command + '\n')


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

    # Restart apache
    restart()


def restart():
    service_restart("apache2")
    log('Restarted apache')


def stop():
    service_stop("apache2")


def setup_http_server():
    public_address = sh.unit_get('public-address').rstrip()

    log('setting up "http-server" with address "{0}"'.format(public_address))

    sh.relation_set('hostname={0}'.format(public_address))

    restart()


def store_relation_hostname_in_env(environment_variable_name):
    # Get the hostname of the relation
    relation_hostname = sh.relation_get('hostname').rstrip()

    # Save it as an environment variable
    save_environment_variable(environment_variable_name, relation_hostname)

    restart()


def save_environment_variable(name, value):
    variables_string = '{name}={value}'.format(name=name, value=value)

    save_environment_variables_string(variables_string)


def save_environment_variables_string(env_vars):
    log('setting environment variable: {0}'.format(env_vars))

    export_string = 'export {0}\n'.format(env_vars)

    already_set = False

    with open(scriptrc_path) as scriptrc_read:
        already_set = export_string in scriptrc_read.read()

    # Save into scripts/scriptrc
    if not already_set:
        with open(scriptrc_path, 'a') as scriptrc:
            scriptrc.write(export_string)
