#!/usr/bin/env python3
"""两性健康知识快速查询 - 轻量级版本
用法: health-sex <关键词> 或 health-sex list
特点: 零外部依赖，SQLite FTS5检索
"""
import sys
import subprocess
import json
from pathlib import Path

KB_DIR = Path("/workspace/knowledge-base/sources")


def kb_search(keyword: str) -> list:
    """调用kb-search工具"""
    try:
        result = subprocess.run(
            ["kb-search", keyword, "--json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except:
        pass
    return []


def list_topics():
    """列出可用主题"""
    print("📚 两性健康查询:\n")
    print("  • STI/性病: 梅毒、淋病、衣原体、HPV、疱疹、HIV")
    print("  • 避孕: 避孕方法、安全套、避孕药、IUD、植入")
    print("  • 症状: 生殖器溃疡、分泌物、排尿疼痛")
    print("  • 就医: 何时检查、检测建议")
    print("  • 疫苗: HPV疫苗、乙肝疫苗")
    print("\n💡 用法: health-sex <关键词>")


def query(keyword: str) -> str:
    """搜索知识库"""
    results = kb_search(keyword)
    
    if not results:
        # 兜底：直接读文件
        for md_file in KB_DIR.glob("*.md"):
            if "性" in md_file.name or "health" in md_file.name.lower():
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                if keyword.lower() in content.lower():
                    # 提取相关段落
                    lines = content.split("\n")
                    output_lines = []
                    for i, line in enumerate(lines):
                        if keyword.lower() in line.lower():
                            start = max(0, i - 3)
                            end = min(len(lines), i + 10)
                            output_lines.extend(lines[start:end])
                            output_lines.append("---")
                    
                    if output_lines:
                        return "\n".join(output_lines)[:2000]
        
        return f"❌ 未找到「{keyword}」相关内容\n\n建议尝试: STI、避孕、症状、就医、疫苗"
    
    # 格式化输出
    output = []
    for r in results:
        output.append(f"**{r['title']}**")
        if "snippet" in r and r["snippet"]:
            snippet = r["snippet"].replace("\n", " ").strip()
            if snippet:
                output.append(snippet[:150] + "...")
        output.append("")
    
    return "\n".join(output)


def main():
    if len(sys.argv) < 2:
        list_topics()
        return
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        list_topics()
        return
    
    # 搜索
    print(f"🔍 搜索「{cmd}」...\n")
    result = query(cmd)
    print(result)


if __name__ == "__main__":
    main()
