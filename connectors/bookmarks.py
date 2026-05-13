"""浏览器书签数据源连接器

解析 Chrome/Firefox/Edge 等浏览器导出的 Netscape 书签 HTML 文件。
"""

import hashlib
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup


class BookmarksConnector:

    def __init__(self, file_path: str, data_dir: Path = None):
        self.file_path = Path(file_path)
        self.data_dir = data_dir or Path("./data/raw")
        if not self.file_path.exists():
            raise FileNotFoundError(f"书签文件不存在: {file_path}")

    def _parse_date(self, add_date_str: str) -> str:
        """Unix时间戳转日期字符串"""
        if not add_date_str:
            return ""
        try:
            ts = int(add_date_str)
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return ""

    def fetch_all(self) -> list[dict]:
        """解析书签文件，返回统一schema列表"""
        with open(self.file_path, "r", encoding="utf-8") as f:
            html = f.read()

        soup = BeautifulSoup(html, "html.parser")
        items = []
        seen_urls = set()

        for link in soup.find_all("a"):
            url = link.get("href", "")
            title = link.get_text(strip=True) or "无标题"
            add_date = link.get("add_date", "")

            # 去重（有些书签会在多个文件夹出现）
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 推断所属文件夹（向上查找 DT > H3 或其他 DL 结构）
            folder = ""
            parent_dl = link.find_parent("dl")
            if parent_dl:
                # 找当前 DL 前面的标题
                prev = parent_dl.find_previous_sibling("h3")
                if prev:
                    folder = prev.get_text(strip=True)

            items.append({
                "id": f"bookmark_{hashlib.md5(url.encode()).hexdigest()[:12]}",
                "title": title,
                "text": f"{title}\n{url}",
                "source_type": "bookmark",
                "source_url": url,
                "date_collected": self._parse_date(add_date),
                "tags": [folder] if folder else [],
                "metadata": {
                    "folder": folder,
                }
            })

        print(f"浏览器书签总计: {len(items)} 条 (来自 {self.file_path})")
        return items
