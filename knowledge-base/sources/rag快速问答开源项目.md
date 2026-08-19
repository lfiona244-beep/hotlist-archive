# RAG 快速问答开源项目清单

> 2026-08-19 整理。GitHub 上从知识库快速找答案的开源方案。
> 分类：轻量级（纯脚本）/ 全栈系统 / 垂直领域

---

## ⭐ 推荐项目（高星/活跃）

### 1. Chat2Anything (114⭐)
- **链接**: https://github.com/allenpubgit/Chat2Anything
- **语言**: Python
- **特点**: 面向企业内部环境的LLM知识库问答系统，含后台管理
- **技术栈**: LangChain + ChatGLM/GPT
- **适用**: 企业知识库、文档问答

### 2. KnowledgeRAG-OGAS (144⭐)
- **链接**: https://github.com/Zhongye1/KnowledgeRAG-OGAS
- **语言**: Vue3 + FastAPI + Python
- **特点**: 集成文档解析、知识库管理、知识图谱生成、向量检索
- **适用**: 智能知识管理、可视化问答

### 3. grid-qa (127⭐)
- **链接**: https://github.com/zhyese/grid-qa
- **语言**: Python + Vue3
- **特点**: 电网自主运维智能问答，支持 DeepSeek/百炼/火山云
- **适用**: 垂直行业知识问答

### 4. ai-medical-assistant (109⭐)
- **链接**: https://github.com/zhttyy520/ai-medical-assistant
- **语言**: Python + React
- **特点**: 基于通义千问的医疗知识问答，支持RAG
- **适用**: 医疗健康知识库

---

## 🔧 轻量级方案（适合手机端）

### 5. Simple-Local-QA (34⭐)
- **链接**: https://github.com/yatengLG/Simple-Local-QA
- **语言**: Python
- **特点**: 最简单代码实现本地知识库问答
- **技术**: ChatGLM + embedding + 向量检索
- **适用**: 学习RAG原理、轻量部署

### 6. Knowledge-Base-LLMs-QA (30⭐)
- **链接**: https://github.com/WangRongsheng/Knowledge-Base-LLMs-QA
- **语言**: Python
- **特点**: 基于大模型的知识库问答，含WebUI
- **适用**: 快速搭建问答系统

### 7. private-knowledge-agent (8⭐)
- **链接**: https://github.com/Annyfee/private-knowledge-agent
- **语言**: Python
- **特点**: LangGraph + MCP + FastAPI，支持本地研究
- **适用**: 私有知识库、多Agent协作

---

## 📚 知识图谱增强

### 8. contextual-chunking-graphpowered-rag (49⭐)
- **链接**: https://github.com/lesteroliver911/contextual-chunking-graphpowered-rag
- **特点**: 语义向量搜索 + 知识图谱 + LLM验证
- **适用**: 需要精确答案的场景

### 9. PaperReadingRAG (6⭐)
- **链接**: https://github.com/honglanjingyu/PaperReadingRAG
- **特点**: GraphRAG + 混合检索（向量+BM25+RRF）
- **适用**: 学术论文问答

---

## 🏥 垂直领域

### 10. medicalrag (2⭐)
- **链接**: https://github.com/ShantamShukla/medicalrag
- **特点**: Next.js + LangChain + Pinecone，医疗文档向量存储
- **适用**: 医疗知识库

### 11. Smart-sweep-agent (10⭐)
- **链接**: https://github.com/SYG-curry/Smart-sweep-agent
- **特点**: 扫地机器人领域客服Agent，RAG+LangChain
- **适用**: 垂直领域客服

---

## 🛠️ 技术选型参考

| 需求 | 推荐方案 |
|------|----------|
| 快速上手 | Simple-Local-QA |
| 企业级 | Chat2Anything / KnowledgeRAG-OGAS |
| 垂直领域 | grid-qa / ai-medical-assistant |
| 知识图谱 | contextual-chunking-graphpowered-rag |
| 学术科研 | PaperReadingRAG |

---

## 💡 关键组件

**Embedding模型**:
- text2vec-large-chinese（中文）
- bge-m3（多语言）
- text-embedding-ada-002（OpenAI）

**向量数据库**:
- FAISS（轻量）
- ChromaDB（本地）
- Milvus（生产）
- pgvector（PostgreSQL扩展）

**RAG框架**:
- LangChain
- LlamaIndex
- Haystack

**LLM API**:
- DeepSeek（免费额度）
- 通义千问
- ChatGLM（本地）

---

## ⚠️ 注意事项

1. **手机端限制**: proot环境无法运行完整Web服务，可吸收其架构思路
2. **API依赖**: 多数项目需要OpenAI兼容API或本地部署模型
3. **中文支持**: 优先选择支持中文的embedding模型
4. **离线方案**: Simple-Local-QA可完全本地运行，无需联网
