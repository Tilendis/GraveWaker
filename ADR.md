# ADR — GraveWaker 架构决策记录

---

## ADR-001: 编程语言选 Python

**Status:** ACCEPTED

**Decision:** 全部后端逻辑使用 Python 3.11+。

**Context:**
- 用户仅了解 Python 基础
- 需要能读懂代码、调试运行、借助 AI 修改
- 生态需求：文本处理、HTTP 请求、PDF 解析、向量数据库、LLM 调用

**Consequences:**
- 正面：Python 生态覆盖所有需求（ChromaDB、LangChain、FastAPI、pdfplumber 等）；AI 辅助写 Python 最成熟
- 负面：单线程性能瓶颈，但对个人级数据量（千条级）完全够用；可视化只能用 Web 前端分担

---

## ADR-002: 本地存储方案 — SQLite + ChromaDB

**Status:** ACCEPTED

**Decision:**
- **结构化数据**（元数据、来源信息、用户搜索历史）→ SQLite
- **文本块 + 向量**（用于语义搜索）→ ChromaDB（持久化模式）
- 两者均存放在 D 盘项目目录下

**Context:**
- 需零配置、零运维、单文件/单目录级别的数据库
- 用户不会装 MySQL/PostgreSQL，也不能忍受 Docker

**Alternatives considered:**
- FAISS：纯向量库，无元数据存储能力，需额外整合
- LanceDB：更轻量但生态不如 ChromaDB 成熟
- Qdrant：需要独立服务进程

**Consequences:**
- ChromaDB 依赖 sqlite3 底层存储，与 SQLite 配合自然
- 向量维度建议 768-1024（取决于嵌入模型）
- 预估磁盘占用：1000+200 条文本向量化约 100MB-300MB

---

## ADR-003: 分阶段数据摄取

**Status:** ACCEPTED

**Decision:**
- **Phase 1（MVP）:** B站 API + 浏览器书签导出
- **Phase 2（后续）:** 本地电子书 PDF、微信收藏自动化（待调研可行方案）
- 每个数据源作为独立连接器（connector），统一输出格式，可插拔

**Context:**
- 微信反爬风险高，电子书主要在微信内不便提取，均不应阻塞 MVP
- MVP 两个源足以验证"知识地图+语义搜索"的产品价值
- 用户开发时间受限

**Consequences:**
- 架构从一开始就设计为 plugin-style 数据源模块
- 每个 connector 输出统一 schema：`{id, title, text, source_type, source_url, date_collected, tags}`
- Phase 1 先写 2 个 connector，后续按需添加

---

## ADR-004: 语义搜索方案 — 本地嵌入 + 云 LLM 混合

**Status:** ACCEPTED

**Decision:**
- **嵌入模型**（文本→向量）：本地运行轻量模型（如 BGE-small-zh，~100MB），用于语义相似度搜索
- **摘要/分析生成**：调用免费云 API（DeepSeek / 通义千问），用于生成内容摘要、报告文字
- **搜索流程:** 用户输入 → 本地 embedding → ChromaDB 向量检索 Top-K → 云 LLM 对结果做重排序 + 摘要

**Context:**
- 必须支持中文语义理解（不能只是 jieba 分词+关键词）
- 用户硬盘空间有限（10GB 总预算），不能跑大模型
- 嵌入模型只需加载一次，推理快，不占很多资源

**Alternatives considered:**
- 全部用云 API：搜索延迟取决于网络，且搜索频率高时可能触发限流
- 全部本地：需要跑至少 7B 模型（~4GB），超出磁盘预算且吃内存

**Consequences:**
- BGE-small-zh 约 100MB，内存占用低
- 初次索引需要跑嵌入（全量约几分钟），后续增量更新
- 依赖云 API 需处理网络异常和限流降级

---

## ADR-005: 用户界面 — 本地 Web 应用

**Status:** ACCEPTED

**Decision:**
- 后端：FastAPI（Python），单文件启动
- 前端：单个 HTML 文件 + ECharts（知识地图）+ Vanilla JS
- 启动方式：`python app.py` → 浏览器打开 `http://localhost:8765`

**Context:**
- 用户不懂前端框架（React/Vue），且不应引入 npm 构建链
- 知识地图需要力导向图可视化，ECharts 的 CDN 可直接引用
- 必须是"一键启动"，用户只面对浏览器

**Alternatives considered:**
- Streamlit / Gradio：开发更快，但知识地图定制能力弱
- 纯命令行：无法满足"可视化知识地图"核心需求
- Electron：太重，违反轻量原则

**Consequences:**
- 前端尽量保持单文件 HTML，复杂度可控
- ECharts 通过 CDN 加载（需要联网），离线时地图不可用但搜索仍可用
- FastAPI 约占用 50MB 内存，轻量化运行

