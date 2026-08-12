#!/usr/bin/env python3
"""
知识库在线源健康巡检脚本
用于 GitHub Actions 定时执行。巡检核心在线源存活状态，防止知识库死链失明。

输出目录：
  data/YYYY/MM/DD/source-health.json   当日巡检报告
  latest/source-health.json            最新巡检报告（AI 快速读取）

用法：
  python3 scripts/source_health.py
"""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
TIMEOUT = 8

SOURCES = {
    "60s热榜API": ("https://60s.viki.moe/v2/zhihu", 200, "知乎热榜（hotlist 数据源）"),
    "60s新闻API": ("https://60s.viki.moe/v2/60s", 200, "每日新闻60s"),
    "默沙东手册": ("https://www.msdmanuals.cn/home", 200, "心理健康权威源（kb-run 路径）"),
    "追剧导航站": ("https://zhuiju.me", 200, "awesome-zhuiju-free 官网"),
    "追剧资源JSON": ("https://raw.githubusercontent.com/laoma2053/awesome-zhuiju-free/main/resources/resources.json", 200, "94个追剧资源清单"),
    "GitHub API": ("https://api.github.com", 200, "GitHub 官方 API"),
    "博查搜索API": ("https://api.bochaai.com/v1/web-search", 405, "博查 AI 搜索（POST接口，405=存活）"),
    "美股日报": ("https://finews.elsetech.app/", 200, "美股盘后日报"),
    "Bing搜索": ("https://www.bing.com", 200, "中文搜索兜底"),
    "StackExchange": ("https://api.stackexchange.com", 400, "技术问答（400=存活）"),
}


def check(url, expect=200):
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            code = r.getcode()
            ms = int((time.time() - start) * 1000)
            return code, ms, (code == expect)
    except urllib.error.HTTPError as e:
        code = e.code
        ms = int((time.time() - start) * 1000)
        return code, ms, (code == expect)
    except Exception as e:
        return None, int((time.time() - start) * 1000), False


def main():
    now = datetime.now(TZ)
    date_str = now.strftime("%Y-%m-%d")
    dir_path = f"data/{now.year}/{now.month:02d}/{now.day:02d}"
    os.makedirs(dir_path, exist_ok=True)
    os.makedirs("latest", exist_ok=True)

    print(f"🩺 在线源健康巡检 · {date_str}")

    results = []
    for name, (url, expect, note) in SOURCES.items():
        code, ms, ok = check(url, expect)
        results.append({
            "name": name,
            "url": url,
            "status": "✅ 正常" if ok else "❌ 异常",
            "code": code,
            "latency_ms": ms,
            "expect": expect,
            "note": note,
        })
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}: HTTP {code} · {ms}ms")

    ok_count = sum(1 for r in results if r["status"] == "✅ 正常")
    report = {
        "date": date_str,
        "checked_at": now.isoformat(),
        "total": len(results),
        "ok": ok_count,
        "fail": len(results) - ok_count,
        "sources": results,
    }

    write_json(f"{dir_path}/source-health.json", report)
    write_json("latest/source-health.json", report)
    print(f"\n✅ 巡检完成：{ok_count}/{len(results)} 正常")
    if ok_count < len(results):
        print("  ⚠️ 有异常源，注意排查")


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()