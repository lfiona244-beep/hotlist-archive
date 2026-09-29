#!/usr/bin/env python3
"""
free_sources.py — 免费公开数据源统一取数（2026-09-30 建）

背景：60s.viki.moe 全线失效（09-29 起 429/400/403），热榜/新闻/油价/历史四段
永久空。排查时发现知识库 `sources/数据源/平台热榜接口大全.md` 里早就存着官方
直连接口（抖音/头条/百度实测全通）——**存了没用上**，代码却绑死在 60s 上。

本模块把「官方直连、无需 key」的取数集中一处，本地 brief.py 与本仓库 archive.py
共用同一套逻辑，避免两处各写一遍又漂移（单一来源原则）。

数据源（2026-09-30 实测可用）：
  - 抖音热搜  aweme-lq.snssdk.com（零请求头）
  - 头条热榜  toutiao.com（需浏览器 UA）
  - 百度热搜  top.baidu.com（HTML 内嵌 s-data 注释里的 JSON）
  - 历史上的今天  baike.baidu.com（CMS 静态 JSON，按月一个文件）
  - 油价  qiyoujiage.com（HTML 表格，按省份）
  - 新闻  知乎日报 news-at.zhihu.com（无 key JSON）

⚠️ 每个取数函数失败返回 None/[]，不抛异常——上游可能随时失效，
   调用方自行降级（数据源失效是常态，不该整份简报崩）。
"""
import json
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}


def _get(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _get_json(url, headers=None, timeout=10):
    return json.loads(_get(url, headers, timeout))


def _to_int(v):
    """热度值统一成 int。各源有的给数字有的给字符串，clean.py 按数字排序会崩。"""
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


# ── 热榜（三个官方直连源）────────────────────────────────────────

def hot_douyin(limit=10):
    """抖音热搜。零请求头，最稳。"""
    try:
        d = _get_json("https://aweme-lq.snssdk.com/aweme/v1/hot/search/list/"
                      "?aid=1128&version_code=880")
        words = (d.get("data") or {}).get("word_list") or []
        return [{"title": w.get("word", ""), "hot": _to_int(w.get("hot_value"))} for w in words[:limit]]
    except Exception:
        return []


def hot_toutiao(limit=10):
    """头条热榜。需浏览器 UA。"""
    try:
        d = _get_json("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc")
        return [{"title": x.get("Title", ""), "hot": _to_int(x.get("HotValue"))}
                for x in (d.get("data") or [])[:limit]]
    except Exception:
        return []


def hot_baidu(limit=10):
    """百度热搜。榜单 JSON 嵌在 HTML 的 <!--s-data:...--> 注释里。"""
    try:
        h = _get("https://top.baidu.com/board?tab=realtime")
        m = re.search(r"s-data:(\{.*?\})-->", h, re.S)
        if not m:
            return []
        # ⚠️ cards 在顶层，不在 data 下；榜单又是两层嵌套：
        #    cards[0]["content"][0]["content"] 才是条目列表（2026-09-30 实测）。
        cards = json.loads(m.group(1)).get("cards", [])
        content = []
        if cards:
            inner = cards[0].get("content") or []
            content = (inner[0].get("content") if inner and isinstance(inner[0], dict)
                       else inner) or []
        return [{"title": c.get("word") or c.get("query", ""), "hot": _to_int(c.get("hotScore"))}
                for c in content[:limit]]
    except Exception:
        return []


# ── 历史上的今天（百度百科 CMS 静态 JSON）─────────────────────────

def today_in_history(month=None, day=None, limit=3):
    """历史上的今天。百度百科按月提供静态文件 09.json，键为 MM/DD。
    返回 [{year, title}]；标题里的 HTML 标签剥掉。"""
    from datetime import datetime
    now = datetime.now()
    month = month or now.month
    day = day or now.day
    try:
        d = _get_json(f"https://baike.baidu.com/cms/home/eventsOnHistory/{month:02d}.json")
        items = (d.get(f"{month:02d}") or {}).get(f"{month:02d}{day:02d}") or []
        out = []
        for e in items[:limit]:
            title = re.sub(r"<[^>]+>", "", e.get("title", "") or "")
            out.append({"year": e.get("year", ""), "title": title})
        return out
    except Exception:
        return []


# ── 油价（按省份，HTML 表格）──────────────────────────────────────

_PROVINCE_SLUG = {"广东": "guangdong", "北京": "beijing", "上海": "shanghai",
                  "湖北": "hubei", "深圳": "guangdong", "佛山": "guangdong"}


def fuel_price(province="广东", limit=4):
    """今日油价。qiyoujiage.com 按省份页面，<dt>品名</dt><dd>价格</dd>。
    返回 [{name, price}]；失败返回 []。"""
    slug = _PROVINCE_SLUG.get(province, "guangdong")
    try:
        h = _get(f"http://www.qiyoujiage.com/{slug}.shtml")
        pairs = re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", h, re.S)
        out = []
        for name, price in pairs[:limit]:
            name = re.sub(r"<[^>]+>", "", name).strip()
            price = re.sub(r"<[^>]+>", "", price).strip()
            if name and price:
                out.append({"name": name, "price": price})
        return out
    except Exception:
        return []


# ── 新闻（知乎日报，无 key JSON）─────────────────────────────────

def news_zhihu_daily(limit=8):
    """知乎日报最新。无 key JSON，字段 stories[].title。
    ⚠️ 这是「话题式」新闻不是「快讯式」，跟原 60s 每日 8 条的形态不同——
    当每日资讯摘要用，别当突发快讯。"""
    try:
        d = _get_json("https://news-at.zhihu.com/api/4/news/latest")
        return [{"title": s.get("title", ""), "url": s.get("url", "")}
                for s in (d.get("stories") or [])[:limit]]
    except Exception:
        return []


if __name__ == "__main__":
    print("抖音:", [x["title"] for x in hot_douyin(3)])
    print("头条:", [x["title"] for x in hot_toutiao(3)])
    print("百度:", [x["title"] for x in hot_baidu(3)])
    print("历史:", today_in_history())
    print("油价:", fuel_price())
    print("新闻:", [x["title"] for x in news_zhihu_daily(3)])
