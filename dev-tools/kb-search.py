#!/usr/bin/env python3
"""轻量级知识库搜索 - SQLite FTS5
用法: kb-search <关键词> [--json] [--limit N] [--rebuild]
特点: 零外部依赖，纯Python内置库
"""
import os
import sys
import json
import sqlite3
import difflib
from pathlib import Path
from datetime import datetime

KB_DIR = Path("/workspace/knowledge-base/sources")
DB_PATH = "/tmp/kb-search.db"


def build_index():
    """构建FTS5索引"""
    # 删除旧数据库
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建FTS5表
    cursor.execute("""
        CREATE VIRTUAL TABLE kb_fts USING fts5(
            title,
            content,
            path,
            updated_at,
            tokenize='unicode61'
        )
    """)
    
    # 扫描所有md文件
    count = 0
    for md_file in KB_DIR.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            
            # 提取标题
            title = ""
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            if not title:
                title = md_file.stem
            
            # 提取内容（前3000字符）
            text_content = "\n".join(lines[:60])[:3000]
            
            # 插入
            cursor.execute("""
                INSERT INTO kb_fts (title, content, path, updated_at)
                VALUES (?, ?, ?, ?)
            """, (title, text_content, str(md_file), str(datetime.now())))
            
            count += 1
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    return count


def search(query: str, limit: int = 10) -> list:
    """搜索知识库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    results = []
    
    # FTS5搜索
    try:
        cursor.execute("""
            SELECT title, snippet(kb_fts, 1, '[', ']', '...', 15) as snippet
            FROM kb_fts
            WHERE kb_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))
        
        for row in cursor.fetchall():
            results.append({
                "type": "fts5",
                "title": row[0],
                "snippet": row[1]
            })
    except:
        pass
    
    # FTS5没结果时，用简单匹配兜底
    if not results:
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
    
    # 重建索引
    if args.rebuild:
        count = build_index()
        print(f"✅ 索引已重建，共 {count} 个文件")
        return 0
    
    # 检查索引
    if not os.path.exists(DB_PATH):
        build_index()
    
    # 搜索
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
                print(f"   {r['snippet'][:80]}...")
            print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
