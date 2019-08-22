import configparser
import os
from pathlib import Path


class Configuration():
    def __init__(self, cfg_dir=os.environ.get('AWSSSO_CONFIG_DIR', '~/.awssso')):
        self._config = configparser.ConfigParser()
        self._config_dir = Path(cfg_dir).expanduser()
        self._config_file = Path(f'{self._config_dir.resolve()}/config')

        self.__ensure_config_dir()
        self.__read()

    def __ensure_config_dir(self):
        self._config_dir.mkdir(exist_ok=True)

    def __read(self):
        self._config.read(self._config_file.resolve())

    @property
    def configfile(self):
        return self._config_file

    @property
    def configdir(self):
        return self._config_dir.resolve()

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, cfg):
        self._config = cfg

    def save(self):
        with self._config_file.open('w') as f:
            self._config.write(f)
