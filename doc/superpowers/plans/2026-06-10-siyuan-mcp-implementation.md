# 思源笔记 MCP 服务 — 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现连接 Claude 与思源笔记的单体 MCP 服务，提供 `sy-save`/`sy-find`/`code-find` 三个工具

**架构：** 单一 Python 进程，通过 MCP stdio 协议与 Claude 通信，内部按职责模块分层（config/siyuan/codebase）

**技术栈：** Python 3.10+、MCP Python SDK、httpx、pyyaml、ripgrep（运行时）

**参考文档：** `doc/superpowers/specs/2026-06-10-siyuan-mcp-design.md`

---

## 文件结构总览

```
d:\Code\siyuan-bridge\
├── siyuan_mcp/
│   ├── __init__.py
│   ├── __main__.py              # python -m 入口
│   ├── server.py                # MCP 服务主文件
│   ├── siyuan/
│   │   ├── __init__.py
│   │   ├── client.py            # 思源 HTTP API 客户端
│   │   └── models.py            # 数据模型（Pydantic）
│   ├── codebase/
│   │   ├── __init__.py
│   │   ├── search.py            # ripgrep 代码搜索
│   │   └── config.py            # 代码库路径管理
│   └── config/
│       ├── __init__.py
│       ├── loader.py            # YAML 加载/合并/校验
│       └── defaults.py          # 内置默认值
├── tests/
│   ├── __init__.py
│   ├── test_config_loader.py
│   ├── test_siyuan_client.py
│   └── test_codebase_search.py
├── config.yaml.example
├── pyproject.toml
└── README.md
```

---

### 任务 1：项目脚手架

**文件：**
- 创建：`pyproject.toml`
- 创建：`siyuan_mcp/__init__.py`
- 创建：`siyuan_mcp/__main__.py`
- 创建：`siyuan_mcp/config/__init__.py`
- 创建：`siyuan_mcp/siyuan/__init__.py`
- 创建：`siyuan_mcp/codebase/__init__.py`
- 创建：`tests/__init__.py`

- [ ] **步骤 1：创建 pyproject.toml**

```toml
[project]
name = "siyuan-mcp"
version = "0.1.0"
description = "MCP service connecting Claude with Siyuan Note"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-httpx>=0.30",
    "ruff>=0.4",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
include = ["siyuan_mcp*"]
```

- [ ] **步骤 2：创建所有 __init__.py**

```python
# siyuan_mcp/__init__.py
"""siyuan-mcp: MCP service for Siyuan Note integration."""

__version__ = "0.1.0"
```

```python
# siyuan_mcp/__main__.py
"""Entry point for `python -m siyuan_mcp`."""

import sys
from siyuan_mcp.server import main

sys.exit(main())
```

```python
# siyuan_mcp/config/__init__.py
from siyuan_mcp.config.loader import ConfigLoader, Config
__all__ = ["ConfigLoader", "Config"]
```

```python
# siyuan_mcp/siyuan/__init__.py
from siyuan_mcp.siyuan.client import SiyuanClient
__all__ = ["SiyuanClient"]
```

```python
# siyuan_mcp/codebase/__init__.py
from siyuan_mcp.codebase.search import CodebaseSearcher
__all__ = ["CodebaseSearcher"]
```

```python
# tests/__init__.py
```

- [ ] **步骤 3：验证导入正确**

运行：`cd d:\Code\siyuan-bridge && python -c "from siyuan_mcp import __version__; print(__version__)"`
预期：`0.1.0`

- [ ] **步骤 4：Commit**

```bash
git add -A
git commit -m "chore: scaffold project structure with pyproject.toml"
```

---

### 任务 2：配置系统 — 默认值与模型

**文件：**
- 创建：`siyuan_mcp/config/defaults.py`

- [ ] **步骤 1：编写测试**

```python
# tests/test_config_loader.py
import pytest
from siyuan_mcp.config.defaults import get_defaults

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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_config_loader.py -v`
预期：ModuleNotFoundError（defaults.py 不存在）

- [ ] **步骤 3：编写默认值模块**

