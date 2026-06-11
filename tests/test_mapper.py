"""测试 NotebookMapper 笔记本映射器。"""

import pytest
from siyuan_mcp.mapper import NotebookMapper
from siyuan_mcp.siyuan.models import NotebookInfo


@pytest.fixture
def mapper():
    m = NotebookMapper()
    m._notebooks = [
        NotebookInfo(id="nb-ai", name="AI知识体系", closed=False),
        NotebookInfo(id="nb-diary", name="日记本", closed=False),
        NotebookInfo(id="nb-archive", name="项目归档", closed=True),
    ]
    return m


def test_default_returns_first_notebook(mapper):
    assert mapper.resolve("") == "nb-ai"


def test_index_one_based(mapper):
    assert mapper.resolve("1") == "nb-ai"
    assert mapper.resolve("2") == "nb-diary"
    assert mapper.resolve("3") == "nb-archive"


def test_name_exact_match(mapper):
    assert mapper.resolve("AI知识体系") == "nb-ai"
    assert mapper.resolve("日记本") == "nb-diary"


def test_name_fuzzy_match(mapper):
    """输入包含笔记本名称，或笔记本名称包含输入。"""
    assert mapper.resolve("AI") == "nb-ai"
    assert mapper.resolve("知识") == "nb-ai"


def test_index_out_of_range_raises(mapper):
    with pytest.raises(ValueError, match="超出范围"):
        mapper.resolve("0")
    with pytest.raises(ValueError, match="超出范围"):
        mapper.resolve("4")


def test_name_not_found_raises(mapper):
    with pytest.raises(ValueError, match="未找到"):
        mapper.resolve("不存在的笔记本")


def test_format_list_contains_names_and_default_marker(mapper):
    out = mapper.format_list()
    assert "AI知识体系" in out
    assert "日记本" in out
    assert "项目归档" in out
    assert "当前默认" in out
    assert "🔒" in out  # closed 标记
