# 工具集重设计 — 规格说明

> 日期: 2026-06-11
> 状态: 待实现
> 参考图: [architecture.png](../architecture.png) | [sy-save-flow.png](../sy-save-flow.png)

---

## 概述

将现有 5 个工具（sy-notebooks、sy-save、sy-auto、sy-find、code-find）精简为 3 个，消除功能重叠，统一交互风格。

| 现状 | 重设计后 |
|------|---------|
| sy-notebooks | → sy-list（改名统一） |
| sy-save（含 name/tags/source 参数） | → sy-save（精简参数，增加确认流程） |
| sy-auto | → 合并到 sy-save（自动项目匹配） |
| sy-find | → sy-find（增加 mode:code 吸收 code-find） |
| code-find | → 合并到 sy-find(mode:code) |

---

## 工具 1: `sy-list` — 列出笔记本

**输入参数：** 无

**输出格式：**
```
📚 思源笔记本列表：

  1. AI知识体系          ← 当前默认
  2. 日记本
  3. 工作文档
  4. 项目归档        🔒
```

用户只需说"1"或"AI知识体系"即可在 sy-save 中引用。

**实现要点：**
- 调用 `/api/notebook/lsNotebooks`
- 返回编号从 1 开始
- 标记当前默认笔记本（索引 0）
- 标记已关闭笔记本
- 服务器端缓存 notebooks 列表，供 sy-save 的序号/名称映射使用

---

## 工具 2: `sy-save` — 统一保存

### 输入参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `content` | 是 | 笔记内容（Markdown），或以 `@` 开头的文件路径 |
| `notebook` | 否 | 笔记本序号或名称，不指定则用默认（索引 0） |

**删掉的参数：** `name`、`tags`、`source`（全部由系统自动推理）

### 核心流程（6 步）

**Step 1 解析内容来源**
- 纯文本 → 来源标记为"笔记"
- `@文件路径` → 读取文件，来源标记为"文件 xxx.md"
- 对话内容 → 来源标记为"整个对话"

**Step 2 提取标题 + 匹配项目**
- 从 Markdown 提取第一个 `#` 或 `##` 作为标题
- 在内容中扫描 `codebase.repos` 的项目名 → 自动关联项目目录

**Step 3 映射笔记本**
- `notebook=""` → 索引 0（默认笔记本）
- `notebook="2"` → 索引 1
- `notebook="AI知识体系"` → 模糊匹配 name

**Step 4 自动生成标签**
- 使用 jieba 分词提取关键词
- 数量 ≤ 6
- 内容 < 20 字时不生成
- 标签最长 10 字符

**Step 5 返回确认信息（不保存）**
```
⚠️ 即将保存整个对话内容（共 15 条消息）
 📓 笔记本：AI知识体系
 📝 标题：JWT 认证方案
 📎 项目：wallet
 🏷️  标签：JWT、认证、签名算法、安全

 摘要：JWT 认证的实现思路是使用 RS256 签名...

 确认保存？回复"好"、"确认"、"保存"
```
- 整个对话内容必须有 ⚠️ + 醒目提示
- 用户可以在此环节修改：换笔记本、改标题、增减标签

**Step 6 写入 + 返回位置**
```
✅ 已保存

  📓 笔记本：AI知识体系
  📂 路径：项目/钱包/JWT认证方案
  📝 标题：JWT 认证方案
  🏷️  标签：JWT、认证、签名算法、Rust
  🔗 siyuan://blocks/20260611123456-xxxxx
```

**错误处理：**
- 笔记本序号超出范围 → 友好提示并显示可用列表
- 笔记本名称无匹配 → 提示未找到并显示可用列表
- 思源连接失败 → 明确提示"思源笔记未运行"
- 内容为空 → "内容不能为空"

---

## 工具 3: `sy-find` — 统一搜索

### 输入参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `query` | 是 | 搜索词 |
| `mode` | 否 | `normal`（默认） / `ai` / `code` |
| `limit` | 否 | 最大返回数，默认 10 |
| `notebook` | 否 | 限定笔记本（仅 normal/ai 模式） |
| `path` | 否 | 限定项目名（仅 code 模式，匹配 repo name） |
| `file_type` | 否 | 仅 code 模式：`code` / `doc` |
| `context_lines` | 否 | 仅 code 模式，默认 3 |

### mode 路由

```
query + mode
  ├─ normal → POST /api/search/searchNote (keyword)
  ├─ ai     → POST /api/search/searchNote ( semantic )
  └─ code   → ripgrep 本地搜索
```

**思源搜索输出：**
```
🔍 找到 3 条结果（mode: normal）：

1. 📄 **JWT 认证方案**
   > JWT 认证的实现思路是使用 RS256 签名...
   📁 AI知识体系 / 项目 / auth / JWT认证方案
   🔗 siyuan://blocks/202606...
```

**代码搜索输出：**
```
🔍 找到 3 处代码匹配「Transfer」（mode: code）：

1. **wallet** — src/transfer.rs:42
   ```rust
   pub fn transfer(from: &Account, to: &Account, amount: u64) -> Result<()> {
   ...
   ```
```

---

## 配置精简

| 配置项 | 状态 | 说明 |
|--------|------|------|
| `siyuan.host` | ✅ 保留 | API 地址 |
| `siyuan.port` | ✅ 保留 | API 端口 |
| `siyuan.token` | ✅ 保留 | API Token |
| `siyuan.workspace` | ❌ 移除 | 自动检测 |
| `codebase.repos` | ✅ 保留 | 项目匹配用 |
| `search.default_mode` | ❌ 移除 | 用户每次指定 mode |
| `search.max_results` | ✅ 保留 | 搜索结果上限 |
| `search.rg_path` | ✅ 保留 | ripgrep 路径 |
| `storage.default_notebook` | ❌ 移除 | 统一用索引 0 |
| `storage.inbox_path` | ❌ 移除 | "收集箱"概念废弃 |

**环境变量覆盖机制**保留，对应精简后的配置项。

---

## 笔记本映射机制

**输入：** notebook 参数（序号如 `"2"` / 名称如 `"AI知识体系"` / 空字符串）
**输出：** notebook_id

映射规则：
- 空字符串 → 索引 0（默认笔记本）
- 序号 `"1"` 到 `"N"` → 对应索引 0 到 N-1
- 名称模糊匹配 → 遍历 notebooks，匹配 name 包含或包含于输入
- 序号超出范围 / 名称无匹配 → 报错并列出可用笔记本

缓存：启动时拉取一次，sy-save 内部持有映射器实例。

---

## 自动标签规则

**输入：** Markdown 内容
**输出：** ≤6 个标签

- 使用 jieba 分词，去除停用词和单字
- 按词频取 top ≤6
- 内容 < 20 字时不生成
- 单标签最长 10 字符，超长截断
- 标签在确认环节展示，用户可干预（增/删/改/全清除）

---

## 测试要点

- 笔记本序号映射（边界：0、超出、负数、非数字字符串）
- 笔记本名称匹配（精确、模糊、无匹配）
- 自动标签（短内容不生成、长内容不超过 6 个、去掉停用词）
- sy-save 确认流程不写入（验证 confirm 阶段 create_doc 未被调用）
- sy-save 确认后写入（verify create_doc 被调用）
- sy-find mode 路由正确分发
- 配置加载兼容旧格式（保证迁移平滑）

---

## 配置示例

精简后的 `config.yaml`：

```yaml
siyuan:
  host: "127.0.0.1"
  port: 6806
  token: ""

codebase:
  repos:
    - path: "D:/Code/wallet"
      name: "wallet"

search:
  max_results: 10
  rg_path: "rg"
```
