import configparser
import os
from pathlib import Path


class Configuration(object):
    def __init__(self, cfg_dir=os.environ.get('AWSSSO_CONFIG_DIR', '~/.awssso')):
        self._cfg = configparser.ConfigParser()
        self._cfg_dir = Path(cfg_dir).expanduser()
        self._make_config_dir()
        self._cfg_file = Path(f'{self._cfg_dir.resolve()}/config')
        self._read_config()

    def _make_config_dir(self):
        self._cfg_dir.mkdir(exist_ok=True)

    def _read_config(self):
        self._cfg.read(self._cfg_file.resolve())

    def read_section(self, section):
        try:
            return self._cfg[section]
        except KeyError:
            return {}

    def write_section(self, section, cfg):
        self._cfg[section] = cfg
        with self._cfg_file.open('w') as f:
            self._cfg.write(f)

    def config_dir(self):
        return self._cfg_dir.resolve()
