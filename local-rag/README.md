# Local RAG

简单的**本地 RAG** 教学项目：文档入库 → 向量检索 → LLM 回答（带引用）。  
代码刻意精简，并带有面向新手的注释。

## 能力

- 支持 `txt` / `md` / `pdf`
- 本地嵌入模型（`sentence-transformers`，首次会自动下载）
- 简易向量库（`numpy`，无需 Docker / Chroma）
- 生成端：OpenAI 兼容 API（DeepSeek / 本地 Ollama 等）
- Web UI：上传、重建索引、提问

## 快速开始

```bash
cd local-rag
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 配置 LLM
cp llm_config.example.json llm_config.json
# 编辑 llm_config.json，填入 api_key

./run.sh
```

浏览器打开：http://127.0.0.1:8780

## 使用流程

1. 左侧上传文档（或把文件放进 `data/docs/`）
2. 点击「重建索引」（首次嵌入模型下载可能较慢）
3. 右侧提问，查看回答与引用片段

## 文档

- `docs/工作原理.md`：系统流程与设计说明  
- `docs/新手完全指南.md`：零基础讲解文（含目录，可作公众号长文/连载底稿）

```
local-rag/
  data/docs/       # 原始文档
  data/index/      # 向量索引
  src/             # 后端
  static/          # 前端
  llm_config.json  # LLM 配置（勿提交密钥）
```

## 仅用 Ollama 示例

`llm_config.json`：

```json
{
  "enabled": true,
  "base_url": "http://127.0.0.1:11434/v1",
  "api_key": "ollama",
  "model": "qwen2.5:7b",
  "temperature": 0.2,
  "max_tokens": 2048
}
```
