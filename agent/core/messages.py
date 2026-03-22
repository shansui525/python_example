"""
消息系统模块
定义Agent内部使用的消息数据结构
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class MessageRole(Enum):
    """
    消息角色枚举

    角色说明：
    - system: 系统消息，设置Agent行为规则
    - user: 用户输入
    - assistant: LLM回复
    - tool: 工具执行结果
    """
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """
    消息数据类

    Attributes:
        role: 消息角色
        content: 消息内容
        name: 可选名称（工具名称）
        tool_call_id: 工具调用ID
    """
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "role": self.role.value,
            "content": self.content
        }
        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result


@dataclass
class ToolCall:
    """
    工具调用数据结构

    当LLM决定调用工具时，会生成ToolCall对象
    """
    id: str                      # 唯一ID
    name: str                    # 工具名称
    arguments: Dict[str, Any]    # 工具参数

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        """从字典创建"""
        func = data.get("function", {})
        args = func.get("arguments", {})
        if isinstance(args, str):
            import json
            try:
                args = json.loads(args)
            except:
                args = {}
        return cls(
            id=data.get("id", ""),
            name=func.get("name", ""),
            arguments=args
        )


@dataclass
class Tool:
    """
    工具定义数据类

    描述一个可被Agent调用的工具
    """
    name: str                           # 工具名称
    description: str                    # 工具描述（供LLM理解）
    parameters: Dict[str, Any]           # 参数模式（JSON Schema格式）
    source: str = "builtin"              # 来源：builtin/mcp/skill

    def to_schema(self) -> Dict[str, Any]:
        """转换为OpenAI格式的工具schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class MessageHistory:
    """
    消息历史管理器

    负责维护完整的对话历史，支持：
    - 添加消息
    - 获取历史
    - 导出/导入
    - 上下文管理
    """

    def __init__(self):
        self._messages: List[Message] = []

    def add(self, role: MessageRole, content: str,
            name: Optional[str] = None,
            tool_call_id: Optional[str] = None) -> None:
        """添加消息"""
        self._messages.append(Message(
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id
        ))

    def add_message(self, message: Message) -> None:
        """添加消息对象"""
        self._messages.append(message)

    def get_all(self) -> List[Message]:
        """获取所有消息"""
        return self._messages.copy()

    def get_for_llm(self) -> List[Dict[str, Any]]:
        """获取适合发送给LLM的格式"""
        return [msg.to_dict() for msg in self._messages]

    def clear(self) -> None:
        """清空历史"""
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)

    def __getitem__(self, index: int) -> Message:
        return self._messages[index]
