"""
Agent核心模块
实现基于ReAct模式的主Agent类
"""

import json
import re
from typing import List, Dict, Any, Optional
from .llm import OllamaLLM
from .messages import Message, MessageRole, ToolCall
from .tools import ToolRegistry


class Agent:
    """
    本地AI Agent核心类

    采用ReAct模式 (Reasoning + Acting)，核心工作流程：
    1. 接收用户任务
    2. LLM分析并决定是否调用工具
    3. 如需工具，执行并获取结果
    4. 将结果反馈给LLM继续分析
    5. 循环直到任务完成

    Attributes:
        model: 使用的LLM模型
        max_iterations: 最大循环次数
        tools: 工具注册表
        history: 消息历史
    """

    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "http://localhost:11434",
        max_iterations: int = 15,
        system_prompt: Optional[str] = None
    ):
        """
        初始化Agent

        Args:
            model: LLM模型名称
            base_url: Ollama服务地址
            max_iterations: 最大循环次数，防止无限循环
            system_prompt: 自定义系统提示词
        """
        # 初始化LLM
        self.llm = OllamaLLM(model=model, base_url=base_url)

        # 初始化工具注册表
        self.tools = ToolRegistry()

        # 消息历史
        self.history = []

        # 配置
        self.max_iterations = max_iterations
        self.model = model

        # 设置系统提示
        if system_prompt:
            self._system_prompt = system_prompt
        else:
            self._system_prompt = self._default_system_prompt()

        # 初始化系统消息
        self._init_system_message()

    def _default_system_prompt(self) -> str:
        """默认系统提示词"""
        return """你是一个智能助手，擅长使用工具来扩展你的能力。

【工作原则】
1. 理解任务：仔细分析用户需求
2. 规划行动：决定是否需要使用工具
3. 执行反馈：调用工具并分析结果
4. 给出答案：当确定答案后直接回答

【工具使用策略】
- 简单问题直接回答，不需要工具
- 需要实时信息时使用搜索工具
- 需要执行特定操作时使用MCP或Skill工具
- 不确定时，宁可调用工具也不要胡乱猜测

【响应要求】
- 简洁明了
- 必要时展示思考过程
- 不确定时诚实说明"""

    def _init_system_message(self) -> None:
        """初始化系统消息"""
        self.history.append(Message(
            role=MessageRole.SYSTEM,
            content=self._system_prompt
        ))

    def reset(self) -> None:
        """重置Agent状态"""
        self.history = [Message(
            role=MessageRole.SYSTEM,
            content=self._system_prompt
        )]
        print("Agent已重置")

    def add_tools(self, tools: List[Dict[str, Any]], functions: Dict[str, callable]) -> None:
        """
        批量添加工具

        Args:
            tools: 工具定义列表
            functions: 工具名称到函数的映射
        """
        for tool_def in tools:
            name = tool_def.get("name") or tool_def.get("function", {}).get("name")
            if name in functions:
                func = functions[name]
                desc = tool_def.get("description") or tool_def.get("function", {}).get("description", "")
                params = tool_def.get("parameters") or tool_def.get("function", {}).get("parameters", {})

                self.tools.register(
                    name=name,
                    description=desc,
                    parameters=params,
                    func=func
                )

    def run(self, user_input: str) -> str:
        """
        运行Agent处理用户输入

        核心ReAct循环：
        1. 发送请求到LLM
        2. 检查是否有工具调用
        3. 如有工具，执行并继续循环
        4. 如无工具，返回最终答案

        Args:
            user_input: 用户输入

        Returns:
            Agent的最终响应
        """
        # 添加用户消息到历史
        self.history.append(Message(
            role=MessageRole.USER,
            content=user_input
        ))

        print("\n" + "="*60)
        print("Agent开始处理...")
        print("="*60)

        # ReAct循环
        for iteration in range(self.max_iterations):
            print(f"\n[迭代 {iteration + 1}/{self.max_iterations}]")

            # 获取LLM响应
            response = self._call_llm()

            if "error" in response:
                error_msg = response["error"]
                print(f"错误: {error_msg}")
                return f"抱歉，发生了错误：{error_msg}"

            # 提取响应内容
            assistant_message = response.get("message", {})
            content = assistant_message.get("content", "")
            tool_calls = assistant_message.get("tool_calls", [])

            # 清理内容（移除思考标签等）
            content = self._clean_content(content)

            # 添加助手消息到历史
            self.history.append(Message(
                role=MessageRole.ASSISTANT,
                content=content
            ))

            print(f"思考: {content[:150]}{'...' if len(content) > 150 else ''}")

            # 检查是否有工具调用
            if tool_calls:
                print(f"需要调用 {len(tool_calls)} 个工具...")

                for tc in tool_calls:
                    tool_call = ToolCall.from_dict(tc)
                    print(f"  -> {tool_call.name}: {tool_call.arguments}")

                    # 执行工具
                    result = self.tools.execute(
                        tool_call.name,
                        tool_call.arguments
                    )
                    print(f"     结果: {result[:100]}{'...' if len(result) > 100 else ''}")

                    # 添加工具结果到历史
                    self.history.append(Message(
                        role=MessageRole.TOOL,
                        content=result,
                        name=tool_call.name,
                        tool_call_id=tool_call.id
                    ))

                # 继续下一轮循环
                continue

            # 无工具调用，任务完成
            print("\n任务完成!")
            print("="*60)
            return content

        # 超过最大迭代
        return "任务过于复杂，已达到最大迭代次数。"

    def _call_llm(self) -> Dict[str, Any]:
        """调用LLM获取响应"""
        # 准备消息
        messages = [msg.to_dict() for msg in self.history]

        # 获取工具schema
        tool_schemas = self.tools.get_schemas()

        # 调用LLM
        return self.llm.chat(
            messages=messages,
            tools=tool_schemas if tool_schemas else None
        )

    def _clean_content(self, content: str) -> str:
        """清理响应内容"""
        # 移除qwen3的思考标签
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()

        # 移除其他可能的标记
        content = content.strip()

        return content

    def check_status(self) -> Dict[str, Any]:
        """检查Agent状态"""
        connected = self.llm.check_connection()

        return {
            "status": "ready" if connected else "error",
            "model": self.model,
            "ollama_connected": connected,
            "tools_count": len(self.tools),
            "tools": self.tools.list_tools(),
            "message_count": len(self.history)
        }
