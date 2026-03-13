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
    """LLM处理器：用于热点筛选 + 内容创作"""

    def __init__(self, api_key: str = "ollama", base_url: str = "http://localhost:11434/v1",
                 model: str = "qwen3:8b", temperature: float = 1.0):
        if not HAS_OPENAI:
            raise ImportError("请安装 openai 库：pip install openai")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.is_kimi = "kimi" in model.lower()
        print(
            f"[LOG] LLM 初始化完成 -> Model: {model}, BaseURL: {base_url}, Temperature: {temperature}, IsKimi: {self.is_kimi}")

    def _call_api_with_retry(self, messages, max_tokens, timeout, max_retries=2):
        """带指数退避的API调用"""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
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

    def _extract_json(self, content: str) -> Optional[Dict]:
        """智能提取JSON，支持多种格式"""
        print(f"[DEBUG] 原始响应内容: {content[:500]}...")

        try:
            return json.loads(content)
        except:
            pass

        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, content)
        for match in matches:
            try:
                return json.loads(match.strip())
            except:
                continue

        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except:
                pass

        start = content.find('[')
        end = content.rfind(']')
        if start != -1 and end > start:
            try:
                ids = json.loads(content[start:end + 1])
                return {"selected_ids": ids}
            except:
                pass

        print(f"[ERROR] 所有JSON提取方式失败")
        return None

    def select_hot_articles(self, articles: List[Dict[str, Any]], final_limit: int = 25,
                            max_per_feed: int = 8, retry: int = 2) -> List[Dict[str, Any]]:
        """
        第一阶段：AI热点筛选 - 严格强制执行来源分布
        """
        print(f"[LOG] 开始热点筛选：输入文章数={len(articles)}")

        if not articles:
            return []

        # 构建ID到文章对象的映射
        id_to_article = {art.get('id'): art for art in articles if art.get('id')}
        valid_ids = set(id_to_article.keys())
        print(f"[LOG] 构建ID映射: {len(id_to_article)}篇文章，ID范围: {min(valid_ids)}-{max(valid_ids)}")

        # 按来源分组，用于后续强制分布
        feed_groups = defaultdict(list)
        for art in articles:
            feed_groups[art.get('feed_name', 'unknown')].append(art)
        print(f"[LOG] 候选池来源分布: {dict((k, len(v)) for k, v in feed_groups.items())}")

        # 构建输入上下文
        context_lines = []
        for art in articles:
            art_id = art.get('id', 0)
            title = (art.get('title') or '无标题')[:50]
            keywords = (art.get('keywords') or '')[:30]
            feed = (art.get('feed_name') or 'unknown')[:25]
            context_lines.append(f"ID:{art_id}|来源:{feed}|标题:{title}|关键词:{keywords}")

        full_context = "\n".join(context_lines)
        print(f"[LOG] 筛选Prompt长度约={len(full_context)}字符")

        # 增强Prompt - 更严格的约束
        prompt = f"""你是资深科技编辑，从以下{len(articles)}篇文章中筛选出{final_limit}篇最具热点价值的AI/科技资讯。

【筛选标准】
1. 热点价值：AI技术突破、重大发布、争议事件、数据亮眼
2. 来源均衡：严格单一来源不超过{max_per_feed}篇，必须覆盖至少4个不同来源
3. 质量把关：排除非科技/AI主题内容

【文章列表】
{full_context}

【强制约束】
- 只能从上述ID中选择，禁止编造ID
- 单一来源绝对不超过{max_per_feed}篇，这是硬性限制
- 必须覆盖至少4个不同来源
- 优先跨来源选择，避免连续选择同一来源

【输出格式】
严格返回JSON：
{{"selected_ids": [ID1, ID2, ...], "source_dist": {{"来源A": 数量, "来源B": 数量}}}}"""

        for attempt in range(retry):
            try:
                print(f"[LOG] 热点筛选尝试{attempt + 1}/{retry}...")

                response = self._call_api_with_retry(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=800,
                    timeout=120,
                    max_retries=2
                )

                if not response:
                    continue

                content = response.choices[0].message.content.strip()
                print(f"[LOG] 原始响应长度={len(content)}")

                result = self._extract_json(content)

                if result and "selected_ids" in result:
                    selected_ids = result.get("selected_ids", [])
                    print(f"[LOG] AI返回{len(selected_ids)}个ID")

                    # 严格验证ID有效性
                    selected_ids = [int(x) for x in selected_ids if str(x).isdigit()]
                    valid_selected_ids = [aid for aid in selected_ids if aid in valid_ids]
                    invalid_ids = [aid for aid in selected_ids if aid not in valid_ids]

                    if invalid_ids:
                        print(f"[WARN] 过滤{len(invalid_ids)}个无效ID: {invalid_ids[:5]}...")

                    print(f"[LOG] 有效ID: {len(valid_selected_ids)}个")

                    # 获取文章并强制执行分布限制
                    prelim_articles = [id_to_article[aid] for aid in valid_selected_ids]

                    # 强制执行单一来源不超过8篇
                    final_articles = self._enforce_strict_distribution(
                        prelim_articles, articles, final_limit, max_per_feed
                    )

                    # 验证最终分布
                    final_dist = defaultdict(int)
                    for art in final_articles:
                        final_dist[art.get('feed_name', 'unknown')] += 1
                    print(f"[LOG] 最终来源分布: {dict(final_dist)}")

                    # 检查约束
                    max_count = max(final_dist.values()) if final_dist else 0
                    if max_count > max_per_feed:
                        print(f"[WARN] 警告：单一来源{max_count}篇，超过{max_per_feed}篇限制")

                    print(f"[LOG] ✅ 筛选完成: 选中{len(final_articles)}篇")
                    return final_articles

            except Exception as e:
                print(f"[ERROR] 热点筛选异常：{type(e).__name__}: {e}")
                continue

        # 降级
        print(f"[WARN] AI筛选失败，启用均匀分布降级策略")
        return self._fallback_select(articles, final_limit, max_per_feed)

    def _enforce_strict_distribution(self, selected: List[Dict], candidates: List[Dict],
                                     final_limit: int, max_per_feed: int) -> List[Dict]:
        """
        强制执行来源分布限制 - 超标时从其他来源补充
        """
        print(f"[LOG] 强制执行分布限制: 当前{len(selected)}篇，目标{final_limit}篇，单源上限{max_per_feed}")

        # 统计当前分布
        feed_counts = defaultdict(int)
        for art in selected:
            feed_counts[art.get('feed_name', 'unknown')] += 1

        print(f"[LOG] 初始分布: {dict(feed_counts)}")

        result = []
        excess_pool = []  # 超标的文章暂存

        # 第一轮：保留未超标的，收集超标的
        for art in selected:
            feed = art.get('feed_name', 'unknown')
            current_count = sum(1 for a in result if a.get('feed_name', 'unknown') == feed)
            if current_count < max_per_feed:
                result.append(art)
            else:
                excess_pool.append(art)

        if excess_pool:
            print(f"[LOG] 发现{len(excess_pool)}篇超标文章，暂存替换")

        # 从候选池补充其他来源的文章
        selected_ids = {a.get('id') for a in result}
        available = [a for a in candidates if a.get('id') not in selected_ids]

        # 按来源分组可用文章
        available_by_feed = defaultdict(list)
        for art in available:
            available_by_feed[art.get('feed_name', 'unknown')].append(art)

        # 优先从文章少的来源补充
        while len(result) < final_limit:
            current_dist = defaultdict(int)
            for a in result:
                current_dist[a.get('feed_name', 'unknown')] += 1

            # 找出当前文章数最少的来源
            all_feeds = set(available_by_feed.keys()) | set(current_dist.keys())
            sorted_feeds = sorted(all_feeds, key=lambda f: current_dist.get(f, 0))

            added = False
            for feed in sorted_feeds:
                if current_dist.get(feed, 0) >= max_per_feed:
                    continue

                # 获取该来源可用文章，按质量排序
                avail = [a for a in available_by_feed.get(feed, [])
                         if a.get('id') not in {x.get('id') for x in result}]

                if avail:
                    avail.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
                    result.append(avail[0])
                    added = True
                    break

            if not added:
                # 所有来源都到上限了，从超标池取回质量最高的
                if excess_pool and len(result) < final_limit:
                    excess_pool.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
                    result.append(excess_pool.pop(0))
                    print(f"[WARN] 所有来源已达上限，被迫使用超标文章")
                    added = True

                if not added:
                    break

        final_dist = defaultdict(int)
        for a in result:
            final_dist[a.get('feed_name', 'unknown')] += 1
        print(f"[LOG] 强制分布后: {len(result)}篇，分布: {dict(final_dist)}")

        return result

    def _fallback_select(self, articles: List[Dict[str, Any]], final_limit: int = 25,
                         max_per_feed: int = 8) -> List[Dict[str, Any]]:
        """
        降级策略：严格轮询确保均匀分布
        """
        print(f"[LOG] 降级筛选：候选{len(articles)}篇，目标{final_limit}篇，单源上限{max_per_feed}")

        feed_groups = defaultdict(list)
        for art in articles:
            feed = art.get('feed_name', 'unknown')
            feed_groups[feed].append(art)

        # 每个来源按质量排序
        for feed in feed_groups:
            feed_groups[feed].sort(key=lambda x: x.get('quality_score', 0), reverse=True)

        print(f"[LOG] 来源数: {len(feed_groups)}个")

        selected = []
        feed_counts = defaultdict(int)
        round_num = 0

        while len(selected) < final_limit and round_num < 50:
            added_this_round = 0
            # 按当前数量排序，优先从少的来源取
            feeds_sorted = sorted(feed_groups.keys(), key=lambda f: feed_counts[f])

            for feed in feeds_sorted:
                if feed_counts[feed] >= max_per_feed:
                    continue

                # 获取该来源下一篇未选的文章
                already_ids = {a.get('id') for a in selected}
                next_art = None
                for art in feed_groups[feed]:
                    if art.get('id') not in already_ids:
                        next_art = art
                        break

                if next_art:
                    selected.append(next_art)
                    feed_counts[feed] += 1
                    added_this_round += 1

            if added_this_round == 0:
                break
            round_num += 1

        print(f"[LOG] ✅ 降级完成: {len(selected)}篇，分布: {dict(feed_counts)}")
        return selected

    def generate_report_content(self, articles: List[Dict[str, Any]], retry: int = 2) -> Optional[Dict[str, str]]:
        """
        第二阶段：创作标题/开头/结尾
        """
        print(f"[LOG] 开始内容创作：输入文章数={len(articles)}")

        if not articles:
            return None

        context_lines = []
        for i, art in enumerate(articles):
            summary = art.get('summary', '')
            if '---QUALITY---' in summary:
                summary = summary.split('---QUALITY---')[0].strip()
            summary = summary[:120]
            title = (art.get('title') or '无标题')[:40]
            text = f"{i + 1}.{title}|{summary}"
            context_lines.append(text)

        full_context = "\n".join(context_lines)
        print(f"[LOG] 创作Prompt长度约={len(full_context)}字符")

        # 爆款标题Prompt - 去除方括号，更直接
        prompt = f"""你是顶级科技媒体主编，基于以下{len(articles)}篇文章创作10w+爆款AI日报。

【参考文章】
{full_context}

【输出要求】
严格返回JSON，不要任何其他文字：

{{"main_title":"🚨 AI日报｜15字内冲突标题带数字如70%代码AI写人类末日降临","intro":"钩子段落2-3句带数字冲突引发好奇\\n\\n本期核心炸点：\\n\\n🔥 **事件1**（数字+冲突）\\n\\n🔥 **事件2**（数字+冲突）\\n\\n🔥 **事件3**（数字+冲突）\\n\\n🔥 **事件4**（数字+冲突）","outro":"趋势总结+扎心金句+反问"}}

【爆款要素】
- 数字具体：70%、1600人、4000美元、22个漏洞
- 动词暴力：碾压、崩塌、失控、实锤、曝光、封杀
- 制造对立：AI vs 人类、效率 vs 失业、自动化 vs 伦理
- 标题不带方括号，直接陈述冲突"""

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
                print(f"[LOG] 原始响应长度={len(content)}")
                print(f"[LOG] 原始响应前300字: {content[:300]}")

                result = self._extract_json(content)

                if result and result.get("main_title") and result.get("intro") and result.get("outro"):
                    # 清理标题中的方括号
                    main_title = result.get("main_title", "")
                    main_title = re.sub(r'[\[\]]', '', main_title)  # 去除方括号
                    result["main_title"] = main_title

                    print(f"[LOG] ✅ 创作成功: {main_title[:40]}...")
                    intro_preview = result.get("intro", "")[:150].replace('\n', ' ')
                    print(f"[LOG] intro预览: {intro_preview}...")
                    return result

            except Exception as e:
                print(f"[ERROR] 创作异常：{type(e).__name__}: {e}")
                continue

        return None


