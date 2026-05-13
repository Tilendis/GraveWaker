"""核心索引器

将 connector 获取的文本内容分块、向量化，存入 ChromaDB 和 SQLite。
"""

import sqlite3
import json
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer
from chromadb.config import Settings as ChromaSettings


class Indexer:
    CHUNK_SIZE = 500      # 每个文本块最多500字
    CHUNK_OVERLAP = 100   # 块之间重叠100字

    def __init__(self, data_dir: str = "./data", embedding_model: str = "BAAI/bge-small-zh-v1.5"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 ChromaDB（持久化存储）
        chroma_path = str(self.data_dir / "chroma")
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="graves",
            metadata={"hnsw:space": "cosine"},
        )

        # 初始化 SQLite（元数据存储）
        sqlite_path = str(self.data_dir / "sqlite" / "metadata.db")
        (self.data_dir / "sqlite").mkdir(parents=True, exist_ok=True)
        self.sqlite = sqlite3.connect(sqlite_path)
        self._init_tables()

        # 加载本地嵌入模型
        print(f"正在加载嵌入模型: {embedding_model} ...")
        self.model = SentenceTransformer(embedding_model)
        print("嵌入模型加载完成")

    def _init_tables(self):
        self.sqlite.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                title TEXT,
                source_type TEXT,
                source_url TEXT,
                date_collected TEXT,
                tags TEXT,
                metadata TEXT,
                indexed_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self.sqlite.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                item_id TEXT,
                chunk_index INTEGER,
                chunk_text TEXT,
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
        """)
        self.sqlite.commit()

    def _split_text(self, text: str) -> list[str]:
        """简单滑动窗口分块"""
        if len(text) <= self.CHUNK_SIZE:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.CHUNK_SIZE
            chunks.append(text[start:end])
            start = end - self.CHUNK_OVERLAP
        return chunks

    def index_items(self, items: list[dict]):
        """将一批内容项索引到向量库"""
        if not items:
            print("没有内容需要索引")
            return

        chunk_id_list = []
        chunk_text_list = []
        chunk_meta_list = []

        for item in items:
            item_id = item["id"]

            # 存入 SQLite 元数据
            self.sqlite.execute(
                """INSERT OR REPLACE INTO items
                   (id, title, source_type, source_url, date_collected, tags, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id,
                    item.get("title", ""),
                    item.get("source_type", ""),
                    item.get("source_url", ""),
                    item.get("date_collected", ""),
                    json.dumps(item.get("tags", []), ensure_ascii=False),
                    json.dumps(item.get("metadata", {}), ensure_ascii=False),
                ),
            )

            # 分块
            chunks = self._split_text(item.get("text", ""))
            for i, chunk_text in enumerate(chunks):
                chunk_id = f"{item_id}_chunk_{i}"
                chunk_id_list.append(chunk_id)
                chunk_text_list.append(chunk_text)
                chunk_meta_list.append({
                    "item_id": item_id,
                    "title": item.get("title", ""),
                    "source_type": item.get("source_type", ""),
                    "source_url": item.get("source_url", ""),
                    "date_collected": item.get("date_collected", ""),
                })

                # 存入 SQLite 分块记录
                self.sqlite.execute(
                    "INSERT OR REPLACE INTO chunks (chunk_id, item_id, chunk_index, chunk_text) VALUES (?, ?, ?, ?)",
                    (chunk_id, item_id, i, chunk_text),
                )

            # 删除该条目的旧向量（支持增量更新）
            old = self.collection.get(where={"item_id": item_id})
            if old["ids"]:
                self.collection.delete(ids=old["ids"])

        self.sqlite.commit()

        # 批量向量化 + 写入 ChromaDB
        print(f"正在向量化 {len(chunk_text_list)} 个文本块 ...")
        embeddings = self.model.encode(
            chunk_text_list,
            show_progress_bar=True,
            normalize_embeddings=True,
        )

        # 分批写入 ChromaDB（避免一次提交过多）
        BATCH = 500
        for i in range(0, len(chunk_id_list), BATCH):
            end = min(i + BATCH, len(chunk_id_list))
            self.collection.add(
                ids=chunk_id_list[i:end],
                embeddings=embeddings[i:end].tolist(),
                documents=chunk_text_list[i:end],
                metadatas=chunk_meta_list[i:end],
            )

        print(f"索引完成: {len(items)} 条内容, {len(chunk_id_list)} 个块")

    def get_stats(self) -> dict:
        """获取索引统计"""
        item_count = self.sqlite.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        chunk_count = self.collection.count()
        sources = self.sqlite.execute(
            "SELECT source_type, COUNT(*) FROM items GROUP BY source_type"
        ).fetchall()
        return {
            "total_items": item_count,
            "total_chunks": chunk_count,
            "by_source": dict(sources),
        }

    def close(self):
        self.sqlite.close()
