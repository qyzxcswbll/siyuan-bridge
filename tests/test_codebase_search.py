"""测试代码库搜索模块。"""

import pytest
from siyuan_mcp.codebase.search import CodebaseSearcher, CodeSearchResult
from siyuan_mcp.config.loader import Config, CodebaseRepo


class TestCodeSearchResult:
    def test_to_dict(self):
        r = CodeSearchResult(
            repo="wallet",
            file="src/main.go",
            line=42,
            snippet="func Transfer() {}",
            match="Transfer",
        )
        d = r.to_dict()
        assert d["repo"] == "wallet"
        assert d["file"] == "src/main.go"
        assert d["line"] == 42


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

    def test_path_filter_excludes_other_repos(self, tmp_path):
        repo_dir = tmp_path / "wallet"
        repo_dir.mkdir()
        (repo_dir / "main.go").write_text("package main\nfunc Transfer() {}\n")

        other_dir = tmp_path / "exchange"
        other_dir.mkdir()
        (other_dir / "main.go").write_text("package main\nfunc Swap() {}\n")

        config = Config()
        config.codebase.repos = [
            CodebaseRepo(path=str(repo_dir), name="wallet"),
            CodebaseRepo(path=str(other_dir), name="exchange"),
        ]
        searcher = CodebaseSearcher(config)
        results, skipped = searcher.search("Transfer", path_filter="exchange")
        assert results == []

    def test_parse_rg_output(self, tmp_path):
        """通过真实 rg 命令测试搜索。"""
        repo_dir = tmp_path / "testrepo"
        repo_dir.mkdir()
        (repo_dir / "main.go").write_text(
            "package main\n\nfunc Transfer() {\n\t// TODO\n}\n"
        )

        config = Config()
        config.codebase.repos = [
            CodebaseRepo(path=str(repo_dir), name="testrepo")
        ]
        config.search.rg_path = "rg"
        searcher = CodebaseSearcher(config)

        results, skipped = searcher.search("Transfer", context_lines=1)
        assert len(results) >= 1
        assert results[0].repo == "testrepo"
        assert "Transfer" in results[0].snippet
