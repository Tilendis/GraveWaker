"""GraveWaker 主入口

启动本地 Web 服务，提供搜索 API 和知识地图数据 API。

使用方式:
    python app.py
    然后浏览器打开 http://localhost:8765
"""

import os
import sys

# 修复: 国内 HuggingFace 镜像 + SSL 证书
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("SSL_CERT_FILE", __import__("certifi").where())

import json
import sqlite3
from pathlib import Path

import yaml
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from core.searcher import Searcher

app = FastAPI(title="GraveWaker", version="0.1.0")

# 加载配置
config_path = Path("config.yaml")
if not config_path.exists():
    raise FileNotFoundError("config.yaml not found. 请先复制并填写配置文件。")

with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

DATA_DIR = config.get("storage", {}).get("data_dir", "./data")
EMBEDDING_MODEL = config.get("embedding", {}).get("model", "BAAI/bge-small-zh-v1.5")

# 初始化搜索器
searcher = Searcher(data_dir=DATA_DIR, embedding_model=EMBEDDING_MODEL)


@app.get("/api/search")
def api_search(
    q: str = Query(..., description="搜索关键词（自然语言）"),
    top_k: int = 20,
    min_score: float = 0.3,
):
    """语义搜索，自动过滤低分噪声"""
    results = searcher.search(q, top_k=top_k, min_score=min_score)
    return {"query": q, "count": len(results), "results": results}


@app.get("/api/similar/{item_id}")
def api_similar(item_id: str, top_k: int = 5):
    """获取与指定条目相似的其他内容（用于知识地图连线）"""
    results = searcher.get_similar_items(item_id, top_k=top_k)
    return {"item_id": item_id, "count": len(results), "results": results}


@app.get("/api/items/{item_id}")
def api_item_detail(item_id: str):
    """获取某个条目的详细信息"""
    sqlite_path = Path(DATA_DIR) / "sqlite" / "metadata.db"
    if not sqlite_path.exists():
        return {"error": "数据库不存在，请先运行 python scripts/ingest.py"}

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.close()

    if row is None:
        return {"error": "未找到该条目"}

    return {
        "id": row["id"],
        "title": row["title"],
        "source_type": row["source_type"],
        "source_url": row["source_url"],
        "date_collected": row["date_collected"],
        "tags": json.loads(row["tags"]),
        "metadata": json.loads(row["metadata"]),
    }


@app.get("/api/stats")
def api_stats():
    """获取索引统计信息"""
    sqlite_path = Path(DATA_DIR) / "sqlite" / "metadata.db"
    if not sqlite_path.exists():
        return {"total_items": 0, "by_source": {}}

    conn = sqlite3.connect(str(sqlite_path))
    total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    sources = conn.execute(
        "SELECT source_type, COUNT(*) as cnt FROM items GROUP BY source_type"
    ).fetchall()
    conn.close()

    return {
        "total_items": total,
        "by_source": {s: c for s, c in sources},
    }


@app.get("/api/map")
def api_map(ids: str = Query("", description="搜索结果ID列表，逗号分隔")):
    """构建搜索驱动的知识地图：搜索结果 + 其语义关联节点 + 连线"""
    sqlite_path = Path(DATA_DIR) / "sqlite" / "metadata.db"
    if not sqlite_path.exists() or not ids:
        return {"nodes": [], "edges": []}

    seed_ids = [i.strip() for i in ids.split(",") if i.strip()]
    if not seed_ids:
        return {"nodes": [], "edges": []}

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row

    seen_ids = set(seed_ids)
    nodes = []
    edges = []
    seed_set = set(seed_ids)

    # 1. 加入种子节点（搜索结果），标记为 primary
    placeholders = ",".join("?" for _ in seed_ids)
    rows = conn.execute(
        f"SELECT id, title, source_type, source_url, date_collected FROM items WHERE id IN ({placeholders})",
        seed_ids,
    ).fetchall()
    for row in rows:
        nodes.append({
            "id": row["id"],
            "title": row["title"],
            "source_type": row["source_type"],
            "source_url": row["source_url"],
            "date_collected": row["date_collected"],
            "primary": True,
        })

    # 2. 对每个种子找相似节点，建立连线
    if searcher.collection:
        for seed_id in seed_ids:
            sims = searcher.get_similar_items(seed_id, top_k=5)
            for r in sims:
                if r["score"] < 0.5:
                    continue
                edges.append({
                    "source": seed_id,
                    "target": r["item_id"],
                    "score": r["score"],
                })
                if r["item_id"] not in seen_ids:
                    seen_ids.add(r["item_id"])
                    nodes.append({
                        "id": r["item_id"],
                        "title": r.get("title", ""),
                        "source_type": r.get("source_type", ""),
                        "source_url": r.get("source_url", ""),
                        "date_collected": r.get("date_collected", ""),
                        "primary": False,
                    })

    conn.close()
    return {"nodes": nodes, "edges": edges}


# 静态文件 — 前端界面
ui_dir = Path("ui")
ui_dir.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = ui_dir / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>GraveWaker</h1><p>前端文件未找到，请创建 ui/index.html</p>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