```python
# siyuan_mcp/config/defaults.py
"""内置默认配置值。用户配置会覆盖这些值。"""

from typing import Any

def get_defaults() -> dict[str, Any]:
    """返回内置默认配置。"""
    return {
        "siyuan": {
            "host": "127.0.0.1",
            "port": 6806,
            "token": "",
            "workspace": "",
        },
        "codebase": {
            "repos": [],
        },
        "search": {
            "default_mode": "normal",
            "max_results": 10,
            "rg_path": "rg",
        },
        "storage": {
            "default_notebook": "",
            "inbox_path": "/",
        },
    }
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_config_loader.py -v`
预期：3 passed

- [ ] **步骤 5：Commit**

```bash
git add -A
git commit -m "feat(config): add default configuration values"
```

---

### 任务 3：配置系统 — 加载器（Loader）

**文件：**
- 创建：`siyuan_mcp/config/loader.py`

- [ ] **步骤 1：编写 Config 数据类及 loader 测试**

```python
# 追加到 tests/test_config_loader.py 末尾
import os
import tempfile
import yaml
from pathlib import Path
from siyuan_mcp.config.loader import ConfigLoader, Config


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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_config_loader.py -v`
预期：Failure（loader.py 未实现）

- [ ] **步骤 3：编写 ConfigLoader**

```python
# siyuan_mcp/config/loader.py
"""YAML 配置加载、合并与校验。"""

import os
import json
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
    workspace: str = ""


class CodebaseConfig(BaseModel):
    repos: list[CodebaseRepo] = []


class SearchConfig(BaseModel):
    default_mode: str = "normal"
    max_results: int = 10
    rg_path: str = "rg"


class StorageConfig(BaseModel):
    default_notebook: str = ""
    inbox_path: str = "/"


class Config(BaseModel):
    siyuan: SiyuanConfig = SiyuanConfig()
    codebase: CodebaseConfig = CodebaseConfig()
    search: SearchConfig = SearchConfig()
    storage: StorageConfig = StorageConfig()


_ENV_MAP: dict[str, str] = {
    "SIYUAN_HOST": ("siyuan", "host"),
    "SIYUAN_PORT": ("siyuan", "port"),
    "SIYUAN_TOKEN": ("siyuan", "token"),
    "SIYUAN_WORKSPACE": ("siyuan", "workspace"),
    "CODEBASE_REPOS": ("codebase", "repos"),
    "SEARCH_DEFAULT_MODE": ("search", "default_mode"),
    "SEARCH_MAX_RESULTS": ("search", "max_results"),
    "STORAGE_DEFAULT_NOTEBOOK": ("storage", "default_notebook"),
    "STORAGE_INBOX_PATH": ("storage", "inbox_path"),
}


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
        if p.exists():
            return p
        return None

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
    for env_key, (section, field) in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is None:
            continue
        if env_key == "CODEBASE_REPOS":
            try:
                val = json.loads(val)
            except json.JSONDecodeError:
                continue
            raw.setdefault(section, {})[field] = val
        elif env_key == "SIYUAN_PORT" or env_key == "SEARCH_MAX_RESULTS":
            try:
                val = int(val)
            except ValueError:
                continue
            raw.setdefault(section, {})[field] = val
        else:
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
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_config_loader.py -v`
预期：All tests passed

- [ ] **步骤 5：Commit**

```bash
git add -A
git commit -m "feat(config): implement YAML config loader with env overrides"
```

---

### 任务 4：思源 API 客户端 — 数据模型

**文件：**
- 创建：`siyuan_mcp/siyuan/models.py`

- [ ] **步骤 1：编写测试**

```python
# tests/test_siyuan_client.py
import pytest
from siyuan_mcp.siyuan.models import (
    CreateDocRequest,
    SearchNotesRequest,
    SearchNotesResult,
)


class TestModels:
    def test_create_doc_request_defaults(self):
        req = CreateDocRequest(markdown="# Hello")
        assert req.markdown == "# Hello"
        assert req.notebook_id == ""  # 空=使用默认笔记本

    def test_search_notes_request(self):
        req = SearchNotesRequest(query="test", limit=5)
        assert req.query == "test"
        assert req.limit == 5

    def test_search_notes_result(self):
        data = {
            "id": "abc123",
            "title": "笔记标题",
            "snippet": "匹配片段...",
            "path": "/笔记/文档",
            "score": 0.95,
            "updated": "2026-06-10T12:00:00",
        }
        result = SearchNotesResult(**data)
        assert result.id == "abc123"
        assert result.title == "笔记标题"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_siyuan_client.py -v`
