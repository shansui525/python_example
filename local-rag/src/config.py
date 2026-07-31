"""
config.py —— 路径与配置（教学项目的「总开关」）

为什么单独抽配置？
  避免在业务代码里写死路径、模型名、密钥。
  改一处，全项目生效；密钥也不该提交到 Git。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---- 目录约定 ----
# src/config.py → 上一级是项目根 local-rag/
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = DATA_DIR / "docs"  # 原始文档
INDEX_DIR = DATA_DIR / "index"  # 向量索引

CONFIG_PATH = ROOT / "llm_config.json"
EXAMPLE_PATH = ROOT / "llm_config.example.json"


def ensure_dirs() -> None:
    """确保 docs / index 目录存在。"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def load_llm_config() -> dict[str, Any]:
    """
    加载 LLM 配置，优先级：
      1) 环境变量 LOCAL_RAG_LLM_CONFIG 指定的文件
      2) 本项目 llm_config.json
      3) example 模板

    环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 可覆盖字段。
    """
    cfg: dict[str, Any] = {}
    env_path = os.environ.get("LOCAL_RAG_LLM_CONFIG")
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(CONFIG_PATH)

    for p in candidates:
        if p and p.exists():
            cfg = json.loads(p.read_text(encoding="utf-8"))
            break
    else:
        if EXAMPLE_PATH.exists():
            cfg = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    # 环境变量覆盖（CI / 临时调试常用）
    if os.environ.get("LLM_API_KEY"):
        cfg["api_key"] = os.environ["LLM_API_KEY"]
    if os.environ.get("LLM_BASE_URL"):
        cfg["base_url"] = os.environ["LLM_BASE_URL"]
    if os.environ.get("LLM_MODEL"):
        cfg["model"] = os.environ["LLM_MODEL"]

    # 兼容另一套字段命名
    if cfg.get("llm_api_key"):
        cfg["api_key"] = cfg["llm_api_key"]
    if cfg.get("llm_api_base"):
        cfg["base_url"] = cfg["llm_api_base"]
    if cfg.get("llm_model"):
        cfg["model"] = cfg["llm_model"]

    api_key = str(cfg.get("api_key") or "")
    # 占位密钥视为未启用
    cfg["enabled"] = bool(api_key and api_key != "sk-your-key-here")
    cfg.setdefault("base_url", "https://api.deepseek.com/v1")
    cfg.setdefault("model", "deepseek-chat")
    cfg.setdefault("temperature", 0.2)
    cfg.setdefault("max_tokens", 2048)
    cfg.setdefault("timeout_sec", 120)
    return cfg


def load_rag_settings() -> dict[str, Any]:
    """
    RAG 超参数（可写在 llm_config.json 的 rag 字段）。

    chunk_size / chunk_overlap → 影响切片粒度
    top_k → 问答时取几段资料
    embedding_model → 本地嵌入模型名
    """
    cfg = load_llm_config()
    rag = cfg.get("rag") if isinstance(cfg.get("rag"), dict) else {}
    return {
        "chunk_size": int(rag.get("chunk_size", 600)),
        "chunk_overlap": int(rag.get("chunk_overlap", 100)),
        "top_k": int(rag.get("top_k", 4)),
        "embedding_model": str(
            rag.get("embedding_model")
            or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ),
    }
