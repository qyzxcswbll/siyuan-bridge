"""YAML 配置加载、合并与校验。"""

import json
import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel

from siyuan_mcp.config.defaults import get_defaults


class CodebaseRepo(BaseModel):
    path: str
    name: str


class SiyuanConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 6806
    token: str = ""


class CodebaseConfig(BaseModel):
    repos: list[CodebaseRepo] = []


class SearchConfig(BaseModel):
    max_results: int = 10
    rg_path: str = "rg"


class Config(BaseModel):
    siyuan: SiyuanConfig = SiyuanConfig()
    codebase: CodebaseConfig = CodebaseConfig()
    search: SearchConfig = SearchConfig()


# 环境变量到配置路径的映射：(env_key, (section, field))
_ENV_MAP: list[tuple[str, tuple[str, str]]] = [
    ("SIYUAN_HOST", ("siyuan", "host")),
    ("SIYUAN_PORT", ("siyuan", "port")),
    ("SIYUAN_TOKEN", ("siyuan", "token")),
    ("CODEBASE_REPOS", ("codebase", "repos")),
    ("SEARCH_MAX_RESULTS", ("search", "max_results")),
]


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 覆盖 base。"""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _find_config_path(custom_path: Optional[str]) -> Optional[Path]:
    """按优先级查找配置文件。"""
    if custom_path:
        p = Path(custom_path)
        return p if p.exists() else None

    candidates = [
        Path.cwd() / "config.yaml",
        Path.cwd() / "config.yml",
        Path.home() / ".siyuan-mcp" / "config.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_yaml(path: Path) -> dict:
    """加载 YAML 文件，返回字典。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("配置格式错误：顶层必须是对象")
        return data
    except yaml.YAMLError as e:
        raise ValueError(f"配置格式错误：{e}") from e


def _apply_env_overrides(raw: dict) -> dict:
    """通过环境变量覆盖配置。"""
    for env_key, (section, field) in _ENV_MAP:
        val = os.environ.get(env_key)
        if val is None:
            continue

        if env_key == "CODEBASE_REPOS":
            val = json.loads(val)
        elif env_key in ("SIYUAN_PORT", "SEARCH_MAX_RESULTS"):
            val = int(val)

        raw.setdefault(section, {})[field] = val
    return raw


class ConfigLoader:
    """配置加载器：按优先级加载并合并配置。"""

    def __init__(self, config_path: Optional[str] = None):
        self._custom_path = config_path

    def load(self) -> Config:
        raw = get_defaults()

        yaml_path = _find_config_path(self._custom_path)
        if yaml_path:
            yaml_data = _load_yaml(yaml_path)
            raw = _deep_merge(raw, yaml_data)

        raw = _apply_env_overrides(raw)
        return Config(**raw)
