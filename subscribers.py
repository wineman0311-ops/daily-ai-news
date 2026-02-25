#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
訂閱者管理模組
將訂閱名單儲存為 JSON 檔案。
Zeabur 部署時請掛載持久化 Volume 至 DATA_DIR（預設 /app/data）。
"""

import json
import os
from pathlib import Path
from datetime import datetime

# Zeabur 請設定 DATA_DIR=/app/data 並掛載 Volume，確保重啟後資料不遺失
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))
SUBSCRIBERS_FILE = DATA_DIR / "subscribers.json"


def _load() -> dict:
    if not SUBSCRIBERS_FILE.exists():
        return {}
    try:
        with open(SUBSCRIBERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def subscribe(chat_id: int | str, username: str = None, first_name: str = None) -> bool:
    """新增訂閱。回傳 True 表示新訂閱，False 表示已存在。"""
    data = _load()
    key = str(chat_id)
    if key in data:
        return False
    data[key] = {
        "chat_id":       str(chat_id),
        "username":      username,
        "first_name":    first_name,
        "subscribed_at": datetime.now().isoformat(),
    }
    _save(data)
    return True


def unsubscribe(chat_id: int | str) -> bool:
    """取消訂閱。回傳 True 表示成功，False 表示原本未訂閱。"""
    data = _load()
    key = str(chat_id)
    if key not in data:
        return False
    del data[key]
    _save(data)
    return True


def is_subscribed(chat_id: int | str) -> bool:
    return str(chat_id) in _load()


def get_chat_ids() -> list[str]:
    return list(_load().keys())


def get_count() -> int:
    return len(_load())


def get_all() -> dict:
    return _load()
