#!/usr/bin/env python3
"""两性健康知识快速查询
用法:
  health-sex <关键词>     查询特定主题
  health-sex list         列出所有可用主题
  health-sex <关键词> --url  输出权威来源链接
  
示例:
  health-sex STI
  health-sex 避孕
  health-sex 症状
"""
import sys
import json
import subprocess
from pathlib import Path

KB_PATH = Path("/workspace/knowledge-base/sources/两性健康知识.md")
INDEX_PATH = Path("/workspace/knowledge-base/sources/INDEX.md")

# 快速索引（章节→关键词映射）
TOPICS = {
    "sti": ["性传播感染", "STI", "STD", "性病", "梅毒", "淋病", "衣原体", "滴虫", "HPV", "疱疹", "HIV", "乙肝"],
    "contraception": ["避孕", "避孕方法", "安全套", "避孕药", "IUD", "植入", "针剂"],
    "symptoms": ["症状", "检测", "筛查", "就医", "检查"],
    "emergency": ["紧急避孕", "事后药", "5天"],
    "vaccine": ["疫苗", "HPV疫苗", "乙肝疫苗"],
    "resources": ["资源", "网站", "WHO", "Planned Parenthood", "Mayo Clinic"]
}

def search_content(keyword: str) -> str:
    """搜索知识库内容"""
    if not KB_PATH.exists():
        return "❌ 知识库文件不存在"
    
    content = KB_PATH.read_text(encoding="utf-8")
    lines = content.split("\n")
    
    # 找到关键词所在章节
    results = []
    current_section = ""
    section_lines = []
    
    for line in lines:
        if line.startswith("## "):
            if section_lines and current_section:
                results.append((current_section, "\n".join(section_lines[-10:])))
            current_section = line[3:].strip()
            section_lines = [line]
        else:
            section_lines.append(line)
            # 检查是否包含关键词
            if keyword.lower() in line.lower():
                # 记录这个结果
                pass
    
    # 返回匹配度最高的内容
    for section, text in results:
        if keyword.lower() in section.lower() or keyword in text:
            return f"**{section}**\n{text[:800]}"
    
    # 如果没找到具体章节，返回全文摘要
    for line in lines:
        if keyword.lower() in line.lower():
            idx = lines.index(line)
            start = max(0, idx - 2)
            end = min(len(lines), idx + 10)
            return "\n".join(lines[start:end])
    
    return None

def list_topics():
    """列出所有可用主题"""
    print("📚 可用查询主题：\n")
    for key, keywords in TOPICS.items():
        print(f"  • {key}: {', '.join(keywords[:3])}...")
    print("\n💡 用法: health-sex <关键词>")

def get_urls(keyword: str) -> str:
    """获取权威来源链接"""
    urls = {
        "sti": "https://www.who.int/health-topics/sexually-transmitted-infections",
        "contraception": "https://www.plannedparenthood.org/learn/birth-control",
        "symptoms": "https://www.mayoclinic.org/diseases-conditions/sexually-transmitted-diseases/symptoms-causes/syc-20370565",
        "emergency": "https://www.plannedparenthood.org/learn/birth-control/condoms/erection-prevention-contraception",
        "vaccine": "https://www.who.int/news-room/fact-sheets/detail/human-papillomavirus-(hpv)-and-cervical-cancer",
        "resources": "https://www.plannedparenthood.org/learn"
    }
    
    for key, url in urls.items():
        if key in keyword.lower():
            return f"📖 权威来源：\n{url}"
    return None

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        list_topics()
        return
    
    if cmd == "--url" or "-u" in sys.argv:
        keyword = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else sys.argv[-1]
        url_result = get_urls(keyword)
        if url_result:
            print(url_result)
        else:
            print("未找到相关权威链接")
        return
    
    keyword = sys.argv[1]
    
    # 先搜索本地知识
    result = search_content(keyword)
    if result:
        print(result)
        return
    
    # 尝试用搜索补充
    print(f"🔍 正在搜索「{keyword}」的权威信息...\n")
    try:
        # 调用EXA搜索
        query = f"{keyword} site:who.int OR site:mayoclinic.org OR site:plannedparenthood.org"
        proc = subprocess.run(
            ["python3", "/workspace/agent/search.py", query],
            capture_output=True, text=True, timeout=10
        )
        if proc.stdout:
            print(proc.stdout[:2000])
    except:
        pass
    
    # 输出本地知识库内容
    if KB_PATH.exists():
        print("\n--- 本地知识库参考 ---")
        result = search_content(keyword)
        if result:
            print(result)
        else:
            print("本地知识库中未找到相关内容，建议访问权威机构网站查询。")

if __name__ == "__main__":
    main()
