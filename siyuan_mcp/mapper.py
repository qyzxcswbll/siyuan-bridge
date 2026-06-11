"""笔记本序号/名称 → notebook_id 映射。"""

from siyuan_mcp.siyuan.models import NotebookInfo


class NotebookMapper:
    """将用户输入的序号或笔记本名称映射为 notebook_id。

    用户输入:
        ""       → 索引 0（默认笔记本）
        "2"      → 索引 1（1-based 序号）
        "AI知识" → 模糊匹配笔记本名称
    """

    def __init__(self):
        self._notebooks: list[NotebookInfo] = []

    def set_notebooks(self, notebooks: list[NotebookInfo]):
        self._notebooks = list(notebooks)

    def resolve(self, spec: str = "") -> str:
        if not spec:
            if not self._notebooks:
                raise ValueError("笔记本列表为空，请先调用 sy-list")
            return self._notebooks[0].id

        # 序号模式："1" → 索引 0
        if spec.isdigit():
            idx = int(spec) - 1
            if idx < 0 or idx >= len(self._notebooks):
                raise ValueError(
                    f"笔记本序号超出范围（1-{len(self._notebooks)}）"
                )
            return self._notebooks[idx].id

        # 名称模式：精确匹配优先，模糊匹配回退
        for nb in self._notebooks:
            if spec == nb.name:
                return nb.id
        for nb in self._notebooks:
            if spec in nb.name or nb.name in spec:
                return nb.id

        raise ValueError(f"未找到笔记本「{spec}」")

    def format_list(self) -> str:
        if not self._notebooks:
            return "📚 笔记本列表为空"
        lines = ["📚 思源笔记本列表：\n"]
        for i, nb in enumerate(self._notebooks, 1):
            marker = " ← 当前默认" if i == 1 else ""
            lock = " 🔒" if nb.closed else ""
            lines.append(f"  {i}. {nb.name}{marker}{lock}")
        lines.append("\n输入序号或笔记名称即可作为 sy-save 的 notebook 参数")
        return "\n".join(lines)
