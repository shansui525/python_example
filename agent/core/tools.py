"""
工具系统模块
管理Agent可用的所有工具（内置/MCP/Skill）
"""

import json
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Dict, Callable, Any, Optional, List
from .messages import Tool


class ToolRegistry:
    """
    工具注册表

    核心功能：
    - 注册各种来源的工具（内置/MCP/Skill）
    - 存储工具元信息和执行函数
    - 提供工具schema供LLM使用
    - 执行工具并返回结果

    设计思路：
    采用注册表模式，所有工具通过register()方法注册，
    便于扩展和维护。
    """

    def __init__(self):
        # 工具名称 -> Tool对象
        self._tools: Dict[str, Tool] = {}
        # 工具名称 -> 执行函数
        self._functions: Dict[str, Callable] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        func: Callable,
        source: str = "builtin"
    ) -> None:
        """
        注册工具

        Args:
            name: 工具名称
            description: 工具描述
            parameters: JSON Schema格式的参数定义
            func: 工具执行函数
            source: 工具来源（builtin/mcp/skill）
        """
        tool = Tool(
            name=name,
            description=description,
            parameters=parameters,
            source=source
        )
        self._tools[name] = tool
        self._functions[name] = func
        print(f"[工具注册] [{source}] {name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具定义"""
        return self._tools.get(name)

    def get_schemas(self) -> List[Dict[str, Any]]:
        """
        获取所有工具的schema列表

        用于发送给LLM，告诉它有哪些工具可用
        """
        return [tool.to_schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        执行指定工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果的字符串表示

        Raises:
            KeyError: 如果工具不存在
        """
        if name not in self._functions:
            raise KeyError(f"工具 '{name}' 不存在")

        func = self._functions[name]
        try:
            # 执行工具函数
            result = func(**arguments)
            return str(result)
        except TypeError as e:
            # 参数错误
            return f"错误：工具参数不正确 - {str(e)}"
        except Exception as e:
            # 其他执行错误
            return f"错误：执行工具 '{name}' 失败 - {str(e)}"

    def list_tools(self) -> List[Dict[str, str]]:
        """列出所有已注册的工具"""
        return [
            {"name": name, "description": tool.description, "source": tool.source}
            for name, tool in self._tools.items()
        ]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
