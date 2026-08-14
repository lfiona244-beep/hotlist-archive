#!/usr/bin/env python3
"""
hotlist-archive 数据清洗脚本
在 archive.py 之后运行，负责：
  1. 跨平台去重合并（同一话题出现在多个平台）
  2. 内容分类打标（娱乐/科技/社会/体育/生活/财经/游戏/动漫）
  3. 剔除低质量噪音
  4. 生成「今日概要」精简版
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))

# ── 分类关键词 ──
CATEGORIES = {
    "娱乐": ["明星", "演员", "歌手", "综艺", "电影", "电视剧", "票房", "演唱会", "音乐", "舞台",
              "出道", "绯闻", "恋情", "婚", "离婚", "塌房", "翻车", "人设", "粉丝", "饭圈",
              "选秀", "男团", "女团", "爱豆", "偶像", "综艺", "真人秀", "脱口秀", "喜剧"],
    "科技": ["手机", "华为", "小米", "苹果", "iPhone", "AI", "人工智能", "芯片", "大模型",
              "自动驾驶", "机器人", "5G", "6G", "软件", "应用", "App", "系统", "更新",
              "发布", "新品", "发布会", "算法", "数据", "云", "数字化"],
    "社会": ["警方", "通报", "调查", "回应", "官方", "政府", "政策", "立法", "法规",
              "民生", "教育", "医疗", "社保", "养老", "房价", "物价", "交通",
              "事故", "火灾", "救援", "失踪", "落网", "破获", "案件"],
    "体育": ["NBA", "CBA", "中超", "欧冠", "奥运", "世界杯", "冠军", "比赛", "决赛",
              "球员", "教练", "转会", "进球", "得分", "金牌", "奖牌", "田径", "游泳",
              "篮球", "足球", "乒乓球", "羽毛球", "网球", "电竞", "LOL", "KPL"],
    "财经": ["股市", "基金", "理财", "投资", "保险", "银行", "利率", "汇率", "黄金",
              "油价", "股价", "涨停", "跌停", "GDP", "CPI", "经济", "贸易", "关税",
              "上市", "融资", "财报", "营收", "利润", "亏损"],
    "生活": ["健康", "养生", "减肥", "健身", "美食", "旅游", "穿搭", "美妆", "护肤",
              "育儿", "宠物", "家居", "装修", "汽车", "驾照", "油价", "天气",
              "放假", "假期", "调休", "节日", "春节", "国庆"],
    "游戏": ["游戏", "手游", "端游", "PS5", "Switch", "Steam", "原神", "王者荣耀",
              "和平精英", "英雄联盟", "LOL", "吃鸡", "氪金", "抽卡", "皮肤", "版本",
              "更新", "上线", "公测", "内测"],
    "动漫": ["动漫", "动画", "漫画", "番剧", "二次元", "B站", "番剧", "新番",
              "剧场版", "漫改", "Cos", "cosplay", "声优", "周边", "手办", "谷子"],
}

# ── 噪音过滤器 ──
NOISE_KEYWORDS = [
    "广告", "推广", "点击", "链接", "扫码", "关注", "点赞", "转发",
    "抽奖", "福利", "免费", "优惠", "折扣", "限时", "抢购",
]

NOISE_PATTERNS = [
    r'^#.*#$',           # 纯话题标签
    r'^[0-9]{4,}$',       # 纯数字
    r'^[a-zA-Z\s]{10,}$', # 纯英文长文本
    r'【.*?】$',           # 纯【】标题
]

def classify(title):
    """给标题打分类标签"""
    scores = {}
    for cat, kws in CATEGORIES.items():
        score = sum(1 for kw in kws if kw in title)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "其他"

def is_noise(title):
    """判断是否低质量噪音"""
    if not title or len(title) < 3:
        return True
    if len(title) > 50:
        # 特别长的标题很可能是新闻标题堆砌
        pass
    for kw in NOISE_KEYWORDS:
        if kw in title:
            return True
    for pat in NOISE_PATTERNS:
        if re.match(pat, title):
            return True
    return False

def clean_title(title):
    """清洗标题：去emoji、去特殊符号、去多余空格"""
    # 去emoji
    title = re.sub(r'[\U00010000-\U0010ffff]', '', title)
    # 去特殊符号
    title = re.sub(r'[#*\[\]【】《》「」『』]', '', title)
    # 去多余空格
    title = re.sub(r'\s+', ' ', title).strip()
    return title[:60] if len(title) > 60 else title

def deduplicate(items):
    """跨平台去重合并：同一话题合并，标注来源平台"""
    merged = {}
    for item in items:
        title = item.get("title", item) if isinstance(item, str) else item.get("title", "")
        if not title:
            continue
        platform = item.get("platform", "未知")
        key = title[:20]  # 用前20字做去重key
        if key in merged:
            merged[key]["platforms"].append(platform)
            merged[key]["count"] += 1
        else:
            merged[key] = {
                "title": title,
                "platforms": [platform],
                "count": 1,
                "category": classify(title),
                "hot": item.get("hot", 0) or item.get("hot_value", 0) or item.get("play", 0) or 0,
            }
    return merged

def main():
    now = datetime.now(TZ)
    dir_path = f"data/{now.year}/{now.month:02d}/{now.day:02d}"
    if not os.path.exists(dir_path):
        print(f"❌ 今日数据目录不存在: {dir_path}")
        # 尝试昨天
        yesterday = now - timedelta(days=1)
        dir_path = f"data/{yesterday.year}/{yesterday.month:02d}/{yesterday.day:02d}"
        if not os.path.exists(dir_path):
            print("❌ 没有可用数据")
            return
        print(f"📂 使用昨日数据: {dir_path}")

    print(f"🧹 清洗数据: {dir_path}")

    # 1. 读取热榜数据
    hot_path = f"{dir_path}/hotlist.json"
    all_items = []
    if os.path.exists(hot_path):
        with open(hot_path, encoding="utf-8") as f:
            hot = json.load(f)
        for pname, pdata in hot.get("platforms", {}).items():
            if not pdata:
                continue
            for item in pdata.get("data", []):
                title = item.get("title", "")
                if title and not is_noise(title):
                    t = clean_title(title)
                    all_items.append({
                        "title": t,
                        "platform": pname,
                        "hot": item.get("hot_value", item.get("hot", 0))
                    })
        print(f"  📥 原始热榜: {len(all_items)} 条")

    # 2. 去重合并
    merged = deduplicate(all_items)
    deduped = sorted(merged.values(), key=lambda x: x["count"], reverse=True)
    print(f"  🔄 去重合并后: {len(deduped)} 条")

    # 3. 分类统计
    cat_stats = {}
    for item in deduped:
        c = item["category"]
        cat_stats[c] = cat_stats.get(c, 0) + 1
    print(f"  📊 分类分布: {cat_stats}")

    # 4. 生成今日概要
    hotspot = [item for item in deduped if item["count"] >= 2]  # 多平台共同热点
    # 按热度排序
    all_sorted = sorted(deduped, key=lambda x: x["hot"], reverse=True)[:30]

    summary = {
        "date": hot.get("date", now.strftime("%Y-%m-%d")),
        "generated_at": now.isoformat(),
        "total_raw": len(all_items),
        "total_cleaned": len(deduped),
        "category_stats": cat_stats,
        "hotspot": [{
            "title": item["title"],
            "platforms": item["platforms"],
            "category": item["category"],
        } for item in hotspot[:10]],
        "top_trending": [{
            "title": item["title"],
            "platforms": item["platforms"],
            "category": item["category"],
        } for item in all_sorted[:15]],
    }

    # 5. 读取新闻和B站、知乎日报补充
    news_path = f"{dir_path}/news.json"
    if os.path.exists(news_path):
        with open(news_path, encoding="utf-8") as f:
            news = json.load(f)
        nd = news.get("data", {})
        news_list = nd.get("news", []) if isinstance(nd, dict) else []
        summary["news"] = [n.get("title", n) if isinstance(n, dict) else n for n in news_list[:8]]
        summary["news_tip"] = nd.get("tip", "") if isinstance(nd, dict) else ""

    bili_path = f"{dir_path}/bilibili.json"
    if os.path.exists(bili_path):
        with open(bili_path, encoding="utf-8") as f:
            bili = json.load(f)
        summary["bilibili"] = [{
            "title": v.get("title", ""),
            "author": v.get("author", ""),
            "play": v.get("play", 0),
        } for v in bili[:8]]

    zhihu_path = f"{dir_path}/zhihu_daily.json"
    if os.path.exists(zhihu_path):
        with open(zhihu_path, encoding="utf-8") as f:
            zhihu = json.load(f)
        summary["zhihu_daily"] = [{
            "title": z.get("title", ""),
        } for z in zhihu[:5]]

    # 6. 写入
    clean_path = f"{dir_path}/clean.json"
    with open(clean_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  💾 {clean_path}")

    # 7. 同时写入latest
    os.makedirs("latest", exist_ok=True)
    with open("latest/clean.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  💾 latest/clean.json")

    print(f"✅ 清洗完成 · {len(deduped)} 条有效数据 · {len(hotspot)} 个跨平台热点")


if __name__ == "__main__":
    main()