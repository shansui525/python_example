"""
联网搜索模块
集成真实的网络搜索功能
"""

import requests
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from ddgs import DDGS
from agent.core.messages import Tool
from agent.core.tools import ToolRegistry


class WebSearchTool:
    """
    网络搜索工具

    使用DuckDuckGo进行真实联网搜索
    支持获取搜索结果和网页内容
    """

    def __init__(self, max_results: int = 5):
        """
        初始化搜索工具

        Args:
            max_results: 最大返回结果数
        """
        self.max_results = max_results

    def search(self, query: str, max_results: Optional[int] = None) -> str:
        """
        执行网络搜索

        Args:
            query: 搜索关键词
            max_results: 最大结果数（可选）

        Returns:
            格式化的搜索结果字符串
        """
        if max_results is None:
            max_results = self.max_results

        try:
            results = []
            with DDGS() as ddgs:
                # 执行搜索
                search_results = list(ddgs.text(query, max_results=max_results))

                if not search_results:
                    return f"没有找到关于 '{query}' 的搜索结果"

                # 格式化结果
                for i, result in enumerate(search_results, 1):
                    title = result.get("title", "无标题")
                    href = result.get("href", "")
                    body = result.get("body", "")

                    results.append(f"{i}. {title}")
                    results.append(f"   链接: {href}")
                    results.append(f"   摘要: {body[:200]}...")
                    results.append("")

            return "\n".join(results)

        except Exception as e:
            return f"搜索失败: {str(e)}\n请检查网络连接后重试。"

    def search_and_scrape(self, query: str, max_results: int = 3) -> str:
        """
        搜索并抓取网页内容

        Args:
            query: 搜索关键词
            max_results: 最大抓取页数

        Returns:
            搜索结果和网页内容的组合
        """
        try:
            # 先搜索
            search_result = self.search(query, max_results)

            # 获取第一个结果的详细内容
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=1))
                if results:
                    url = results[0].get("href", "")
                    if url:
                        content = self._scrape_url(url)
                        return f"{search_result}\n\n详细内容:\n{content}"

            return search_result

        except Exception as e:
            return f"搜索抓取失败: {str(e)}"

    def _scrape_url(self, url: str, timeout: int = 10) -> str:
        """
        抓取网页内容

        Args:
            url: 网页URL
            timeout: 超时时间

        Returns:
            网页文本内容（提取主要文字）
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()

            # 解析HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()

            # 获取文本
            text = soup.get_text(separator="\n", strip=True)

            # 清理空行
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            content = "\n".join(lines)

            # 限制长度
            if len(content) > 2000:
                content = content[:2000] + "\n...(内容过长已截断)"

            return content

        except Exception as e:
            return f"无法获取页面内容: {str(e)}"


def create_search_tools() -> List[Dict[str, Any]]:
    """
    创建搜索工具定义

    Returns:
        工具定义列表
    """
    tools = [
        {
            "name": "web_search",
            "description": "执行网络搜索，获取最新的实时信息。适用于查询新闻、事件、人物、公司、产品等任何需要从互联网获取信息的场景。返回搜索结果列表，包含标题、链接和摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题。建议使用具体、明确的搜索词以获得更准确的结果。例如：'今天北京的天气'、'Python web框架比较 2024'。"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回结果数，默认为5条",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "web_scrape",
            "description": "搜索关键词并获取第一个结果的详细内容。适用于需要深入了解某个主题的场景。先执行搜索，找到最相关的页面后抓取详细内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "搜索结果数（默认3）",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    ]
    return tools


def create_search_functions() -> Dict[str, callable]:
    """
    创建搜索工具函数

    Returns:
        函数字典
    """
    search_tool = WebSearchTool()

    return {
        "web_search": search_tool.search,
        "web_scrape": search_tool.search_and_scrape
    }
