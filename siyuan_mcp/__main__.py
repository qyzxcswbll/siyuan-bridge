"""Entry point for `python -m siyuan_mcp`."""

import json
import sys
from pathlib import Path

from siyuan_mcp.server import main


def _install():
    """注册 siyuan-mcp 到全局 MCP 配置。"""
    config = {
        "mcpServers": {
            "siyuan-mcp": {
                "command": sys.executable,
                "args": ["-m", "siyuan_mcp"],
            }
        }
    }

    home = Path.home()
    mcp_path = home / ".mcp.json"

    if mcp_path.exists():
        try:
            existing = json.loads(mcp_path.read_text(encoding="utf-8"))
            existing.setdefault("mcpServers", {})["siyuan-mcp"] = config["mcpServers"]["siyuan-mcp"]
            mcp_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception:
            mcp_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    else:
        mcp_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"✅ siyuan-mcp 已注册到 {mcp_path}")
    print("   重启 VS Code 或 Claude Desktop 即可使用")


def _install_cli():
    """CLI entry point 供 `siyuan-mcp-install` 命令调用。"""
    _install()


if __name__ == "__main__":
    if "--install" in sys.argv:
        _install()
    else:
        sys.exit(main())
