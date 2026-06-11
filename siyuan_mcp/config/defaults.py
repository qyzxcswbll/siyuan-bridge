"""内置默认配置值。用户配置会覆盖这些值。"""

from typing import Any


def get_defaults() -> dict[str, Any]:
    """返回内置默认配置。"""
    return {
        "siyuan": {
            "host": "127.0.0.1",
            "port": 6806,
            "token": "",
        },
        "codebase": {
            "repos": [],
        },
        "search": {
            "max_results": 10,
            "rg_path": "rg",
        },
    }