预期：ModuleNotFoundError

- [ ] **步骤 3：编写数据模型**

```python
# siyuan_mcp/siyuan/models.py
"""思源笔记 API 数据模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreateDocRequest(BaseModel):
    """创建文档的请求参数。"""
    markdown: str
    notebook_id: str = ""
    title: str = ""


class CreateDocResponse(BaseModel):
    """创建文档的响应。"""
    id: str
    title: str


class SearchNotesRequest(BaseModel):
    """搜索笔记的请求参数。"""
    query: str
    mode: str = "normal"  # normal | ai
    limit: int = 10
    notebook: str = ""


class SearchNotesResult(BaseModel):
    """单条搜索结果。"""
    id: str
    title: str
    snippet: str
    path: str = ""
    score: float = 0.0
    updated: Optional[str] = None
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_siyuan_client.py -v`
预期：All passed

- [ ] **步骤 5：Commit**

```bash
git add -A
git commit -m "feat(siyuan): add data models for API requests/responses"
```

---

### 任务 5：思源 API 客户端 — 网络调用

**文件：**
- 创建：`siyuan_mcp/siyuan/client.py`

- [ ] **步骤 1：编写测试**

```python
# 追加到 tests/test_siyuan_client.py 末尾
import pytest
from unittest.mock import AsyncMock, patch
from siyuan_mcp.siyuan.client import SiyuanClient
from siyuan_mcp.config.loader import Config, SiyuanConfig


@pytest.mark.asyncio
async def test_save_note_success():
    config = Config()
    config.siyuan = SiyuanConfig(host="127.0.0.1", port=6806, token="")
    client = SiyuanClient(config)

    # 模拟思源 API 响应
    mock_response = {
        "code": 0,
        "msg": "",
        "data": {
            "id": "20260610123456-abc123",
            "title": "测试笔记",
        },
    }

    with patch.object(client._client, "post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = lambda: mock_response

        result = await client.create_doc("# 测试笔记")
        assert result.id == "20260610123456-abc123"
        assert result.title == "测试笔记"


@pytest.mark.asyncio
async def test_search_notes_success():
    config = Config()
    config.siyuan = SiyuanConfig(host="127.0.0.1", port=6806, token="")
    client = SiyuanClient(config)

    mock_response = {
        "code": 0,
        "msg": "",
        "data": [
            {
                "id": "abc123",
                "title": "搜索结果",
                "snippet": "匹配...",
                "path": "/根/文档",
                "score": 0.95,
                "updated": "2026-06-10T12:00:00",
            }
        ],
    }

    with patch.object(client._client, "post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = lambda: mock_response

        results = await client.search_notes("test keyword")
        assert len(results) == 1
        assert results[0].id == "abc123"
        assert results[0].title == "搜索结果"


@pytest.mark.asyncio
async def test_connection_error_returns_friendly_message():
    config = Config()
    config.siyuan = SiyuanConfig(host="127.0.0.1", port=6806, token="")
    client = SiyuanClient(config)

    with patch.object(client._client, "post") as mock_post:
        mock_post.side_effect = Exception("连接被拒绝")

        with pytest.raises(Exception, match="思源笔记未运行"):
            await client.create_doc("# test")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_siyuan_client.py -v`
预期：ModuleNotFoundError / ImportError

- [ ] **步骤 3：编写 SiyuanClient**

