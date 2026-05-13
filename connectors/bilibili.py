"""B站收藏夹数据源连接器

通过B站公开API获取用户收藏视频的元数据（标题、描述、标签等）。
不需要登录即可获取公开收藏夹内容。
"""

import time
import requests
from pathlib import Path

# 统一输出 schema，所有 connector 必须遵守
# {
#     "id": str,           # 全局唯一ID
#     "title": str,        # 标题
#     "text": str,         # 用于全文索引的文本
#     "source_type": str,  # 来源平台: bilibili / bookmarks / wechat / pdf
#     "source_url": str,   # 原始链接
#     "date_collected": str,  # 收藏日期 YYYY-MM-DD
#     "tags": list[str],   # 平台自带标签/分类
#     "metadata": dict     # 平台特有字段
# }


class BilibiliConnector:
    BASE_URL = "https://api.bilibili.com"

    def __init__(self, uid: str, cookie: str = "", fid: str = "", data_dir: Path = None):
        self.uid = uid
        self.fid = fid  # 默认收藏夹 media_id（从收藏页URL的 ?fid= 获取）
        self.data_dir = data_dir or Path("./data/raw")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com",
        })
        if cookie:
            # 如果用户填了完整Cookie（含=），直接用；否则当作SESSDATA值
            if "=" in cookie:
                self.session.headers["Cookie"] = cookie
            else:
                self.session.cookies.set("SESSDATA", cookie)

    def _api_get(self, path: str, params: dict = None) -> dict:
        """封装API请求，成功返回 data，失败返回 None"""
        resp = self.session.get(f"{self.BASE_URL}{path}", params=params)
        resp.raise_for_status()
        data = resp.json()
        if data["code"] != 0:
            return None
        return data["data"]

    def get_fav_folders(self) -> list[dict]:
        """获取收藏夹列表：自建收藏夹 + 默认收藏夹"""
        folders = []

        # 1. 尝试获取自建收藏夹（created/list 可能需要特定条件）
        data = self._api_get("/x/v3/fav/folder/created/list",
                             {"up_mid": self.uid, "platform": "web"})
        if data and data.get("list"):
            folders.extend(data["list"])

        # 2. 探测默认收藏夹：优先用用户提供的 fid，其次用 UID
        for mid in [self.fid, self.uid]:
            if not mid:
                continue
            probe = self._api_get("/x/v3/fav/resource/list", {
                "media_id": mid, "pn": 1, "ps": 1, "platform": "web",
            })
            if probe is not None and probe.get("medias") is not None:
                info = probe.get("info", {})
                folders.append({
                    "id": mid,
                    "title": info.get("title", "默认收藏夹"),
                    "media_count": info.get("media_count", len(probe.get("medias", []))),
                })
                break  # 找到默认收藏夹就停

        return folders

    def get_fav_items(self, media_id, pn: int = 1, ps: int = 20):
        """分页获取某个收藏夹的内容，无内容时返回 None"""
        return self._api_get("/x/v3/fav/resource/list", {
            "media_id": media_id,
            "pn": pn,
            "ps": ps,
            "platform": "web",
        })

    def fetch_all(self) -> list[dict]:
        """拉取所有收藏夹的全部视频元数据，返回统一schema列表"""
        all_items = []
        folders = self.get_fav_folders()
        print(f"找到 {len(folders)} 个收藏夹")

        for folder in folders:
            media_id = folder["id"]
            folder_title = folder["title"]
            total = folder["media_count"]
            if total == 0:
                print(f"  收藏夹「{folder_title}」为空，跳过")
                continue
            print(f"  收藏夹「{folder_title}」共 {total} 个视频，正在拉取...")

            page = 1
            collected = 0
            while True:
                data = self.get_fav_items(media_id, pn=page, ps=20)
                if data is None:
                    break
                medias = data.get("medias", [])
                if not medias:
                    break

                for item in medias:
                    bvid = item.get("bvid", "")
                    title = item.get("title", "无标题")
                    intro = item.get("intro", "")
                    upper = item.get("upper", {})
                    owner_name = upper.get("name", "")

                    # 构造用于索引的文本：标题+简介+UP主
                    text_parts = [title, intro, owner_name]
                    text = "\n".join(p for p in text_parts if p)

                    fav_time = item.get("fav_time", 0)
                    if fav_time:
                        date_str = time.strftime("%Y-%m-%d", time.localtime(fav_time))
                    else:
                        date_str = ""

                    all_items.append({
                        "id": f"bilibili_{bvid}",
                        "title": title,
                        "text": text,
                        "source_type": "bilibili",
                        "source_url": f"https://www.bilibili.com/video/{bvid}",
                        "date_collected": date_str,
                        "tags": [folder_title, item.get("type_name", "")],
                        "metadata": {
                            "bvid": bvid,
                            "duration": item.get("duration", ""),
                            "owner": owner_name,
                            "folder": folder_title,
                            "view_count": item.get("cnt_info", {}).get("play", 0),
                        }
                    })
                    collected += 1

                if not data.get("has_more", False):
                    break
                page += 1
                time.sleep(0.6)  # 请求间隔，避免限流

            print(f"    拉取完成: {collected} 条")

        print(f"\nB站总计获取: {len(all_items)} 条收藏")
        return all_items