---

## ADR-006: 报告推送 — SMTP 邮件

**Status:** ACCEPTED

**Decision:**
- 使用 SMTP 协议发送定期报告到用户邮箱
- 用户需配置自己的发件邮箱（如 QQ邮箱 SMTP）
- 触发方式：用户手动运行 `python report.py`（Phase 1），后续可加操作系统的定时任务

**Context:**
- "发到微信"需要企业微信/公众号/第三方推送服务，复杂度远高于邮件
- 用户已有 QQ 邮箱，开通 SMTP 是零成本操作
- 报告内容为纯文本+简单 HTML 格式

**Alternatives considered:**
- 微信推送：需 Server酱/PushPlus 等第三方，或企业微信应用，增加依赖
- 桌面通知：容易被忽略，不能回头翻看
- 生成 HTML 本地打开：用户说"也会变成数字垃圾"

**Consequences:**
- 用户需一次性配置 SMTP 授权码（约 5 分钟）
- 邮件天然支持离线阅读和回溯
- 后续可扩展到微信推送（架构预留）

---

## ADR-007: 项目目录结构

**Status:** ACCEPTED

**Decision:**

```
GraveWaker/
├── data/                    # 持久化数据（D盘）
│   ├── chroma/              # ChromaDB 向量库
│   ├── sqlite/              # SQLite 元数据库
│   ├── raw/                 # 原始导出文件（书签HTML、B站JSON等）
│   └── cache/               # PDF文本提取缓存
├── connectors/              # 数据源连接器（可插拔）
│   ├── bilibili.py          # Phase 1
│   ├── bookmarks.py         # Phase 1
│   └── pdf_books.py         # Phase 2
├── core/                    # 核心逻辑
│   ├── indexer.py           # 文本分段+向量化+入库
│   ├── searcher.py          # 语义搜索
│   ├── mapper.py            # 知识地图数据生成
│   └── reporter.py          # 报告生成
├── app.py                   # FastAPI 主入口 + API 路由
├── ui/
│   └── index.html           # 单文件前端（知识地图+搜索框）
├── scripts/
│   ├── ingest.py            # 一键摄取所有数据源
│   └── report.py            # 手动触发报告生成
├── requirements.txt
├── config.yaml              # 用户配置（邮箱SMTP、API Key等）
├── CONTEXT.md
└── ADR.md
```

**Context:**
- 用户需要清晰的文件组织，方便按 README 操作
- 模块间低耦合，每个 connector 可单独开发测试
- 所有数据在 D 盘项目目录下，不污染 C 盘

**Consequences:**
- `connectors/` 目录后续可轻松添加新数据源
- `core/` 是稳定核心，不随数据源变化
- 单文件前端降低维护成本

---

## ADR-008: LLM API 选型优先级

**Status:** ACCEPTED

**Decision:**
1. **首选：DeepSeek API**（免费额度充足，中文能力强）
2. **备选：通义千问 API**（阿里云，免费额度）
3. **兜底：本地 Ollama + Qwen3-1.7B**（约 2GB，纯离线）

**Context:**
- 需要支持中文语义理解、摘要生成、搜索结果重排序
- 免费优先，但需考虑 API 不可用时的降级方案
- 用户愿意后期转本地模型

**Consequences:**
- 代码中抽象 LLM 调用接口，支持切换
- 搜索（高频低复杂度）依赖本地嵌入模型，不消耗 API
- 摘要/报告（低频高复杂度）消耗 API，预估每月 < 1000 次调用

---

## 依赖清单预览

| 包 | 用途 | 大小（约） |
|---|------|----------|
| `fastapi` + `uvicorn` | Web 服务 | ~10MB |
| `chromadb` | 向量存储 | ~50MB |
| `sentence-transformers` | 本地嵌入模型 | ~20MB + 模型 100MB |
| `pdfplumber` | PDF 文本提取 | ~5MB |
| `requests` / `httpx` | HTTP 请求（B站API、云API） | 内置 |
| `jieba` | 中文分词辅助 | ~10MB |
| `pyyaml` | 配置文件解析 | 内置 |
| **总计** | | **~200MB + 模型 ~100MB** |

项目总大小预计 < 1GB（含索引数据），远低于 10GB 上限。

---

## 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 微信收藏无法自动化 | 高 | 中 | 延后到 Phase 2，不阻塞 MVP |
| 免费云 API 限流/停服 | 中 | 中 | 架构预留本地模型降级方案 |
| B站 API 接口变更 | 中 | 低 | 官方公开 API，稳定性较好 |
| ChromaDB 数据损坏 | 低 | 高 | 原始文件保留在 `data/raw/`，可重建索引 |
| 用户精力不足项目中途放弃 | 中 | 高 | MVP 收窄到 2 个数据源，先跑通核心闭环 |
