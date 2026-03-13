import sqlite3
import re
import json
import time
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
import os

try:
    from openai import OpenAI
    from openai import APIConnectionError, AuthenticationError, RateLimitError

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class LLMProcessor:
    """仅用于创作，不参与筛选"""

    def __init__(self, api_key: str = "ollama", base_url: str = "http://localhost:11434/v1", model: str = "qwen3:8b"):
        if not HAS_OPENAI:
            raise ImportError("请安装 openai 库：pip install openai")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.is_kimi = "kimi" in model.lower()
        print(f"[LOG] LLM 初始化完成 -> Model: {model}, BaseURL: {base_url}, IsKimi: {self.is_kimi}")

    def _call_api_with_retry(self, messages, max_tokens, timeout, max_retries=2):
        """带指数退避的API调用"""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=1,
                    max_tokens=max_tokens,
                    timeout=timeout
                )
                return response
            except RateLimitError as e:
                wait_time = (2 ** attempt) + 1
                print(f"[WARN] API限流，{wait_time}秒后重试({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            except Exception as e:
                print(f"[ERROR] API调用异常: {type(e).__name__}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    raise
        return None

    def generate_report_content(self, articles: List[Dict[str, Any]], retry: int = 2) -> Optional[Dict[str, str]]:
        """
        仅创作标题/开头/结尾，Token极简
        """
        print(f"[LOG] 开始创作：输入文章数={len(articles)}")

        # 超压缩上下文
        context_lines = []
        for i, art in enumerate(articles):
            summary = art.get('summary', '')
            if '---QUALITY---' in summary:
                summary = summary.split('---QUALITY---')[0].strip()
            summary = summary[:80]  # 压缩到80字

            text = f"{i + 1}.{art.get('zh_title', art.get('title'))[:35]}|{summary}"
            context_lines.append(text)

        full_context = "\n".join(context_lines)
        print(f"[LOG] Prompt长度约={len(full_context)}字符")

        # 极简Prompt
        prompt = f"""基于以下{len(articles)}篇文章创作AI日报。
{full_context}

输出JSON：
{{"main_title":"🚨 AI日报｜xxx（20字内冲突标题）","intro":"> **钩子**\\n\\n🔥 **标题**：内容\\n\\n🔥 **标题**：内容\\n\\n**一句话反问**","outro":"结尾\\n\\n**一句话**：金句\\n\\n**最后丢个问题**：反问"}}

要求：动词暴力化，数字具体化，换行用\\n\\n。"""

        for attempt in range(retry):
            try:
                print(f"[LOG] 创作尝试{attempt + 1}/{retry}...")

                response = self._call_api_with_retry(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1200,
                    timeout=90,
                    max_retries=2
                )

                if not response:
                    continue

                content = response.choices[0].message.content.strip()
                print(f"[LOG] 响应长度={len(content)}")

                # 提取JSON
                start = content.find('{')
                end = content.rfind('}') + 1
                if start == -1 or end <= start:
                    continue

                result = json.loads(content[start:end])

                if "main_title" in result and "intro" in result and "outro" in result:
                    print(f"[LOG] ✅ 创作成功: {result['main_title'][:35]}...")
                    return result

            except Exception as e:
                print(f"[ERROR] 创作异常：{e}")
                continue

        return None


class DailyReportGenerator:
    def __init__(self, db_path: str = "rss_data.db", use_llm: bool = True, llm_config: Dict = None):
        self.db_path = db_path
        self.today_str = date.today().strftime("%Y-%m-%d")
        self.report_date_str = date.today().strftime("%Y.%m.%d")
        self.weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
        self.weekday = self.weekday_map[date.today().weekday()]

        self.use_llm = use_llm
        self.llm_processor = None

        if use_llm and HAS_OPENAI:
            config = llm_config or {}
            try:
                self.llm_processor = LLMProcessor(
                    api_key=config.get("api_key", "ollama"),
                    base_url=config.get("base_url", "http://localhost:11434/v1"),
                    model=config.get("model", "qwen2.5:7b")
                )
            except Exception as e:
                print(f"[ERROR] 大模型初始化失败：{e}，将降级为本地模式。")
                self.use_llm = False

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_candidates_distributed(self, total_limit: int = 100, max_per_feed: int = 8, final_limit: int = 25) -> \
    List[Dict[str, Any]]:
        """
        SQL层面确保来源分布均衡，直接返回25篇精选
        使用窗口函数ROW_NUMBER()限制每来源数量
        """
        # 第一步：每来源最多取8篇，共取100篇（确保多样性）
        query_distributed = f"""
            WITH ranked AS (
                SELECT 
                    a.*, 
                    f.name as feed_name,
                    ROW_NUMBER() OVER (PARTITION BY f.name ORDER BY a.quality_score DESC) as rn
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE date(a.published_at) = date(?)
                  AND a.quality_recommendation IN ('推荐阅读', '强烈推荐', '一般浏览')
            )
            SELECT * FROM ranked 
            WHERE rn <= {max_per_feed}
            ORDER BY quality_score DESC
            LIMIT {total_limit}
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query_distributed, (self.today_str,))
            candidates = [dict(row) for row in cursor.fetchall()]

        print(f"[LOG] SQL分布式筛选：共{len(candidates)}篇（已限制每来源≤{max_per_feed}篇）")

        # 显示来源分布
        feed_dist = defaultdict(int)
        for art in candidates:
            feed_dist[art.get('feed_name', 'unknown')] += 1
        print(f"[LOG] 来源分布: {dict(feed_dist)}")

        # 第二步：从100篇中取前25篇（质量优先，但来源已均衡）
        # 如果需要更严格的来源控制，可以再用窗口函数
        if len(candidates) > final_limit:
            # 简单取前25，因为来源已经分散
            final_candidates = candidates[:final_limit]
        else:
            final_candidates = candidates

        # 验证最终来源分布
        final_dist = defaultdict(int)
        for art in final_candidates:
            final_dist[art.get('feed_name', 'unknown')] += 1
        print(f"[LOG] 最终{len(final_candidates)}篇来源分布: {dict(final_dist)}")

        return final_candidates

    def generate_markdown(self, articles: List[Dict[str, Any]], llm_content: Optional[Dict[str, str]] = None) -> str:
        if not articles:
            return "# 无内容"

        grouped = defaultdict(list)
        for art in articles:
            grouped[art['feed_name']].append(art)
        sorted_feeds = sorted(grouped.keys(), key=lambda x: -len(grouped[x]))

        content = []

        # 标题
        if llm_content and llm_content.get('main_title'):
            content.append(f"# {llm_content['main_title']}")
        else:
            content.append(f"# 🚨 AI日报｜{self.report_date_str} 科技前沿")

        content.append("")
        content.append(f"**日期**：{self.report_date_str} {self.weekday}")
        content.append(f"**文章数**：{len(articles)}")
        content.append("")
        content.append("---")
        content.append("")

        # 开头
        if llm_content and llm_content.get('intro'):
            intro = llm_content['intro'].replace('\\n', '\n')
            content.append(intro)
        else:
            content.append("> **你的AI同事，正在偷偷关注市场与技术变革。**")

        content.append("")
        content.append("---")
        content.append("")

        # 文章列表
        for feed in sorted_feeds:
            content.append(f"## 📰 {feed}")
            content.append("")
            for idx, art in enumerate(grouped[feed], 1):
                title = art.get('zh_title', art.get('title'))
                summary = art.get('summary', '')
                if '---QUALITY---' in summary:
                    summary = summary.split('---QUALITY---')[0].strip()

                badge = "🌟" if art.get('quality_score', 0) >= 90 else ("⭐" if art.get('quality_score', 0) >= 75 else "")

                content.append(f"### {idx}. {badge} {title}")
                content.append("")
                content.append(f"> {summary[:200]}...")
                content.append("")
                content.append(f"🔗 [原文链接]({art.get('url', '#')})")
                content.append("")
                content.append("---")
            content.append("")

        # 结尾
        content.append("---")
        content.append("")

        if llm_content and llm_content.get('outro'):
            outro = llm_content['outro'].replace('\\n', '\n')
            content.append(outro)
        else:
            content.append("结尾")
            content.append("")
            content.append("**一句话**：技术在狂奔，市场在波动，唯有代码与逻辑永恒。")
            content.append("")
            content.append("**最后丢个问题**：如果AI能自动交易股票，你愿意把多少仓位交给它管理？")

        content.append("")
        content.append("---")
        content.append(f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(content)

    def save_report(self, output_dir: str = "Daily/Daily"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print(f"🚀 [START] 开始生成日报流程...")
        print(f"🔍 步骤 1/2: SQL分布式筛选文章...")

        # SQL直接选出25篇，来源已均衡
        selected_articles = self.fetch_candidates_distributed(
            total_limit=100,
            max_per_feed=8,
            final_limit=25
        )

        if not selected_articles:
            print("⚠️ 无可用文章。")
            return

        print(f"[LOG] ✅ SQL筛选完成，选中{len(selected_articles)}篇")

        llm_generated_content = None

        if self.use_llm and self.llm_processor:
            print(f"✍️ 步骤 2/2: LLM创作标题、开头、结尾...")
            llm_generated_content = self.llm_processor.generate_report_content(selected_articles, retry=2)
            if llm_generated_content:
                print("[LOG] ✨ LLM创作成功")
            else:
                print("⚠️ LLM创作失败，使用默认模板")

        print(f"💾 正在写入文件...")
        md_content = self.generate_markdown(selected_articles, llm_generated_content)
        filename = f"{self.today_str}-RSS 日报.md"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"🎉 [DONE] 日报已生成：{filepath}")


if __name__ == "__main__":
    LLM_CONFIG = {
        "api_key": "sk-D5tJStIDZboeYfSMqMhgNwED3hkwOYRygt3twVsbr0v5UE5I",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2.5"
    }

    USE_LLM = True

    generator = DailyReportGenerator(
        db_path="rss_data.db",
        use_llm=USE_LLM,
        llm_config=LLM_CONFIG if USE_LLM else None
    )
    generator.save_report(output_dir="Daily/Daily")