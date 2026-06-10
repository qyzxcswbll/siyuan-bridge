"""测试配置系统：默认值 + 加载器。"""

import os
import tempfile
import pytest
import yaml
from siyuan_mcp.config.defaults import get_defaults
from siyuan_mcp.config.loader import ConfigLoader, Config, CodebaseRepo


# ── 默认值测试 ─────────────────────────────────

def test_get_defaults_returns_expected_structure():
    defaults = get_defaults()
    assert "siyuan" in defaults
    assert "codebase" in defaults
    assert "search" in defaults
    assert "storage" in defaults


def test_siyuan_defaults():
    defaults = get_defaults()
    siyuan = defaults["siyuan"]
    assert siyuan["host"] == "127.0.0.1"
    assert siyuan["port"] == 6806
    assert siyuan["token"] == ""
    assert siyuan["workspace"] == ""


def test_search_defaults():
    defaults = get_defaults()
    search = defaults["search"]
    assert search["default_mode"] == "normal"
    assert search["max_results"] == 10
    assert search["rg_path"] == "rg"


# ── 加载器测试 ─────────────────────────────────

class TestConfigLoader:
    def test_default_config_when_no_file(self):
        loader = ConfigLoader(config_path=None)
        config = loader.load()
        assert isinstance(config, Config)
        assert config.siyuan.host == "127.0.0.1"
        assert config.siyuan.port == 6806
        assert config.codebase.repos == []

    def test_load_from_yaml_file(self):
        data = {
            "siyuan": {"host": "0.0.0.0", "token": "abc123"},
            "codebase": {
                "repos": [{"path": "/tmp/test-repo", "name": "test"}]
            },
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(data, f)
            fpath = f.name

        try:
            loader = ConfigLoader(config_path=fpath)
            config = loader.load()
            assert config.siyuan.host == "0.0.0.0"
            assert config.siyuan.token == "abc123"
            assert config.siyuan.port == 6806  # 未覆盖的使用默认值
            assert len(config.codebase.repos) == 1
            assert config.codebase.repos[0].name == "test"
        finally:
            os.unlink(fpath)

    def test_environment_variable_overrides(self):
        os.environ["SIYUAN_HOST"] = "10.0.0.1"
        os.environ["SEARCH_MAX_RESULTS"] = "20"
        try:
            loader = ConfigLoader(config_path=None)
            config = loader.load()
            assert config.siyuan.host == "10.0.0.1"
            assert config.search.max_results == 20
        finally:
            del os.environ["SIYUAN_HOST"]
            del os.environ["SEARCH_MAX_RESULTS"]

    def test_invalid_yaml_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("invalid: yaml: : broken")
            fpath = f.name

        try:
            loader = ConfigLoader(config_path=fpath)
            with pytest.raises(ValueError, match="配置格式错误"):
                loader.load()
        finally:
            os.unlink(fpath)

    def test_siyuan_port_env_override(self):
        os.environ["SIYUAN_PORT"] = "9999"
        try:
            loader = ConfigLoader(config_path=None)
            config = loader.load()
            assert config.siyuan.port == 9999
        finally:
            del os.environ["SIYUAN_PORT"]
