#!/usr/bin/env python3
"""
hotlist-archive 每日自动化抓取脚本
用于 GitHub Actions 定时执行

数据源（2026-09-30 换源，原全部走 60s.viki.moe）：
  - 天气：Open-Meteo（2026-09-29 起，60s/weather 源失效改用）
  - 热榜：抖音/头条/百度官方直连（60s 全线失效后改用）
  - 新闻：知乎日报 news-at.zhihu.com
  - 油价：qiyoujiage.com（按省份）
  - 历史：百度百科 CMS 静态 JSON
  - 知乎日报：RSS
  - B站热门：api.bilibili.com
  ⚠️ 60s.viki.moe 2026-09-29 起全线失效（429/400/403），四段长期输出空。
     统一走 scripts/free_sources.py（本地 dev-tools/free_sources.py 同源）。

输出目录：
  data/YYYY/MM/DD/   每日原始数据
    - hotlist.json   全网热榜（抖音/头条/百度）
    - news.json      每日资讯（知乎日报）
    - weather.json   广州天气（Open-Meteo）
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
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

# free_sources 与脚本同目录（GitHub Actions 从仓库根跑 python3 scripts/archive.py）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import free_sources as fs

# 北京时间
TZ = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"

# 广州坐标（Open-Meteo 用）
GZ_LAT, GZ_LON = 23.13, 113.26

# WMO weather_code → 中文天气描述（Open-Meteo 返回的是数字代码）
WMO_CODE = {
    0: "晴", 1: "多云", 2: "阴", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
    56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "冰粒",
    80: "阵雨", 81: "阵雨", 82: "大雨",
    85: "阵雪", 86: "阵雪",
    95: "雷暴", 96: "雷暴", 99: "雷暴",
}


def fetch(url, label=""):
    """抓取 JSON 数据，失败返回 None"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  ⚠️ {label} 抓取失败: {e}")
        return None


