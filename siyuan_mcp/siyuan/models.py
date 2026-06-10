"""思源笔记 API 数据模型。"""

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
