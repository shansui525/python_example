"""
极简本地 AI Agent - 基于 Ollama qwen3:8b
核心原理：Sense → Think → Act → Loop (ReAct 模式)
"""

import json
import ollama
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Tool:
    """工具定义：Agent 的能力边界"""
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable

    def to_ollama_format(self) -> Dict:
        """转换为 Ollama API 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def execute(self, **kwargs) -> str:
        """执行工具"""
        try:
            result = self.func(**kwargs)
            return str(result)
        except Exception as e:
            return f"工具执行错误: {str(e)}"


@dataclass
class AgentMemory:
    """Agent 工作记忆（上下文管理）"""
    messages: List[Dict] = field(default_factory=list)
    max_messages: int = 20  # 防止上下文过长

    def add(self, role: str, content: str, **kwargs):
        """添加消息"""
        msg = {"role": role, "content": content, **kwargs}
        self.messages.append(msg)
        # 保留系统提示，裁剪早期对话
        if len(self.messages) > self.max_messages:
            # 保留 system 和最近的消息
            system_msgs = [m for m in self.messages if m["role"] == "system"]
            other_msgs = [m for m in self.messages if m["role"] != "system"]
            self.messages = system_msgs + other_msgs[-(self.max_messages-len(system_msgs)):]

    def get(self) -> List[Dict]:
        """获取当前记忆"""
        return self.messages.copy()

    def clear(self):
        """清空记忆"""
        self.messages = []


class OllamaAgent:
    """
    基于 Ollama 的极简 Agent
    核心循环：观察 → 思考(LLM) → 行动(工具) → 观察 → ...
    """

    def __init__(
        self,
        model: str = "qwen3:8b",
        system_prompt: Optional[str] = None,
        max_iterations: int = 5
    ):
        self.model = model
        self.tools: Dict[str, Tool] = {}
        self.memory = AgentMemory()
        self.max_iterations = max_iterations

        # 初始化系统提示
        default_system = """你是一个智能 Agent，能够使用工具完成任务。
当需要获取实时信息或执行特定操作时，请使用可用工具。
不要编造信息，如果不确定请使用工具查询。"""

        self.memory.add("system", system_prompt or default_system)

        # 检查 Ollama 连接
        self._check_connection()

    def _check_connection(self):
        """检查 Ollama 服务"""
        try:
            ollama.list()
            print(f"✅ 已连接到 Ollama，使用模型: {self.model}")
        except Exception as e:
            print(f"❌ 无法连接 Ollama: {e}")
            print("请确保 Ollama 已启动: ollama serve")
            raise

    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool
        print(f"🔧 注册工具: {tool.name}")

    def run(self, user_input: str) -> str:
        """
        Agent 主循环
        """
        print(f"\n🧑 用户: {user_input}")

        # 添加用户输入到记忆
        self.memory.add("user", user_input)

        for i in range(self.max_iterations):
            print(f"\n--- 思考迭代 {i+1}/{self.max_iterations} ---")

            # 1. 调用 LLM 进行思考
            response = self._think()

            # 2. 检查是否需要调用工具
            tool_calls = response.get('tool_calls', [])

            if tool_calls:
                # 有工具调用，执行行动
                print(f"🤖 决定调用工具: {[tc['function']['name'] for tc in tool_calls]}")

                # 添加 assistant 的 tool_calls 到记忆
                self.memory.add(
                    "assistant",
                    response.get('content', ''),
                    tool_calls=tool_calls
                )

                # 执行每个工具调用
                for tool_call in tool_calls:
                    result = self._act(tool_call)
                    print(f"🔧 工具结果: {result[:100]}...")

            else:
                # 没有工具调用，给出最终答案
                content = response.get('content', '')
                print(f"✅ 最终答案: {content[:200]}...")
                self.memory.add("assistant", content)
                return content

        return "达到最大迭代次数，任务未完成"

    def _think(self) -> Dict:
        """
        思考步骤：调用 LLM 决定下一步行动
        """
        messages = self.memory.get()
        tools = [t.to_ollama_format() for t in self.tools.values()]

        try:
            # 调用 Ollama，传入工具定义
            response = ollama.chat(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
                options={
                    "temperature": 0.7,
                    "num_ctx": 4096
                }
            )

            return response['message']

        except Exception as e:
            print(f"LLM 调用错误: {e}")
            return {"content": f"错误: {e}", "tool_calls": []}

    def _act(self, tool_call: Dict) -> str:
        """
        行动步骤：执行工具调用
        """
        func_info = tool_call.get('function', {})
        tool_name = func_info.get('name')
        arguments = func_info.get('arguments', {})

        # 解析参数（Ollama 可能返回字符串或 dict）
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return f"参数解析错误: {arguments}"

        print(f"  调用 {tool_name}({arguments})")

        if tool_name not in self.tools:
            result = f"错误: 未知工具 '{tool_name}'"
        else:
            tool = self.tools[tool_name]
            result = tool.execute(**arguments)

        # 将工具结果加入记忆（tool 角色）
        self.memory.add(
            "tool",
            result,
            tool_name=tool_name
        )

        return result

    def chat_history(self) -> List[Dict]:
        """查看对话历史"""
        return self.memory.get()

    def clear_history(self):
        """清空对话历史（保留系统提示）"""
        system_msg = None
        for msg in self.memory.get():
            if msg["role"] == "system":
                system_msg = msg
                break

        self.memory.clear()
        if system_msg:
            self.memory.messages.append(system_msg)


# ============ 工具实现 ============

def get_weather(city: str) -> str:
    """获取天气（模拟）"""
    mock_data = {
        "北京": "晴天，25°C，空气质量良",
        "上海": "多云，28°C，湿度65%",
        "深圳": "小雨，30°C，东南风2级",
        "杭州": "阴天，22°C，适宜出行"
    }
    return mock_data.get(city, f"{city}天气数据暂缺，建议查看天气预报APP")

def calculate(expression: str) -> str:
    """安全计算器"""
    allowed_chars = set('0123456789+-*/.() ')
    if not all(c in allowed_chars for c in expression):
        return "错误：表达式包含非法字符"
    try:
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {e}"

def get_current_time() -> str:
    """获取当前时间"""
    now = datetime.now()
    return now.strftime("%Y年%m月%d日 %H:%M:%S")

def search_knowledge(query: str) -> str:
    """模拟知识库检索"""
    knowledge_base = {
        "agent": "Agent 是能够感知环境并采取行动的智能体，核心组件包括：感知、思考、行动、记忆",
        "ollama": "Ollama 是本地大模型运行框架，支持工具调用、流式输出等功能",
        "qwen3": "Qwen3 是阿里通义千问第三代模型，支持工具调用和推理能力",
        "mcp": "MCP (Model Context Protocol) 是 Anthropic 提出的开放协议，用于标准化 AI 与外部工具的交互"
    }

    for key, value in knowledge_base.items():
        if key in query.lower():
            return value
    return f"知识库中未找到 '{query}' 的相关信息"

def write_file(filename: str, content: str) -> str:
    """写入文件（演示工具副作用）"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"成功写入文件: {filename}，字数: {len(content)}"
    except Exception as e:
        return f"写入失败: {e}"


