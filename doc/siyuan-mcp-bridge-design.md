# siyuan-mcp-bridge 设计文档

> TypeScript 重写版架构设计。基于 Python v0.1.x 的经验积累和对标竞品（porkll/siyuan-mcp、sisyphus）的调研结论。

---

## 一、为什么重写

### 原 Python 版的问题

| 问题 | 表现 | 影响 |
|------|------|------|
| 语言生态 | Python，MCP 生态主流是 TypeScript | 无法 npx 零配置启动，用户需要本地装 Python |
| 工具设计 | 1:1 handler，6 工具即上限 | 每加一个操作就多一个 tool，context 膨胀 |
| 配置体验 | 手动复制 yaml，修改 token | 门槛高，激活率低 |
| 分发渠道 | 仅 PyPI | 错过 npm/npx 生态的用户 |
| 差异化不突出 | 中文语义搜索、代码搜索藏在表格里 | 用户不知道我们有什么独特能力 |

### 重写目标

1. **npx 可启动**：`npx siyuan-mcp-bridge` 一条命令运行
2. **Action Routing 设计**：6 个 tool 覆盖 20+ 操作，不膨胀
3. **配置体验**：`--token xxx` 传参 > `init` 交互式 > 手动配 yaml
4. **功能补全**：从 CRUD + 搜索扩展到文档管理全场景
5. **保留差异化**：中文语义搜索、代码搜索作为核心卖点

---

## 二、技术栈

| 项 | 选择 | 理由 |
|---|------|------|
| 语言 | TypeScript 5.x | MCP 生态标准、npx 零配置、类型安全 |
| 模块 | ESM（`"type": "module"`） | MCP SDK 和 CLI 工具链都偏好 ESM |
| 运行时 | Node >= 18 | 原生 fetch，无需 node-fetch |
| MCP SDK | `@modelcontextprotocol/sdk` ^1.8 | 官方 SDK，Claude/Cursor 都兼容 |
| CLI | `commander` ^13 | 成熟的 CLI 框架，子命令原生支持 |
| 配置校验 | `zod` ^3.24 | 轻量、类型推导优秀 |
| 交互式 | `@clack/prompts` ^0.10 | 现代化交互体验 |
| YAML | `yaml` ^2.7 | 纯 JS 解析，无原生依赖 |
| 测试 | `vitest` ^3.0 | 原生 ESM、高速、TypeScript 友好 |

---

## 三、架构总览

```
┌─────────────────────────────────────────────────┐
│                   CLI (commander)                │
│  siyuan-mcp-bridge --token xxx --port 6806      │
│  siyuan-mcp-bridge init                         │
└──────────┬──────────────────────────┬───────────┘
           │                          │
           ▼                          ▼
    ┌──────────────┐        ┌──────────────────┐
    │ ConfigLoader │        │ Init 交互式配置     │
    │ YAML > ENV   │        │ @clack/prompts    │
    │ > CLI Args   │        │ → 生成 config.yaml│
    └──────┬───────┘        └──────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │              MCP Server (server.ts)          │
    │  - ListToolsRequestHandler                   │
    │  - CallToolRequestHandler                    │
    │  - StdioServerTransport                      │
    └──────────┬───────────────────────────────────┘
               │
               ▼
    ┌──────────────────────────────────────────────┐
    │            ToolRegistry (registry.ts)        │
    │  sy-doc  │  sy-search  │  sy-notebook       │
    │  sy-tag  │  sy-daily   │  sy-snapshot       │
    └────┬──────────┬──────────┬───────────────────┘
         │          │          │
         ▼          ▼          ▼
    ┌────────┐ ┌──────────┐ ┌────────────┐
    │Siyuan  │ │Codebase  │ │Notebook    │
    │Client  │ │Searcher  │ │Mapper      │
    │(HTTP)  │ │(ripgrep) │ │(name→id)   │
    └────────┘ └──────────┘ └────────────┘
```

---

## 四、Action Routing 设计

### 核心思想

不把每个操作暴露为一个独立 tool，而是按「领域」归组。每个 tool 通过 `action` 参数路由到子处理器。

### 工具定义