```python
# siyuan_mcp/siyuan/client.py
"""思源笔记 HTTP API 客户端封装。"""

from typing import Any

import httpx

from siyuan_mcp.config.loader import Config
from siyuan_mcp.siyuan.models import (
    CreateDocRequest,
    CreateDocResponse,
    SearchNotesRequest,
    SearchNotesResult,
)


class SiyuanClient:
    """思源笔记 API 客户端。封装 HTTP 请求。"""

    def __init__(self, config: Config):
        siyuan = config.siyuan
        base_url = f"http://{siyuan.host}:{siyuan.port}"
        headers = {"Content-Type": "application/json"}
        if siyuan.token:
            headers["Authorization"] = f"Token {siyuan.token}"

        self._client = httpx.AsyncClient(base_url=base_url, headers=headers)

    async def create_doc(
        self,
        markdown: str,
        notebook_id: str = "",
        title: str = "",
    ) -> CreateDocResponse:
        """在思源中创建文档。"""
        data = CreateDocRequest(
            markdown=markdown,
            notebook_id=notebook_id,
            title=title,
        )
        resp = await self._call_api("/api/filetree/createDocWithMd", data.model_dump())
        return CreateDocResponse(
            id=resp.get("id", ""),
            title=resp.get("title", title or "未命名"),
        )

    async def search_notes(
        self,
        query: str,
        mode: str = "normal",
        limit: int = 10,
        notebook: str = "",
    ) -> list[SearchNotesResult]:
        """在思源中搜索笔记。"""
        request_data = SearchNotesRequest(
            query=query,
            mode=mode,
            limit=limit,
            notebook=notebook,
        )

        # 思源 API 路径因模式不同
        api_path = (
            "/api/search/searchFullText" if mode == "ai"
            else "/api/search/searchNotes"
        )

        resp = await self._call_api(api_path, request_data.model_dump())
        raw_results = resp if isinstance(resp, list) else resp.get("results", resp)

        return [SearchNotesResult(**item) for item in raw_results]

    async def _call_api(self, path: str, data: dict[str, Any]) -> Any:
        """调用思源 API 并处理错误。"""
        try:
            response = await self._client.post(path, json=data, timeout=15.0)
        except Exception as e:
            msg = (
                "思源笔记未运行，请先启动思源笔记。"
                if "连接被拒绝" in str(e) or "ConnectError" in type(e).__name__
                else f"思源 API 请求失败：{e}"
            )
            raise ConnectionError(msg) from e

        if response.status_code != 200:
            raise ConnectionError(
                f"思源 API 返回异常状态码：{response.status_code}"
            )

        body = response.json()
        if body.get("code") != 0:
            raise ValueError(
                f"思源 API 错误：{body.get('msg', '未知错误')}"
            )

        return body.get("data", {})

    async def close(self):
        await self._client.aclose()
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_siyuan_client.py -v`
预期：All passed

- [ ] **步骤 5：Commit**

```bash
git add -A
git commit -m "feat(siyuan): implement HTTP API client"
```

---

### 任务 6：代码库搜索 — 路径管理

**文件：**
- 创建：`siyuan_mcp/codebase/search.py`

- [ ] **步骤 1：编写测试**

```python
# tests/test_codebase_search.py
import pytest
from siyuan_mcp.codebase.search import CodebaseSearcher
from siyuan_mcp.config.loader import Config, CodebaseRepo


class TestCodebaseSearcher:
    def test_no_repos_returns_empty(self):
        config = Config()
        searcher = CodebaseSearcher(config)
        results, skipped = searcher.search("test")
        assert results == []
        assert skipped == []

    def test_nonexistent_repo_is_skipped(self, tmp_path):
        config = Config()
        repo = CodebaseRepo(path=str(tmp_path / "nonexistent"), name="ghost")
        config.codebase.repos = [repo]
        searcher = CodebaseSearcher(config)
        results, skipped = searcher.search("test")
        assert results == []
        assert "ghost" in str(skipped[0])

    def test_repo_with_matching_file(self, tmp_path):
        # 在临时目录中创建一个文件
        repo_dir = tmp_path / "wallet"
        repo_dir.mkdir()
        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.go").write_text(
            "package main\n\nfunc Transfer() {}\n"
        )

        config = Config()
        config.codebase.repos = [
            CodebaseRepo(path=str(repo_dir), name="wallet")
        ]
        searcher = CodebaseSearcher(config)
        results, skipped = searcher.search("Transfer")
        assert len(results) == 1
        assert results[0].repo == "wallet"
        assert results[0].file.endswith("main.go")
        assert results[0].line == 3
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_codebase_search.py -v`
预期：ModuleNotFoundError

- [ ] **步骤 3：编写 codebase search**

