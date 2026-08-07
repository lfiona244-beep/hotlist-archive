# hotlist-archive

全网热榜 / 新闻 / 天气 / 油价每日自动存档仓库。

- 由 GitHub Actions 每天 UTC 02:00（北京时间 10:00）定时抓取
- 数据结构：`data/YYYY/MM/DD/`
  - `hotlist.json` — 知乎/微博/抖音/头条四平台热榜
  - `news.json` — 每日新闻 60s
  - `weather.json` — 广州天气
  - `fuel.json` — 广东油价
  - `today.json` — 历史上的今天
  - `summary.json` — 当日汇总

## 查询方式

远程 AI 可通过 GitHub API 读取任意历史日期数据：
```
https://raw.githubusercontent.com/lfiona244-beep/hotlist-archive/main/data/2026/08/07/hotlist.json
```

本地 AI 通过 session-start 自动拉取最新存档到本地 memory/hotlist/