| Tool | Actions | 覆盖操作数 | 对应原 Python 工具 |
|------|---------|-----------|-------------------|
| `sy-doc` | create / read / update / append / delete / move / tree | 7 | sy-save, sy-read, sy-delete, sy-list |
| `sy-search` | (mode: normal \| ai \| code) | 3 | sy-find |
| `sy-notebook` | list / recent | 2 | sy-notebook |
| `sy-tag` | list / replace | 2 | 全新 |
| `sy-daily` | append | 1 | 全新 |
| `sy-snapshot` | create / list / rollback | 3 | 全新 |

6 个 tool 覆盖 18 个操作，且新增操作只需加 action 不需要加 tool。

### Action Routing 实现

```typescript
// 每个 tool 的 handler 用 switch/case 分发：
async function handleDoc(client, args) {
  switch (args.action) {
    case 'create': return createDoc(client, args);
    case 'read':   return readDoc(client, args);
    case 'delete': return deleteDoc(client, args);
    // ...
  }
}
```

MCP client 看到的 tool 定义只有 6 个，但每个的 inputSchema 包含 action enum。

---

## 五、配置管道

```
优先级从低到高：

  1. 硬编码默认值 ────── host=127.0.0.1, port=6806, token=""
       │
  2. YAML 配置文件 ────── 搜索 cwd/config.yaml > ~/.siyuan-mcp/config.yaml
       │                    deepMerge 递归合并
  3. 环境变量 ─────────── SIYUAN_HOST, SIYUAN_PORT, SIYUAN_TOKEN
       │                    CODEBASE_REPOS, SEARCH_MAX_RESULTS
  4. CLI 参数 ─────────── --host, --port, --token, --rg-path, --max-results
       │
      ▼
  最终 Config 对象
```

配置合并使用 `deepMerge`（递归对象合并，数组直接替换），与 Python 版的 `_deep_merge` 行为一致。

---

## 六、Siyuan API 客户端

### 接口定义

```typescript
class SiyuanClient {
  constructor(config: Config)

  // 笔记本
  listNotebooks(): Promise<NotebookInfo[]>

  // 文档 CRUD
  createDoc(markdown, notebookId, title, path): Promise<{id, title}>
  getDoc(docId): Promise<DocInfo>              // id, content, path, title
  removeDoc(notebookId, path): Promise<boolean>
  listDocs(notebookId, path?): Promise<DocInfo[]>

  // 搜索
  searchNotes(query, mode, limit, notebook?): Promise<SearchResult[]>

  // 日常笔记
  getOrCreateDailyNote(notebookId): Promise<string>
  appendBlock(parentId, content): Promise<any>
}
```

### HTTP 调用

所有 API 通过 `fetch` POST 到 `http://{host}:{port}{apiPath}`，带 JSON body 和可选的 `Authorization: Token {token}` 头。

响应结构：
```json
{ "code": 0, "msg": "", "data": ... }
```

- `code !== 0` → 抛 `ApiError(msg, code)`
- 网络错误 → 抛 `ConnectionError("思源笔记未运行")`

---

## 七、NotebookMapper

与 Python 版行为完全一致：

- 空字符串 → 返回第一个笔记本（索引 0）
- 纯数字字符串 → 1-based 索引
- 其他字符串 → 先精确匹配名称，再子字符串模糊匹配
- 匹配失败 → 抛 `ValueError`

---

## 八、标签生成（Tagger）

Python 版用 `jieba` 做中文分词。TypeScript 版采用 CJK 二元分词 + 英文单词提取：

```
1. 去除 Markdown 标题、代码块、链接
2. 提取所有 CJK 二元组（连续两个汉字）
3. 提取英文单词（字母数字序列）
4. 过滤停用词 + 单字符词
5. 按词频排序，取前 N 个
```

这是一个合理的简化方案。如果需要更准确的分词，后续可接入 `nodejieba` 或 WASM 分词器。

---

## 九、代码搜索（CodebaseSearcher）

与 Python 版行为一致：

- 遍历配置中的 repos，对每个 repo 执行 `rg` 子进程
- 解析 `filepath:line:content` 格式输出
- 支持 `path_filter`（限定 repo）、`file_type`（code/docs）、`context_lines`
- 达到 `maxResults` 上限时截断

---

## 十、与 Python 版的差异

### Breaking Changes