```python
# siyuan_mcp/codebase/search.py
"""代码库搜索：使用 ripgrep 在本地 Git 项目中搜索代码。"""

import subprocess
import re
from pathlib import Path
from typing import Optional

from siyuan_mcp.config.loader import Config, CodebaseRepo


class CodeSearchResult:
    """单条代码搜索结果。"""
    def __init__(
        self,
        repo: str,
        file: str,
        line: int,
        snippet: str,
        match: str,
    ):
        self.repo = repo
        self.file = file
        self.line = line
        self.snippet = snippet
        self.match = match

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "file": self.file,
            "line": self.line,
            "snippet": self.snippet,
            "match": self.match,
        }


class CodebaseSearcher:
    """代码搜索器。对配置中的每个代码库路径执行 ripgrep。"""

    def __init__(self, config: Config):
        self._repos = config.codebase.repos
        self._rg_path = config.search.rg_path
        self._max_results = config.search.max_results

    def search(
        self,
        query: str,
        path_filter: Optional[str] = None,
        file_type: str = "code",
        context_lines: int = 3,
    ) -> tuple[list[CodeSearchResult], list[str]]:
        """在所有配置的代码库中搜索。

        返回：
            (results, skipped_repos)
        """
        all_results: list[CodeSearchResult] = []
        skipped: list[str] = []

        for repo in self._repos:
            if path_filter and path_filter not in repo.name:
                continue

            repo_path = Path(repo.path)
            if not repo_path.is_dir():
                skipped.append(f"{repo.name}（路径不存在：{repo.path}）")
                continue

            try:
                results = self._search_repo(
                    repo=repo,
                    query=query,
                    file_type=file_type,
                    context_lines=context_lines,
                )
                all_results.extend(results)
            except FileNotFoundError:
                skipped.append(
                    f"{repo.name}（未找到 ripgrep，请安装：winget install BurntSushi.ripgrep）"
            )
            except Exception as e:
                skipped.append(f"{repo.name}（搜索异常：{e}）")

            if len(all_results) >= self._max_results:
                all_results = all_results[: self._max_results]
                break

        return all_results, skipped

    def _search_repo(
        self,
        repo: CodebaseRepo,
        query: str,
        file_type: str,
        context_lines: int,
    ) -> list[CodeSearchResult]:
        """在单个代码库中搜索。"""
        cmd = [
            self._rg_path,
            "--line-number",
            "--with-filename",
            "--no-heading",
            "--color", "never",
        ]

        if context_lines > 0:
            cmd.extend(["--context", str(context_lines)])

        if file_type == "code":
            cmd.extend(["--type-not", "markdown"])
            cmd.extend(["--type-not", "text"])

        try:
            cmd.append(query)
            cmd.append(str(repo.path))
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return []

        if result.returncode not in (0, 1):
            return []  # rg exits 1 when no matches

        return self._parse_rg_output(result.stdout, repo.name)

    def _parse_rg_output(
        self, output: str, repo_name: str
    ) -> list[CodeSearchResult]:
        """解析 ripgrep 文本输出。"""
        results: list[CodeSearchResult] = []
        # rg --no-heading 格式:  filepath:line:content
        pattern = re.compile(r"^(.+?):(\d+):(.*)")

        for line in output.strip().split("\n"):
            m = pattern.match(line)
            if not m:
                continue

            filepath = m.group(1)
            line_num = int(m.group(2))
            content = m.group(3)

            # 跳过上下文行（以 -- 开头的是 rg 的分隔符）
            if content.startswith("--"):
                continue

            # 提取匹配关键词前后内容作为 snippet
            results.append(CodeSearchResult(
                repo=repo_name,
                file=str(Path(filepath).relative_to(
                    Path(filepath).anchor
                ).as_posix()),
                line=line_num,
                snippet=content.strip(),
                match=query,
            ))

        return results
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd d:\Code\siyuan-bridge && python -m pytest tests/test_codebase_search.py -v`
预期：All passed

- [ ] **步骤 5：Commit**

```bash
git add -A
git commit -m "feat(codebase): implement ripgrep-based code search"
```

---

### 任务 7：MCP 服务器 — 工具注册

**文件：**
- 创建：`siyuan_mcp/server.py`
- 修改：`siyuan_mcp/__main__.py`（更新 main 函数）

- [ ] **步骤 1：编写 server 入口和工具注册

