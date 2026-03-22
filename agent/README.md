---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 3046022100da230298c3581211b888e51eaa8d47677ff789dafe69e3f07255dea470374a06022100daf5d93d4b2858fe74bebe8d087198c08bc81a9b9be462090f8052b205790fc4
    ReservedCode2: 304402201c11a497a5ece78d0154f28068f15bcb958b277d3df6c15ff2c51d79581c9e9202200f719598843ba2762391b909e96e6cbfcf97c943c941a245b6ef8516c53ab210
---

# 本地AI Agent

一个功能完整的本地AI Agent，基于ReAct模式实现，支持联网搜索、MCP协议集成和Skill技能系统。

## 目录

- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [核心设计](#核心设计)
- [扩展指南](#扩展指南)
- [使用示例](#使用示例)

## 功能特性

### 1. 联网搜索 🌐

- 使用DuckDuckGo进行真实网络搜索
- 支持搜索结果获取和网页内容抓取
- 获取最新、最准确的信息

### 2. MCP协议集成 🔌

- 支持Model Context Protocol标准
- 可连接外部MCP服务器
- 动态发现和调用MCP工具

### 3. Skill技能系统 ⚡

- 高级任务封装
- 支持复杂的多步骤任务
- 内置常用技能（研究、代码分析、摘要等）

### 4. 核心Agent能力 🤖

- 基于ReAct模式（Reasoning + Acting）
- 循环执行直到任务完成
- 完整的对话历史管理
- 工具自动选择和调用

## 快速开始

### 1. 环境要求

- Python 3.8+
- Ollama服务运行中
- 模型：qwen3:8b（已下载）

### 2. 安装依赖

```bash
cd agent
pip install -r requirements.txt
```

### 3. 启动Ollama

```bash
# 拉取模型（如需要）
ollama pull qwen3:8b

# 启动服务
ollama serve
```

### 4. 运行Agent

```bash
# 交互式对话模式
python main.py

# 单次查询模式
python main.py -q "今天北京的天气怎么样？"

# 查看状态
python main.py -c
# 然后输入: status
```

## 项目结构

```
agent/
├── core/                    # 核心模块
│   ├── __init__.py
│   ├── agent.py            # Agent主类
│   ├── llm.py              # LLM封装
│   ├── messages.py         # 消息系统
│   └── tools.py            # 工具注册表
├── integrations/           # 集成模块
│   ├── __init__.py
│   ├── web_search.py       # 联网搜索
│   ├── mcp.py              # MCP协议
│   └── skills.py           # 技能系统
├── mcp_servers/            # MCP服务器配置
├── skills/                # 自定义技能目录
├── config.py              # 配置文件
├── main.py                # 主程序入口
└── requirements.txt       # 依赖清单
```

## 核心设计

### Agent架构

```
┌─────────────────────────────────────────────────────────────┐
│                        LocalAgent                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    Agent Core                       │   │
│  │  ┌───────────┐  ┌───────────┐  ┌─────────────────┐  │   │
│  │  │   LLM     │  │   Tools   │  │ Message History │  │   │
│  │  │ (Ollama)  │  │ Registry  │  │                 │  │   │
│  │  └─────┬─────┘  └─────┬─────┘  └────────┬────────┘  │   │
│  └────────┼──────────────┼─────────────────┼───────────┘   │
│           │              │                 │               │
│  ┌────────▼──────────────▼─────────────────▼───────────┐  │
│  │                   ReAct 循环                         │  │
│  │  1. Think (LLM思考)                                 │  │
│  │  2. Act (如需工具则调用)                             │  │
│  │  3. Observe (获取结果)                               │  │
│  │  4. Loop until done                                 │  │
│  └─────────────────────────────────────────────────────┘  │
│           │                                               │
│  ┌────────▼───────────────────────────────────────────┐  │
│  │                 工具集成层                          │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │  │
│  │  │  搜索    │ │   MCP    │ │  Skill   │            │  │
│  │  │ WebSearch│ │          │ │          │            │  │
│  │  └──────────┘ └──────────┘ └──────────┘            │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### ReAct工作流

```
用户: "搜索Python的最新动态"

┌─────────────────────────────────────────────────────────────┐
│ 迭代 1                                                       │
├─────────────────────────────────────────────────────────────┤
│  1. Think: 用户需要搜索信息，应该调用web_search工具           │
│  2. Act: 调用 web_search(query="Python最新动态")              │
│  3. Observe: 获取搜索结果列表                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 迭代 2                                                       │
├─────────────────────────────────────────────────────────────┤
│  1. Think: 已获取搜索结果，可以整理回答用户                   │
│  2. Act: 无需更多工具，直接回答                               │
│  3. Observe: 回答完成，结束循环                              │
└─────────────────────────────────────────────────────────────┘

Agent: 最新的Python动态包括...
```

## 扩展指南

### 添加新工具

在对应的集成模块中注册工具：

```python
# 在 integrations/xxx.py 中定义
def my_tool(param1: str, param2: int) -> str:
    """工具实现"""
    return f"处理结果: {param1}, {param2}"

# 创建工具定义
def create_my_tools():
    return [{
        "name": "my_tool",
        "description": "我的自定义工具",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
                "param2": {"type": "integer"}
            },
            "required": ["param1"]
        }
    }]

def create_my_functions():
    return {"my_tool": my_tool}

# 在 main.py 中注册
my_tools = create_my_tools()
my_funcs = create_my_functions()
agent.add_tools(my_tools, my_funcs)
```

### 添加MCP服务器

```python
from integrations.mcp import MCPClient

mcp = MCPClient()
mcp.add_server_from_config(
    name="my_server",
    command="npx",
    args=["-y", "@mcp/server-package"]
)

# 发现工具
tools = mcp.discover_tools("my_server")
functions = mcp.get_functions()
agent.add_tools(tools, functions)
```

### 添加Skill技能

在 `skills/` 目录下创建 `skill_xxx.py`：

```python
# skills/skill_xxx.py

def register_skill(registry):
    """注册技能的入口函数"""
    registry.register(
        name="my_skill",
        description="我的技能描述",
        parameters={
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        },
        execute_func=my_skill_execute
    )

def my_skill_execute(context):
    """技能执行函数"""
    input_data = context.get("input", "")
    # 处理逻辑
    return f"处理结果: {input_data}"
```

## 使用示例

### 基础对话

```
你: 你好
Agent: 你好！有什么可以帮助你的吗？
```

### 联网搜索

```
你: 搜索一下今天有什么重大新闻
Agent: [联网搜索后返回新闻列表]
```

### 使用MCP工具

```
你: 帮我读取 /tmp/test.txt 文件的内容
Agent: [调用 filesystem_read 工具读取文件]
```

### 使用Skill技能

```
你: 帮我研究一下人工智能的发展历史
Agent: [调用 execute_research 技能进行深度研究]
```

## 配置说明

编辑 `config.py` 修改配置：

```python
LLM_CONFIG = {
    "model": "qwen3:8b",           # 使用的模型
    "base_url": "http://localhost:11434",  # Ollama地址
    "temperature": 0.7,
    "timeout": 120,
}

AGENT_CONFIG = {
    "max_iterations": 15,         # 最大循环次数
    "system_prompt": "...",       # 系统提示词
}
```

## 故障排除

### Ollama连接失败

```bash
# 检查Ollama是否运行
curl http://localhost:11434/api/tags

# 启动Ollama
ollama serve

# 拉取模型
ollama pull qwen3:8b
```

### 搜索功能不可用

```bash
pip install duckduckgo-search beautifulsoup4
```

### 导入错误

```bash
# 确保在项目根目录
cd /workspace/agent
python main.py
```

## License

MIT License
