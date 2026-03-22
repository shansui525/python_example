"""
Agent配置文件
定义全局配置项
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# LLM配置
LLM_CONFIG = {
    "model": "qwen3:8b",           # Ollama模型
    "base_url": "http://localhost:11434",  # Ollama地址
    "temperature": 0.7,             # 温度参数
    "timeout": 120,                 # 超时时间（秒）
    "max_tokens": 4096,             # 最大token数
}

# Agent配置
AGENT_CONFIG = {
    "max_iterations": 15,           # 最大循环次数
    "system_prompt": """你是一个智能助手，擅长使用工具来完成任务。

【核心能力】
- 使用搜索工具获取最新信息
- 调用MCP服务获取外部功能
- 执行Skill技能完成特定任务
- 当不确定时，会先搜索确认

【工作流程】
1. 理解用户任务
2. 决定是否需要工具
3. 如需要，选择合适的工具
4. 执行并分析结果
5. 给出最终答案

【重要规则】
- 优先使用搜索获取实时信息
- MCP工具可扩展Agent能力
- Skill用于复杂任务自动化
- 回答简洁准确""",
}

# MCP配置
MCP_CONFIG = {
    "servers_path": PROJECT_ROOT / "mcp_servers",  # MCP服务器目录
    "transport": "stdio",                             # 传输方式
}

# Skill配置
SKILL_CONFIG = {
    "skills_path": PROJECT_ROOT / "skills",          # Skill目录
}

# 搜索配置
SEARCH_CONFIG = {
    "provider": "duckduckgo",        # 搜索提供者
    "max_results": 5,                # 最大结果数
    "timeout": 30,                   # 超时时间
}

# 调试模式
DEBUG = os.getenv("AGENT_DEBUG", "false").lower() == "true"
