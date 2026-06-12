---
name: siyuan-mcp-retrospective
description: 对标 porkll/siyuan-mcp 和 sisyphus 的复盘总结——需求、架构、使用、分发四个维度的差距分析与深层原因
metadata: 
  node_type: memory
  type: project
  date: 2026-06-11
  originSessionId: 213b69bc-0c8c-419a-96cb-c4c0c7bc0b9e
---

# siyuan-mcp 复盘：我们为什么没想到这些？

## 一、需求分析维度 —— 眼界决定了功能边界

### 我们做了什么
- 把自己定位成「Claude 与思源笔记之间的 MCP 服务」
- 设计了 6 个低层级工具：notebook、list、save、read、delete、find
- 强调「每个工具只做一件事，不做猜测」

### 别人做了什么
- **porkll/siyuan-mcp**（15 个工具）：unified_search、create_document、append_to_document、update_document、move_documents、get_document_tree、append_to_daily_note、get_recently_updated_documents、create_snapshot、list_snapshots、rollback_to_snapshot、list_all_tags、batch_replace_tag 等
- **sisyphus**（12 action-routed tools）：文件系统路径（fs 工具）、Git 式文档时间线、命名快照与回滚、notebook 级别权限模型

### 差距分析

| 维度 | 我们 | 别人 | 为什么没想到 |
|------|------|------|-------------|
| **目标用户** | 仅 Claude | Claude + Cursor + Cherry Studio + Cline 全生态 | 默认只考虑了 Claude Code 场景，没调研 MCP 生态的用户分布 |
| **工具覆盖** | CRUD + 搜索 | 文档管理 + 快照 + 标签 + 日常笔记 + 移动 | 只抽象了最小必要操作，没从「用户任务流」反推动物 |
| **差异化能力** | 中文语义搜索、代码搜索 | 文档时间线、fs 路径、权限控制 | 有独特优势却不自知，README 只字不提 |
| **使用场景** | AI 保存/读取 | AI 编辑 + 版本管理 + 组织整理 + 安全管控 | 把自己想窄了，只覆盖了「读写」两个场景 |

### 根本原因
**缺乏上游思维。** 我们没有去 npm/GitHub 调研已有的思源 MCP 项目，不知道赛道里已经有人在做了，更不知道他们做到了什么程度。如果一开始就 fork 或参考这些项目，功能设计会完全不同。

---

## 二、代码框架维度 —— 架构选择影响一切

### 我们做了什么
- Python 3.10+，MCP Python SDK
- 扁平工具注册：每个工具一个 handler 函数
- 配置驱动：ConfigLoader → SiyuanClient
- 6 个独立文件（client、models、search、mapper、tagger、config）

### 别人做了什么
- **porkll/siyuan-mcp**：TypeScript + `@modelcontextprotocol/sdk`，src/api/ + mcp-server/handlers/ 分层
- **sisyphus**：SiYuan 插件 + CLI 双入口，12 个 action-routed tools 共享同一核心

### 差距分析

| 维度 | 我们的选择 | 别人的选择 | 优劣 |
|------|-----------|-----------|------|
| **语言** | Python | TypeScript | TypeScript 生态更贴合 MCP（npx 零配置、Cursor 原生支持） |
| **工具组织** | 1 对 1 handler | action routing（12→100+ 能力） | 我们 6 工具即上限，再增加工具列表会膨胀；sisyphus 的设计可扩展 |
| **入口方式** | 纯 MCP | MCP + CLI + 插件 | CLI 用于脚本/自动化，插件用于图形化设置，覆盖更全的使用习惯 |
| **配置方式** | yaml 文件 | 命令行参数 / init 交互式 | 用户更接受 `--token xxx` 而非手动建 yaml |

### 需要学习的设计模式
**Action Routing 模式**（sisyphus）：不把每个操作暴露为一个独立 tool，而是按「动作类型」归组。例如一个 `doc` tool 接受 action=create/read/update/delete/move/tree。这样 12 个 tool 就能覆盖 100+ 操作，且上下文窗口不会爆炸。

---

## 三、使用体验维度 —— 用户感知决定成败

### 我们做了什么
- 纯文字 README，工具表格只有 3 列
- 配置需要手动复制 config.yaml.example
- 只有 pip 安装一种方式
- 没有使用示例

