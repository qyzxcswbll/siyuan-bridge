"""代码库搜索：使用 ripgrep 在本地 Git 项目中搜索代码。"""

import re
import subprocess
from pathlib import Path
from typing import Optional

from siyuan_mcp.config.loader import Config, CodebaseRepo


class CodeSearchResult:
    """单条代码搜索结果。"""

    def __init__(self, repo: str, file: str, line: int, snippet: str, match: str):
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


# rg 输出解析正则：filepath:line:content
# 使用贪婪匹配配合回溯，从右侧匹配最后一次出现的 :N: 避免被 Windows 路径 C:\ 干扰
_RG_LINE_RE = re.compile(r"^(.*):(\d+):(.*)$")


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
                    f"{repo.name}（未找到 ripgrep，请安装：https://github.com/BurntSushi/ripgrep）"
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
            "--color",
            "never",
        ]

        if context_lines > 0:
            cmd.extend(["--context", str(context_lines)])

        if file_type == "code":
            cmd.extend(["--type-not", "markdown"])

        cmd.extend([query, str(repo.path)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return []

        if result.returncode not in (0, 1):
            return []

        return self._parse_rg_output(result.stdout, repo.name, query)

    def _parse_rg_output(
        self, output: str, repo_name: str, match_query: str
    ) -> list[CodeSearchResult]:
        """解析 ripgrep 文本输出。"""
        results: list[CodeSearchResult] = []

        for line in output.strip().split("\n"):
            m = _RG_LINE_RE.match(line)
            if not m:
                continue

            filepath = m.group(1)
            line_num = int(m.group(2))
            content = m.group(3)

            if content.startswith("--"):
                continue

            results.append(
                CodeSearchResult(
                    repo=repo_name,
                    file=filepath,
                    line=line_num,
                    snippet=content.strip(),
                    match=match_query,
                )
            )

        return results
