#!/usr/bin/env python3
"""
追剧资源每日存档脚本
用于 GitHub Actions 定时执行。数据源：awesome-zhuiju-free（5607⭐，每日自动检测资源可用性）

拉取两份结构化数据并存档：
  resources/resources.json        94 个资源及分类
  reports/availability.json       每日检测的可用性报告

输出目录：
  data/YYYY/MM/DD/zhuiju.json     当日合并快照（含统计摘要）
  latest/zhuiju.json              最新快照（AI 快速读取）
"""

import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
BASE = "https://raw.githubusercontent.com/laoma2053/awesome-zhuiju-free/main"
UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"


def fetch(url, label=""):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  ⚠️ {label} 抓取失败: {e}")
        return None


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def classify_count(resources):
    counts = {}
    for r in resources:
        raw = r.get("category") or r.get("分类") or r.get("type") or "其它"
        counts[str(raw).strip()] = counts.get(str(raw).strip(), 0) + 1
    return counts


def main():
    now = datetime.now(TZ)
    date_str = now.strftime("%Y-%m-%d")
    dir_path = f"data/{now.year}/{now.month:02d}/{now.day:02d}"
    os.makedirs(dir_path, exist_ok=True)
    os.makedirs("latest", exist_ok=True)

    print(f"🎬 追剧资源存档 · {date_str}")

    resources = fetch(f"{BASE}/resources/resources.json", "资源列表")
    availability = fetch(f"{BASE}/reports/availability.json", "可用性报告")

    if resources is None:
        if availability is not None:
            write_json(f"{dir_path}/zhuiju.json", {"date": date_str, "resources": None, "availability": availability})
            write_json("latest/zhuiju.json", {"date": date_str, "resources": None, "availability": availability})
        raise SystemExit("❌ 资源列表抓取失败，未生成完整存档")

    res_list = resources if isinstance(resources, list) else resources.get("resources", resources.get("data", []))
    if not isinstance(res_list, list):
        res_list = []

    # 可用性报告解析：results 数组，每条含 resource_id + status(reachable/restricted/unreachable) + http_status
    avail_map = {}
    if isinstance(availability, dict):
        a = availability.get("results") or availability.get("availability") or availability.get("data") or availability
        if isinstance(a, list):
            avail_map = {item.get("resource_id"): item for item in a if isinstance(item, dict)}
        elif isinstance(a, dict):
            avail_map = a

    total = len(res_list)
    ok_count = 0
    ok_samples = []
    broken = []
    restricted = []
    for r in res_list:
        name = r.get("名称") or r.get("name") or r.get("title") or ""
        info = avail_map.get(r.get("id")) or avail_map.get(name)
        st = info.get("status") if isinstance(info, dict) else None
        code = info.get("http_status") if isinstance(info, dict) else None
        if st in ("reachable", "ok", "up", "available", True, 200):
            ok_count += 1
            ok_samples.append(name)
        elif st == "restricted":
            restricted.append({"name": name, "status": f"受限 HTTP {code}"})
        elif st in ("unreachable", "down", "dead", "fail", False):
            broken.append({"name": name, "status": str(st)})

    cats = classify_count(res_list)

    snapshot = {
        "date": date_str,
        "fetched_at": now.isoformat(),
        "source": "awesome-zhuiju-free",
        "total": total,
        "available": ok_count,
        "available_rate": round(ok_count / total * 100, 1) if total else 0,
        "categories": cats,
        "available_samples": ok_samples[:8],
        "restricted": restricted[:10],
        "broken": broken[:10],
    }
    snapshot["resources"] = res_list
    if availability is not None:
        snapshot["availability"] = availability

    write_json(f"{dir_path}/zhuiju.json", snapshot)
    write_json("latest/zhuiju.json", {
        "date": date_str,
        "total": total,
        "available": ok_count,
        "available_rate": round(ok_count / total * 100, 1) if total else 0,
        "categories": cats,
        "available_samples": ok_samples[:8],
        "restricted": restricted[:10],
        "broken": broken[:10],
    })

    print(f"  ✅ 共 {total} 个资源，可用 {ok_count}，可用率 {round(ok_count/total*100,1) if total else 0}%")
    print(f"  💾 {dir_path}/zhuiju.json + latest/zhuiju.json")


if __name__ == "__main__":
    main()