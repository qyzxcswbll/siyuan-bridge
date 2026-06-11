"""自动标签生成：使用 jieba 分词提取关键词。"""

import re

try:
    import jieba
except ImportError:
    jieba = None  # type: ignore


# 通用中文停用词
_STOP_WORDS: set[str] = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "它", "们", "那", "什么", "怎么", "因为", "所以", "可以", "这个",
    "那个", "我们", "他们", "它们", "被", "把", "让", "对", "与",
    "而", "但", "但是", "如果", "虽然", "然后", "或者", "还是",
    "以及", "其中", "其", "之", "为", "所", "能", "于", "及", "等",
    "中", "从", "将", "用", "以", "来", "还", "做", "和", "或",
    "并", "而", "且", "被", "把", "让", "给", "向", "对", "比",
}


def generate_tags(content: str, max_tags: int = 6) -> list[str]:
    """从 Markdown 内容中提取最多 max_tags 个标签。

    规则：
    - 内容 < 20 字 → 返回空列表
    - 去掉 Markdown 标题、代码块、链接
    - jieba 分词 → 过滤停用词+单字 → 按词频排序 → 取 top N
    - 单标签最长 10 字符
    """
    text = content.strip()
    if len(text) < 20:
        return []

    # 去掉 Markdown 元素
    text = re.sub(r'^#+\s.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'\[.+?\]\(.+?\)', '', text)

    if jieba is None:
        # fallback: 简单标点分词
        words = re.findall(r'[\w一-鿿]+', text)
    else:
        words = jieba.lcut(text)

    # 过滤：停用词、单字、空白
    filtered = [
        w.strip() for w in words
        if w.strip() and len(w.strip()) > 1 and w.strip() not in _STOP_WORDS
    ]

    # 按词频排序
    freq: dict[str, int] = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1

    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    tags = [w for w, _ in sorted_words[:max_tags]]
    return [t[:10] for t in tags]
