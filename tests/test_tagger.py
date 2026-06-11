"""测试自动标签生成。"""

import pytest
from siyuan_mcp.tagger import generate_tags


def test_short_content_returns_empty():
    assert generate_tags("短") == []


def test_normal_content_returns_tags():
    content = (
        "JWT 认证方案\n"
        "JWT 是一种基于 Token 的认证方式。"
        "它使用 RS256 签名算法对 Token 进行签名。"
        "认证流程包括登录、签发 Token、验证 Token 三个步骤。"
    )
    tags = generate_tags(content)
    assert len(tags) <= 6
    assert len(tags) >= 1
    # JWT 应该是高频词
    assert any("JWT" in t for t in tags)


def test_max_six_tags():
    content = (
        "Python Rust Go Java 性能对比\n"
        "Python 在 AI 领域有优势，Rust 在系统编程有优势。"
        "Go 在并发编程方面表现优秀。Java 在企业级应用广泛。"
        "这些语言各有特点，适用于不同场景。"
        "性能方面 Rust 最优，Go 次之。"
        "开发效率 Python 最高。生态系统 Java 最丰富。"
    )
    tags = generate_tags(content)
    assert len(tags) <= 6


def test_tags_truncated_to_10_chars():
    content = "这是一个超长标签测试 " * 20
    tags = generate_tags(content)
    for t in tags:
        assert len(t) <= 10


def test_markdown_headers_removed():
    """Markdown 标题不应进入标签。"""
    content = "# 这是一个很长的标题\n\n正文内容是关于认证的话题。认证很重要。"
    tags = generate_tags(content)
    assert "这是一个很长的标题" not in tags
    assert len(tags) > 0
