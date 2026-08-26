"""跨电脑配置与本地数据路径。只包含连接/路径配置，不改变测量参数。"""

from copy import deepcopy
import os
from pathlib import Path
import tomllib


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = {
    "visa": {
        "keithley_6221": "GPIB0::12::INSTR",
        "keithley_2182a": "GPIB0::7::INSTR",
        "keithley_2400": "GPIB0::21::INSTR",
    },
    "serial": {
        "magnet": "COM3",
        "rotator": "COM4",
    },
    "data": {
        "output_dir": "",
    },
}

_cached_config = None


def _merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value


def load_config(force=False):
    global _cached_config
    if _cached_config is not None and not force:
        return _cached_config

    config = deepcopy(DEFAULT_CONFIG)
    for filename in ("config.toml", "config.local.toml"):
        path = PROJECT_DIR / filename
        if path.exists():
            with path.open("rb") as file:
                _merge(config, tomllib.load(file))

    _cached_config = config
    return config


def visa_resource(name):
    return str(load_config()["visa"][name])


def serial_port(name):
    return str(load_config()["serial"][name])


def output_root():
    configured = os.environ.get("VI_INST_DATA_DIR", "").strip()
    if not configured:
        configured = str(load_config()["data"].get("output_dir", "")).strip()

    if configured:
        path = Path(os.path.expandvars(configured)).expanduser()
    else:
        path = Path.home() / "VI_Inst_Data"

    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def data_path(filename):
    """返回可写的数据文件路径；相对路径统一放到本地数据根目录。"""
    path = Path(filename)
    if not path.is_absolute():
        path = output_root() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

