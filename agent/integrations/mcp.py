"""
MCP协议集成模块

MCP (Model Context Protocol) 是一个标准化协议，
允许Agent与外部工具服务进行通信。

本模块实现：
1. MCP服务器管理
2. 工具发现和注册
3. 工具调用
"""

import json
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass


@dataclass
class MCPServer:
    """
    MCP服务器定义

    Attributes:
        name: 服务器名称
        command: 启动命令
        args: 命令参数
        env: 环境变量
    """
    name: str
    command: str
    args: List[str]
    env: Dict[str, str] = None


class MCPClient:
    """
    MCP客户端

    负责：
    - 管理MCP服务器连接
    - 发现服务器提供的工具
    - 调用服务器工具

    工作原理：
    MCP使用JSON-RPC over stdio进行通信。
    发送请求到服务器，接收工具列表或执行结果。
    """

    def __init__(self):
        self._servers: Dict[str, MCPServer] = {}
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._processes: Dict[str, subprocess.Popen] = {}

    def add_server(self, server: MCPServer) -> None:
        """
        添加MCP服务器

        Args:
            server: MCP服务器配置
        """
        self._servers[server.name] = server
        print(f"[MCP] 添加服务器: {server.name}")

    def add_server_from_config(self, name: str, command: str,
                               args: List[str] = None,
                               env: Dict[str, str] = None) -> None:
        """
        从配置添加MCP服务器

        Args:
            name: 服务器名称
            command: 命令路径
            args: 命令参数
            env: 环境变量
        """
        server = MCPServer(
            name=name,
            command=command,
            args=args or [],
            env=env or {}
        )
        self.add_server(server)

    def discover_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        发现服务器提供的工具

        Args:
            server_name: 服务器名称

        Returns:
            工具定义列表
        """
        if server_name not in self._servers:
            print(f"[MCP] 服务器 '{server_name}' 不存在")
            return []

        server = self._servers[server_name]

        try:
            # 启动服务器进程
            process = subprocess.Popen(
                [server.command] + server.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**server.env}
            )

            # 发送工具列表请求 (JSON-RPC)
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list"
            }

            process.stdin.write(json.dumps(request).encode() + b"\n")
            process.stdin.flush()

            # 读取响应
            response_line = process.stdout.readline()
            response = json.loads(response_line.decode())

            process.terminate()

            # 解析工具列表
            tools = []
            if "result" in response and "tools" in response["result"]:
                for tool in response["result"]["tools"]:
                    tool_def = {
                        "name": tool.get("name"),
                        "description": tool.get("description"),
                        "parameters": tool.get("inputSchema", {})
                    }
                    tools.append(tool_def)
                    self._tools[tool["name"]] = tool_def

            return tools

        except Exception as e:
            print(f"[MCP] 发现工具失败: {e}")
            return []

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        调用MCP工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        # 找到工具所属服务器
        # 这里简化处理，实际应该从工具元数据中获取服务器信息

        # 遍历所有服务器尝试调用
        for server_name, server in self._servers.items():
            try:
                result = self._call_server_tool(server, tool_name, arguments)
                return result
            except:
                continue

        return f"错误：未找到工具 '{tool_name}' 或服务器不可用"

    def _call_server_tool(self, server: MCPServer,
                         tool_name: str,
                         arguments: Dict[str, Any]) -> str:
        """
        向服务器发送工具调用请求

        Args:
            server: MCP服务器
            tool_name: 工具名称
            arguments: 参数

        Returns:
            工具执行结果
        """
        process = subprocess.Popen(
            [server.command] + server.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**server.env}
        )

        # 发送调用请求
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        process.stdin.write(json.dumps(request).encode() + b"\n")
        process.stdin.flush()

        # 读取响应
        response_line = process.stdout.readline()
        response = json.loads(response_line.decode())

        process.terminate()

        if "result" in response:
            content = response["result"].get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", str(response["result"]))
            return str(response["result"])
        elif "error" in response:
            return f"工具调用错误: {response['error']}"

        return "未知响应"

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有已发现的工具"""
        return list(self._tools.values())

    def get_functions(self, tool_map: Dict[str, str] = None) -> Dict[str, Callable]:
        """
        获取可调用的函数映射

        Args:
            tool_map: 工具名称映射 {tool_name: function_name}

        Returns:
            函数字典
        """
        functions = {}
        for tool_name, tool_def in self._tools.items():
            func_name = tool_map.get(tool_name, tool_name) if tool_map else tool_name

            # 创建一个包装函数
            def make_wrapper(name):
                def wrapper(**kwargs):
                    return self.call_tool(name, kwargs)
                return wrapper

            functions[func_name] = make_wrapper(tool_name)

        return functions


class MCPToolWrapper:
    """
    MCP工具包装器

    将MCP工具转换为Agent可用的格式
    """

    @staticmethod
    def convert_to_tools(mcp_tools: List[Dict[str, Any]],
                        prefix: str = "") -> List[Dict[str, Any]]:
        """
        转换MCP工具为标准格式

        Args:
            mcp_tools: MCP工具列表
            prefix: 工具名称前缀

        Returns:
            标准格式工具列表
        """
        tools = []
        for tool in mcp_tools:
            name = f"{prefix}{tool['name']}" if prefix else tool["name"]
            tools.append({
                "name": name,
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object"})
            })
        return tools


def create_mcp_tools() -> List[Dict[str, Any]]:
    """
    创建示例MCP工具定义

    实际使用时，应从MCP服务器动态发现

    Returns:
        工具定义列表
    """
    # 这里定义一些常见的MCP工具模板
    # 实际工具应通过MCP服务器的发现机制获取
    return [
        {
            "name": "filesystem_read",
            "description": "读取文件内容。当需要查看代码、文档或配置文件时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"}
                },
                "required": ["path"]
            }
        },
        {
            "name": "filesystem_write",
            "description": "写入内容到文件。用于创建或修改文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "文件内容"}
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "bash_execute",
            "description": "执行bash命令。用于运行系统命令。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"}
                },
                "required": ["command"]
            }
        }
    ]


def create_mcp_functions() -> Dict[str, Callable]:
    """
    创建MCP工具函数

    Returns:
        函数字典
    """
    # 本地实现这些MCP工具
    def filesystem_read(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read(5000)  # 限制读取长度
                return f"文件内容 ({path}):\n{content}"
        except Exception as e:
            return f"读取失败: {e}"

    def filesystem_write(path: str, content: str) -> str:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"成功写入: {path}"
        except Exception as e:
            return f"写入失败: {e}"

    def bash_execute(command: str) -> str:
        import subprocess
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout if result.stdout else result.stderr
            return f"执行结果:\n{output[:2000]}"
        except subprocess.TimeoutExpired:
            return "命令执行超时"
        except Exception as e:
            return f"执行失败: {e}"

    return {
        "filesystem_read": filesystem_read,
        "filesystem_write": filesystem_write,
        "bash_execute": bash_execute
    }
