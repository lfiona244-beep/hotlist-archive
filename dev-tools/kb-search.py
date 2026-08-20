#!/usr/bin/env python3
"""知识库搜索 - FAISS向量检索 + FTS5全文检索
用法: kb-search <关键词> [--json] [--limit N] [--rebuild]
特点: fastembed语义检索 + FTS5兜底，零后台进程
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
INDEX_PATH = "/tmp/kb-faiss.index"
EMBEDDING_CACHE = "/tmp/kb-embeddings.json"

# 同义词映射
SYNONYMS = {
    "STI": ["性病", "性传播感染", "STD"],
    "STD": ["性病", "性传播疾病"],
    "HIV": ["艾滋病", "爱滋病"],
    "HPV": ["人乳头瘤病毒", "宫颈癌病毒"],
    "梅毒": ["syphilis", "硬下疳"],
    "淋病": ["gonorrhea", "淋球菌"],
    "衣原体": ["chlamydia", "沙眼衣原体"],
    "疱疹": ["herpes", "HSV", "生殖器疱疹"],
    "避孕": ["contraception", "节育", "避孕方法"],
    "安全套": ["condom", "避孕套", "套套"],
    "PrEP": ["暴露前预防", "事前预防"],
    "PEP": ["暴露后预防", "事后预防"],
}


def load_embedding_model():
    """延迟加载fastembed模型"""
    try:
        from fastembed import TextEmbedding
        model = TextEmbedding(model_name="BAAI/bge-small-zh-v1.5")
        return model
    except Exception as e:
        print(f"⚠️  fastembed加载失败: {e}", file=sys.stderr)
        return None


def build_embeddings(model, texts):
    """批量生成向量"""
    if model is None:
        return []
    embeddings = list(model.embed(texts))
    return [list(e) for e in embeddings]


def build_index():
    """构建FTS5索引 + FAISS向量索引 + embedding缓存"""
    global _model
    
    # 清理旧文件
    for f in [DB_PATH, INDEX_PATH, EMBEDDING_CACHE]:
        if os.path.exists(f):
            os.remove(f)
    
    # 1. 收集文档
    docs = []
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
            
            # 同义词扩展
            extended = text_content
            for kw, syns in SYNONYMS.items():
                if kw in text_content:
                    extended += " " + " ".join(syns)
            
            docs.append({
                "title": title,
                "content": text_content,
                "extended": extended,
                "path": str(md_file)
            })
        except:
            pass
    
    # 2. 构建FTS5
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE VIRTUAL TABLE kb_fts USING fts5(
            title, content, path, updated_at
        )
    """)
    
    for d in docs:
        cursor.execute(
            "INSERT INTO kb_fts (title, content, path, updated_at) VALUES (?, ?, ?, ?)",
            (d["title"], d["extended"], d["path"], str(datetime.now()))
        )
    conn.commit()
    conn.close()
    
    # 3. 构建FAISS索引
    try:
        import faiss
        import numpy as np
        from fastembed import TextEmbedding
        
        # 加载模型
        model = TextEmbedding(model_name="BAAI/bge-small-zh-v1.5")
        
        # 生成所有文档的向量
        print("生成嵌入向量...")
        docs_texts = [d["extended"] for d in docs]
        embeddings = list(model.embed(docs_texts))
        
        if embeddings:
            # 转换为numpy数组
            matrix = np.array(embeddings, dtype=np.float32)
            dimension = matrix.shape[1]
            
            # 构建FAISS索引
            index = faiss.IndexFlatIP(dimension)
            index.add(matrix)
            
            # 保存索引
            faiss.write_index(index, INDEX_PATH)
            
            # 保存元数据
            meta = {
                "doc_count": len(docs),
                "dimension": dimension,
                "doc_paths": [d["path"] for d in docs],
                "doc_titles": [d["title"] for d in docs]
            }
            with open("/tmp/kb-search-meta.json", "w") as f:
                json.dump(meta, f)
            
            # 保存嵌入向量（避免重复计算）
            embeddings_list = [e.tolist() for e in embeddings]
            with open(EMBEDDING_CACHE, "w") as f:
                json.dump({"embeddings": embeddings_list, "updated": str(datetime.now())}, f)
            
            print(f"✅ FAISS索引已构建: {len(docs)}文档, {dimension}维")
        else:
            print("⚠️  没有文档可索引")
            
    except Exception as e:
        print(f"⚠️  FAISS构建失败: {e}")
    
    return len(docs)


def expand_query(query: str) -> str:
    """扩展查询词"""
    parts = []
    for word in re.findall(r'[\w\u4e00-\u9fff]+', query):
        parts.append(word)
        if word in SYNONYMS:
            parts.extend(SYNONYMS[word])
    return " OR ".join(parts)


def search(query: str, limit: int = 10) -> list:
    """搜索知识库"""
    results = []
    
    # 1. FTS5搜索
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        expanded = expand_query(query)
        
        cursor.execute("""
            SELECT title, snippet(kb_fts, 1, '[', ']', '...', 15)
            FROM kb_fts
            WHERE kb_fts MATCH ?
            LIMIT ?
        """, (expanded, limit))
        
        for row in cursor.fetchall():
            results.append({
                "type": "fts5",
                "title": row[0],
                "snippet": row[1]
            })
        conn.close()
    except:
        pass
    
    # 2. FAISS向量搜索（兜底）
    if not results:
        try:
            import faiss
            import numpy as np
            
            if os.path.exists(EMBEDDING_CACHE):
                # 使用缓存的向量
                with open(EMBEDDING_CACHE) as f:
                    cache = json.load(f)
                
                # 编码查询
                from fastembed import TextEmbedding
                model = TextEmbedding(model_name="BAAI/bge-small-zh-v1.5")
                query_vec = list(model.embed([query]))[0]
                query_vec = [float(x) for x in query_vec]
                
                # 加载索引
                index = faiss.read_index(INDEX_PATH)
                meta = json.load(open("/tmp/kb-search-meta.json"))
                
                # 搜索
                scores, indices = index.search(np.array([query_vec]), limit)
                
                for score, idx in zip(scores[0], indices[0]):
                    if score > 0.1 and idx < len(meta["doc_paths"]):
                        results.append({
                            "type": "faiss",
                            "title": meta["doc_titles"][idx],
                            "score": float(score)
                        })
        except Exception as e:
            pass
    
    # 3. 简单匹配兜底
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
                        "score": round(ratio, 3)
                    })
            except:
                pass
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="知识库搜索")
    parser.add_argument("query", nargs="?", help="搜索关键词")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--limit", type=int, default=10, help="返回结果数")
    parser.add_argument("--rebuild", action="store_true", help="重建索引")
    
    args = parser.parse_args()
    
    if args.rebuild:
        count = build_index()
        print(f"✅ 索引已重建，共 {count} 个文件")
        return 0
    
    if not args.query:
        print("❌ 请提供搜索关键词")
        return 1
    
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
                print(f"   {r['snippet'][:80]}...")
            elif "score" in r:
                print(f"   相似度: {r['score']:.3f}")
            print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
