#!/usr/bin/env python3
"""轻量级知识库搜索 - FAISS向量检索 + FTS5全文检索
用法: kb-search <关键词> [--json] [--limit N] [--rebuild]
特点: FAISS已安装，支持向量相似度搜索
"""
import os
import sys
import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime
from collections import Counter
import numpy as np

KB_DIR = Path("/workspace/knowledge-base/sources")
DB_PATH = "/tmp/kb-search.db"
INDEX_PATH = "/tmp/kb-faiss.index"

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

# 全局词频统计
global_doc_freq = Counter()


def build_vocabulary(docs_texts: list) -> dict:
    """构建词表"""
    vocab = {}
    doc_freq = Counter()
    
    for text in docs_texts:
        bigrams = [text[i:i+2] for i in range(len(text)-1)]
        unique_bigrams = set(bigrams)
        for bg in unique_bigrams:
            doc_freq[bg] += 1
    
    # 只保留出现在至少2个文档中的词
    for bg, df in doc_freq.items():
        if df >= 2 and bg not in vocab:
            vocab[bg] = len(vocab)
    
    return vocab, doc_freq


def tfidf_vector(text: str, vocab: dict, doc_freq: Counter, doc_count: int) -> np.ndarray:
    """计算TF-IDF向量"""
    bigrams = [text[i:i+2] for i in range(len(text)-1)]
    freq = Counter(bigrams)
    
    max_dim = min(500, len(vocab))
    vec = np.zeros(max_dim, dtype=np.float32)
    
    for i, bg in enumerate(vocab.keys()):
        if i >= max_dim:
            break
        tf = freq.get(bg, 0) / max(len(bigrams), 1)
        df = doc_freq.get(bg, 1)
        idf = np.log((doc_count + 1) / (df + 1)) + 1
        vec[i] = tf * idf
    
    # L2归一化
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    
    return vec


def build_index():
    """构建FTS5索引 + FAISS向量索引"""
    global global_doc_freq
    
    # 清理旧文件
    for f in [DB_PATH, INDEX_PATH]:
        if os.path.exists(f):
            os.remove(f)
    
    # 1. 构建FTS5
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE VIRTUAL TABLE kb_fts USING fts5(
            title, content, path, updated_at
        )
    """)
    
    # 2. 收集所有文档
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
            
            cursor.execute(
                "INSERT INTO kb_fts (title, content, path, updated_at) VALUES (?, ?, ?, ?)",
                (title, extended, str(md_file), str(datetime.now()))
            )
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    
    # 3. 构建FAISS索引
    try:
        import faiss
        
        # 构建词表
        all_texts = [d["extended"] for d in docs]
        vocab, doc_freq = build_vocabulary(all_texts)
        global_doc_freq = doc_freq
        
        # 编码所有文档
        vectors = []
        for d in docs:
            vec = tfidf_vector(d["extended"], vocab, doc_freq, len(docs))
            vectors.append(vec)
        
        if vectors and vocab:
            matrix = np.array(vectors, dtype=np.float32)
            dimension = matrix.shape[1]
            
            # 构建FAISS索引
            index = faiss.IndexFlatIP(dimension)
            index.add(matrix)
            
            # 保存索引
            faiss.write_index(index, INDEX_PATH)
            
            # 保存元数据
            meta = {
                "vocab_size": len(vocab),
                "doc_count": len(docs),
                "dimension": dimension
            }
            with open("/tmp/kb-search-meta.json", "w") as f:
                json.dump(meta, f)
            
            print(f"✅ FAISS索引已构建: {len(docs)}文档, {dimension}维")
        else:
            print("⚠️  没有文档可索引")
            
    except ImportError:
        print("⚠️  FAISS未安装，仅使用FTS5")
    
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
    if not results and os.path.exists(INDEX_PATH):
        try:
            import faiss
            
            index = faiss.read_index(INDEX_PATH)
            
            with open("/tmp/kb-search-meta.json") as f:
                meta = json.load(f)
            
            # 重建词表（用相同逻辑）
            all_texts = []
            for md_file in KB_DIR.glob("*.md"):
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                all_texts.append(content[:3000])
            
            vocab, doc_freq = build_vocabulary(all_texts)
            query_vec = tfidf_vector(query, vocab, doc_freq, len(all_texts)).reshape(1, -1)
            
            scores, indices = index.search(query_vec, limit)
            
            doc_files = sorted(KB_DIR.glob("*.md"))
            for score, idx in zip(scores[0], indices[0]):
                if score > 0.01 and idx < len(doc_files):
                    results.append({
                        "type": "faiss",
                        "title": doc_files[idx].stem,
                        "score": float(score)
                    })
        except:
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
                print(f"   {r['snippet'][:80]}...")
            print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
