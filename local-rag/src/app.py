"""
app.py —— Web API 入口（把 rag.py 的能力挂到浏览器可访问的 URL 上）

教学要点：
  前后端分离：
    - 前端 static/：按钮、展示
    - 后端本文件：接收 HTTP，调用 rag，返回 JSON

  本文件刻意写得很「薄」：复杂逻辑都在 rag / ingest / store。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(__file__).resolve().parent
# 允许 `from config import ...` 这种教学友好的导入写法
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import DOCS_DIR, ensure_dirs  # noqa: E402
from ingest import SUPPORTED_SUFFIX  # noqa: E402
from rag import ask, rebuild_index, status  # noqa: E402

STATIC = ROOT / "static"
app = FastAPI(title="Local RAG", version="0.1.0")


class AskBody(BaseModel):
    """提问请求体；Pydantic 会自动校验字段。"""

    question: str = Field(..., min_length=1)
    top_k: Optional[int] = None  # 不传则用配置默认值


@app.on_event("startup")
def _startup():
    """服务启动时确保数据目录存在。"""
    ensure_dirs()


@app.get("/api/health")
def health():
    """探活：用来确认服务是否在跑。"""
    return {"ok": True}


@app.get("/api/status")
def api_status():
    """前端顶部状态徽章、文档列表都靠它。"""
    return status()


@app.post("/api/reindex")
def api_reindex():
    """全量重建向量索引（可能较慢：要跑嵌入模型）。"""
    try:
        return rebuild_index()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/ask")
def api_ask(body: AskBody):
    """RAG 问答：检索 + 生成。"""
    try:
        return ask(body.question, top_k=body.top_k)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """
    上传文件到 data/docs/。

    重要：这里只存文件，不自动建索引。
    教学上让「入库」和「建索引」两步分开，方便理解。
    """
    ensure_dirs()
    name = Path(file.filename or "upload.bin").name
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIX:
        raise HTTPException(
            status_code=400,
            detail="仅支持: {}".format(", ".join(sorted(SUPPORTED_SUFFIX))),
        )
    dest = DOCS_DIR / name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "filename": name}


@app.delete("/api/docs/{filename}")
def api_delete_doc(filename: str):
    """删除 docs 中的文件；删完后仍需手动重建索引。"""
    ensure_dirs()
    path = DOCS_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    path.unlink()
    return {"ok": True}


@app.get("/")
def index():
    """打开网站首页。"""
    return FileResponse(STATIC / "index.html")


# 静态资源：CSS / JS
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
