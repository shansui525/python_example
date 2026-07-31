"""
embed.py —— 文本向量化 / Embedding（RAG 流水线第 2 步）

教学要点：
  Embedding 把「文字」变成「向量」（一串数字，可理解为语义坐标 / 数字指纹）。
  意思相近的句子，向量也更接近 → 才能做「语义检索」（不是简单关键词匹配）。

注意：
  - 这不是聊天大模型（LLM）；它只负责「表示语义」，不负责写回答。
  - 建库（文档切片）与提问必须用同一个 embedding_model，
    否则问题和文档不在同一张「语义地图」上，检索会失效。

在本项目中的位置：
  建库：ingest 得到 Chunk → embed_texts → store.save
  问答：用户问题 → embed_query → store.search → 再交给 LLM
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

import numpy as np


@lru_cache(maxsize=1)
def _load_model(model_name: str):
    """
    加载本地 SentenceTransformer 嵌入模型。

    为什么用 lru_cache？
      模型权重通常几十～上百 MB，加载很慢。
      cache 保证同一个 model_name 在进程里只加载一次，
      后续 embed_texts / embed_query 都复用同一实例。

    首次运行：若本机没有缓存，会联网下载模型，需要网络。
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_texts(texts: List[str], model_name: str) -> np.ndarray:
    """
    批量编码：多段文字 → 向量矩阵。

    参数：
      texts       字符串列表，如 ["切片1正文", "切片2正文", ...]
      model_name  嵌入模型名（与配置 / 建库时保持一致）

    返回：
      numpy.ndarray，dtype=float32，形状约 [N, D]
        N = 文本条数（len(texts)）
        D = 向量维度（由模型决定，常见如 384）
      每一行对应 texts 里的一句话/一段切片。

    用途：
      建索引时，把所有 Chunk.text 一次性编成矩阵，再交给 store.save。
    """
    if not texts:
        # 空列表时返回 0 行占位，避免上层对 None 处理；
        # 列数 384 只是常见维度的占位，真正有数据时以模型输出为准。
        return np.zeros((0, 384), dtype=np.float32)

    model = _load_model(model_name)

    # ---------- 核心：model.encode ----------
    # 作用：把每段文字编码成一条语义向量（数字指纹）。
    #
    # texts:
    #   输入的字符串列表；一条文本 → 输出矩阵中的一行。
    #
    # normalize_embeddings=True:
    #   对每条向量做 L2 归一化（把长度缩成 1）。
    #   归一化之后：点积 A·B 就等于余弦相似度。
    #   因此 store.search 里可以写：scores = vectors @ query_vec
    #   而不用再手写余弦公式。
    #
    # show_progress_bar=False:
    #   关闭进度条。服务端 / 教学演示时日志更干净。
    #
    # convert_to_numpy=True:
    #   直接返回 numpy 数组，便于 np.save 存盘、矩阵乘法检索。
    #
    # 返回值形状大致为 [N, D]（N 条文本，每条 D 维）。
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    # 统一成 float32：更省内存，并与 store.py / vectors.npy 约定一致
    return np.asarray(vectors, dtype=np.float32)


def embed_query(text: str, model_name: str) -> np.ndarray:
    """
    单条问题编码：一句话 → 一条向量（专供检索使用）。

    含义与步骤：
      1) text        —— 用户问题，例如 "什么是 RAG？"
      2) model_name  —— 嵌入模型名（必须与建库时相同）
      3) 调用 embed_texts([text], ...)：
           把单句包成「只有 1 个元素的列表」，复用批量编码逻辑。
           这样能保证与建库时用同一套 encode 参数（含归一化）。
      4) arr 的形状约为 [1, D]（1 行 = 这一个问题的向量）
      5) return arr[0]：取出第 0 行，得到形状 (D,) 的一维向量

    用途（在 rag.ask 里）：
      qvec = embed_query(问题)
      hits = store.search(qvec, top_k)   # 和索引里所有切片比相似度
      再把命中的原文塞进 Prompt，交给 LLM 生成答案。

    返回结果：
      类型：numpy.ndarray
      形状：(D,)，一维；D 由模型决定（如 384）
      含义：该问题的「语义坐标 / 数字指纹」（已 L2 归一化）
      注意：返回的不是回答文字，只是检索用的向量。

    为什么单独包一层，而不是提问时直接 encode？
      - 接口语义更清晰：embed_texts=建库批量，embed_query=提问单条
      - 强制复用 embed_texts，避免两套参数不一致
    """
    # [text]：单句变成长度为 1 的列表，走统一的批量编码路径
    arr = embed_texts([text], model_name)
    # arr[0]：从 [1, D] 矩阵里取出唯一那一行 → (D,) 向量
    return arr[0]
