"""
rag.py —— RAG 总导演（把零件串成「建库 / 问答」两条业务）

教学对照：
  建库：docs → ingest → embed → store.save
  问答：question → embed → store.search → 拼 Prompt → llm.chat

读本文件即可抓住项目精髓；其它文件是零件。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import INDEX_DIR, DOCS_DIR, ensure_dirs, load_llm_config, load_rag_settings
from embed import embed_query, embed_texts
from ingest import ingest_paths, list_docs
from llm import chat
from store import VectorStore


def get_store() -> VectorStore:
    """加载磁盘上的向量索引到内存。"""
    ensure_dirs()
    store = VectorStore(INDEX_DIR)
    store.load()
    return store


def rebuild_index() -> Dict[str, Any]:
    """
    全量重建索引（教学实现：简单可靠）。

    注意：上传/删除文件后必须再调用本函数，
    否则 data/index 仍是旧内容。
    """
    ensure_dirs()
    settings = load_rag_settings()
    docs = list_docs(DOCS_DIR)
    # 1) 文件 → Chunk 列表
    chunks = ingest_paths(
        docs,
        chunk_size=settings["chunk_size"],
        overlap=settings["chunk_overlap"],
    )
    store = VectorStore(INDEX_DIR)
    if not chunks:
        store.clear()
        return {"ok": True, "docs": 0, "chunks": 0, "message": "docs 目录为空"}

    # 2) Chunk 文本 → 向量矩阵
    vectors = embed_texts([c.text for c in chunks], settings["embedding_model"])
    # 3) 落盘
    store.save(chunks, vectors, embedding_model=settings["embedding_model"])
    return {
        "ok": True,
        "docs": len(docs),
        "chunks": len(chunks),
        "embedding_model": settings["embedding_model"],
    }


def status() -> Dict[str, Any]:
    """给前端展示：有哪些文档、索引是否就绪、LLM 是否配置。"""
    ensure_dirs()
    store = get_store()
    cfg = load_llm_config()
    settings = load_rag_settings()
    docs = list_docs(DOCS_DIR)
    return {
        "docs_count": len(docs),
        "docs": [p.name for p in docs],
        "chunk_count": len(store.chunks),
        "has_index": store.exists(),
        "embedding_model": store.model_name or settings["embedding_model"],
        "llm_enabled": bool(cfg.get("enabled")),
        "llm_model": cfg.get("model"),
        "llm_base_url": cfg.get("base_url"),
        "top_k": settings["top_k"],
    }


def ask(question: str, *, top_k: Optional[int] = None) -> Dict[str, Any]:
    """
    在线问答：检索增强生成。

    返回：
      answer    — 模型回答
      citations — 用到的原文片段（可溯源，教学与产品都重要）
    """
    question = (question or "").strip()
    if not question:
        raise ValueError("问题不能为空")

    settings = load_rag_settings()
    store = get_store()
    if not store.exists() or not store.chunks:
        raise RuntimeError("尚未建立索引。请先上传文档并点击「重建索引」。")

    # 必须与建库同一嵌入模型
    model_name = store.model_name or settings["embedding_model"]
    k = int(top_k or settings["top_k"])

    # —— Retrieval：问题向量 → Top-K 切片 ——
    qvec = embed_query(question, model_name)
    hits = store.search(qvec, top_k=k)

    # —— 拼 Prompt 用的「资料正文」+ 给前端的引用列表 ——
    # contexts：稍后拼进 user 消息，给 LLM 看
    # citations：原样返回前端展示，不参与模型计算
    contexts = []
    citations = []
    for i, (chunk, score) in enumerate(hits, start=1):
        # 每一段资料的格式，例如：
        #   [资料1 | rag-intro.md | 相关度 0.812]
        #   （这里是切片原文……）
        contexts.append(
            "[资料{} | {} | 相关度 {:.3f}]\n{}".format(i, chunk.source, score, chunk.text)
        )
        citations.append(
            {
                "rank": i,
                "source": chunk.source,
                "chunk_index": chunk.chunk_index,
                "score": round(score, 4),
                "text": chunk.text,
            }
        )

    # 多段资料之间空一行；若完全没命中，给模型一句明确占位，避免空资料
    context_block = "\n\n".join(contexts) if contexts else "（未检索到相关片段）"

    # —— Augmented Prompt：拼成 messages 再交给 llm.chat ——
    # 最终发给模型的是两条消息：
    #   1) role=system  → 规则（只根据资料答、不足则说明未找到）
    #   2) role=user    → 「资料：…\n\n问题：…」
    # 这就是 RAG 里的「增强」：把检索结果写进 Prompt，而不是只扔一个光秃秃的问题。
    system = (
        "你是本地知识库助手。请只根据给定资料回答用户问题；"
        "若资料不足，请明确说明“资料中未找到”，不要编造。"
        "回答使用简洁中文，必要时引用资料编号如 [资料1]。"
    )
    # user 最终长这样（示意）：
    #   资料：
    #   [资料1 | xxx.md | 相关度 0.8]
    #   ……原文……
    #
    #   [资料2 | ...]
    #   ……
    #
    #   问题：用户的问题
    user = "资料：\n{}\n\n问题：{}".format(context_block, question)

    # —— Generation ——
    answer = chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    return {
        "answer": answer,
        "citations": citations,
        "top_k": k,
    }
