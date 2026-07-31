"""
llm.py —— 调用大语言模型生成答案（RAG 流水线最后一步）

教学要点：
  LLM 不会自动读你的磁盘文件；它只看你塞进 messages 的文字。
  RAG 的「增强」就是：把检索到的资料写进 Prompt，再调用本模块。

  openai 库兼容多种服务：DeepSeek、OpenAI、本地 Ollama 等，
  区别主要在 base_url / api_key / model。
"""

from __future__ import annotations

from typing import Any, Dict, List

from config import load_llm_config


def chat(messages: List[Dict[str, str]]) -> str:
    """
    messages 示例：
      [{"role": "system", "content": "规则..."},
       {"role": "user", "content": "资料...\\n\\n问题..."}]
    返回：模型生成的纯文本答案。
    """
    cfg = load_llm_config()
    if not cfg.get("enabled"):
        raise RuntimeError(
            "未配置可用的 LLM。请复制 llm_config.example.json 为 llm_config.json 并填入 api_key。"
        )

    from openai import OpenAI

    client = OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
        timeout=float(cfg.get("timeout_sec") or 120),
    )
    kwargs: Dict[str, Any] = {
        "model": cfg.get("model") or "deepseek-chat",
        "messages": messages,
        # temperature 偏低：知识库问答更希望稳定、少发挥
        "temperature": float(cfg.get("temperature", 0.2)),
        "max_tokens": int(cfg.get("max_tokens", 2048)),
    }
    # 某些厂商需要额外字段（如关闭 thinking），透传即可
    extra = cfg.get("extra_body")
    if isinstance(extra, dict) and extra:
        kwargs["extra_body"] = extra

    # 真正向 LLM 服务发请求：把 model / messages / temperature 等展开传入
    # **kwargs 等价于 create(model=..., messages=..., temperature=..., ...)
    # 返回值 resp 是完整响应对象（含用量、多候选等），不只是一串文字
    resp = client.chat.completions.create(**kwargs)
    # choices[0]：默认取第一个（也是通常唯一的）候选回答
    # message.content：模型生成的正文；可能为 None，故用 or ""
    # strip()：去掉首尾空白，方便直接展示给前端
    return (resp.choices[0].message.content or "").strip()
