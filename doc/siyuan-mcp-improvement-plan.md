# siyuan-mcp 改进规划

> 基于对同类项目的调研复盘，形成这份规划。分三部分：借鉴部分、完善功能、重新设计。

---

## 一、应该借鉴的部分

### 1. 工具设计理念

| 借鉴点 | 来源 | 说明 |
|--------|------|------|
| 从用户任务流反推动物集 | porkll | 不是想「最小操作是什么」，而是想「用户要用 AI 完成什么任务」 |
| Action Routing 归组 | sisyphus | doc (action:create\|read\|update\|delete) 代替每操作一个 tool，减少 context 占用 |
| CLI + MCP 双入口 | sisyphus | 轻量操作走 CLI，复杂任务走 MCP，覆盖不同使用习惯 |

### 2. README 写法

| 借鉴点 | 来源 | 说明 |
|--------|------|------|
| 徽章行（版本/许可证/语言） | 两者都有 | 建立信任的第一眼信号 |
| Feature 区 + 截图 | sisyphus | 5 秒内让用户知道「能干什么」 |
| 自然语言使用示例 | porkll | 用户直接复制问法给 AI |
| 多客户端配置模板 | 两者都有 | Claude/Cursor/Cherry Studio 各给一段可复制配置 |
| FAQ | porkll | 常见问题自解决，减少 Issue |

### 3. 配置体验

| 借鉴点 | 来源 | 说明 |
|--------|------|------|
| `--token xxx` 命令行参数优先 | porkll | 比手动配 yaml 省 3 步 |
| `init` 交互式引导 | sisyphus | 适合首次使用，降低门槛 |
| 配置片段可直接复制 | 两者都有 | 不要用户自己拼 JSON |

### 4. 分发策略

| 借鉴点 | 来源 | 说明 |
|--------|------|------|
| npx 零配置启动 | porkll | MCP 用户大多在 Node.js 生态 |
| 插件市场安装 | sisyphus | 思源用户从插件市场发现最自然 |

### 5. 上次 README 踩过的坑（重写时绕开）

以下是从 v0.1.x Python 版 README 中总结的教训：

1. ❌ **写了「参考 obsidian-mcp」** → 用户困惑「关我啥事」
2. ❌ **工具表只有 3 列** → 用户看不明白参数怎么用
3. ❌ **没有徽章行** → 缺乏信任信号，不像成熟项目
4. ❌ **没有 Feature 区** → 前 5 秒不知道能干什么
5. ❌ **没有自然语言示例** → 用户不知道怎么跟 AI 说
6. ❌ **没有 FAQ** → 遇到问题只能提 Issue
7. ❌ **没有把差异化放前面** → 中文语义搜索、代码搜索藏在表格里
8. ❌ **没有多客户端配置模板** → 用 Cursor 还得自己猜
9. ❌ **设计原则占了篇幅** → 用户不关心设计哲学，关心能做什么

---

## 二、要完善的功能

### P0 — 现在做（无前置依赖）

#### README 改造

- [ ] 顶部加徽章：PyPI 版本、Python 版本、License
- [ ] 工具参数表精细化：每工具标注必填/可选/默认值/参数说明
- [ ] 多客户端配置模板：Claude Code 一段、Cursor 一段
- [ ] 使用示例按场景分组（保存、搜索、管理三个场景）
- [ ] FAQ 区（Token 获取、连不上思源、ID 获取）
- [ ] 删除「参考 obsidian-mcp」引用

#### 代码清理

- [ ] 删除 README 中无效的设计原则引用
- [ ] 删除或重构设计原则章节

### P1 — 紧接着做

#### 配置体验改进

- [ ] 支持命令行参数：`--token` `--port` `--host`
- [ ] 支持环境变量：`SIYUAN_TOKEN` `SIYUAN_PORT` `SIYUAN_HOST`
- [ ] 新增 `siyuan-mcp init` 交互式配置
- [ ] 优先级：命令行 > 环境变量 > 配置文件

#### 安装分发

- [ ] 修复 npm 包发布（2FA/token 权限问题）
- [ ] README 增加 npx 安装方式

#### 新增工具

- [ ] `sy-append`：追加内容到已有文档
- [ ] `sy-tree`：获取文档树结构
- [ ] `sy-daily`：追加到今日日记
- [ ] `sy-recent`：最近更新文档列表
- [ ] `sy-tag`：列出/替换标签
- [ ] `sy-move`：移动文档

### P2 — 远期

- [ ] Notebook 级别权限控制（none / r / rw / rwd）
- [ ] Action Routing 架构重构
- [ ] 独立文档站（VitePress）

---

## 三、如果要重新做

### 技术选型

```
语言：    TypeScript（非 Python）
SDK：     @modelcontextprotocol/sdk
分发：    npx（主） + pip + 插件市场
配置：    命令行参数 > 环境变量 > 配置文件
工具：    Action Routing 模式，12 tool 覆盖 100+ 操作
文档：    VitePress 独立站点 + 完整 README
```

### 做之前

1. 去 npm/GitHub 搜 `siyuan-mcp`，读完所有同类项目的 README
2. 列出现有项目全部功能，标注哪些是高频、哪些是差异化
3. 确定自己的定位：**不是再做一套 CRUD，而是突出差异化**
   - 中文语义搜索（别人没有）
   - 代码库搜索（别人没有）
   - jieba 自动标签（别人没有）

### 架构设计

```
siyuan-mcp/
├── bin/                  # CLI 入口
│   └── siyuan-mcp.js
├── src/
│   ├── api/             # 思源 HTTP API 封装
│   ├── tools/           # Action-routed tools
│   │   ├── doc.ts       # create/read/update/append/delete/move/tree
│   │   ├── search.ts    # content/tag/code 搜索
│   │   ├── notebook.ts  # list/recent
│   │   ├── tag.ts       # list/replace
│   │   ├── daily.ts     # append
│   │   └── snapshot.ts  # create/list/rollback
│   ├── init.ts          # init 交互式配置
│   └── server.ts        # MCP server 入口
├── README.md            # 产品首页风格
├── docs/                # VitePress 文档站
└── package.json
```

### 构建阶段

```
第一周（基础）：
  - 项目骨架 + MCP server
  - doc tool（CRUD）
  - search tool（思源 + 代码）
  - npx 发布

第二周（完善）：
  - 剩余工具（notebook/tag/daily/snapshot）
  - init 命令
  - README 产品化
  - 多客户端配置模板

第三周（发布）：
  - npm 发布
  - PyPI 同步发布
  - 文档站搭建
  - FAQ 补充
```

### 发布清单

- [ ] npm publish（`npx siyuan-mcp-bridge` 可用）
- [ ] PyPI publish（`pip install siyuan-mcp` 可用）
- [ ] 思源插件市场提交（可选）
- [ ] README 包含全部工具参数说明
- [ ] README 包含多客户端配置模板
- [ ] README 包含 FAQ
- [ ] 工具可命令行传参（`--token`）

---

## 四、执行路径

当前项目基于 Python，所以分两条线：

**短线（基于现有 Python 代码，1-2 天内完成）：**
```
README 改造 ──── 今天做完
代码清理 ─────── 顺手
新增工具 ─────── 2-3 个/天
配置体验改进 ──── 1 天
```

**长线（如果未来决定重写）：**
```
TypeScript 重写 ── 按第三部分架构来
```
