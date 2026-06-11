"""思源笔记 HTTP API 客户端封装。"""

from typing import Any

import httpx

from siyuan_mcp.config.loader import Config
from siyuan_mcp.siyuan.models import (
    AppendBlockRequest,
    CreateDocRequest,
    CreateDocResponse,
    NotebookInfo,
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

        self._client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=15.0)

    async def create_doc(
        self,
        markdown: str,
        notebook_id: str = "",
        title: str = "",
        path: str = "",
    ) -> CreateDocResponse:
        """在思源中创建文档。notebook_id 必填（调用 sy-list 获取）。"""
        if not notebook_id:
            raise ValueError("no_notebook")

        data = CreateDocRequest(
            markdown=markdown,
            notebook_id=notebook_id,
            title=title,
            path=path,
        ).model_dump()
        resp = await self._call_api("/api/filetree/createDocWithMd", data)
        # API 返回 data 为文档 ID 字符串，或 null
        doc_id = resp if isinstance(resp, str) else (resp.get("id", "") if resp else "")
        return CreateDocResponse(id=doc_id or "", title=title or "未命名")

    async def search_notes(
        self,
        query: str,
        mode: str = "normal",
        limit: int = 10,
        notebook: str = "",
    ) -> list[SearchNotesResult]:
        """在思源中搜索笔记。"""
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if notebook:
            payload["notebook"] = notebook

        api_path = (
            "/api/search/searchFullText" if mode == "ai"
            else "/api/search/searchNotes"
        )

        resp = await self._call_api(api_path, payload)
        raw_results = resp if isinstance(resp, list) else resp.get("results", [])
        return [SearchNotesResult(**item) for item in raw_results]

    async def get_or_create_daily_note(self, notebook_id: str = "") -> str:
        """获取或创建今日日记。notebook_id 必填（调用 sy-list 获取）。"""
        if not notebook_id:
            raise ValueError("no_notebook")
        payload: dict[str, Any] = {"notebook": notebook_id}
        resp = await self._call_api("/api/filetree/createDailyNote", payload)
        # API 返回 data 为文档 ID 字符串
        return resp if isinstance(resp, str) else (resp.get("id", "") if resp else "")

    async def append_block(self, parent_id: str, content: str) -> list[dict]:
        """向指定块追加内容。"""
        data = AppendBlockRequest(
            parent_id=parent_id,
            data=content,
        ).model_dump()
        return await self._call_api("/api/block/appendBlock", data)

    async def list_notebooks(self) -> list[NotebookInfo]:
        """获取笔记本列表。"""
        resp = await self._call_api("/api/notebook/lsNotebooks", {})
        raw = resp if isinstance(resp, list) else resp.get("notebooks", [])
        return [NotebookInfo(**nb) for nb in raw]

    async def _call_api(self, path: str, data: dict[str, Any]) -> Any:
        """调用思源 API 并处理错误。"""
        try:
            response = await self._client.post(path, json=data)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise ConnectionError("思源笔记未运行，请先启动思源笔记") from e

        if response.status_code != 200:
            raise ConnectionError(
                f"思源 API 返回异常状态码：{response.status_code}"
            )

        body = response.json()
        if body.get("code") != 0:
            raise ValueError(f"思源 API 错误：{body.get('msg', '未知错误')}")

        data = body.get("data")
        if data is None:
            return {}
        return data

    async def close(self):
        await self._client.aclose()
