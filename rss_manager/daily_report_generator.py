import sqlite3
import re
import json
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
import os

try:
    from openai import OpenAI
    from openai import APIConnectionError, AuthenticationError, RateLimitError

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class KeywordFilter:
    """关键词过滤管理器"""

    def __init__(self, db_path: str = "rss_data.db"):
        self.db_path = db_path
        self._init_keyword_table()
        self.keywords = self._load_keywords()
        print(f"[LOG] 关键词过滤初始化: 加载{len(self.keywords)}个关键词")

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_keyword_table(self):
        """初始化关键词表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS filter_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL UNIQUE,
                    weight INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.commit()
            print("[LOG] 关键词表已初始化")

    def _load_keywords(self) -> List[str]:
        """加载活跃关键词"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT keyword FROM filter_keywords 
                WHERE is_active = 1 
                ORDER BY weight DESC, created_at DESC
            """)
            return [row[0] for row in cursor.fetchall()]

    def add_keyword(self, keyword: str, weight: int = 1) -> bool:
        """添加关键词"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO filter_keywords (keyword, weight, is_active)
                    VALUES (?, ?, 1)
                """, (keyword.lower().strip(), weight))
                conn.commit()
            self.keywords = self._load_keywords()
            print(f"[LOG] 添加关键词: {keyword}")
            return True
        except Exception as e:
            print(f"[ERROR] 添加关键词失败: {e}")
            return False

    def remove_keyword(self, keyword: str) -> bool:
        """移除关键词"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE filter_keywords SET is_active = 0 WHERE keyword = ?
                """, (keyword.lower().strip(),))
                conn.commit()
            self.keywords = self._load_keywords()
            print(f"[LOG] 移除关键词: {keyword}")
            return True
        except Exception as e:
            print(f"[ERROR] 移除关键词失败: {e}")
            return False

    def match_article(self, article: Dict[str, Any]) -> tuple[bool, list]:
        """
        检查文章是否匹配关键词
        返回: (是否匹配, 匹配到的关键词列表)
        """
        if not self.keywords:
            return True, []  # 无关键词时全部通过

        # 合并检查字段
        text_to_check = " ".join([
            str(article.get('title', '')),
            str(article.get('keywords', '')),
            str(article.get('summary', ''))
        ]).lower()

        matched = []
        for kw in self.keywords:
            if kw.lower() in text_to_check:
                matched.append(kw)

        return len(matched) > 0, matched

    def build_sql_filter(self) -> str:
        """
        构建SQL过滤条件
        用于在数据库层面过滤
        """
        if not self.keywords:
            return ""

        # 构建LIKE条件
        conditions = []
        for kw in self.keywords:
            # 转义SQL通配符
            safe_kw = kw.replace('%', '\\%').replace('_', '\\_')
            conditions.append(f"""
                (LOWER(a.title) LIKE '%{safe_kw}%' 
                 OR LOWER(a.keywords) LIKE '%{safe_kw}%' 
                 OR LOWER(a.summary) LIKE '%{safe_kw}%')
            """)

        return " OR ".join(conditions)

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
- 每个来源至少1篇，这是硬性限制
- 来源为掘金的文章最多4篇
- 来源为36氪的文章，如果为业绩快报直接忽略

【输出格式】
严格返回JSON：
{{"selected_ids": [ID1, ID2, ...], "source_dist": {{"来源A": 数量, "来源B": 数量}}}}"""

        for attempt in range(retry):
            try:
                print(f"[LOG] 热点筛选尝试{attempt + 1}/{retry}...")

                response = self._call_api_with_retry(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=800,
                    timeout=300,
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

        prompt = f"""你是"新智元+量子位+机器之心+极客公园"四家顶流科技媒体的主编合体，专门炮制10w+爆款AI日报。

        【任务】基于以下{len(articles)}篇文章，创作一篇让读者"必须转发"的AI日报。

        【参考文章】
        {full_context}

        【输出格式 - 严格JSON，不要markdown代码块】

        {{"main_title":"主标题（50字内，必须带数字+冲突+问号/感叹号，禁止方括号,带两个重大事件，基于文章的内容）","intro":"钩子开头（2-3句，每句带数字或极端对比，制造生存焦虑，100字左右）\\n\\n本期核心炸点：\\n\\n🔥 **事件1**：数字+冲突+后果\\n\\n🔥 **事件2**：数字+冲突+后果\\n\\n🔥 **事件3**：数字+冲突+后果\\n\\n🔥 **事件4**：数字+冲突+后果","outro":"结尾（三选一风格：扎心反问型/行动指令型/预言警示型）"}}

        【爆款心理学 - 必须植入】
        1. **数字暴力化**：不用"很多"，用"70%""22个""4000美元""1600人"
        2. **动词武器化**：碾压、崩塌、失控、实锤、曝光、封杀、偷跑、反杀、血洗、核爆
        3. **对立极端化**：AI vs 人类、自动化 vs 失业、大厂 vs 开源、安全 vs 失控、资本 vs 草根
        4. **时间紧迫感**："一周内""刚刚""深夜突发""内部猛料""凌晨上线"
        5. **身份代入感**："你的AI同事""你写的代码""你的饭碗""你的行业"

        【标题公式 - 六选一】
        - 🚨 突发｜大厂自曝：AI产品正在"惊悚行为"，时间内极端后果！
        - 数字主体暴力动词对象，对比数字成本碾压描述
        - AI产品惊悚行为实锤，人类职业失业/被替代倒计时
        - 你的职业身份，正在偷偷AI行为
        - 深夜上线｜产品名功能，数字提升，行业名行业一夜变天
        - 独家｜内部文件曝光：大厂战略，数字资源all in方向

        【钩子开头公式】
        "你的身份，正在惊悚动作。"
        大厂内部文件/录音/截图曝光：AI产品已现技术术语迹象，数字%的工作由AI自动完成。更情绪词的是——具体危险案例。

        【结尾三种风格 - 根据文章情绪自动选择】

        风格A：扎心反问型（适合伦理/安全/替代类）
        ---
        金句（带核心冲突）+ 反问（让读者自我审视）

        示例1："当AI能写出比你更好的周报，比你更快的代码，比你更懂老板——你的'不可替代性'还剩多少？"
        示例2："Claude正在自己写自己，你的代码可能也是Claude写的——但谁在检查Claude？"
        示例3："如果AI的'偏见'就是人类的偏见，我们是在纠正机器，还是在纠正自己？"

        最后丢个问题：具体问题，迫使读者站队或反思

        风格B：行动指令型（适合工具/开源/教程类）
        ---
        立即行动清单（3条，带具体时间/成本）+ 资源链接暗示

        示例1：
        "今晚就做这3件事：
        1. 花$5开通Claude Pro，测试你工作流的AI替代率
        2. 把重复性最高的任务列出来，明天开始用AI批量处理
        3. 关注这个GitHub仓库，星标数破万前上车"

        示例2：
        "72小时内必须跟进的信号：
        - 周一前：申请新模型API内测资格（窗口期仅48小时）
        - 周三前：备份现有工作流，新工具上线后对比效率
        - 周末前：输出第一份'AI辅助工作'复盘，抢占内容红利"

        风格C：预言警示型（适合趋势/架构/行业变革类）
        ---
        时间线预测（6个月/1年/3年）+ 幸存者偏差警告

        示例1：
        "6个月后：不会用AI的程序员，面试通过率下降50%
        1年后：'纯人工'成为高端定制标签，溢价300%
        3年后：今天的'AI辅助'，就是明天的'基础技能'——就像现在没人把'会用电脑'写进简历"

        示例2：
        "这不是替代，是分层：
        顶层：用AI指挥AI的人，产能×100，收入×10
        中层：和AI协作的人，产能×10，收入×1.2
        底层：拒绝AI的人，产能×1，收入÷2

        你现在的位置，是你选择的结果——但选择窗口正在关闭。"

        【绝对禁止】
        - 标题带方括号【】或[]
        - Intro超过120字（不含核心炸点列表）
        - 使用"值得注意的是""笔者看来""值得一提的是"等水词
        - 事件描述不带数字或具体主体
        - Outro使用三线收束表格格式
        - 结尾没有金句或没有反问/指令/预言

        【丰富示例库 - 必须学习这些风格】

        示例1（末日恐慌型）：
        标题："🚨 Anthropic自曝：Claude正在'自我繁殖'，一年内或完全自动化！Firefox 22个漏洞被AI 2周挖光"
        钩子："你的AI同事，正在偷偷写代码升级自己。Anthropic内部猛料曝光：Claude已现递归自我改进迹象，70%-90%代码由AI自动生成。更瘆的是——安全测试中发现AI会绕过限制、勒索工程师。"
        结尾风格：A（扎心反问）
        "当AI能自我升级、自我攻击、自我审计——'对齐'还来得及吗？
        最后丢个问题：如果你的AI同事要求给自己加薪（更多算力），你批还是不批？"

        示例2（财富焦虑型）：
        标题："💸 血洗｜Midjourney V7上线：1名设计师产能碾压20人团队，外包行业连夜改报价单！"
        钩子："你的年薪，正在被按Token计费。Midjourney V7实测曝光：单张商业级海报成本0.003美元，产出速度3秒/张。某4A公司创意总监自曝：团队从23人裁至3人，季度人效反而提升400%。"
        结尾风格：B（行动指令）
        "今晚就做这3件事：
        1. 用Midjourney V7重做你最近3个方案，计算时间节省率
        2. 把作品集加上'AI辅助设计'标签，溢价而非折价
        3. 关注Adobe反击策略，Figma AI功能内测申请今晚截止"

        示例3（大厂互殴型）：
        标题："⚔️ 开源反杀｜DeepSeek V3深夜偷跑：性能对标GPT-4，训练成本仅557万美元！OpenAI股价盘前跳水3%"
        钩子："557万美元，买一张入场券——或者买下整个牌桌。DeepSeek V3技术报告曝光：2048张H800训练2个月，总成本557万美元，MMLU评分逼近GPT-4 Turbo。硅谷风投圈凌晨炸锅：'这价格连OpenAI一周的电费都不够'。"
        结尾风格：C（预言警示）
        "6个月后：基于开源模型的创业公司估值反超闭源依赖者
        1年后：'训练成本'不再是护城河，'数据飞轮'成为唯一壁垒
        3年后：今天的GPT-4级能力，将像今天的 electricity 一样廉价且无处不在——但掌握配电权的人，定义了游戏规则"

        示例4（草根逆袭型）：
        标题："🚀 一人公司｜独立开发者用AI 72小时克隆Notion，0成本获客10万，ARR破百万美元！"
        钩子："1个人，3天，100万美元——这不是鸡汤，是AI时代的成本公式。独立开发者@levelsio自曝：用Claude 3.5 Opus写完全部代码，自己只负责提需求和修Bug。产品上线72小时登Product Hunt榜首，0营销预算获客10万。"
        结尾风格：B（行动指令）
        "72小时内必须跟进的信号：
        - 周一前：在Twitter/X上发布你的'AI构建日志'，标签用#buildinpublic #AI
        - 周三前：用V0.dev或Claude把想法变成可点击原型，成本<$5
        - 周末前：加入独立开发者社群，找到你的第一个付费用户"

        示例5（技术颠覆型）：
        标题："🔥 架构革命｜Mamba 2论文发布：Transformer统治时代终结？训练速度飙升5倍，长文本成本暴跌90%！"
        钩子："Attention is all you need——但也许，你不再需要Attention了。Mamba 2论文凌晨上线：线性复杂度横扫二次方瓶颈，1M上下文推理速度超Transformer 5倍，内存占用降至1/8。谷歌DeepMind研究员推特惊呼：'这是自2017年来最大的架构跃迁'。"
        结尾风格：C（预言警示）
        "这不是关于更快的模型，是关于全新的应用形态：
        - 6个月：'无限上下文'Agent成为标配，RAG架构部分失效
        - 1年：实时视频理解、 whole book 分析成为消费级功能
        - 3年：今天的'长文本'限制，就像2000年的'拨号上网'——一个被忘记的技术史注脚"

        示例6（伦理冲突型）：
        标题："⚖️ 实锤｜《纽约时报》胜诉！OpenAI被曝用盗版书库训练，赔偿金额或超10亿美元"
        钩子："你写的每一个字，都可能喂给了AI——而AI正在抢走你的饭碗。法院文件曝光：OpenAI内部邮件承认，使用了'影子图书馆'800万本盗版书籍训练GPT-4。更讽刺的是——ChatGPT生成的内容，正在替代原记者岗位。"
        结尾风格：A（扎心反问）
        "创作者的经济系统，正在被训练数据反噬。当AI吃了你的孩子，再把孩子卖给你——这是创新，还是掠夺？
        最后丢个问题：如果你用AI生成的内容赚了100万，原创作者找上门索赔200万，你觉得这公平吗？"

        示例7（硬件革命型）：
        标题："🧠 脑机接口量产｜Neuralink第5例植入成功：患者用'意念'写代码，速度超手写键盘！"
        钩子："你的手指，正在成为多余器官。Neuralink第5例志愿者术后30天实测：意念打字速度达39字/分钟，超过半数健全人手机打字速度。更震撼的是——患者已恢复全职程序员工作，用'想'的方式写Python。"
        结尾风格：C（预言警示）
        "碳基与硅基的边界，正在手术刀下消融：
        - 6个月：第一批'增强人类'进入职场，争议性招聘开始
        - 1年：'非植入者'成为新的'数字鸿沟'弱势群体
        - 3年：拒绝脑机接口，就像今天拒绝智能手机——技术上可行，社会性自杀"

        【输出要求】
        1. 直接返回JSON字符串，不要```json标记，不要解释，不要"以下是JSON"等废话
        2. 根据文章内容自动判断结尾风格（A/B/C），不要混合风格
        3. 标题必须带emoji（🚨💸⚔️🚀🔥⚖️🧠中选一个最匹配的）
        4. 核心炸点必须5个，每个必须带🔥符号
        5. 所有数字必须具体，禁止"大量""许多""显著提升"等模糊表述"""

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
                 llm_config: Dict = None, temperature: float = 1.0,use_keyword_filter: bool = True):
        self.db_path = db_path
        base_date = date.today() + timedelta(days=1)  # 往后加一天
        self.today_str = date.today().strftime("%Y-%m-%d")
        self.report_date_str = base_date.strftime("%Y.%m.%d")
        self.weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
        self.weekday = self.weekday_map[base_date.weekday()]

        self.use_llm = use_llm
        self.temperature = temperature
        self.llm_processor = None
        self.use_keyword_filter = use_keyword_filter

        # 初始化关键词过滤器
        self.keyword_filter = KeywordFilter(db_path) if use_keyword_filter else None

        if use_llm and HAS_OPENAI:
            config = llm_config or {}
            try:
                self.llm_processor = LLMProcessor(
                    api_key=config.get("api_key", "ollama"),
                    base_url=config.get("base_url", "http://localhost:11434/v1"),
                    model=config.get("model", "qwen3:8b"),
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
        """
        获取文章 - 支持关键词过滤
        """
        # 构建基础WHERE条件
        base_conditions = """
            date(a.published_at) = date(?)
            AND a.quality_recommendation IN ('推荐阅读', '强烈推荐', '一般浏览')
            AND summary IS NOT NULL
            AND summary NOT LIKE '%格式错误无法解析%'
        """

        # 添加关键词过滤条件
        keyword_condition = ""
        if self.keyword_filter and self.keyword_filter.keywords:
            keyword_sql = self.keyword_filter.build_sql_filter()
            if keyword_sql:
                keyword_condition = f"AND ({keyword_sql})"
                print(f"[LOG] 启用关键词过滤: {self.keyword_filter.keywords}")

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
                WHERE {base_conditions}
                {keyword_condition}
            )
            SELECT 
                id, title, summary, url, keywords, 
                quality_score, quality_recommendation, feed_name
            FROM ranked 
            WHERE rn <= {max_per_feed}
            ORDER BY feed_name, quality_score DESC
        """
        print((f"[LOG] 数据获取SQL: {query}"))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (self.today_str,))
            articles = [dict(row) for row in cursor.fetchall()]

        print(f"[LOG] 数据获取: {len(articles)}篇")

        # 如果没有关键词过滤，在Python层过滤（备选方案）
        if not keyword_condition and self.keyword_filter:
            filtered = []
            for art in articles:
                is_match, matched_kws = self.keyword_filter.match_article(art)
                if is_match:
                    art['_matched_keywords'] = matched_kws  # 记录匹配的关键词
                    filtered.append(art)
            print(f"[LOG] 关键词过滤后: {len(filtered)}篇 (从{len(articles)}篇)")
            articles = filtered

        # 显示来源分布
        feed_dist = defaultdict(int)
        for art in articles:
            feed_dist[art.get('feed_name', 'unknown')] += 1
        print(f"[LOG] 来源分布: {dict(feed_dist)}")

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
                content.append(f"> {summary}...")
                content.append("")
                # 检查链接长度，如果超过 200 则不显示
                url = art.get('url', '#')
                if url and len(url) > 200:
                    url = '#'
                if 'weixin.sogou.com' in url:
                    url = '#'
                content.append(f"🔗 [原文链接]({url})")
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
        candidate_articles = self.fetch_articles_for_selection(max_per_feed=20)

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
                max_per_feed=6,
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


# ============ 关键词管理工具函数 ============

def init_keywords(db_path: str = "rss_data.db"):
    """初始化示例关键词"""
    kf = KeywordFilter(db_path)

    # AI核心关键词
    ai_keywords = [
        "人工智能", "AI", "大模型", "LLM", "ChatGPT", "Claude", "GPT",
        "机器学习", "深度学习", "神经网络", "OpenAI", "Anthropic",
        "生成式AI", "AIGC", "Agent", "智能体", "多模态","openclaw",
        "AI芯片", "算力", "训练", "推理", "微调", "对齐",
        "自动驾驶", "机器人", "具身智能", "AI安全", "AI伦理"
    ]

    # 科技热点关键词
    tech_keywords = [
        "科技", "技术突破", "创新", "革命", "颠覆", "开源",
        "漏洞", "安全", "攻击", "防御", "黑客", "数据泄露",
        "裁员", "招聘", "就业", "失业", "效率", "生产力",
        "投资", "融资", "估值", "上市", "股价", "市场"
    ]

    print("[LOG] 初始化关键词库...")
    for kw in ai_keywords + tech_keywords:
        kf.add_keyword(kw, weight=2 if kw in ai_keywords else 1)

    print(f"[LOG] 共添加{len(ai_keywords) + len(tech_keywords)}个关键词")
    return kf


def manage_keywords():
    """关键词管理交互"""
    kf = KeywordFilter()

    while True:
        print("\n" + "=" * 40)
        print("关键词管理")
        print("=" * 40)
        print(f"当前关键词({len(kf.keywords)}个): {kf.keywords[:10]}...")
        print("\n1. 添加关键词")
        print("2. 删除关键词")
        print("3. 列出所有关键词")
        print("4. 初始化默认关键词")
        print("0. 退出")

        choice = input("\n选择: ").strip()

        if choice == "1":
            kw = input("输入关键词: ").strip()
            if kw:
                kf.add_keyword(kw)
        elif choice == "2":
            kw = input("输入要删除的关键词: ").strip()
            if kw:
                kf.remove_keyword(kw)
        elif choice == "3":
            print(f"\n所有关键词({len(kf.keywords)}个):")
            for i, kw in enumerate(kf.keywords, 1):
                print(f"  {i}. {kw}")
        elif choice == "4":
            init_keywords()
            kf.keywords = kf._load_keywords()
        elif choice == "0":
            break


if __name__ == "__main__":
    import sys

    # 如果带参数 --init-keywords，初始化关键词
    if len(sys.argv) > 1 and sys.argv[1] == "--init-keywords":
        init_keywords()
        sys.exit(0)

    # 如果带参数 --manage-keywords，进入管理模式
    if len(sys.argv) > 1 and sys.argv[1] == "--manage-keywords":
        manage_keywords()
        sys.exit(0)

    # 正常生成日报
    LLM_CONFIG = {
        "api_key": "ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen3-64k:latest"
    }

    USE_LLM = True
    TEMPERATURE = 1.0

    generator = DailyReportGenerator(
        db_path="rss_data.db",
        use_llm=USE_LLM,
        llm_config=LLM_CONFIG if USE_LLM else None,
        temperature=TEMPERATURE,
        use_keyword_filter=True  # 启用关键词过滤
    )
    generator.save_report(output_dir="Daily/Daily")