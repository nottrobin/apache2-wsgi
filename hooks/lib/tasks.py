#!/usr/bin/env python

import os
from datetime import datetime
from base64 import b64decode

import lib.sh
from lib.charmhelpers.core.hookenv import config


charm_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir)
)


def install_apt_packages():
    """
    Install both core and extra apt packages
    """

    install(config('core_packages').split())
    install(config('extra_packages').split())


def extract_app_files():
    """
    Extract the app zip file
    into an install directory (specified in config)
    """

    app_tgz_path = get_app_tgz()

    install_dir = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    install_path = os.path.join(config('install_path'), install_dir)

    # Extract files into install dir
    sh.tar(
        file=app_tgz_path,
        directory=install_path,
        strip=1, z=True, x=True
    )

    return install_path


def set_current(app_path):
    """
    Set an app directory to the currently live app
    by creating a symlink as specified in config
    """

    current_link_path = os.path.join(
        config('install_path'),
        config('live_symlink_name')
    )

    sh.rm(current_link_path, force=True)
    sh.ln(app_path, current_link_path, symbolic=True)


def get_app_tgz():
    """
    Get the app tar.gz file from the config (if specified)
    and save it in the cache directory
    for later extraction
    """

    app_tgz_path = os.path.join(cache_dir(), 'project.tgz')
    b64_tgz = config('app_package')

    if b64_tgz:
        tgz_contents = b64decode()

        with open(app_tgz_path, 'w') as tgz_file:
            tgz_file.write(tgz_contents)

    return app_tgz_path


def install_dependencies(app_path):
    """
    Install pip and gem dependencies
    for the app
    """

    pip_dependencies_path = 


def install(packages):
    """
    Install a list of packages
    if the list contains any
    """

    if packages:
        sh.apt_get.install(packages, y=True)


def cache_dir():
    """
    Create the cache directory, if it doesn't exist
    and return its path
    """

    cache_dir = os.path.join(charm_dir, 'cache')
    sh.mv(cache_dir, p=True)

    return cache_dir
