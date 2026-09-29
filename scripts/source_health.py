#!/usr/bin/env python3
"""
知识库在线源健康巡检脚本
用于 GitHub Actions 定时执行。巡检核心在线源存活状态，防止知识库死链失明。

2026-09-29 新增：发现异常时自动创建 GitHub Issue 通知。
  这是"跨时间主动性"的外部触发机制——模型不会"想起来"读健康报告，
  靠 Issue 邮件推送让异常主动浮出，不靠人主动查。
  去重：相同标题的 open Issue 已存在则不重复创建。

2026-09-30 更新：60s.viki.moe 全线失效，原两条 60s 巡检项换成新数据源
  （抖音热搜、知乎日报），否则巡检会一直报这两个已知失效的源。

输出目录：
  data/YYYY/MM/DD/source-health.json   当日巡检报告
  latest/source-health.json            最新巡检报告（AI 快速读取）

用法：
  python3 scripts/source_health.py
  （需环境变量 GITHUB_TOKEN，Actions 里默认提供）
"""

import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
TIMEOUT = 8

SOURCES = {
    "抖音热搜API": ("https://aweme-lq.snssdk.com/aweme/v1/hot/search/list/?aid=1128&version_code=880", 200, "抖音热榜（hotlist 数据源）"),
    "知乎日报API": ("https://news-at.zhihu.com/api/4/news/latest", 200, "每日资讯（news 数据源）"),
    "百度百科历史": ("https://baike.baidu.com/cms/home/eventsOnHistory/09.json", 200, "历史上的今天"),
    "油价网": ("http://www.qiyoujiage.com/guangdong.shtml", 200, "广东油价"),
    "默沙东手册": ("https://www.msdmanuals.cn/home", 200, "心理健康权威源（kb-run 路径）"),
    "追剧导航站": ("https://zhuiju.me", 200, "awesome-zhuiju-free 官网"),
    "追剧资源JSON": ("https://raw.githubusercontent.com/laoma2053/awesome-zhuiju-free/main/resources/resources.json", 200, "94个追剧资源清单"),
    "GitHub API": ("https://api.github.com", 200, "GitHub 官方 API"),
    "博查搜索API": ("https://api.bochaai.com/v1/web-search", 405, "博查 AI 搜索（POST接口，405=存活）"),
    "美股日报": ("https://finews.elsetech.app/", 200, "美股盘后日报"),
    "Bing搜索": ("https://www.bing.com", 200, "中文搜索兜底"),
    "StackExchange": ("https://api.stackexchange.com/2.3/sites", 200, "技术问答（sites 公开接口）"),
    "EcoHub追剧": ("https://eco.fe-spark.cn/", 200, "主追剧源（Next.js 聚合站）"),
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


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def gh_api(method, path, token, body=None):
    """调用 GitHub API。repo 从 GITHUB_REPOSITORY 取（Actions 默认提供）。"""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo or not token:
        return None
    url = f"https://api.github.com/repos/{repo}/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8")) if r.status != 204 else {}
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", errors="ignore")}
    except Exception as e:
        return {"error": str(e)}


def create_health_issue(failures, report):
    """发现异常时创建 GitHub Issue 通知。去重：相同标题的 open Issue 已存在则跳过。"""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("  ℹ️ 无 GITHUB_TOKEN，跳过 Issue 创建")
        return
    if not failures:
        return

    title = f"🩺 数据源异常 · {len(failures)} 个源不可用"

    # 去重：查已有 open issue（不带 label，避免 label 不存在报错）
    existing = gh_api("GET", "issues?state=open&per_page=100", token)
    if isinstance(existing, list):
        for issue in existing:
            if issue.get("title") == title:
                print(f"  ℹ️ 已有相同 Issue（#{issue.get('number')}），不重复创建")
                return

    # 构造正文
    lines = [f"**{report['date']} 巡检发现 {len(failures)} 个数据源异常**\n"]
    for f in failures:
        lines.append(f"- **{f['name']}**: HTTP {f['code']}（预期 {f['expect']}）· {f['note']}")
        lines.append(f"  - URL: `{f['url']}`")
    lines.append(f"\n巡检时间: {report['checked_at']}")
    lines.append(f"\n查看完整报告: `latest/source-health.json`")
    body = "\n".join(lines)

    result = gh_api("POST", "issues", token, {
        "title": title,
        "body": body,
    })

    if isinstance(result, dict) and result.get("number"):
        print(f"  📬 已创建 Issue #{result['number']} 通知异常")
    else:
        print(f"  ⚠️ Issue 创建失败: {result}")


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

    # 发现异常时主动创建 Issue 通知（跨时间主动性的外部触发）
    failures = [r for r in results if r["status"] != "✅ 正常"]
    if failures:
        print(f"\n📬 发现 {len(failures)} 个异常，创建 Issue 通知...")
        create_health_issue(failures, report)
    else:
        print("  全部正常，无需通知")


if __name__ == "__main__":
    main()