```python
# siyuan_mcp/server.py
"""MCP 服务主文件。声明所有工具，启动服务。"""

import sys
from typing import Optional

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

from siyuan_mcp.config.loader import ConfigLoader
from siyuan_mcp.siyuan.client import SiyuanClient
from siyuan_mcp.codebase.search import CodebaseSearcher


# 全局状态（MCP 框架要求工具用同步签名，内部异步调用）
_config = None
_siyuan_client = None
_code_searcher = None

server = Server("siyuan-mcp")


def _ensure_initialized():
    """懒初始化全局依赖。"""
    global _config, _siyuan_client, _code_searcher
    if _config is None:
        loader = ConfigLoader()
        _config = loader.load()
        _siyuan_client = SiyuanClient(_config)
        _code_searcher = CodebaseSearcher(_config)


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """声明 MCP 工具列表。"""
    return [
        types.Tool(
            name="sy-save",
            description="快速保存笔记到思源收集箱。将内容以 Markdown 格式保存到思源笔记的默认笔记本。",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "笔记内容（Markdown 格式）",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选，标签列表",
                    },
                    "source": {
                        "type": "string",
                        "description": "可选，来源标记（如 claude-chat）",
                    },
                },
                "required": ["content"],
            },
        ),
        types.Tool(
            name="sy-find",
            description="搜索思源笔记知识库。支持普通关键词搜索和 AI 语义搜索两种模式。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["normal", "ai"],
                        "description": "搜索模式：normal（关键词匹配）或 ai（语义搜索）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最大返回结果数（默认 10）",
                    },
                    "notebook": {
                        "type": "string",
                        "description": "可选，限定笔记本",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="code-find",
            description="在关联的本地 Git 项目中搜索代码。支持正则表达式，可限定项目范围。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词（支持正则表达式）",
                    },
                    "path": {
                        "type": "string",
                        "description": "可选，限定在特定项目中搜索（匹配 repo name）",
                    },
                    "file_type": {
                        "type": "string",
                        "enum": ["code", "doc"],
                        "description": "文件类型过滤：code（排除文档）或 doc（仅文档）",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "匹配行上下文的行数（默认 3）",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    """工具调用分发。"""
    _ensure_initialized()

    if name == "sy-save":
        return await _handle_sy_save(arguments or {})
    elif name == "sy-find":
        return await _handle_sy_find(arguments or {})
    elif name == "code-find":
        return await _handle_code_find(arguments or {})
    else:
        raise ValueError(f"未知工具：{name}")


async def _handle_sy_save(args: dict) -> list[types.TextContent]:
    """处理 sy-save 保存笔记。"""
    content = args.get("content", "")
    if not content.strip():
        return [types.TextContent(
            type="text",
            text="❌ 内容不能为空",
        )]

    try:
        # 构建标题（取第一行或默认）
        title = args.get("source", "Claude 笔记")
        result = await _siyuan_client.create_doc(
            markdown=content,
            title=title,
        )
        return [types.TextContent(
            type="text",
            text=f"✅ 已保存到思源\n"
                 f"- 文档 ID: `{result.id}`\n"
                 f"- 标题: {result.title}\n"
                 f"- 链接: siyuan://blocks/{result.id}",
        )]
    except ConnectionError as e:
        return [types.TextContent(
            type="text",
            text=f"❌ {e}",
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ 保存失败：{e}",
        )]


async def _handle_sy_find(args: dict) -> list[types.TextContent]:
    """处理 sy-find 搜索知识库。"""
    query = args.get("query", "")
    mode = args.get("mode", "normal")
    limit = args.get("limit", 10)
    notebook = args.get("notebook", "")

    if not query.strip():
        return [types.TextContent(
            type="text",
            text="❌ 搜索关键词不能为空",
        )]

    try:
        results = await _siyuan_client.search_notes(
            query=query,
            mode=mode,
            limit=limit,
            notebook=notebook,
        )

        if not results:
            return [types.TextContent(
                type="text",
                text=f"📭 未找到与「{query}」相关的结果",
            )]

        lines = [f"🔍 找到 {len(results)} 条结果（模式：{mode}）：\n"]
        for r in results:
            lines.append(f"**{r.title}**")
            lines.append(f"> {r.snippet}")
            if r.path:
                lines.append(f"  📁 {r.path}")
            lines.append("")

        return [types.TextContent(type="text", text="\n".join(lines))]
    except ConnectionError as e:
        return [types.TextContent(
            type="text",
            text=f"❌ {e}",
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ 搜索失败：{e}",
        )]


async def _handle_code_find(args: dict) -> list[types.TextContent]:
    """处理 code-find 搜索代码库。"""
    query = args.get("query", "")
    path_filter = args.get("path", None)
    file_type = args.get("file_type", "code")
    context_lines = args.get("context_lines", 3)

    if not query.strip():
        return [types.TextContent(
            type="text",
            text="❌ 搜索关键词不能为空",
        )]

    try:
        results, skipped = _code_searcher.search(
            query=query,
            path_filter=path_filter,
            file_type=file_type,
            context_lines=context_lines,
        )

        if not results:
            msg = f"📭 代码库中未找到「{query}」"
            if skipped:
                msg += f"\n⚠️ 以下项目已跳过：{'；'.join(skipped)}"
            return [types.TextContent(type="text", text=msg)]

        lines = [f"🔍 找到 {len(results)} 处代码匹配「{query}」：\n"]
        for r in results:
            lines.append(f"**{r.repo}** — `{r.file}:{r.line}`")
            lines.append(f"```\n{r.snippet}\n```")
            lines.append("")

        if skipped:
            lines.append(f"⚠️ 以下项目已跳过：{'；'.join(skipped)}")

        return [types.TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ 代码搜索失败：{e}",
        )]


async def main() -> int:
    """启动 MCP 服务。"""
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="siyuan-mcp",
                    server_version="0.1.0",
                ),
            )
        return 0
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1
```

