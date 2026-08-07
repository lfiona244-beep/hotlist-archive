#!/usr/bin/env python3
"""
hotlist-archive 每日自动化抓取脚本
用于 GitHub Actions 定时执行，数据源：60s.viki.moe（免费公开 API）

输出目录：data/YYYY/MM/DD/
- hotlist.json   全网热榜（知乎/微博/抖音/头条）
- news.json      每日新闻 60s
- weather.json   广州天气
- fuel.json      广东油价
- today.json     历史上的今天
- summary.json   当天汇总（整合以上所有）
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# 北京时间
TZ = timezone(timedelta(hours=8))
BASE = "https://60s.viki.moe/v2"

UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"

def fetch(url, label=""):
    """抓取 JSON 数据，失败返回 None"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  ⚠️ {label} 抓取失败: {e}")
        return None

def main():
    now = datetime.now(TZ)
    date_str = now.strftime("%Y-%m-%d")
    dir_path = f"data/{now.year}/{now.month:02d}/{now.day:02d}"
    os.makedirs(dir_path, exist_ok=True)

    print(f"📦 开始抓取 {date_str}")
    print(f"   输出目录: {dir_path}")

    results = {}

    # 1. 全网热榜
    print("\n🔥 热榜获取中...")
    hotlist = {}
    platforms = {
        "zhihu": "知乎",
        "weibo": "微博",
        "douyin": "抖音",
        "toutiao": "头条",
    }
    for key, name in platforms.items():
        data = fetch(f"{BASE}/{key}", f"{name}热榜")
        if data:
            hotlist[key] = data
            print(f"  ✅ {name}: {len(data.get('data', data)) if isinstance(data, dict) else '?'} 条")
        else:
            hotlist[key] = None

    path = f"{dir_path}/hotlist.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": date_str, "platforms": hotlist}, f, ensure_ascii=False, indent=2)
    print(f"  💾 {path}")

    # 2. 每日新闻
    print("\n📰 每日新闻...")
    data = fetch(f"{BASE}/60s", "60s新闻")
    if data:
        path = f"{dir_path}/news.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ {len(data.get('data',[])) if isinstance(data, dict) else '?'} 条 → {path}")

    # 3. 广州天气
    print("\n🌤️ 广州天气...")
    data = fetch(f"{BASE}/weather?query=广州", "天气")
    if data:
        path = f"{dir_path}/weather.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ {path}")

    # 4. 广东油价
    print("\n⛽ 广东油价...")
    data = fetch(f"{BASE}/fuel-price?region=广东", "油价")
    if data:
        path = f"{dir_path}/fuel.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ {path}")

    # 5. 历史上的今天
    print("\n📅 历史上的今天...")
    data = fetch(f"{BASE}/today-in-history", "历史上的今天")
    if data:
        path = f"{dir_path}/today.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ {path}")

    # 6. 汇总
    print("\n📋 生成汇总...")
    summary = {
        "date": date_str,
        "fetched_at": now.isoformat(),
        "has_hotlist": hotlist.get("zhihu") is not None,
        "has_news": data is not None,
    }
    path = f"{dir_path}/summary.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {path}")

    print(f"\n✅ 抓取完成 · {date_str}")

if __name__ == "__main__":
    main()