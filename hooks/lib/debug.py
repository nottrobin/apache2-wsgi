import yaml

config_data = None

with open(path.join(charm_dir, 'config.yaml')) as config_file:
    config_data = yaml.load(config_file.read())['']


def config(key):
    return config_data


def log(message):
    print message