| 项 | Python 版 | TypeScript 版 |
|---|----------|--------------|
| 启动方式 | `python -m siyuan_mcp` | `npx siyuan-mcp-bridge` |
| 工具名称 | `sy-save`, `sy-read`, `sy-delete`, `sy-list`, `sy-find`, `sy-notebook` | `sy-doc`, `sy-search`, `sy-notebook`, `sy-tag`, `sy-daily`, `sy-snapshot` |
| 配置方式 | yaml 文件为主 | CLI 参数 > 环境变量 > yaml |
| 安装 | `pip install siyuan-mcp` | `npx siyuan-mcp-bridge` |
| 运行环境 | Python 3.10+ | Node.js 18+ |

### 功能提升

| 功能 | Python 版 | TypeScript 版 |
|------|----------|--------------|
| 工具数量 | 6 | 6 (覆盖 18 操作) |
| 追加内容 | ❌ | ✅ `sy-doc action=append` |
| 文档树 | ❌ | ✅ `sy-doc action=tree` |
| 移动文档 | ❌ | ✅ `sy-doc action=move` |
| 更新文档 | ❌ | ✅ `sy-doc action=update` |
| 每日日记 | ❌ | ✅ `sy-daily` |
| 标签管理 | ❌ | ✅ `sy-tag` |
| 快照管理 | ❌ | ✅ `sy-snapshot` |
| 最近文档 | ❌ | ✅ `sy-notebook action=recent` |
| 交互式配置 | ❌ | ✅ `siyuan-mcp-bridge init` |

---

## 十一、项目结构

```
siyuan-bridge/
├── package.json                  # 包清单 + bin 入口 + scripts
├── tsconfig.json / build.json    # TypeScript 编译配置
├── .npmignore                    # npm 发布排除
├── bin/
│   └── siyuan-mcp.js             # ESM shim → 加载 dist/cli.js
├── src/
│   ├── cli.ts                    # Commander 入口
│   ├── server.ts                 # MCP Server 核心
│   ├── config/
│   │   ├── index.ts              # Config 类型 + 默认值
│   │   └── loader.ts             # 配置加载合并
│   ├── commands/
│   │   └── init.ts               # 交互式配置生成
│   ├── siyuan/
│   │   ├── client.ts             # Siyuan HTTP API 客户端
│   │   ├── models.ts             # 请求/响应类型
│   │   └── errors.ts             # ConnectionError, ApiError
│   ├── tools/
│   │   ├── registry.ts           # ToolRegistry 注册中心
│   │   ├── doc.ts                # sy-doc router
│   │   ├── search.ts             # sy-search router
│   │   ├── notebook.ts           # sy-notebook router
│   │   ├── tag.ts                # sy-tag router
│   │   ├── daily.ts              # sy-daily router
│   │   └── snapshot.ts           # sy-snapshot router
│   ├── codebase/
│   │   └── search.ts             # ripgrep 搜索
│   ├── mapper/
│   │   └── notebook.ts           # 笔记本名称→ID 映射
│   └── tagger/
│       └── index.ts              # 中文标签生成
├── src/__tests__/                # vitest 测试
├── doc/                          # 文档
└── README.md
```

---

## 十二、测试策略

| 层 | 测试框架 | 覆盖范围 |
|----|---------|---------|
| Config | vitest | 默认值、YAML 合并、环境变量覆盖、CLI 参数覆盖 |
| Client | vitest + mock fetch | 每个 API 调用、网络错误、API 错误 |
| Tool | vitest + mock client | 每个 action 分发、输入校验、空值处理 |
| Mapper | vitest | 索引/名称/模糊匹配、边界条件 |
| Searcher | vitest + 真实 rg | rg 调用、输出解析、repo 跳过 |
| Tagger | vitest | 短文本、标签数量、长度截断 |

---

## 十三、构建与发布

### 构建

```bash
npm run build    # tsc -p tsconfig.build.json
```

输出到 `dist/`，目录结构镜像 `src/`。

### 发布

```bash
npm publish      # 自动 build + test（prepublishOnly hook）
```

---

## 十四、Roadmap

| 阶段 | 内容 | 预估 |
|------|------|------|
| Phase 1 | 项目骨架 + 配置系统 | 1 天 |
| Phase 2 | Siyuan 客户端 + Mapper + Tagger | 1 天 |
| Phase 3 | 代码搜索 | 0.5 天 |
| Phase 4 | 6 个 action-routed tool | 2 天 |
| Phase 5 | 服务端集成 + init 命令 | 1 天 |
| Phase 6 | README 重写 + CI + npm publish | 1 天 |
