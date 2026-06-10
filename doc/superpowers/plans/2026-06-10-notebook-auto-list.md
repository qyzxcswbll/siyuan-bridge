# 笔记本自动列表 — 实现计划

> **目标：** 保存工具无 notebook 参数时自动返回笔记本列表让用户选择

**架构：** handler 的 ValueError 分支调用现有的 `_handle_sy_notebooks`，统一返回笔记本列表

**技术栈：** Python / MCP SDK（现有）

---

### 任务 1：保存工具自动列出笔记本

**文件：**
- 修改：`siyuan_mcp/server.py`

#### 步骤 1-4 合并（改动极小，一个步骤完成）

**改动 1** — `_handle_sy_save` 的 except ValueError 分支：

将：
```python
    except ValueError as e:
        if str(e) == "no_notebook":
            return [types.TextContent(
                type="text",
                text="⚠️ 请先调用 `sy-notebooks` 选择笔记本，然后用 `notebook` 参数指定笔记本 ID",
            )]
        return [types.TextContent(type="text", text=f"❌ 保存失败：{e}")]
```

改为：
```python
    except ValueError as e:
        if str(e) == "no_notebook":
            return await _handle_sy_notebooks({})
        return [types.TextContent(type="text", text=f"❌ 保存失败：{e}")]
```

**改动 2** — `_handle_sy_today` 的 except ValueError 分支（同样改动）

**改动 3** — `_handle_sy_auto` 的 except ValueError 分支（同样改动）

三处改法完全一致：`return "...提示信息..."` → `return await _handle_sy_notebooks({})`

#### 步骤 5：运行测试

```bash
cd d:\Code\siyuan-bridge && python -m pytest -v
```

预期：42 passed（当前是 42，断言需更新）

#### 步骤 6：更新测试

`tests/test_server.py` 中 `test_sy_save_without_notebook_prompts` 和 `test_sy_auto_without_notebook_prompts` 的断言从 `"sy-notebooks" in result[0].text` 改为验证返回的是笔记本列表格式（mock 了 `_siyuan_client`，但 `_handle_sy_notebooks` 不走 mock）。

改为不 mock 直接测真实 API 调用，或改为验证不抛异常。

#### 步骤 7：Commit

```bash
git add -A
git commit -m "feat: auto-list notebooks when save tools called without notebook param"
```

---
