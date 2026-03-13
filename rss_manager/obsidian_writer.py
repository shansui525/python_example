"""
Obsidian报告生成和保存模块
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ObsidianWriter:
    def __init__(self, vault_path: str = None):
        self.vault_path = vault_path or ""
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """加载配置"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def set_vault_path(self, path: str):
        """设置Obsidian vault路径"""
        self.vault_path = path
        self.config['obsidian_vault_path'] = path
        self._save_config()

    def _save_config(self):
        """保存配置"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def check_vault_exists(self) -> bool:
        """检查Vault路径是否存在"""
        if not self.vault_path:
            return False
        return os.path.isdir(self.vault_path)

    def generate_report(self, articles: List[Dict], title: str = None,
                       date: str = None) -> str:
        """生成Markdown报告"""
        if not date:
            date = datetime.now().strftime('%Y.%m.%d')

        # 获取星期几
        weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        weekday = weekday_names[datetime.now().weekday()]

        # 默认标题
        if not title:
            title = "RSS日报"

        # 构建报告内容
        report_lines = [
            f"# {title}",
            "",
            f"**日期**: {date} {weekday}",
            "",
            f"**文章数**: {len(articles)}",
            "",
            "---",
            ""
        ]

        # 按来源分组
        articles_by_feed = {}
        for article in articles:
            feed_name = article.get('feed_name', '未知来源')
            if feed_name not in articles_by_feed:
                articles_by_feed[feed_name] = []
            articles_by_feed[feed_name].append(article)

        # 生成每个来源的文章
        for feed_name, feed_articles in articles_by_feed.items():
            report_lines.append(f"## 📰 {feed_name}")
            report_lines.append("")

            for idx, article in enumerate(feed_articles, 1):
                article_title = article.get('title', '无标题')
                article_summary = article.get('summary', '无摘要')
                article_url = article.get('url', '')

                report_lines.append(f"### {idx}. {article_title}")
                report_lines.append("")

                if article_summary:
                    report_lines.append(f"> {article_summary}")
                    report_lines.append("")

                if article_url:
                    report_lines.append(f"🔗 [原文链接]({article_url})")
                    report_lines.append("")

                report_lines.append("---")
                report_lines.append("")

        # 添加时间戳
        report_lines.extend([
            "",
            f"---",
            f"",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])

        return "\n".join(report_lines)

    def save_report(self, content: str, filename: str = None,
                   subfolder: str = "Daily") -> Dict:
        """保存报告到Obsidian"""
        if not self.vault_path:
            return {
                'success': False,
                'error': '未设置Obsidian Vault路径'
            }

        if not self.check_vault_exists():
            return {
                'success': False,
                'error': f'Vault路径不存在: {self.vault_path}'
            }

        # 生成文件名
        if not filename:
            date_str = datetime.now().strftime('%Y-%m-%d')
            filename = f"{date_str}-RSS日报.md"

        # 创建子文件夹
        if subfolder:
            folder_path = os.path.join(self.vault_path, subfolder)
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, filename)
        else:
            file_path = os.path.join(self.vault_path, filename)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Report saved to: {file_path}")

            return {
                'success': True,
                'file_path': file_path,
                'filename': filename
            }
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_report_preview(self, articles: List[Dict], max_articles: int = 3) -> str:
        """获取报告预览"""
        preview_articles = articles[:max_articles]
        report = self.generate_report(preview_articles)

        if len(articles) > max_articles:
            report += f"\n\n... 还有 {len(articles) - max_articles} 篇文章"

        return report
