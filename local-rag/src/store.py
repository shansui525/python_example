"""
store.py —— 迷你向量库（RAG 流水线第 3 步：存 + 查）

教学要点：
  「向量数据库」听起来唬人，本质通常是：
    1) 存下所有 Chunk 的向量
    2) 来了查询向量，按相似度找出 Top-K

  工业界常用 FAISS / Chroma / Milvus…
  本教学项目用 numpy 暴力检索：慢一点但逻辑一目了然。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from ingest import Chunk


class VectorStore:
    """本地目录里的简易索引：json 存文本，npy 存向量。"""

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        # 三件套：正文元数据 / 向量矩阵 / 模型信息
        self.meta_path = self.index_dir / "chunks.json"
        self.vec_path = self.index_dir / "vectors.npy"
        self.info_path = self.index_dir / "info.json"
        self.chunks: List[Chunk] = []
        self.vectors: Optional[np.ndarray] = None  # shape=[N, D]
        self.model_name: str = ""  # 记录建库时用的嵌入模型

    def exists(self) -> bool:
        """是否已经建过索引。"""
        return self.meta_path.exists() and self.vec_path.exists()

    def load(self) -> None:
        """启动问答前：从磁盘读回内存。"""
        if not self.exists():
            self.chunks = []
            self.vectors = None
            self.model_name = ""
            return
        raw = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self.chunks = [Chunk.from_dict(x) for x in raw]
        self.vectors = np.load(str(self.vec_path))
        info = {}
        if self.info_path.exists():
            info = json.loads(self.info_path.read_text(encoding="utf-8"))
        self.model_name = str(info.get("embedding_model") or "")

    def save(
        self,
        chunks: List[Chunk],
        vectors: np.ndarray,
        *,
        embedding_model: str,
    ) -> None:
        """建索引时：把内存结果持久化（全量覆盖写入）。"""
        self.chunks = chunks
        self.vectors = np.asarray(vectors, dtype=np.float32)
        self.model_name = embedding_model
        self.meta_path.write_text(
            json.dumps([c.to_dict() for c in chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        np.save(str(self.vec_path), self.vectors)
        self.info_path.write_text(
            json.dumps(
                {
                    "embedding_model": embedding_model,
                    "chunk_count": len(chunks),
                    "dim": int(self.vectors.shape[1]) if len(self.vectors) else 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def clear(self) -> None:
        """清空索引文件（例如 docs 目录为空时）。"""
        for p in (self.meta_path, self.vec_path, self.info_path):
            if p.exists():
                p.unlink()
        self.chunks = []
        self.vectors = None
        self.model_name = ""

    def search(self, query_vec: np.ndarray, top_k: int = 4) -> List[Tuple[Chunk, float]]:
        """
        语义检索：用「问题向量」在全部切片向量里找最像的 top_k 段。

        参数：
          query_vec  问题向量，形状 (D,)，来自 embed_query()
          top_k      最多返回几段（默认 4）；若总段数更少，则全返回

        返回：
          [(Chunk, score), ...]，按 score 从高到低排列
          Chunk 是原文切片；score 是相似度（越高越相关，约在 -1~1，归一化后常接近 0~1）

        精髓：
          建库时 embed 做了 L2 归一化，因此：
            scores = vectors @ q   （矩阵点积）
          就等于每段与问题的余弦相似度，不必再写复杂公式。

        这是「暴力检索」：和每一段都比一遍。教学上最直观；
        数据量极大时才会换成 FAISS 等近似近邻算法。
        """
        # 还没建索引，或索引为空 → 无结果可查
        if self.vectors is None or len(self.chunks) == 0:
            return []

        # 保证问题向量是 float32，与 self.vectors 类型一致，避免隐式类型转换坑
        q = np.asarray(query_vec, dtype=np.float32)

        # ---------- 算分（本函数最核心的一行）----------
        # self.vectors 形状 [N, D]：N 个切片，每个 D 维
        # q             形状 [D]
        # @ 是矩阵乘法 / 批量点积：
        #   第 i 个切片向量 · q  →  scores[i]
        # 得到 scores 形状 [N]，即「每一段和问题有多像」
        scores = self.vectors @ q

        # 实际要取的个数：不能超过总段数
        k = min(top_k, len(scores))

        # ---------- 取出分数最高的 k 个下标 ----------
        # 为什么先用 argpartition，而不是直接全排序？
        #   全排序要对全部 N 个分数排序，N 很大时更慢。
        #   argpartition 只保证「前 k 大」被选出来，不保证这 k 个内部有序，但更快。
        #
        # 对 scores 取负：argpartition 默认找「最小」的一侧；
        #   -scores 后，「最小的负数」对应原来「最大的分数」。
        # kth=k-1：划分点，使得至少有 k 个「较小」（即原分数较大）的元素在左侧。
        # [:k]：取这 k 个下标（此时这 k 个之间尚未按分数排好）。
        idx = np.argpartition(-scores, kth=k - 1)[:k]

        # 把这 k 个下标按分数从高到低再排一次，方便后面按相关度展示
        # argsort(-scores[idx])：对选中的分数取负再升序 → 等价于原分数降序
        idx = idx[np.argsort(-scores[idx])]

        # 组装结果：下标 i → (第 i 个 Chunk, 对应相似度分数)
        return [(self.chunks[i], float(scores[i])) for i in idx]
