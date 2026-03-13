"""
RSS获取和内容摘要生成模块
"""
import feedparser
import requests
from bs4 import BeautifulSoup
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import time
from database import Database
import json
import os
from dateutil import parser

# 配置日志
try:
    import logging as logging_module
    logging_module.basicConfig(
        level=logging_module.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging_module.getLogger(__name__)
except Exception:
    # 备用：如果日志配置失败，创建一个简易的 logger 替代
    class SimpleLogger:
        def info(self, msg): print(f"[INFO] {msg}")
        def warning(self, msg): print(f"[WARNING] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")
    logger = SimpleLogger()


class RSSFetcher:
    def __init__(self, db: Database, api_key: str = None, base_url: str = None):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 【新增】初始化 Summarizer，传入 db 和可能的配置
        # 如果不传参，Summarizer 内部会尝试读取环境变量或默认配置
        self.summarizer = Summarizer(db=db, api_key=api_key, base_url=base_url)

    def fetch_feed(self, url: str) -> Optional[Dict]:
        """解析RSS订阅源"""
        try:
            logger.info(f"Fetching feed: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            if feed.bozo and not feed.entries:
                logger.warning(f"Feed may be malformed: {url}")
                return None

            return {
                'title': feed.feed.get('title', 'Unknown'),
                'entries': [
                    {
                        'guid': entry.get('id') or entry.get('link') or entry.get('title'),
                        'title': entry.get('title', 'No Title'),
                        'link': entry.get('link'),
                        'content': entry.get('content', [{}])[0].get('value')
                                 or entry.get('summary', ''),
                        'published': entry.get('published') or entry.get('updated')
                                   or datetime.now().isoformat()
                    }
                    for entry in feed.entries[:50]  # 限制获取最近50条
                ]
            }
        except Exception as e:
            logger.error(f"Error fetching feed {url}: {e}")
            return None

    def fetch_all_feeds(self) -> Dict:
        """获取所有订阅源的文章"""
        feeds = self.db.get_all_feeds()
        results = {
            'total_feeds': len(feeds),
            'new_articles': 0,
            'feeds': []
        }

        for feed in feeds:
            feed_result = self._fetch_single_feed(feed)
            if feed_result:
                results['feeds'].append(feed_result)
                results['new_articles'] += feed_result['new_count']

        return results

    def _fetch_single_feed(self, feed: Dict) -> Optional[Dict]:
        """获取单个订阅源的文章并立即生成摘要"""
        url = feed['url']
        feed_id = feed['id']

        parsed = self.fetch_feed(url)
        if not parsed:
            return None

        new_count = 0
        summarized_count = 0

        for entry in parsed['entries']:
            # 解析时间 (保持原有逻辑)
            raw_published_at = entry.get('published') or entry.get('updated')
            try:
                parsed_time = parser.parse(raw_published_at)
                formatted_published_at = parsed_time.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logger.warning(f"Failed to parse published time: {raw_published_at}, error: {e}")
                formatted_published_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 清理内容
            clean_content = self._clean_html(entry['content'])

            # 存入数据库
            article_id = self.db.add_article(
                feed_id=feed_id,
                guid=entry['guid'],
                title=entry['title'],
                url=entry['link'],
                content=clean_content,
                published_at=formatted_published_at
            )

            if article_id:
                new_count += 1

                # 【新增】如果文章成功插入，且内容足够，立即生成摘要
                if len(clean_content) > 50:
                    logger.info(f"正在生成摘要：{entry['title']}")
                    keywords, summary = self.summarizer.summarize(
                        content=clean_content,
                        title=entry['title']
                    )

                    # 只有当摘要生成成功（不包含错误标记）时才更新数据库
                    if '⚠️' not in summary:
                        self.db.update_article_summary(article_id, summary, keywords)
                        summarized_count += 1
                        logger.info(f"摘要生成成功：{entry['title']}")
                    else:
                        logger.warning(f"摘要生成失败：{entry['title']} - {summary}")

                # 避免触发 Ollama 或 API 限流，每次请求后暂停
                time.sleep(1)

        self.db.update_feed_fetch_time(feed_id)

        return {
            'feed_id': feed_id,
            'feed_name': feed['name'],
            'new_count': new_count,
            'summarized_count': summarized_count,  # 新增统计
            'total_count': len(parsed['entries'])
        }

    def _clean_html(self, html_content: str) -> str:
        """清理HTML内容"""
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, 'lxml')
        text = soup.get_text(separator=' ', strip=True)

        # 清理多余空白
        text = re.sub(r'\s+', ' ', text)
        text = text[:5000]  # 限制内容长度

        return text


class BatchImporter:
    """批量导入RSS源"""

    def __init__(self, db: Database, fetcher: RSSFetcher):
        self.db = db
        self.fetcher = fetcher

    def import_urls(self, urls: List[str]) -> Dict:
        """
        批量导入RSS源
        返回导入结果统计
        """
        results = {
            'total': len(urls),
            'added': 0,
            'duplicates': 0,
            'failed': 0,
            'failed_urls': [],
            'details': []
        }

        # 获取已存在的URL集合
        existing_urls = self.db.get_all_feed_urls()

        for url in urls:
            url = url.strip()
            if not url:
                continue

            # 检查是否已存在
            if url in existing_urls:
                logger.info(f"跳过重复订阅源: {url}")
                results['duplicates'] += 1
                results['details'].append({
                    'url': url,
                    'status': 'duplicate'
                })
                continue

            # 尝试访问
            try:
                result = self.fetcher.fetch_feed(url)
                if result:
                    # 添加到数据库
                    name = result['title']
                    feed_id = self.db.add_feed(url, name)

                    # 更新已存在URL集合
                    existing_urls.add(url)

                    results['added'] += 1
                    results['details'].append({
                        'url': url,
                        'name': name,
                        'status': 'added'
                    })
                    logger.info(f"成功添加订阅源: {name} ({url})")
                else:
                    results['failed'] += 1
                    results['failed_urls'].append(url)
                    results['details'].append({
                        'url': url,
                        'status': 'failed',
                        'error': '无法解析RSS'
                    })
                    logger.warning(f"无法解析RSS: {url}")
            except requests.exceptions.RequestException as e:
                results['failed'] += 1
                results['failed_urls'].append(url)
                results['details'].append({
                    'url': url,
                    'status': 'failed',
                    'error': str(e)
                })
                logger.error(f"访问失败: {url}, 错误: {e}")
                # 继续下一个，不中断

            # 避免请求过快
            time.sleep(0.5)

        return results


class ContentExtractor:
    """从URL提取正文内容"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def extract(self, url: str) -> str:
        """提取网页正文"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')

            # 尝试移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()

            # 获取正文
            text = soup.get_text(separator=' ', strip=True)

            # 清理
            text = re.sub(r'\s+', ' ', text)
            text = text[:5000]

            return text
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return ""


class Summarizer:
    # 【新增】在类级别定义 logger，确保即使模块级失效也能用
    _class_logger = logging.getLogger(__name__ + ".Summarizer")

    def __init__(self, db: Database, api_key: str = None, base_url: str = None):
        self.db = db
        self.api_key = 'ollama'
        self.base_url = base_url or 'http://localhost:11434/v1'
        self.config = self._load_config()
        # 实例化时也绑定一下 logger
        self.logger = logging.getLogger(__name__)

    def _load_config(self) -> Dict:
        """加载配置"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'summary_language': 'zh',
            'summary_length': {'min': 100, 'max': 200}
        }

    def parse_summary_response(self, response: str) -> Tuple[str, str, str, Dict]:
        """
        解析 JSON 响应
        返回: (keywords_str, summary_text, quality_json_str, metadata_dict)
        """
        if not response:
            return "", "", "", {}

        try:
            # 尝试清理可能的 Markdown 代码块标记
            clean_response = re.sub(r'^json\s*', '', response, flags=re.MULTILINE)
            clean_response = re.sub(r'\s*$', '', clean_response, flags=re.MULTILINE)
            clean_response = clean_response.strip()

            data = json.loads(clean_response)

            # 1. 提取关键词 (列表转逗号分隔字符串)
            keywords_list = data.get('metadata', {}).get('keywords', [])
            keywords_str = ','.join(keywords_list)

            # 2. 提取摘要 (连贯文本)
            summary_text = data.get('summary', '')

            # 3. 构建质量评估信息 (用于存储或展示)
            quality_info = {
                'score': data.get('quality_assessment', {}).get('overall_score', 0),
                'recommendation': data.get('quality_assessment', {}).get('recommendation', ''),
                'integrity_score': data.get('audit_result', {}).get('information_integrity_score', 0),
                'honesty_level': data.get('audit_result', {}).get('title_honesty_level', ''),
                'category': data.get('metadata', {}).get('category', '其他')
            }
            quality_json_str = json.dumps(quality_info, ensure_ascii=False)

            return keywords_str, summary_text, quality_json_str, quality_info

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败：{e}, 原始响应：{response[:200]}...")
            # 降级处理：如果解析失败，返回原始文本作为摘要，标记错误
            return "解析失败", f"⚠️ 格式错误无法解析 JSON: {response[:100]}", "", {}
        except Exception as e:
            logger.error(f"解析过程出错：{e}")
            return "错误", f"⚠️ 处理异常：{str(e)}", "", {}

    def summarize(self, content: str, title: str = "") -> Tuple[str, str]:
        """
        生成摘要、关键词及质量评分
        增加多重前置判断以减少大模型调用
        """
        # 1. 基础配置检查
        if not self.api_key and 'localhost' not in self.base_url:
            return "", "⚠️ 未配置 API 密钥"

        # 2. 内容空值检查
        if not content:
            return "", "⚠️ 内容为空"

        # 3. 内容长度预处理
        clean_content = content.strip()
        content_len = len(clean_content)

        # 【优化】过短内容直接跳过
        if content_len < 50:
            logger.info(f"跳过过短文章 (长度:{content_len}): {title[:20]}...")
            return "无", f"⚠️ 文章内容过短 ({content_len}字)，无需生成摘要。"

        # 【优化】过长内容截断 (防止显存溢出，保留前 4000 字通常足够概括)
        max_content_len = 4000
        if content_len > max_content_len:
            logger.warning(f"文章过长 ({content_len}字)，已截断至 {max_content_len}字：{title[:20]}...")
            clean_content = clean_content[:max_content_len] + "\n...(内容过长已截断)"

        # 4. 低质/广告内容简单启发式过滤
        # 检查是否包含大量重复字符或典型广告词
        if clean_content.count("点击阅读全文") > 3 or clean_content.count("......") > 20:
             logger.info(f"疑似低质/广告文章，跳过：{title[:20]}...")
             return "广告/低质", "⚠️ 检测到文章可能为低质内容或广告，已跳过生成。"

        # 5. 简单的语言检测 (可选：如果只想要中文)
        # import re
        # if not re.search(r'[\u4e00-\u9fff]', clean_content):
        #     return "非中文", "⚠️ 非中文内容，跳过生成。"


        try:
            from openai import OpenAI

            model_name = 'qwen3:8b'  # 确保本地有此模型
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)

            language = self.config.get('summary_language', 'zh')
            min_len = self.config.get('summary_length', {}).get('min', 100)
            max_len = self.config.get('summary_length', {}).get('max', 200)

            # === 新 Prompt ===
            # === 修改后的 Prompt ===
            prompt = f"""你是一位资深技术编辑，请用自然、流畅的中文为读者撰写一段文章摘要。

            【写作目标】
            完整概括文章核心内容，包括背景、主要技术方案/观点、关键数据/步骤以及最终结论或价值。

            【风格要求】
            1. **去 AI 化**：严禁使用“本文介绍了”、“文章披露了”、“首先/其次/最后”等刻板句式。直接以事实开头。
            2. **自然叙述**：将技术细节、数据支撑和作者观点有机融合在一个连贯的段落中，不要有明显的拼接感。
            3. **客观精炼**：保留具体的技术名词、版本号、数据指标；去除冗余的形容词和空洞的评价。
            4. **篇幅控制**：控制在 {min_len}-{max_len} 字之间。

            【内容结构建议】（不要在输出中显示这些标签）
            - 开篇直接点明文章解决的核心问题或提出的主要方案。
            - 中间部分自然穿插实现原理、关键步骤或核心数据支撑。
            - 结尾简要提及该方案的实际价值、局限性或与标题承诺的对比（如果标题有夸大，请委婉指出实际内容的侧重）。

            【输出格式】
            严格仅输出一个 JSON 对象，不要包含 markdown 标记（如json），格式如下： {{ "audit_result": {{ "title_promises": ["标题承诺的关键点"], "fulfilled_promises": ["正文实际详细展开的点"], "missing_promises": ["标题提到但正文未展开的点"], "information_integrity_score": 1-5, "title_honesty_level": "高/中/低/欺诈", "actual_focus": ["正文真正的重点"] }}, "summary": "这里填写你生成的自然流畅的摘要段落", "metadata": {{ "keywords": ["关键词 1", "关键词 2", "关键词 3"], "category": "技术/财经/政策/产品/其他", "reading_time": "预计阅读时间", "suitable_for": ["目标读者"] }}, "quality_assessment": {{ "overall_score": 1-100, "information_density": "高/中/低", "practical_value": "高/中/低", "recommendation": "推荐阅读/快速浏览/标题党慎入" }} }}
【评分参考】 90-100: 内容详实且有独到见解；75-89: 信息完整逻辑清晰；60-74: 内容泛泛或有部分缺失；<60: 严重标题党或内容空洞。
文章标题：{title}
文章内容： {content[:3000]}
请直接输出 JSON 对象："""

            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000, # 增加 token 限制以容纳 JSON 结构
                temperature=0.3,  # 降低温度以提高 JSON 稳定性
                timeout=120
            )

            full_response = response.choices[0].message.content.strip()

            # 解析结果
            keywords, summary, quality_json, quality_info = self.parse_summary_response(full_response)

            if '⚠️' in summary:
                return keywords, summary

            # 构造最终存储内容：摘要 + 分隔符 + 质量信息 JSON
            # 这样可以在不修改数据库 schema 的情况下保留评分信息
            # 前端读取时可按 '\n---QUALITY---\n' 分割
            final_summary_content = f"{summary}\n---QUALITY---\n{quality_json}"

            print(f"{title} 审计完成 | 评分:{quality_info.get('score', 'N/A')} | 推荐:{quality_info.get('recommendation', 'N/A')}")

            return keywords, final_summary_content

        except Exception as e:
            # 防御性编程：防止 logger 未定义导致二次崩溃
            try:
                logger.error(f"Error generating summary: {e}")
            except NameError:
                # 如果 logger 真的未定义，使用 print 降级输出
                print(f"[CRITICAL ERROR] Logger not defined. Original error: {e}")
            return "", f"⚠️ 摘要生成失败：{str(e)}"

    # 在 fetcher.py 的 Summarizer 类中
    def summarize_articles(self, articles: List[Dict]) -> Dict:
        """批量生成摘要 - 增加动态延时和详细日志"""
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0, # 新增跳过统计
            'total': len(articles)
        }

        for index, article in enumerate(articles):
            # 双重检查：防止在长循环中状态变化
            if article.get('summary'):
                results['skipped'] += 1
                continue

            content = article.get('content', '')

            # 如果没有内容但有链接，尝试提取 (保持原有逻辑)
            if not content and article.get('url'):
                # 注意：网络提取也耗时，可根据需要决定是否在这里做
                extractor = ContentExtractor()
                content = extractor.extract(article['url'])

            # 调用带前置判断的 summarize
            keywords, summary_content = self.summarize(content, article.get('title', ''))

            # 只有当摘要不是“跳过”类的错误信息时才更新数据库？
            # 这里策略：即使是“内容过短”也写入数据库，标记为已处理，避免下次重复尝试
            self.db.update_article_summary(article['id'], summary_content, keywords)

            if '⚠️' in summary_content:
                # 区分是“跳过”还是“失败”
                if "无需生成" in summary_content or "低质" in summary_content:
                    results['skipped'] += 1
                else:
                    results['failed'] += 1
            else:
                results['success'] += 1

            # 【优化】动态延时：根据文章长度调整休眠时间，给系统喘息机会
            # 基础休眠 1 秒，每 1000 字增加 0.5 秒
            sleep_time = 1.0 + (len(content) / 1000.0) * 0.5
            time.sleep(sleep_time)

            # 每处理 5 篇，打印一次进度，方便监控
            if (index + 1) % 5 == 0:
                logger.info(f"进度：{index + 1}/{len(articles)}")

        return results

