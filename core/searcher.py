"""语义搜索模块

使用本地嵌入模型将查询文本向量化，在 ChromaDB 中检索相似内容。
"""

import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer


class Searcher:
    def __init__(self, data_dir: str = "./data", embedding_model: str = "BAAI/bge-small-zh-v1.5"):
        self.data_dir = Path(data_dir)
        chroma_path = str(self.data_dir / "chroma")

        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )

        # 检查是否已有数据
        try:
            self.collection = self.chroma_client.get_collection("graves")
        except Exception:
            self.collection = None

        if self.collection is None:
            print("警告: 尚未索引任何内容，请先运行 python scripts/ingest.py")
        else:
            print(f"已加载索引: {self.collection.count()} 个文本块")

        print(f"正在加载嵌入模型: {embedding_model} ...")
        self.model = SentenceTransformer(embedding_model)
        print("搜索就绪")

    def search(self, query: str, top_k: int = 20, min_score: float = 0.3) -> list[dict]:
        """语义搜索，返回 top_k 条去重且高于 min_score 的结果"""
        if self.collection is None:
            return []

        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        )

        # 多取候选（top_k * 3），去重+过滤后再截断
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=max(top_k * 3, 60),
        )

        seen = set()
        formatted = []
        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            item_id = meta.get("item_id", "")
            if item_id in seen:
                continue
            seen.add(item_id)

            score = round(1 - results["distances"][0][i], 4)
            if score < min_score:
                continue

            formatted.append({
                "item_id": item_id,
                "title": meta.get("title", "无标题"),
                "source_type": meta.get("source_type", ""),
                "source_url": meta.get("source_url", ""),
                "date_collected": meta.get("date_collected", ""),
                "excerpt": results["documents"][0][i][:200],
                "score": score,
            })

            if len(formatted) >= top_k:
                break

        return formatted

    def get_similar_items(self, item_id: str, top_k: int = 5) -> list[dict]:
        """找与指定内容相似的其它内容（用于知识地图连线）"""
        if self.collection is None:
            return []

        # 获取该条目的所有文本块
        chunks = self.collection.get(
            where={"item_id": item_id},
            include=["embeddings"],
        )
        if len(chunks.get("embeddings", [])) == 0:
            return []

        # 用多个块的平均向量去检索
        import numpy as np
        avg_embedding = np.mean(chunks["embeddings"], axis=0).tolist()

        results = self.collection.query(
            query_embeddings=[avg_embedding],
            n_results=top_k + 1,  # +1 因为会匹配到自己
        )

        formatted = []
        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            if meta.get("item_id") == item_id:
                continue  # 排除自己
            formatted.append({
                "item_id": meta.get("item_id", ""),
                "title": meta.get("title", "无标题"),
                "source_type": meta.get("source_type", ""),
                "source_url": meta.get("source_url", ""),
                "date_collected": meta.get("date_collected", ""),
                "score": round(1 - results["distances"][0][i], 4),
            })
            if len(formatted) >= top_k:
                break

        return formatted
