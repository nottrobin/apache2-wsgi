import sh
from os import path, pardir
from urllib2 import urlopen, URLError
from charmhelpers.core.host import log


def create_dir(dir_path):
    """
    Create a directoy and all parents, if it doesn't already exists
    and log that we've done so
    """

    if not path.exists(dir_path):
        log('Creating directory: {0}'.format(dir_path))
        run(sh.mkdir, dir_path, p=True)


def can_connect(url):
    """
    Check whether we can connect to a URL
    and log the result
    """

    log("Checking connection to: {0}".format(url))
    success = True

    try:
        urlopen(url, timeout=1)
        log("... can connect")
    except URLError:
        log("... can't connect")
        success = False

    return success


def install_packages(packages):
    """
    Install a list of packages if the list isn't empty
    and log that we've done so
    """

    if packages:
        log("Installing apt packages: {0}".format(packages))
        run(sh.apt_get.install, packages.split(), y=True)


def parent_dir(dir_path):
    if not path.isdir(dir_path):
        dir_path = path.dirname(dir_path)

    return path.abspath(path.join(dir_path, pardir))


def run(sh_function, *args, **kwargs):
    """
    Run command with logging
    """

    output = sh_function(*args, **kwargs)

    if output:
        log(str(output))