# ============ 运行演示 ============

if __name__ == "__main__":

    # 初始化 Agent
    agent = OllamaAgent(
        model="qwen3:8b",
        system_prompt="""你是一个有用的 AI Agent，擅长使用工具解决问题。
当用户询问天气、时间、计算或知识问题时，请使用相应工具获取准确信息。
不要编造事实，必须通过工具获取实时信息。"""
    )

    # 注册工具
    agent.register_tool(Tool(
        name="get_weather",
        description="获取指定城市的当前天气信息",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称，如北京、上海"}
            },
            "required": ["city"]
        },
        func=get_weather
    ))

    agent.register_tool(Tool(
        name="calculate",
        description="计算数学表达式，支持加减乘除和括号",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式，如 123 * 456"}
            },
            "required": ["expression"]
        },
        func=calculate
    ))

    agent.register_tool(Tool(
        name="get_current_time",
        description="获取当前日期和时间",
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        },
        func=get_current_time
    ))

    agent.register_tool(Tool(
        name="search_knowledge",
        description="搜索内部知识库获取概念解释",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要查询的关键词"}
            },
            "required": ["query"]
        },
        func=search_knowledge
    ))

    # 测试场景
    test_cases = [
        "北京今天天气怎么样？",
        "帮我算一下 15 * 23 + 47",
        "现在几点了？",
        "什么是 Agent？",
        "先算 100 除以 4，然后告诉我上海天气"
    ]

    print("\n" + "="*50)
    print("开始测试 Agent")
    print("="*50)

    for query in test_cases:
        print("\n" + "="*50)
        result = agent.run(query)
        print(f"\n💡 最终结果: {result}")
        input("\n按回车继续...")

    # 查看完整对话历史
    print("\n" + "="*50)
    print("完整对话历史:")
    print("="*50)
    for msg in agent.chat_history():
        print(f"\n[{msg['role']}] {msg.get('content', '')[:100]}")
        if 'tool_calls' in msg:
            print(f"  [tool_calls] {msg['tool_calls']}")