# GraveWaker — 数字掘墓人

把你散落在各平台的数字收藏"复活"为可检索、可关联的交互式知识地图。

> 微信收藏夹里躺着一千篇"以后再看"的文章，B站稍后再看攒了一千个视频，浏览器书签堆了两百个链接。它们都是你曾经觉得"有用"的东西，但现在只是数字垃圾。
>
> GraveWaker 把这些内容收拢到一个本地离线索引中，分析每一篇的主题，找到内容之间的隐藏关联，生成一张交互式知识地图——让过去的你和现在的你产生对话。

---

## 功能

- **语义搜索** — 用自然语言描述你想找的内容，不是关键词匹配
- **知识地图** — 搜索结果 + 语义关联节点 + 连线，可视化"知识簇"
- **多平台聚合** — B站收藏、浏览器书签统一索引（微信收藏、PDF电子书计划中）
- **本地离线** — 所有数据存本地，不上传任何内容
- **免费运行** — 本地嵌入模型 + 免费云 API，零成本

## 快速开始

### 环境要求

- Python 3.11+
- 磁盘空间：约 1GB（含模型和数据）

### 安装

```bash
git clone https://github.com/Tilendis/GraveWaker.git
cd GraveWaker
pip install -r requirements.txt
```

### 配置

编辑 `config.yaml`：

```yaml
bilibili:
  uid: "你的B站UID"
  fid: "你的默认收藏夹fid"  # 从收藏页URL ?fid= 获取
  cookie: "SESSDATA值"      # F12 → Application → Cookies

bookmarks:
  path: "data/raw/bookmarks.html"  # 浏览器导出书签 → 放到这个路径
```

### 运行

```bash
# 1. 拉取数据 + 建索引（首次需下载嵌入模型 ~100MB）
python scripts/ingest.py

# 2. 启动搜索界面
python app.py
# 浏览器打开 http://localhost:8765

# 或者双击 run.bat
```

## 项目结构

```
GraveWaker/
├── app.py                  # FastAPI 主入口
├── config.yaml             # 用户配置
├── run.bat                 # Windows 一键启动
├── requirements.txt
├── connectors/             # 数据源连接器（可插拔）
│   ├── bilibili.py         # B站收藏 API
│   └── bookmarks.py        # 浏览器书签 HTML 解析
├── core/                   # 核心引擎
│   ├── indexer.py          # 文本分块 + 向量化
│   └── searcher.py         # 语义搜索
├── ui/
│   └── index.html          # 搜索 + 知识地图前端
├── scripts/
│   └── ingest.py           # 一键摄取脚本
├── data/                   # 持久化数据
│   ├── chroma/             # 向量库
│   └── sqlite/             # 元数据库
├── CONTEXT.md              # 项目上下文
└── ADR.md                  # 架构决策记录
```

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python, FastAPI, uvicorn |
| 向量库 | ChromaDB |
| 嵌入模型 | BGE-small-zh (本地, ~100MB) |
| 元数据 | SQLite |
| 前端 | Vanilla JS, ECharts |
| LLM | DeepSeek / 通义千问 (免费 API, Phase 2) |

## 路线图

- [x] B站收藏 + 浏览器书签聚合
- [x] 语义搜索 + 知识地图
- [ ] 时间维度视图（按月/年聚类 + 关键词气泡图）
- [ ] 定期邮件报告
- [ ] 微信收藏（Phase 2 数据源）
- [ ] PDF 电子书索引

## 许可

MIT
