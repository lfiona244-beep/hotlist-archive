#!/usr/bin/env python3
"""
hotlist-archive 每日自动化抓取脚本
用于 GitHub Actions 定时执行，数据源：60s.viki.moe（免费公开 API）

输出目录：
  data/YYYY/MM/DD/   每日原始数据
    - hotlist.json   全网热榜（知乎/微博/抖音/头条）
    - news.json      每日新闻 60s
    - weather.json   广州天气（Open-Meteo 替代方案备用）
    - fuel.json      广东油价
    - today.json     历史上的今天
    - zhihu_daily.json  知乎日报精选（RSS）
    - bilibili.json     B站热门视频
    - summary.json   当天汇总
  latest/            最新数据固定路径（AI 快速读取）
    - brief.json     开工简报（天气+油价+新闻+热点 一页纸）
    - fuel.json      最新油价（供对比变动）
"""

import json
import os
import glob
import urllib.request
import urllib.parse
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


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    now = datetime.now(TZ)
    date_str = now.strftime("%Y-%m-%d")
    dir_path = f"data/{now.year}/{now.month:02d}/{now.day:02d}"
    os.makedirs(dir_path, exist_ok=True)
    os.makedirs("latest", exist_ok=True)

    print(f"📦 开始抓取 {date_str}")
    print(f"   输出目录: {dir_path}")

    # 1. 全网热榜
    print("\n🔥 热榜获取中...")
    hotlist = {}
    platforms = {"zhihu": "知乎", "weibo": "微博", "douyin": "抖音", "toutiao": "头条"}
    for key, name in platforms.items():
        data = fetch(f"{BASE}/{key}", f"{name}热榜")
        if data:
            hotlist[key] = data
            n = len(data.get("data", [])) if isinstance(data, dict) else "?"
            print(f"  ✅ {name}: {n} 条")
        else:
            hotlist[key] = None

    write_json(f"{dir_path}/hotlist.json", {"date": date_str, "platforms": hotlist})
    print(f"  💾 {dir_path}/hotlist.json")

    # 2. 每日新闻
    print("\n📰 每日新闻...")
    news = fetch(f"{BASE}/60s", "60s新闻")
    if news:
        write_json(f"{dir_path}/news.json", news)
        n = len(news.get("data", [])) if isinstance(news, dict) else "?"
        print(f"  ✅ {n} 条")

    # 3. 广州天气
    print("\n🌤️ 广州天气...")
    weather = fetch(f"{BASE}/weather?query={urllib.parse.quote('广州')}", "天气")
    if weather:
        write_json(f"{dir_path}/weather.json", weather)
        print("  ✅")

    # 4. 广东油价
    print("\n⛽ 广东油价...")
    fuel = fetch(f"{BASE}/fuel-price?region={urllib.parse.quote('广东')}", "油价")
    if fuel:
        write_json(f"{dir_path}/fuel.json", fuel)
        write_json("latest/fuel.json", fuel)  # 覆盖最新
        print("  ✅")

    # 5. 历史上的今天
    print("\n📅 历史上的今天...")
    today_hist = fetch(f"{BASE}/today-in-history", "历史上的今天")
    if today_hist:
        write_json(f"{dir_path}/today.json", today_hist)
        print("  ✅")

    # 5b. 知乎日报每日精选
    print("\n📖 知乎日报精选...")
    zhihu_daily = []
    try:
        req = urllib.request.Request(
            "https://ghfast.top/https://raw.githubusercontent.com/zzkeier/gen_zhihu_daily/main/zhihu.xml",
            headers={"User-Agent": UA}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            xml_data = r.read().decode("utf-8")
        import re
        entries = re.findall(r'<item>([\s\S]*?)</item>', xml_data)
        for entry in entries[:12]:
            title = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', entry)
            link = re.search(r'<link>(.*?)</link>', entry)
            desc = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>', entry)
            if title:
                zhihu_daily.append({
                    "title": title.group(1),
                    "link": link.group(1) if link else "",
                    "description": desc.group(1)[:300] if desc else ""
                })
        write_json(f"{dir_path}/zhihu_daily.json", zhihu_daily)
        print(f"  ✅ {len(zhihu_daily)} 条")
    except Exception as e:
        print(f"  ⚠️ 知乎日报抓取失败: {e}")

    # 5c. B站热门
    print("\n📺 B站热门...")
    bili_hot = []
    bili = fetch("https://api.bilibili.com/x/web-interface/popular?ps=20", "B站热门")
    if bili and bili.get("code") == 0:
        bili_data = bili.get("data", {}).get("list", [])
        for v in bili_data[:15]:
            bili_hot.append({
                "title": v.get("title", ""),
                "play": v.get("stat", {}).get("view", 0),
                "like": v.get("stat", {}).get("like", 0),
                "author": v.get("owner", {}).get("name", ""),
                "bvid": v.get("bvid", ""),
                "url": f"https://www.bilibili.com/video/{v.get('bvid', '')}",
            })
        write_json(f"{dir_path}/bilibili.json", bili_hot)
        print(f"  ✅ {len(bili_hot)} 条")
    else:
        print(f"  ⚠️ B站热门抓取失败")
    # 6. 油价变动检测（对比昨天的 latest/fuel.json 是当日覆盖前的旧值，所以存昨日副本）
    print("\n📊 油价变动检测...")
    fuel_changed = False
    fuel_change_detail = ""
    yesterday_path = f"data/{now.year}/{now.month:02d}/{max(now.day-1,1):02d}/fuel.json"
    prev_fuel = read_json(yesterday_path) if os.path.exists(yesterday_path) else None
    if fuel and prev_fuel:
        # 取价格字段做对比（各 API 版本字段不同，尽量通用）
        def prices(d):
            d = d.get("data", d) if isinstance(d, dict) else d
            if isinstance(d, dict):
                return {k: v for k, v in d.items() if isinstance(v, (int, float))}
            return {}
        cur_p = prices(fuel)
        old_p = prices(prev_fuel)
        if cur_p and old_p and cur_p != old_p:
            fuel_changed = True
            fuel_change_detail = f"{old_p} → {cur_p}"
            print(f"  🔺 油价有变动: {fuel_change_detail}")
        else:
            print("  ➖ 油价无变动")
    else:
        print("  ℹ️ 无昨日数据可比（首日运行）")

    # 7. 生成开工简报（一页纸）
    print("\n📋 生成开工简报...")
    news_list = []
    if news:
        nd = news.get("data", {})
        news_list = nd.get("news", []) if isinstance(nd, dict) else []
    brief = {
        "date": date_str,
        "generated_at": now.isoformat(),
        "weather": weather.get("data", weather) if weather else None,
        "fuel": fuel.get("data", fuel) if fuel else None,
        "fuel_changed": fuel_changed,
        "fuel_change_detail": fuel_change_detail,
        "news": news_list[:8],
        "news_tip": (news.get("data", {}).get("tip") if news and isinstance(news.get("data"), dict) else None),
        "hot_topics": [],
        "today_in_history": [],
    }
    # 历史上的今天
    if today_hist:
        th = today_hist.get("data", today_hist)
        if isinstance(th, dict):
            th = th.get("items", [])
        brief["today_in_history"] = th[:3] if isinstance(th, list) else []
    # 多平台共同热点（取各平台前5条标题合并去重）
    seen = set()
    for key in platforms:
        d = hotlist.get(key)
        if not d:
            continue
        items = d.get("data", []) if isinstance(d, dict) else []
        for it in items[:5]:
            title = it.get("title") or it.get("name") or ""
            if title and title not in seen:
                seen.add(title)
                brief["hot_topics"].append({"platform": platforms[key], "title": title})
            if len(brief["hot_topics"]) >= 10:
                break
    write_json(f"{dir_path}/brief.json", brief)
    write_json("latest/brief.json", brief)
    print(f"  ✅ {dir_path}/brief.json + latest/brief.json")

    # 8. 汇总
    summary = {
        "date": date_str,
        "fetched_at": now.isoformat(),
        "has_hotlist": hotlist.get("zhihu") is not None,
        "has_news": news is not None,
        "has_weather": weather is not None,
        "has_fuel": fuel is not None,
        "fuel_changed": fuel_changed,
        "fuel_change_detail": fuel_change_detail,
        "has_zhihu_daily": len(zhihu_daily) > 0,
        "has_bilibili": len(bili_hot) > 0,
    }
    write_json(f"{dir_path}/summary.json", summary)
    print(f"  ✅ {dir_path}/summary.json")

    print(f"\n✅ 抓取完成 · {date_str}")


if __name__ == "__main__":
    main()
