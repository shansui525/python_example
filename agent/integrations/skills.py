"""
Skill技能系统模块

Skill是一种高级任务封装，可以包含：
1. 多个步骤的自动化流程
2. 条件判断和循环
3. 与工具系统的深度集成
4. 可配置的参数和行为
"""

import json
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class SkillStep:
    """
    技能步骤

    Attributes:
        name: 步骤名称
        action: 执行的动作类型（tool/mcp/condition/loop）
        params: 步骤参数
        next_on_success: 成功后下一步
        next_on_failure: 失败后下一步
    """
    name: str
    action: str
    params: Dict[str, Any]
    next_on_success: str = "end"
    next_on_failure: str = "end"


@dataclass
class Skill:
    """
    技能定义

    一个Skill包含：
    - name: 技能名称
    - description: 技能描述
    - parameters: 输入参数定义
    - steps: 执行步骤列表
    - execute: 执行函数
    """
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    steps: List[SkillStep] = field(default_factory=list)
    execute: Optional[Callable] = None


class SkillRegistry:
    """
    技能注册表

    管理所有可用的技能，支持：
    - 动态加载skill目录下的技能
    - 技能注册和发现
    - 技能执行和结果处理
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._functions: Dict[str, Callable] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        execute_func: Callable
    ) -> None:
        """
        注册技能

        Args:
            name: 技能名称
            description: 技能描述
            parameters: 参数定义
            execute_func: 执行函数
        """
        skill = Skill(
            name=name,
            description=description,
            parameters=parameters,
            execute=execute_func
        )
        self._skills[name] = skill
        self._functions[name] = execute_func
        print(f"[Skill] 注册技能: {name}")

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取技能定义"""
        return self._skills.get(name)

    def execute(self, name: str, context: Dict[str, Any]) -> str:
        """
        执行技能

        Args:
            name: 技能名称
            context: 执行上下文（包含参数等）

        Returns:
            执行结果
        """
        if name not in self._functions:
            return f"错误：技能 '{name}' 不存在"

        try:
            func = self._functions[name]
            result = func(context)
            return str(result)
        except Exception as e:
            return f"技能执行失败: {str(e)}"

    def list_skills(self) -> List[Dict[str, str]]:
        """列出所有技能"""
        return [
            {
                "name": name,
                "description": skill.description,
                "parameters": str(skill.parameters.get("properties", {}))
            }
            for name, skill in self._skills.items()
        ]

    def load_skills_from_directory(self, directory: Path) -> int:
        """
        从目录加载技能

        目录下应包含skill_*.py文件，每个文件定义一个技能

        Args:
            directory: 技能目录路径

        Returns:
            加载的技能数量
        """
        if not directory.exists():
            print(f"[Skill] 目录不存在: {directory}")
            return 0

        count = 0
        for file in directory.glob("skill_*.py"):
            try:
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(file.stem, file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # 查找注册函数
                    if hasattr(module, "register_skill"):
                        module.register_skill(self)
                        count += 1
                        print(f"[Skill] 加载技能: {file.stem}")

            except Exception as e:
                print(f"[Skill] 加载失败 {file}: {e}")

        return count


def create_skill_tools() -> List[Dict[str, Any]]:
    """
    创建技能工具定义

    Returns:
        工具定义列表
    """
    return [
        {
            "name": "execute_research",
            "description": "执行深度研究任务。搜索多个来源，整理信息并生成综合报告。适用于需要全面了解某个主题的场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "研究主题"
                    },
                    "depth": {
                        "type": "string",
                        "description": "研究深度 (basic/comprehensive)",
                        "default": "basic"
                    }
                },
                "required": ["topic"]
            }
        },
        {
            "name": "analyze_code",
            "description": "分析代码文件。读取代码内容，分析其功能、依赖和潜在问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "代码文件路径"
                    },
                    "analysis_type": {
                        "type": "string",
                        "description": "分析类型 (overview/security/performance)",
                        "default": "overview"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "summarize_text",
            "description": "对长文本进行摘要。提取关键信息，生成简洁的摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要摘要的文本"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "最大摘要长度",
                        "default": 200
                    }
                },
                "required": ["text"]
            }
        }
    ]


def create_skill_functions() -> Dict[str, Callable]:
    """
    创建技能函数

    Returns:
        函数字典
    """
    # 研究技能
    def execute_research(topic: str, depth: str = "basic") -> str:
        """执行研究任务"""
        # 导入搜索工具
        from agent.integrations.web_search import WebSearchTool

        search = WebSearchTool()

        if depth == "comprehensive":
            results = search.search(topic, max_results=10)
            content = search.search_and_scrape(topic, max_results=5)
            return f"深度研究报告 - {topic}\n\n搜索结果:\n{results}\n\n详细内容:\n{content}"
        else:
            results = search.search(topic, max_results=5)
            return f"研究报告 - {topic}\n\n搜索结果:\n{results}"

    # 代码分析技能
    def analyze_code(file_path: str, analysis_type: str = "overview") -> str:
        """分析代码"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read(3000)

            result = f"代码分析报告 - {file_path}\n"
            result += f"分析类型: {analysis_type}\n\n"
            result += f"代码预览:\n```\n{code}\n```\n\n"

            # 简单统计
            lines = code.split("\n")
            result += f"行数: {len(lines)}\n"
            result += f"字符数: {len(code)}\n"

            # 检测语言
            if "def " in code or "class " in code and "import" in code:
                result += "可能语言: Python\n"
            elif "function" in code or "const" in code or "let" in code:
                result += "可能语言: JavaScript/TypeScript\n"
            elif "def " not in code and "fn " in code:
                result += "可能语言: Rust\n"

            return result
        except Exception as e:
            return f"分析失败: {e}"

    # 摘要技能
    def summarize_text(text: str, max_length: int = 200) -> str:
        """生成摘要"""
        # 简单摘要：取前几句和关键点
        sentences = text.split("。")
        summary = sentences[0] if sentences else text[:200]

        if len(summary) > max_length:
            summary = summary[:max_length] + "..."

        return f"文本摘要:\n{summary}\n\n原文长度: {len(text)} 字符"

    return {
        "execute_research": execute_research,
        "analyze_code": analyze_code,
        "summarize_text": summarize_text
    }