- [ ] **步骤 2：更新 __main__.py**

```python
# siyuan_mcp/__main__.py
"""Entry point for `python -m siyuan_mcp`."""

import asyncio
import sys
from siyuan_mcp.server import main

sys.exit(asyncio.run(main()))
```

- [ ] **步骤 3：验证服务能启动**

运行：`cd d:\Code\siyuan-bridge && echo '{}' | python -m siyuan_mcp`
预期：服务启动，等待 stdio 输入（注意：它会挂起等待输入，按 Ctrl+C 结束）

- [ ] **步骤 4：Commit**

```bash
git add -A
git commit -m "feat(server): implement MCP server with sy-save/sy-find/code-find"
```

---

### 任务 8：示例配置文件

**文件：**
- 创建：`config.yaml.example`

- [ ] **步骤 1：编写示例配置**

```yaml
# config.yaml — 思源笔记 MCP 服务配置
# 将此文件复制到项目根目录或 ~/.siyuan-mcp/config.yaml
# 所有配置项都有默认值，此文件仅列出你需要覆盖的项

# ── 思源笔记连接 ──────────────────────────────────
siyuan:
  # 思源笔记 API 地址（默认 127.0.0.1）
  host: "127.0.0.1"
  # API 端口（思源默认 6806）
  port: 6806
  # API Token（在思源设置 → 关于 → API Token 中获取）
  # 留空表示不鉴权（仅限本地使用）
  token: ""
  # 思源工作空间路径
  # 留空自动检测，如需指定可填如：
  # workspace: "C:/Users/xxx/.siyuan/workspace"

# ── 代码库关联 ────────────────────────────────────
codebase:
  # 要搜索的本地代码库列表
  repos:
    # - path: "D:/Code/wallet"      # 本地路径
    #   name: "wallet"              # 别名（code-find 的 path 参数匹配此项）
    # - path: "D:/Code/exchange"
    #   name: "exchange"
    # - path: "D:/Code/im"
    #   name: "im"
    # 支持 glob 通配：
    # - path: "/home/user/projects/*"

# ── 搜索设置 ──────────────────────────────────────
search:
  # 默认搜索模式: normal（关键词）| ai（语义搜索）
  default_mode: "normal"
  # 默认最大返回结果数
  max_results: 10
  # ripgrep 命令路径（默认在 PATH 中查找）
  rg_path: "rg"

# ── 存储设置 ──────────────────────────────────────
storage:
  # 默认笔记本 ID（空=使用思源默认笔记本）
  default_notebook: ""
  # 收集箱路径
  inbox_path: "/"
```

