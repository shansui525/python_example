"""
LLM封装模块
封装与Ollama API的交互逻辑
"""

import requests
import json
from typing import List, Dict, Any, Optional
from .messages import Message


class OllamaLLM:
    """
    Ollama LLM 封装类

    功能：
    - 管理与Ollama服务的HTTP通信
    - 处理请求/响应格式化
    - 支持工具调用
    - 错误处理和重试

    Attributes:
        model: 模型名称
        base_url: Ollama服务地址
    """

    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "http://localhost:11434"
    ):
        """
        初始化Ollama LLM

        Args:
            model: 模型名称，如 "qwen3:8b"
            base_url: Ollama API地址
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.chat_endpoint = f"{self.base_url}/api/chat"

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        发送对话请求到Ollama

        Args:
            messages: 消息历史列表
            tools: 可用工具列表
            temperature: 温度参数（控制创造性）
            timeout: 超时时间（秒）

        Returns:
            LLM响应字典，包含：
            - message: 回复内容
            - tool_calls: 工具调用列表（如果有）
        """
        # 构建请求体
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,          # 我们使用非流式响应
            "temperature": temperature,
            "options": {
                "temperature": temperature,
            }
        }

        # 如果有工具，添加工具配置
        if tools:
            payload["tools"] = tools

        try:
            # 发送HTTP POST请求
            response = requests.post(
                self.chat_endpoint,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            # 连接失败：Ollama服务未启动
            return {
                "error": "无法连接到Ollama服务。请确保Ollama正在运行（执行 `ollama serve`）。"
            }
        except requests.exceptions.Timeout:
            # 请求超时
            return {
                "error": f"请求超时（{timeout}秒）。模型可能需要更长时间生成响应。"
            }
        except requests.exceptions.HTTPError as e:
            # HTTP错误
            return {
                "error": f"HTTP错误: {e.response.status_code} - {e.response.text}"
            }
        except json.JSONDecodeError:
            # JSON解析错误
            return {
                "error": "无法解析Ollama响应。请检查Ollama版本是否兼容。"
            }
        except Exception as e:
            # 其他错误
            return {
                "error": f"请求失败: {str(e)}"
            }

    def check_connection(self) -> bool:
        """
        检查Ollama服务是否可用

        Returns:
            True如果连接正常，False否则
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def list_models(self) -> List[str]:
        """
        列出Ollama中可用的模型

        Returns:
            模型名称列表
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except:
            pass
        return []
