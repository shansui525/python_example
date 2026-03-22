#!/usr/bin/env python3
"""
本地AI Agent - 主程序入口

功能完整的本地AI Agent，支持：
1. 联网搜索（真实网络搜索）
2. MCP工具集成
3. Skill技能系统

作者：MiniMax Agent
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import LLM_CONFIG, AGENT_CONFIG
from core.agent import Agent
from integrations.web_search import create_search_tools, create_search_functions
from integrations.mcp import create_mcp_tools, create_mcp_functions
from integrations.skills import create_skill_tools, create_skill_functions


class LocalAgent:
    """
    本地AI Agent主类

    整合所有组件：
    - 核心Agent引擎
    - 联网搜索功能
    - MCP工具集成
    - Skill技能系统
    """

    def __init__(self):
        """初始化Agent"""
        print("="*60)
        print("初始化本地AI Agent...")
        print("="*60)

        # 创建核心Agent
        self.agent = Agent(
            model=LLM_CONFIG["model"],
            base_url=LLM_CONFIG["base_url"],
            max_iterations=AGENT_CONFIG["max_iterations"],
            system_prompt=AGENT_CONFIG["system_prompt"]
        )

        # 注册工具
        self._register_tools()

        # 检查状态
        self._check_status()

    def _register_tools(self) -> None:
        """
        注册所有工具

        包括：
        - 内置工具（计算器、时间等）
        - 联网搜索工具
        - MCP工具
        - Skill工具
        """
        print("\n注册工具...")

        # 注册内置工具
        self._register_builtin_tools()

        # 注册搜索工具
        self._register_search_tools()

        # 注册MCP工具
        self._register_mcp_tools()

        # 注册Skill工具
        self._register_skill_tools()

        print(f"\n共注册 {len(self.agent.tools)} 个工具")

    def _register_builtin_tools(self) -> None:
        """注册内置工具"""
        # 计算器
        import math

        def calculator(expression: str) -> str:
            try:
                allowed = set('0123456789+-*/.() sqrtpow三角函数')
                if not all(c in allowed or c.isspace() for c in expression):
                    return "错误：表达式包含非法字符"
                result = eval(expression, {"__builtins__": {}, "sqrt": math.sqrt, "pow": pow})
                return f"计算结果：{expression} = {result}"
            except Exception as e:
                return f"计算错误：{e}"

        self.agent.tools.register(
            name="calculator",
            description="执行数学计算。用于计算表达式，如加法、减法、乘法、除法、平方根等。",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如 '2+3*5' 或 'sqrt(16)'"}
                },
                "required": ["expression"]
            },
            func=calculator
        )

        # 获取当前时间
        def get_current_time() -> str:
            from datetime import datetime
            return f"当前时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}"

        self.agent.tools.register(
            name="current_time",
            description="获取当前系统时间。",
            parameters={"type": "object", "properties": {}},
            func=get_current_time
        )

    def _register_search_tools(self) -> None:
        """注册联网搜索工具"""
        try:
            # 导入搜索工具
            search_tools = create_search_tools()
            search_funcs = create_search_functions()

            self.agent.add_tools(search_tools, search_funcs)
            print(f"  + 联网搜索工具: {len(search_tools)} 个")

        except ImportError:
            print("  ! 搜索功能需要安装依赖: pip install duckduckgo-search beautifulsoup4")
            print("  ! 搜索功能暂时不可用")

    def _register_mcp_tools(self) -> None:
        """注册MCP工具"""
        try:
            mcp_tools = create_mcp_tools()
            mcp_funcs = create_mcp_functions()

            self.agent.add_tools(mcp_tools, mcp_funcs)
            print(f"  + MCP工具: {len(mcp_tools)} 个")

        except Exception as e:
            print(f"  ! MCP工具注册失败: {e}")

    def _register_skill_tools(self) -> None:
        """注册Skill工具"""
        try:
            skill_tools = create_skill_tools()
            skill_funcs = create_skill_functions()

            self.agent.add_tools(skill_tools, skill_funcs)
            print(f"  + Skill技能: {len(skill_tools)} 个")

        except Exception as e:
            print(f"  ! Skill注册失败: {e}")

    def _check_status(self) -> None:
        """检查Agent状态"""
        print("\n检查状态...")

        status = self.agent.check_status()

        if not status["ollama_connected"]:
            print("!" * 40)
            print("警告：无法连接到Ollama服务")
            print(f"  请确保Ollama正在运行（{LLM_CONFIG['base_url']}）")
            print("  运行 'ollama serve' 启动服务")
            print("!" * 40)
        else:
            print(f"  ✓ Ollama连接正常")
            print(f"  ✓ 使用模型: {status['model']}")

        print(f"  ✓ 已注册工具: {status['tools_count']} 个")

    def run(self, query: str) -> str:
        """
        运行Agent处理查询

        Args:
            query: 用户查询

        Returns:
            Agent响应
        """
        return self.agent.run(query)

    def chat(self) -> None:
        """
        交互式对话模式
        """
        print("""
╔══════════════════════════════════════════════════════════╗
║              本地AI Agent - 交互式对话                      ║
╠══════════════════════════════════════════════════════════╣
║  可用功能:                                                 ║
║    - 联网搜索（真实网络搜索）                               ║
║    - MCP工具（文件系统、命令执行等）                        ║
║    - Skill技能（研究、代码分析、摘要等）                    ║
║    - 内置工具（计算器、时间查询等）                        ║
║                                                          ║
║  命令:                                                    ║
║    quit / exit - 退出                                     ║
║    reset - 重置对话                                       ║
║    status - 查看状态                                      ║
╚══════════════════════════════════════════════════════════╝
        """)

        while True:
            try:
                user_input = input("\n你: ").strip()

                if not user_input:
                    continue

                # 处理命令
                if user_input.lower() in ["quit", "exit", "q"]:
                    print("再见!")
                    break

                if user_input.lower() == "reset":
                    self.agent.reset()
                    continue

                if user_input.lower() == "status":
                    status = self.agent.check_status()
                    print(f"\n状态: {status['status']}")
                    print(f"模型: {status['model']}")
                    print(f"Ollama: {'已连接' if status['ollama_connected'] else '未连接'}")
                    print(f"工具数: {status['tools_count']}")
                    print("\n已注册工具:")
                    for tool in status['tools']:
                        print(f"  - [{tool['source']}] {tool['name']}: {tool['description'][:50]}...")
                    continue

                # 处理查询
                response = self.run(user_input)
                print(f"\nAgent: {response}")

            except KeyboardInterrupt:
                print("\n\n已退出")
                break
            except Exception as e:
                print(f"\n错误: {e}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="本地AI Agent")
    parser.add_argument("-q", "--query", type=str, help="单次查询模式")
    parser.add_argument("-c", "--chat", action="store_true", help="交互式对话模式")
    args = parser.parse_args()

    # 创建Agent
    agent = LocalAgent()

    if args.query:
        # 单次查询模式
        response = agent.run(args.query)
        print(f"\nAgent: {response}")
    else:
        # 默认交互模式
        agent.chat()


if __name__ == "__main__":
    main()
