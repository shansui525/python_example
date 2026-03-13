"""
数据库模块 - 负责RSS数据存储和管理
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

import logging  # <--- 1. 导入 logging
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "rss_data.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 订阅源表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT '默认',
                    last_fetched TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 文章表 - 增加关键词和标星字段
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feed_id INTEGER NOT NULL,
                    guid TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    content TEXT,
                    summary TEXT,
                    keywords TEXT,
                    is_starred INTEGER DEFAULT 0,
                    published_at TEXT,
                    is_read INTEGER DEFAULT 0,
                    is_selected INTEGER DEFAULT 0,
                    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                     -- 【新增字段开始】用于存储质量审计信息
                    quality_score INTEGER DEFAULT 0,          -- 综合评分 (0-100)
                    quality_recommendation TEXT,              -- 推荐语 (推荐阅读/标题党等)
                    quality_honesty_level TEXT,               -- 标题诚信度 (高/中/低/欺诈)
                    quality_category TEXT,                    -- 文章分类 (技术/财经等)
                    quality_raw_json TEXT,                     -- 完整的原始 JSON 数据 (可选，用于调试或扩展)
            -- 【新增字段结束】
                    FOREIGN KEY (feed_id) REFERENCES feed (id) ON DELETE CASCADE,
                    UNIQUE(feed_id, guid)
                )
            ''')

            # 创建索引以提升查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_is_starred ON articles(is_starred)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_is_selected ON articles(is_selected)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_is_read ON articles(is_read)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_quality_recommendation ON articles(quality_recommendation)')
            # 设置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            conn.commit()

    # ==================== 订阅源操作 ====================

    def add_feed(self, url: str, name: str, category: str = "默认") -> int:
        """添加订阅源"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO feeds (url, name, category) VALUES (?, ?, ?)",
                    (url, name, category)
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # 订阅源已存在
                cursor.execute("SELECT id FROM feeds WHERE url = ?", (url,))
                return cursor.fetchone()[0]

    def feed_exists(self, url: str) -> bool:
        """检查订阅源是否存在"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM feeds WHERE url = ?", (url,))
            return cursor.fetchone() is not None

    def get_all_feed_urls(self) -> set:
        """获取所有订阅源URL"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url FROM feeds")
            return {row[0] for row in cursor.fetchall()}

    def get_all_feeds(self) -> List[Dict]:
        """获取所有订阅源"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM feeds ORDER BY category, name")
            return [dict(row) for row in cursor.fetchall()]

    def delete_feed(self, feed_id: int):
        """删除订阅源"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
            conn.commit()

    def update_feed_fetch_time(self, feed_id: int):
        """更新订阅源最后抓取时间"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE feeds SET last_fetched = ? WHERE id = ?",
                (datetime.now().isoformat(), feed_id)
            )
            conn.commit()

    # ==================== 文章操作 ====================

    def add_article(self, feed_id: int, guid: str, title: str,
                    url: str = None, content: str = None,
                    published_at: str = None) -> int:
        """添加文章"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO articles (feed_id, guid, title, url, content, published_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (feed_id, guid, title, url, content, published_at))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # 文章已存在
                return None

    def get_articles(self, feed_id: int = None, selected_only: bool = False,
                    starred_only: bool = False) -> List[Dict]:
        """获取文章列表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT a.*, f.name as feed_name, f.category FROM articles a JOIN feeds f ON a.feed_id = f.id WHERE 1=1"
            params = []

            if feed_id:
                query += " AND a.feed_id = ?"
                params.append(feed_id)

            if selected_only:
                query += " AND a.is_selected = 1"

            if starred_only:
                query += " AND a.is_starred = 1"

            query += " ORDER BY a.published_at DESC, a.fetched_at DESC"

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_articles_by_date_range(self, start_date: str = None, end_date: str = None,
                                   feed_id: int = None, has_summary: bool = None,
                                   starred_only: bool = False) -> List[Dict]:
        """获取指定日期范围的文章"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT a.*, f.name as feed_name, f.category FROM articles a JOIN feeds f ON a.feed_id = f.id WHERE 1=1"
            params = []

            # 日期范围筛选
            if start_date:
                query += " AND date(a.published_at) >= date(?)"
                params.append(start_date)
            if end_date:
                query += " AND date(a.published_at) <= date(?)"
                params.append(end_date)

            # 订阅源筛选
            if feed_id:
                query += " AND a.feed_id = ?"
                params.append(feed_id)

            # 摘要状态筛选
            if has_summary is not None:
                if has_summary:
                    query += " AND a.summary IS NOT NULL AND a.summary != ''"
                else:
                    query += " AND (a.summary IS NULL OR a.summary = '')"

            # 标星筛选
            if starred_only:
                query += " AND a.is_starred = 1"

            query += " ORDER BY a.published_at DESC, a.fetched_at DESC"

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_articles_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的文章"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.*, f.name as feed_name, f.category
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE date(a.fetched_at) = date(?)
                ORDER BY a.feed_id, a.published_at DESC
            ''', (date,))
            return [dict(row) for row in cursor.fetchall()]

    def update_article_summary(self, article_id: int, summary: str, keywords: str = None):
        """更新文章摘要和关键词"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if keywords:
                cursor.execute(
                    "UPDATE articles SET summary = ?, keywords = ? WHERE id = ?",
                    (summary, keywords, article_id)
                )
            else:
                cursor.execute(
                    "UPDATE articles SET summary = ? WHERE id = ?",
                    (summary, article_id)
                )
            conn.commit()

    def toggle_article_star(self, article_id: int):
        """切换文章标星状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE articles SET is_starred = NOT is_starred WHERE id = ?",
                (article_id,)
            )
            conn.commit()

    def set_article_star(self, article_id: int, starred: bool = True):
        """设置文章标星状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE articles SET is_starred = ? WHERE id = ?",
                (1 if starred else 0, article_id)
            )
            conn.commit()

    def toggle_article_selection(self, article_id: int):
        """切换文章选中状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE articles SET is_selected = NOT is_selected WHERE id = ?",
                (article_id,)
            )
            conn.commit()

    def select_article(self, article_id: int, selected: bool = True):
        """设置文章选中状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE articles SET is_selected = ? WHERE id = ?",
                (1 if selected else 0, article_id)
            )
            conn.commit()
            # print('更新成功')

    def deselect_article(self, article_id: int):
        """取消选中文章"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE articles SET is_selected = 0 WHERE id = ?",
                (article_id,)
            )
            conn.commit()

    def get_selected_articles(self) -> List[Dict]:
        """获取选中的文章"""
        return self.get_articles(selected_only=True)

    def get_starred_articles(self) -> List[Dict]:
        """获取标星的文章"""
        return self.get_articles(starred_only=True)

    def clear_all_selections(self):
        """清除所有选中状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE articles SET is_selected = 0")
            conn.commit()

    def get_article_count(self, feed_id: int = None) -> int:
        """获取文章数量"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if feed_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM articles WHERE feed_id = ?",
                    (feed_id,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM articles")
            return cursor.fetchone()[0]

    def get_uncached_articles(self) -> List[Dict]:
        """获取需要生成摘要的文章"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.*, f.name as feed_name
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.summary IS NULL OR a.summary = ''
                ORDER BY a.fetched_at DESC
                LIMIT 20
            ''')
            return [dict(row) for row in cursor.fetchall()]

    # ==================== 分页查询方法 ====================

    def get_articles_paginated(self, feed_id: int = None, selected_only: bool = False,
                               starred_only: bool = False, start_date: str = None,
                               end_date: str = None, has_summary: bool = None,
                               search_keyword: str = None,
                               page: int = 1, page_size: int = 50,
                               sort_by: str = 'time',
                               quality_recommendation: str = None) -> List[Dict]: # 确保参数列表包含此字段
        """
        分页获取文章列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT a.*, f.name as feed_name, f.category FROM articles a JOIN feeds f ON a.feed_id = f.id WHERE 1=1"
            params = []

            if feed_id:
                query += " AND a.feed_id = ?"
                params.append(feed_id)
            if selected_only:
                query += " AND a.is_selected = 1"
            if starred_only:
                query += " AND a.is_starred = 1"
            if start_date:
                query += " AND date(a.published_at) >= date(?)"
                params.append(start_date)
            if end_date:
                query += " AND date(a.published_at) <= date(?)"
                params.append(end_date)
            if has_summary is not None:
                if has_summary:
                    query += " AND a.summary IS NOT NULL AND a.summary != ''"
                else:
                    query += " AND (a.summary IS NULL OR a.summary = '')"
            if search_keyword:
                keyword = f"%{search_keyword}%"
                query += " AND (a.title LIKE ? OR a.summary LIKE ? OR a.keywords LIKE ?)"
                params.extend([keyword, keyword, keyword])

            # === 修改开始：直接使用字段精确匹配 ===
            if quality_recommendation:
                query += " AND a.quality_recommendation = ?"
                params.append(quality_recommendation)
            # === 修改结束 ===

            # 排序逻辑
            if sort_by == 'score':
                query += " ORDER BY a.quality_score DESC, a.published_at DESC"
            elif sort_by == 'time_score':
                query += " ORDER BY a.quality_score DESC, a.published_at DESC"
            else:
                query += " ORDER BY a.published_at DESC, a.fetched_at DESC"

            # 分页
            offset = (page - 1) * page_size
            query += " LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


    def get_articles_count(self, feed_id: int = None, selected_only: bool = False,
                          starred_only: bool = False, start_date: str = None,
                          end_date: str = None, has_summary: bool = None,
                          search_keyword: str = None,
                          quality_recommendation: str = None) -> int: # 确保参数列表包含此字段
        """
        获取符合条件的文章总数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT COUNT(*) FROM articles a WHERE 1=1"
            params = []

            if feed_id:
                query += " AND a.feed_id = ?"
                params.append(feed_id)

            if selected_only:
                query += " AND a.is_selected = 1"

            if starred_only:
                query += " AND a.is_starred = 1"

            # 日期范围筛选
            if start_date:
                query += " AND date(a.published_at) >= date(?)"
                params.append(start_date)
            if end_date:
                query += " AND date(a.published_at) <= date(?)"
                params.append(end_date)

            # 摘要状态筛选
            if has_summary is not None:
                if has_summary:
                    query += " AND a.summary IS NOT NULL AND a.summary != ''"
                else:
                    query += " AND (a.summary IS NULL OR a.summary = '')"

            # 模糊搜索
            if search_keyword:
                keyword = f"%{search_keyword}%"
                query += " AND (a.title LIKE ? OR a.summary LIKE ? OR a.keywords LIKE ?)"
                params.extend([keyword, keyword, keyword])

            # === 修改开始：直接使用字段精确匹配 ===
            if quality_recommendation:
                query += " AND a.quality_recommendation = ?"
                params.append(quality_recommendation)
            # === 修改结束 ===

            cursor.execute(query, params)
            return cursor.fetchone()[0]


    # ==================== 设置操作 ====================

    def set_setting(self, key: str, value: str):
        """保存设置"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()

    def get_setting(self, key: str, default: str = None) -> str:
        """获取设置"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def get_filtered_articles(self, date: str = None, has_summary: bool = None) -> List[Dict]:
        """
        获取筛选后的文章列表
        :param date: 日期字符串，格式为 'YYYY-MM-DD'
        :param has_summary: 是否已生成摘要（True/False）
        :return: 符合条件的文章列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT a.*, f.name as feed_name, f.category FROM articles a JOIN feeds f ON a.feed_id = f.id WHERE 1=1"
            params = []

            # 按日期筛选
            if date:
                query += " AND date(a.published_at) = date(?)"
                params.append(date)

            # 按摘要状态筛选
            if has_summary is not None:
                if has_summary:
                    query += " AND a.summary IS NOT NULL AND a.summary != ''"
                else:
                    query += " AND (a.summary IS NULL OR a.summary = '')"

            query += " ORDER BY a.published_at DESC, a.fetched_at DESC"

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


    def get_articles_without_summary(self, limit: int = 50,days_ago=None) -> List[Dict]:
        """获取没有生成摘要的文章"""
        query = "SELECT * FROM articles WHERE summary IS NULL OR summary = ''"
        params = []

        if days_ago:
            # 添加时间过滤条件：published_at >= (当前时间 - days_ago 天)
            query += " AND published_at >= datetime('now', ?)"
            params.append(f"-{days_ago} days")

        query += " ORDER BY published_at DESC LIMIT ?"
        params.append(limit)
        try:
            # 修复：使用上下文管理器获取连接和 cursor
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (limit,))
                rows = cursor.fetchall()
                return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching articles without summary: {e}")
            return []

    def update_article_summary(self, article_id: int, summary_content: str, keywords: str):
        """
        更新摘要和质量评分信息
        """
        import json

        summary_text = summary_content
        quality_score = 0
        quality_rec = ""
        quality_honesty = ""
        quality_cat = ""
        quality_json = ""

        # 解析分隔符，分离纯摘要和质量信息
        if '---QUALITY---' in summary_content:
            parts = summary_content.split('---QUALITY---', 1)
            summary_text = parts[0].strip()
            try:
                q_data = json.loads(parts[1].strip())
                quality_score = q_data.get('score', 0)
                quality_rec = q_data.get('recommendation', '')
                quality_honesty = q_data.get('honesty_level', '')
                quality_cat = q_data.get('category', '')
                quality_json = parts[1].strip()
            except Exception as e:
                logger.error(f"解析质量信息失败：{e}")

        query = """
            UPDATE articles 
            SET summary = ?, 
                keywords = ?,
                quality_score = ?,
                quality_recommendation = ?,
                quality_honesty_level = ?,
                quality_category = ?,
                quality_raw_json = ?
            WHERE id = ?
        """

        try:
            # 修复：使用上下文管理器获取连接和 cursor
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    summary_text,
                    keywords,
                    quality_score,
                    quality_rec,
                    quality_honesty,
                    quality_cat,
                    quality_json,
                    article_id
                ))
                conn.commit() # 上下文管理器退出时会自动 commit/close，但显式调用也没问题
        except Exception as e:
            logger.error(f"Error updating article summary and quality: {e}")
            # 注意：在使用 with 语句时，通常不需要手动 rollback，上下文管理器会在异常时处理
            # 但如果需要显式控制，可以在 with 块内捕获异常后处理，这里保持简单让 with 处理
