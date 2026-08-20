#!/usr/bin/env python3
"""智能问答工具 - 整合知识库检索 + 专项查询 + 联网补充
用法: intelligent-query <问题> [--mode normal|health|hot]
"""
import sys
import subprocess
import json
from pathlib import Path

KB_DIR = Path("/workspace/knowledge-base/sources")


def kb_search(query: str) -> list:
    """调用kb-search"""
    try:
        result = subprocess.run(
            ["kb-search", query, "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return []


def health_search(query: str) -> str:
    """调用health-sex"""
    try:
        result = subprocess.run(
            ["health-sex", query],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except:
        return ""


def search_web(query: str) -> str:
    """联网搜索补充"""
    try:
        from agent.search import search as do_search
        results = do_search(query, num_results=3)
        return results
    except:
        return ""


def analyze_intent(question: str) -> dict:
    """分析意图"""
    keywords = {
        "health": ["避孕", "安全套", "STI", "性病", "HIV", "HPV", "PrEP", "PEP", "两性", "性健康"],
        "weather": ["天气", "中暑", "防晒", "防暑", "降温"],
        "hot": ["热搜", "热榜", "热点", "今天聊什么"],
    }
    
    intent = {"type": "general", "keywords": []}
    for k, vs in keywords.items():
        for v in vs:
            if v in question:
                intent["type"] = k
                intent["keywords"].append(v)
                break
    
    return intent


def answer(question: str, mode: str = None) -> dict:
    """智能问答主流程"""
    # 意图分析
    if mode:
        intent = {"type": mode}
    else:
        intent = analyze_intent(question)
    
    results = {
        "question": question,
        "intent": intent,
        "kb_results": [],
        "health_results": "",
        "web_results": "",
        "summary": ""
    }
    
    # 1. 知识库检索
    if intent["type"] in ["health", "general"]:
        kb_results = kb_search(question)
        results["kb_results"] = kb_results
    
    # 2. 两性健康专项
    if intent["type"] == "health":
        health_text = health_search(question)
        results["health_results"] = health_text
    
    # 3. 联网补充（可选）
    # results["web_results"] = search_web(question)
    
    # 4. 生成总结
    results["summary"] = generate_summary(results)
    
    return results


def generate_summary(results: dict) -> str:
    """生成回答总结"""
    kb = results["kb_results"]
    health = results["health_results"]
    intent = results["intent"]["type"]
    
    summary = f"**问题**: {results['question']}\n\n"
    
    if intent == "health":
        summary += "**🔍 知识库结果**:\n"
        for r in kb[:3]:
            summary += f"- {r.get('title', 'N/A')} (score: {r.get('score', 'N/A')})\n"
        
        if health:
            summary += "\n**📋 专项查询**:\n"
            summary += health[:500] + "..."
    elif intent == "general":
        summary += "**🔍 知识库匹配**:\n"
        for r in kb[:3]:
            summary += f"- {r.get('title', 'N/A')}\n"
    
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="智能问答工具")
    parser.add_argument("question", help="用户问题")
    parser.add_argument("--mode", choices=["normal", "health", "hot"], default=None, help="强制模式")
    parser.add_argument("--json", action="store_true", help="输出JSON")
    
    args = parser.parse_args()
    
    # 执行问答
    results = answer(args.question, args.mode)
    
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(results["summary"])


if __name__ == "__main__":
    main()