- [ ] **步骤 2：Commit**

```bash
git add -A
git commit -m "docs: add example config file with comments"
```

---

### 任务 9：README.md

**文件：**
- 创建：`README.md`

- [ ] **步骤 1：编写 README**

```markdown
# siyuan-mcp

连接 Claude 与思源笔记的 MCP 服务，让你在终端中通过自然语言管理知识库。

## 功能

| 工具 | 说明 |
|------|------|
| `sy-save` | 快速保存笔记到思源收集箱 |
| `sy-find` | 搜索思源知识库（关键词/AI 语义） |
| `code-find` | 在本地 Git 项目中搜索代码 |

## 快速开始

### 前置要求

- Python 3.10+
- 思源笔记 v3.6.5+（运行中）
- [ripgrep (rg)](https://github.com/BurntSushi/ripgrep)（可选，用于 `code-find`）

### 安装

```bash
# 克隆仓库
git clone https://github.com/your/siyuan-mcp.git
cd siyuan-mcp

# 安装依赖（推荐使用 uv）
uv sync
# 或使用 pip
pip install -e .
```

### 配置

```bash
# 复制并编辑配置
cp config.yaml.example config.yaml
# 按需修改（代码库路径、思源 Token 等）
```

### 注册到 Claude

```json
{
  "mcpServers": {
    "siyuan-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "D:/Code/siyuan-bridge", "python", "-m", "siyuan_mcp"]
    }
  }
}
```

### 使用示例

```
> 帮我查一下关于 JWT 认证的笔记
→ [sy-find] 搜索思源知识库...

> 保存这段代码分析到思源
→ [sy-save] 保存到收集箱...

> 在钱包项目中搜索 Transfer 函数
→ [code-find] 搜索代码库...
```

## 配置项完整说明

### 思源连接

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `siyuan.host` | `127.0.0.1` | 思源 API 地址 |
| `siyuan.port` | `6806` | 思源 API 端口 |
| `siyuan.token` | `""` | API Token（[获取方式](https://github.com/siyuan-note/siyuan)） |
| `siyuan.workspace` | `""` | 工作空间路径（自动检测） |

### 代码库

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `codebase.repos` | `[]` | 关联代码库列表 |
| `codebase.repos[].path` | — | 本地路径 |
| `codebase.repos[].name` | — | 别名 |

### 搜索

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `search.default_mode` | `normal` | `normal` 或 `ai` |
| `search.max_results` | `10` | 结果数量上限 |
| `search.rg_path` | `rg` | ripgrep 命令路径 |

### 存储

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `storage.default_notebook` | `""` | 默认笔记本 ID |
| `storage.inbox_path` | `"/"` | 收集箱路径 |

### 环境变量

所有配置项均可通过环境变量覆盖。环境变量名规则：`{SECTION}_{KEY}`，全大写。

```bash
export SIYUAN_HOST="192.168.1.100"
export SIYUAN_TOKEN="your-token-here"
export CODEBASE_REPOS='[{"path": "/projects/wallet", "name": "wallet"}]'
export SEARCH_MAX_RESULTS=20
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest -v

# 代码检查
ruff check siyuan_mcp/
```

## 项目结构

```
siyuan_mcp/
├── server.py          # MCP 服务主文件
├── siyuan/            # 思源 API 客户端
├── codebase/          # 代码库搜索
└── config/            # 配置系统
```

## 许可证

MIT
```

- [ ] **步骤 2：Commit**

```bash
git add -A
git commit -m "docs: add README with installation and configuration guide"
```

---

## 自检

- [x] **规格覆盖度：** 设计文档中所有 V1 内容（3 个工具、配置系统、错误处理）都被对应任务覆盖
- [x] **占位符扫描：** 每个代码步骤都包含实际可运行的代码，无 TODO/待定
- [x] **类型一致性：** 所有返回类型、方法签名、参数名在任务间保持一致
- [x] **配置系统完整度：** defaults.py → loader.py → 示例配置形成完整链路
- [x] **错误处理覆盖：** 思源 API 错误、连接错误、配置错误、rg 未安装均有处理
- [x] **测试覆盖：** 配置加载、思源 API 客户端、代码库搜索均有独立测试
