"""一键数据摄取脚本

从各数据源拉取内容并索引到本地向量库。

使用方式:
    python scripts/ingest.py

首次运行会下载嵌入模型（约100MB），请耐心等待。
"""

import os
import sys

# 修复: 国内 HuggingFace 镜像 + SSL 证书
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("SSL_CERT_FILE", __import__("certifi").where())

import json
import yaml
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from connectors.bilibili import BilibiliConnector
from connectors.bookmarks import BookmarksConnector
from core.indexer import Indexer


def load_config():
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print("错误: config.yaml 不存在")
        print("请复制 config.yaml 并填写必要配置后重试")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    print("=" * 50)
    print("  GraveWaker — 数据摄取")
    print("=" * 50)

    config = load_config()
    data_dir = config.get("storage", {}).get("data_dir", "./data")

    all_items = []

    # --- 1. B站 ---
    bili_cfg = config.get("bilibili", {})
    bili_uid = bili_cfg.get("uid", "")
    if bili_uid:
        print("\n[1/2] 正在拉取 B站 收藏数据...")
        bili = BilibiliConnector(
            uid=bili_uid,
            cookie=bili_cfg.get("cookie", ""),
            fid=bili_cfg.get("fid", ""),
            data_dir=Path(data_dir) / "raw",
        )
        items = bili.fetch_all()

        # 保存原始数据
        raw_file = Path(data_dir) / "raw" / "bilibili_raw.json"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"  原始数据已保存到 {raw_file}")

        all_items.extend(items)
    else:
        print("\n[1/2] 跳过 B站（config.yaml 中未填写 uid）")

    # --- 2. 浏览器书签 ---
    bm_cfg = config.get("bookmarks", {})
    bm_path = bm_cfg.get("path", "")
    if bm_path:
        bm_full_path = project_root / bm_path
        if bm_full_path.exists():
            print("\n[2/2] 正在解析 浏览器书签...")
            bm = BookmarksConnector(str(bm_full_path), data_dir=Path(data_dir) / "raw")
            items = bm.fetch_all()
            all_items.extend(items)
        else:
            print(f"\n[2/2] 跳过浏览器书签（文件不存在: {bm_full_path}）")
            print("  请先在浏览器中导出书签 → 放到 data/raw/ 目录 → 修改 config.yaml")
    else:
        print("\n[2/2] 跳过浏览器书签（config.yaml 中未填写路径）")

    # --- 索引 ---
    if not all_items:
        print("\n没有获取到任何内容，请检查配置后重试。")
        sys.exit(0)

    print(f"\n{'=' * 50}")
    print(f"  总计获取 {len(all_items)} 条内容，开始索引...")
    print(f"{'=' * 50}")

    embedding_model = config.get("embedding", {}).get("model", "BAAI/bge-small-zh-v1.5")
    indexer = Indexer(data_dir=data_dir, embedding_model=embedding_model)
    indexer.index_items(all_items)

    # 输出统计
    stats = indexer.get_stats()
    print(f"\n索引统计: {stats}")
    indexer.close()

    print("\n摄取完成! 运行 python app.py 启动搜索界面")


if __name__ == "__main__":
    main()
