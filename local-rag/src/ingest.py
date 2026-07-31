"""
ingest.py —— 文档加载与切片（RAG 流水线第 1 步）

教学要点：
  检索单位通常不是「整份文件」，而是切好的小段 Chunk。
  长文直接变成一个向量会太「糊」；切段后，相关句子更容易被命中。

本文件职责：文件 → 纯文本 → 若干 Chunk
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class Chunk:
    """知识库中的最小检索单元（一段文字 + 来源信息）。"""

    id: str  # 如 "手册.md#0"，便于调试与引用
    text: str  # 切片正文（真正参与嵌入与检索的内容）
    source: str  # 来源文件名，回答时可告诉用户出处
    chunk_index: int  # 该文件内第几段（从 0 开始）

    def to_dict(self) -> dict:
        """写成 JSON 时可调用（索引落盘要用）。"""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Chunk":
        """从 JSON 字典恢复 Chunk（启动时加载索引）。"""
        return Chunk(
            id=str(data["id"]),
            text=str(data["text"]),
            source=str(data["source"]),
            chunk_index=int(data.get("chunk_index", 0)),
        )


# 教学项目只支持这几类，逻辑简单、依赖少
SUPPORTED_SUFFIX = {".txt", ".md", ".markdown", ".pdf"}


def read_file(path: Path) -> str:
    """把不同格式文件统一读成一个大字符串。"""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        # errors="replace"：遇到坏字符不崩，方便教学演示
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        # pypdf 只能抽「文字层」；扫描版图片 PDF 需要 OCR（本项目未做）
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    raise ValueError("不支持的文件类型: {}".format(path.suffix))


def _normalize(text: str) -> str:
    """轻度清洗：统一换行、压缩多余空行。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_text(text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
    """
    滑动窗口切片。

    - chunk_size: 每段目标长度（字符数，教学上够直观）
    - overlap: 相邻段重叠长度，减少「答案刚好被切断」的概率

    精髓：不是随机切，而是尽量在段落/句号处断开，保持语义完整。
    """
    text = _normalize(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + chunk_size)
        # 未到文末时，尝试在窗口内找更自然的断点
        if end < n:
            window = text[start:end]
            # cut：窗口内最后一个自然断点（相对窗口起点的下标）
            # rfind 找不到时返回 -1，下面的阈值判断会自然跳过
            cut = max(window.rfind("\n\n"), window.rfind("。"), window.rfind("\n"))
            # 只有断点足够靠后才采用，例如 chunk_size=600 时阈值约为 200：
            #   cut >= chunk_size//3  → 在句号/换行处切开（更自然）
            #   cut 太小或为 -1      → 放弃断点，仍切到窗口末尾，避免切出过短碎片
            if cut >= chunk_size // 3:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        # 下一段起点回退 overlap → 形成重叠
        start = max(0, end - overlap)
    return chunks


def ingest_paths(
    paths: Iterable[Path],
    *,
    chunk_size: int = 600,
    overlap: int = 100,
) -> List[Chunk]:
    """批量：路径列表 → Chunk 列表（建索引前的核心输入）。"""
    out: List[Chunk] = []
    for path in paths:
        path = Path(path)
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIX:
            continue
        raw = read_file(path)
        parts = split_text(raw, chunk_size=chunk_size, overlap=overlap)
        for i, part in enumerate(parts):
            cid = "{}#{}".format(path.name, i)
            out.append(
                Chunk(id=cid, text=part, source=path.name, chunk_index=i)
            )
    return out


def list_docs(docs_dir: Path) -> List[Path]:
    """列出知识库目录下可入库的文件。"""
    if not docs_dir.exists():
        return []
    files = []
    for p in sorted(docs_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIX:
            files.append(p)
    return files