def fetch_weather_om():
    """广州天气（Open-Meteo，60s 源失效后的替代）。
    返回整理后的 dict，含 current/today 两段；失败返回 None。"""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={GZ_LAT}&longitude={GZ_LON}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "weather_code,wind_speed_10m,wind_direction_10m"
        "&daily=temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,uv_index_max,sunrise,sunset"
        "&timezone=Asia/Shanghai&forecast_days=1"
    )
    data = fetch(url, "天气(Open-Meteo)")
    if not data:
        return None
    try:
        c = data.get("current", {})
        d = data.get("daily", {})
        code = c.get("weather_code")
        return {
            "source": "open-meteo",
            "location": {"name": "广州", "lat": GZ_LAT, "lon": GZ_LON},
            "fetched_at": c.get("time"),
            "current": {
                "temperature": c.get("temperature_2m"),
                "feels_like": c.get("apparent_temperature"),
                "humidity": c.get("relative_humidity_2m"),
                "condition": WMO_CODE.get(code, f"code{code}"),
                "weather_code": code,
                "wind_speed": c.get("wind_speed_10m"),
                "wind_direction": c.get("wind_direction_10m"),
            },
            "today": {
                "temp_min": (d.get("temperature_2m_min") or [None])[0],
                "temp_max": (d.get("temperature_2m_max") or [None])[0],
                "precipitation_probability": (d.get("precipitation_probability_max") or [None])[0],
                "uv_index": (d.get("uv_index_max") or [None])[0],
                "sunrise": (d.get("sunrise") or [None])[0],
                "sunset": (d.get("sunset") or [None])[0],
            },
        }
    except Exception as e:
        print(f"  ⚠️ 天气解析失败: {e}")
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

    # 1. 全网热榜（官方直连三源）
    print("\n🔥 热榜获取中...")
    hotlist = {}
    platforms = {
        "douyin": ("抖音", fs.hot_douyin),
        "toutiao": ("头条", fs.hot_toutiao),
        "baidu": ("百度", fs.hot_baidu),
    }
    for key, (name, fn) in platforms.items():
        items = fn(20)
        if items:
            # ⚠️ 保持原 JSON 契约 {"data": [...]}：clean.py 和本地 archive-query.py
            # 都按 platforms[key]["data"] 读（2026-09-30 踩坑：写成裸 list 会让两者崩）。
            hotlist[key] = {"data": items}
            print(f"  ✅ {name}: {len(items)} 条")
        else:
            hotlist[key] = None
            print(f"  ⚠️ {name}: 无数据")

    write_json(f"{dir_path}/hotlist.json", {"date": date_str, "platforms": hotlist})
    print(f"  💾 {dir_path}/hotlist.json")

    # 2. 每日资讯（少数派 → 知乎日报降级链；原 60s/60s 已失效）
    print("\n📰 每日资讯...")
    news_items, news_src = fs.news(12)
    # ⚠️ 保持原 JSON 契约 {"data": {"news": [...]}}：clean.py 按 news["data"]["news"] 读。
    news = {"data": {"news": news_items, "tip": None}}
    if news_items:
        write_json(f"{dir_path}/news.json", news)
        print(f"  ✅ {len(news_items)} 条（来源 {news_src}）")
    else:
        print("  ⚠️ 无数据")

    # 3. 广州天气（Open-Meteo）
    print("\n🌤️ 广州天气（Open-Meteo）...")
    weather = fetch_weather_om()
    if weather:
        write_json(f"{dir_path}/weather.json", weather)
        c = weather["current"]
        print(f"  ✅ {c['temperature']}°C（体感{c['feels_like']}°C）{c['condition']} 湿度{c['humidity']}%")
    else:
        print("  ⚠️ 天气抓取失败")

    # 4. 广东油价（qiyoujiage.com）
    print("\n⛽ 广东油价...")
    fuel = fs.fuel_price("广东", 4)
    if fuel:
        write_json(f"{dir_path}/fuel.json", fuel)
        write_json("latest/fuel.json", fuel)  # 覆盖最新
        print(f"  ✅ {'  '.join(x['name'] + ' ' + x['price'] for x in fuel)}")
    else:
        print("  ⚠️ 油价抓取失败")

    # 5. 历史上的今天（百度百科）
    print("\n📅 历史上的今天...")
    today_hist = fs.today_in_history(limit=5)
    if today_hist:
        write_json(f"{dir_path}/today.json", today_hist)
        print(f"  ✅ {len(today_hist)} 条")
    else:
        print("  ⚠️ 历史抓取失败")

    # 5b. 知乎日报每日精选（RSS）
    print("\n📖 知乎日报精选（RSS）...")
    zhihu_daily = []
    # ⚠️ 2026-09-30 修两处：
    #  ① 原来硬编码 ghfast.top 代理前缀——GitHub Actions 在海外，代理反而卡住。
    #  ② raw.githubusercontent.com 在本网络实测直连不通（curl 返回 000），
    #     改走 GitHub contents API 取文件（api.github.com 稳），任何网络都能取。
    xml_data = None
    try:
        _api = ("https://api.github.com/repos/zzkeier/gen_zhihu_daily/contents/zhihu.xml")
        req = urllib.request.Request(_api, headers={
            "User-Agent": UA, "Accept": "application/vnd.github.raw+json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            xml_data = r.read().decode("utf-8")
    except Exception as e:
        print(f"  ⚠️ RSS 源取不到: {e}")
    try:
        import re
        entries = re.findall(r'<item>([\s\S]*?)</item>', xml_data or "")
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

    # 6. 油价变动检测（对比昨天同路径的 fuel.json）
    print("\n📊 油价变动检测...")
    fuel_changed = False
    fuel_change_detail = ""
    yesterday_path = f"data/{now.year}/{now.month:02d}/{max(now.day-1,1):02d}/fuel.json"
    prev_fuel = read_json(yesterday_path) if os.path.exists(yesterday_path) else None
    if fuel and prev_fuel:
        def prices(lst):
            return {x.get("name"): x.get("price") for x in lst if isinstance(x, dict)}
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
    brief = {
        "date": date_str,
        "generated_at": now.isoformat(),
        "weather": weather,
        "fuel": fuel or None,
        "fuel_changed": fuel_changed,
        "fuel_change_detail": fuel_change_detail,
        "news": [x["title"] for x in news_items[:8]],
        "news_tip": None,
        "hot_topics": [],
        "today_in_history": today_hist[:3],
    }
    # 多平台共同热点（取各平台前5条标题合并去重）
    seen = set()
    for key, (name, _fn) in platforms.items():
        items = (hotlist.get(key) or {}).get("data", [])
        for it in items[:5]:
            title = it.get("title") or ""
            if title and title not in seen:
                seen.add(title)
                brief["hot_topics"].append({"platform": name, "title": title})
            if len(brief["hot_topics"]) >= 10:
                break
    write_json(f"{dir_path}/brief.json", brief)
    write_json("latest/brief.json", brief)
    print(f"  ✅ {dir_path}/brief.json + latest/brief.json")

    # 8. 汇总
    summary = {
        "date": date_str,
        "fetched_at": now.isoformat(),
        "has_hotlist": any(hotlist.get(k) for k in platforms),
        "has_news": bool(news_items),
        "has_weather": weather is not None,
        "has_fuel": bool(fuel),
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
