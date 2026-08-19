#!/usr/bin/env python3
"""定期推送GitHub备份（每日最多一次）
用法: github-push-daily
逻辑: 检查last-push时间戳，如果超过24小时就执行git push
"""
import os
import json
import subprocess
import sys
from datetime import datetime, timedelta

STATE_FILE = "/workspace/state/last-github-push.json"
REMOTE_TIMEOUT = 120  # 秒


def read_state():
    """读取最后推送时间"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"last_push": None}


def write_state(ts):
    """写入推送时间戳"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"last_push": ts}, f)


def git_push():
    """执行git push"""
    print("🐙 推送到 GitHub...")
    for branch in ["main", "master"]:
        try:
            result = subprocess.run(
                ["timeout", str(REMOTE_TIMEOUT), "git", "push", "origin", branch],
                capture_output=True,
                text=True,
                timeout=REMOTE_TIMEOUT + 5,
            )
            if result.returncode == 0:
                print(f"✅ GitHub 已同步 (branch: {branch})")
                return True
        except:
            pass
    print("⚠️  GitHub 推送失败（网络或凭据问题）")
    return False


def main():
    # 检查是否需要推送（距离上次推送超过24小时）
    state = read_state()
    last_push = state.get("last_push")
    
    if last_push:
        last_dt = datetime.fromisoformat(last_push)
        now = datetime.now()
        hours_since = (now - last_dt).total_seconds() / 3600
        
        if hours_since < 24:
            print(f"ℹ️  距离上次推送 {hours_since:.1f} 小时，跳过")
            return 0
    
    # 执行推送
    if git_push():
        write_state(datetime.now().isoformat())
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