### 别人做了什么
- README 有徽章、Feature 区、截图、FAQ、多客户端配置模板
- sisyphus 有独立文档站（VitePress）
- porkll 有自然语言使用样例 + TypeScript 编程接口文档
- 配置片段直接可复制使用

### 差距分析

**我们的 README 像「项目说明」；别人的 README 像「产品首页」**

具体对比：

```
我们：| sy-save | 保存文档 | content, notebook |
他们：## 使用示例
      "Search for documents about machine learning"
      "Create a new document called 'Project Ideas'"
      "Append 'Meeting notes' to today's daily note"
```

**关键缺失：**
1. **没有 Feature 区** —— 用户打开 README 前 5 秒不知道这东西能干什么
2. **没有自然语言示例** —— 用户不知道该怎么跟 AI 说
3. **没有多客户端配置** —— 用户用 Cursor 还得自己猜配置格式
4. **没有 FAQ** —— 遇到问题只能提 Issue
5. **没有版本徽章** —— 缺乏信任信号

---

## 四、分发维度 —— 安装越简单，用户越多

### 我们做了什么
- PyPI 发布（pip install siyuan-mcp）
- 手动配 config.yaml

### 别人做了什么
- **porkll**：npm 发布（`npx @porkll/siyuan-mcp`），零配置启动
- **sisyphus**：npm + 思源插件市场 + `siyuan-sisyphus init` 交互式配置
- **都提供多平台配置模板**（Mac/Windows 路径差异化处理）

### 差距分析

| 安装方式 | 用户门槛 | 我们支持 |
|----------|---------|---------|
| `npx xxx` | 零安装 | ❌ |
| `pip install xxx` + 手动配 | 中 | ✅ |
| 插件市场安装 | 最低 | ❌ |
| `npm i -g xxx` | 低 | ❌ |

**根本原因：以为 PyPI 就够了。** 实际 MCP 用户群体中，Node.js 生态用户远多于 Python 用户。npx 的零配置特性让用户「一条命令启动」，而这正是我们缺失的。

---

## 五、总结：十条经验

1. **动手前先调研** —— 去 npm/GitHub 搜一遍同类项目，避免重复造轮、发现已有范式
2. **需求定义要宽泛** —— 不要只服务于 Claude，MCP 生态有 Cursor/Cline/Cherry Studio 等
3. **工具设计从上往下** —— 从用户任务流反推动物集，而不是从「最小操作」往上凑
4. **架构选型要顺势** —— MCP 生态主流是 TypeScript，Python 版本可能错过 npx 零配置优势
5. **Action Routing > 1:1** —— 100+ 操作不应该暴露为 100 个 tool，而应该按动作类型归组
6. **README 是产品首页** —— 需要 Feature、截图、徽章、自然语言示例、FAQ、多客户端配置
7. **配置体验决定激活率** —— `--token xxx` 命令行参数 > `init` 交互式 > 手动复制 yaml
8. **不隐藏独特优势** —— 中文语义搜索、代码搜索是我们的差异化，应该放在最前面
9. **安装渠道越多越好** —— pip + npx + 插件市场 + source，覆盖不同用户习惯
10. **安全设计是卖点** —— 权限控制（notebook 级别 r/rw/rwd）不是可有可无的功能，而是用户信任的基础

---

## 六、如果重来，会怎么做

**一句话：始于调研，终于体验。**

1. 先去 npm/GitHub 查 `siyuan-mcp`，读完所有同类项目的 README
2. 选择 TypeScript + `@modelcontextprotocol/sdk`，npx 分发
3. 采用 Action Routing 设计，12 个 tool 覆盖 100+ 操作
4. README 按「产品首页」写：徽章 → Feature 区 + 截图 → 安装 → 使用示例 → 配置 → FAQ
5. 提供多客户端配置模板（Claude/Cursor/Cherry Studio）
6. 补充差异化功能：语义搜索、代码搜索、自动标签、notebook 权限控制
7. 内置 `init` 命令交互式生成配置
8. 建立独立文档站（VitePress），按场景组织使用指南

**Why:** 以上每一条的缺失都直接降低了项目被采用的概率。这不是事后诸葛亮，而是通过对比优秀同类项目，反推出一个「最小可接受的产品标准」。
