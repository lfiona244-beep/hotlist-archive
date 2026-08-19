#!/usr/bin/env python3
"""轻量级知识库搜索 - SQLite FTS5 + 同义词扩展
用法: kb-search <关键词> [--json] [--limit N] [--rebuild]
特点: 零外部依赖，秒级响应
"""
import os
import sys
import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime

KB_DIR = Path("/workspace/knowledge-base/sources")
DB_PATH = "/tmp/kb-search.db"

# 同义词映射（用于扩展搜索）
SYNONYMS = {
    "STI": ["性病", "性传播感染", "STD"],
    "STD": ["性病", "性传播疾病"],
    "HIV": ["艾滋病", "爱滋病"],
    "HPV": ["人乳头瘤病毒", "宫颈癌病毒"],
    "梅毒": ["syphilis", "硬下疳"],
    "淋病": ["gonorrhea", "淋球菌"],
    "衣原体": ["chlamydia", "沙眼衣原体"],
    "疱疹": ["herpes", "HSV", "生殖器疱疹"],
    "避孕": ["contraception", "避孕", "节育", "避孕方法"],
    "安全套": ["condom", "避孕套", "套套"],
    "PrEP": ["暴露前预防", "事前预防"],
    "PEP": ["暴露后预防", "事后预防"],
}

# 关键词权重（标题匹配权重更高）
TITLE_WEIGHT = 2.0


def build_index():
    """构建FTS5索引"""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE VIRTUAL TABLE kb_fts USING fts5(
            title,
            content,
            path,
            updated_at,
            tokenize='unicode61'
        )
    """)
    
    count = 0
    for md_file in KB_DIR.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            
            title = ""
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            if not title:
                title = md_file.stem
            
            text_content = "\n".join(lines[:80])[:5000]
            
            # 构建同义词扩展内容
            extended_content = text_content
            for kw, syns in SYNONYMS.items():
                if kw in text_content:
                    extended_content += " " + " ".join(syns)
            
            cursor.execute("""
                INSERT INTO kb_fts (title, content, path, updated_at)
                VALUES (?, ?, ?, ?)
            """, (title, extended_content, str(md_file), str(datetime.now())))
            
            count += 1
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    return count


def expand_query(query: str) -> str:
    """扩展查询词（添加同义词）"""
    parts = []
    for word in re.findall(r'[\w\u4e00-\u9fff]+', query):
        parts.append(word)
        if word in SYNONYMS:
            parts.extend(SYNONYMS[word])
    return " OR ".join(parts)


def search(query: str, limit: int = 10) -> list:
    """搜索知识库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    results = []
    expanded_query = expand_query(query)
    
    # FTS5搜索
    try:
        cursor.execute("""
            SELECT title, snippet(kb_fts, 1, '[', ']', '...', 20), path
            FROM kb_fts
            WHERE kb_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (expanded_query, limit))
        
        for row in cursor.fetchall():
            results.append({
                "type": "fts5",
                "title": row[0],
                "snippet": row[1],
                "path": row[2]
            })
    except Exception as e:
        pass
    
    # 兜底：简单匹配
    if not results:
        import difflib
        for md_file in KB_DIR.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                if query.lower() in content.lower():
                    ratio = difflib.SequenceMatcher(None, query, content[:200]).ratio()
                    results.append({
                        "type": "match",
                        "title": md_file.stem,
                        "score": round(ratio, 3),
                        "path": str(md_file)
                    })
            except:
                pass
    
    conn.close()
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="知识库搜索")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--limit", type=int, default=10, help="返回结果数")
    parser.add_argument("--rebuild", action="store_true", help="重建索引")
    
    args = parser.parse_args()
    
    if args.rebuild:
        count = build_index()
        print(f"✅ 索引已重建，共 {count} 个文件")
        return 0
    
    if not os.path.exists(DB_PATH):
        build_index()
    
    results = search(args.query, args.limit)
    
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if not results:
            print("❌ 未找到相关结果")
            return 1
        
        print(f"📚 找到 {len(results)} 个结果：\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['title']}")
            if "snippet" in r and r["snippet"]:
                print(f"   {r['snippet'][:100]}...")
            print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