class DailyReportGenerator:
    def __init__(self, db_path: str = "rss_data.db", use_llm: bool = True,
                 llm_config: Dict = None, temperature: float = 1.0):
        self.db_path = db_path
        self.today_str = date.today().strftime("%Y-%m-%d")
        self.report_date_str = date.today().strftime("%Y.%m.%d")
        self.weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
        self.weekday = self.weekday_map[date.today().weekday()]

        self.use_llm = use_llm
        self.temperature = temperature
        self.llm_processor = None

        if use_llm and HAS_OPENAI:
            config = llm_config or {}
            try:
                self.llm_processor = LLMProcessor(
                    api_key=config.get("api_key", "ollama"),
                    base_url=config.get("base_url", "http://localhost:11434/v1"),
                    model=config.get("model", "qwen2.5:7b"),
                    temperature=self.temperature
                )
            except Exception as e:
                print(f"[ERROR] 大模型初始化失败：{e}，将降级为本地模式。")
                self.use_llm = False

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_articles_for_selection(self, max_per_feed: int = 50) -> List[Dict[str, Any]]:
        query = f"""
            WITH ranked AS (
                SELECT 
                    a.id,
                    a.title,
                    a.summary,
                    a.url,
                    a.keywords,
                    a.quality_score,
                    a.quality_recommendation,
                    f.name as feed_name,
                    ROW_NUMBER() OVER (PARTITION BY f.name ORDER BY a.quality_score DESC, a.published_at DESC) as rn
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE date(a.published_at) = date(?)
                  AND a.quality_recommendation IN ('推荐阅读', '强烈推荐', '一般浏览')
                  AND summary IS NOT NULL
                  AND summary NOT LIKE '%格式错误无法解析%'
            )
            SELECT 
                id, title, summary, url, keywords, 
                quality_score, quality_recommendation, feed_name
            FROM ranked 
            WHERE rn <= {max_per_feed}
            ORDER BY feed_name, quality_score DESC
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (self.today_str,))
            articles = [dict(row) for row in cursor.fetchall()]

        print(f"[LOG] 第一阶段数据获取：共{len(articles)}篇")

        feed_dist = defaultdict(int)
        for art in articles:
            feed_dist[art.get('feed_name', 'unknown')] += 1
        print(f"[LOG] 候选池来源分布: {dict(feed_dist)}")

        return articles

    def generate_markdown(self, articles: List[Dict[str, Any]], llm_content: Optional[Dict[str, str]] = None) -> str:
        if not articles:
            return "# 无内容"

        grouped = defaultdict(list)
        for art in articles:
            grouped[art['feed_name']].append(art)
        sorted_feeds = sorted(grouped.keys(), key=lambda x: -len(grouped[x]))

        content = []

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

        if llm_content and llm_content.get('intro'):
            intro = llm_content['intro'].replace('\\n', '\n')
            content.append(intro)
        else:
            content.append("> **你的AI同事，正在偷偷关注市场与技术变革。**")

        content.append("")
        content.append("---")
        content.append("")

        for feed in sorted_feeds:
            content.append(f"## 📰 {feed}")
            content.append("")
            for idx, art in enumerate(grouped[feed], 1):
                title = art.get('title') or '无标题'
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

        print(f"🔍 步骤 1/4: 从数据库获取候选文章...")
        candidate_articles = self.fetch_articles_for_selection(max_per_feed=50)

        if not candidate_articles:
            print("⚠️ 无可用文章。")
            return

        print(f"[LOG] ✅ 获取候选池完成，共{len(candidate_articles)}篇")

        selected_articles = []

        if self.use_llm and self.llm_processor:
            print(f"🤖 步骤 2/4: AI热点筛选（25篇，单源≤8篇）...")
            selected_articles = self.llm_processor.select_hot_articles(
                articles=candidate_articles,
                final_limit=25,
                max_per_feed=8,
                retry=2
            )

            if selected_articles:
                print(f"[LOG] ✅ AI筛选完成，选中{len(selected_articles)}篇")
            else:
                print(f"[WARN] AI筛选返回空，使用降级策略")
        else:
            print(f"⚠️ 步骤 2/4: LLM不可用，使用降级策略...")
            selected_articles = self.llm_processor._fallback_select(candidate_articles, 25, 8)

        # 验证分布
        final_dist = defaultdict(int)
        for art in selected_articles:
            final_dist[art.get('feed_name', 'unknown')] += 1
        print(f"[LOG] 最终来源分布: {dict(final_dist)}")

        max_count = max(final_dist.values()) if final_dist else 0
        if max_count > 8:
            print(f"[ERROR] 严重警告：单一来源{max_count}篇，超过8篇限制！")
        elif len(final_dist) < 3:
            print(f"[WARN] 警告：仅{len(final_dist)}个来源，分布不够分散")

        llm_generated_content = None
        if self.use_llm and self.llm_processor and selected_articles:
            print(f"✍️ 步骤 3/3: LLM创作...")
            llm_generated_content = self.llm_processor.generate_report_content(selected_articles, retry=2)
            if llm_generated_content:
                print(f"[LOG] ✨ 创作成功: {llm_generated_content.get('main_title', '无')[:40]}")
            else:
                print("⚠️ 创作失败，使用默认模板")

        print(f"💾 写入文件...")
        md_content = self.generate_markdown(selected_articles, llm_generated_content)
        filename = f"{self.today_str}-RSS 日报.md"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"🎉 [DONE] 日报已生成：{filepath}")
        print(f"📊 统计：候选{len(candidate_articles)}篇 -> 选中{len(selected_articles)}篇 -> {len(final_dist)}个来源")


if __name__ == "__main__":
    # LLM_CONFIG = {
    #     "api_key": "ollama",
    #     "base_url": "http://localhost:11434/v1",
    #     "model": "qwen3-64k:latest"
    # }
    LLM_CONFIG = {
        "api_key": "sk-D5tJStIDZboeYfSMqMhgNwED3hkwOYRygt3twVsbr0v5UE5I",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2.5"
    }

    USE_LLM = True
    TEMPERATURE = 1.0

    generator = DailyReportGenerator(
        db_path="rss_data.db",
        use_llm=USE_LLM,
        llm_config=LLM_CONFIG if USE_LLM else None,
        temperature=TEMPERATURE
    )
    generator.save_report(output_dir="Daily/Daily")