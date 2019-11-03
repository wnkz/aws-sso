import configparser
import logging
import os
from pathlib import Path

LOG = logging.getLogger(__name__)


class Configuration():
    ALLOWED_OPTIONS = [
        'aws_profile',
        'instance_id',
        'profile_id',
        'region',
        'url',
        'username',
    ]

    def __init__(self, cfg_dir=os.environ.get('AWSSSO_CONFIG_DIR', '~/.awssso')):
        self._config = configparser.ConfigParser()
        self.config_dir = cfg_dir

    def __ensure_config_dir(self):
        self.config_dir.mkdir(exist_ok=True)

    @property
    def config_dir(self):
        return self._config_dir

    @config_dir.setter
    def config_dir(self, value):
        self._config_dir = Path(value).expanduser()
        self.config_file = f'{self.config_dir.resolve()}/config'

    @property
    def config_file(self):
        return self._config_file

    @config_file.setter
    def config_file(self, value):
        self._config_file = Path(value)

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, cfg):
        self._config = cfg

    def arguments_override(self, section, args, create_section=False):
        if section not in self.config:
            LOG.debug(f'section {section} not in configuration')
            if create_section:
                self.config[section] = {}
        params = self.config[section]

        for arg in vars(args):
            value = getattr(args, arg)
            if arg in Configuration.ALLOWED_OPTIONS and value is not None:
                LOG.debug(f'overriding configuration {arg} with {value}')
                params[arg] = value
        return params

    def read(self):
        LOG.debug(f'reading configuration from {self.config_file.resolve()}')
        self.__ensure_config_dir()
        self.config.read(self.config_file.resolve())
        return self

    def save(self):
        LOG.debug(f'writing configuration to {self.config_file.resolve()}')
        with self._config_file.open('w') as f:
            self._config.write(f)
        return self
