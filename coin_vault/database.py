# -*- coding: utf-8 -*-
"""
数据库管理模块
负责SQLite数据库的初始化、数据操作和备份恢复
"""

import sqlite3
import os
import json
from datetime import datetime
import shutil

class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        """初始化数据库管理器"""
        self.project_root = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(self.project_root, 'data', 'coin_vault.db')
        self.backup_dir = os.path.join(self.project_root, 'data', 'backups')
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        self.conn = None

    def get_connection(self):
        """获取数据库连接"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            # 启用外键约束
            self.conn.execute('PRAGMA foreign_keys = ON')
        return self.conn

    def initialize_database(self):
        """初始化数据库表结构"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 创建藏品主表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                material TEXT NOT NULL CHECK(material IN ('金', '银', '铂', '钯')),
                type TEXT NOT NULL CHECK(type IN ('投资币', '纪念币', '流通币')),
                series TEXT,
                year INTEGER,
                issuer TEXT,
                weight REAL NOT NULL,
                purity TEXT,
                face_value INTEGER,
                diameter REAL,
               发行量 INTEGER,
                grade TEXT,
                cert_id TEXT,
                packaging TEXT,
                photo_front TEXT,
                photo_back TEXT,
                photo_cert TEXT,
                photo_package TEXT,
                tags TEXT,
                buy_date TEXT NOT NULL,
                buy_price REAL NOT NULL,
                buy_quantity INTEGER DEFAULT 1,
                buy_fee REAL DEFAULT 0,
                buy_channel TEXT,
                buy_notes TEXT,
                buy_gram_price REAL,
                total_cost REAL,
                gold_price_at_buy REAL,
                premium_rate REAL,
                sell_date TEXT,
                sell_price REAL,
                sell_fee REAL,
                sell_channel TEXT,
                sell_notes TEXT,
                sell_gram_price REAL,
                net_sales REAL,
                profit_loss REAL,
                profit_rate REAL,
                hold_days INTEGER,
                annual_roi REAL,
                status TEXT DEFAULT '在库' CHECK(status IN ('在库', '已售', '部分卖出', '质押')),
                is_sold INTEGER DEFAULT 0,
                current_price REAL,
                current_market_value REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建金价记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gold_price_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                gold_price REAL,
                silver_price REAL,
                platinum_price REAL,
                palladium_price REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建系统设置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建交易附件表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER,
                file_path TEXT NOT NULL,
                file_type TEXT,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        print(f"数据库初始化完成: {self.db_path}")

    def generate_item_id(self, material, year=None):
        """
        生成唯一的藏品ID
        格式: GLD-2024-001, SLV-2023-001 等
        """
        material_map = {'金': 'GLD', '银': 'SLV', '铂': 'PLT', '钯': 'PDL'}
        prefix = material_map.get(material, 'UNK')

        year_str = str(year)[-2:] if year else datetime.now().strftime('%y')

        conn = self.get_connection()
        cursor = conn.cursor()

        # 查询该年份该材质最大的序号
        cursor.execute('''
            SELECT item_id FROM collections
            WHERE item_id LIKE ?
            ORDER BY item_id DESC LIMIT 1
        ''', (f'{prefix}-{year_str}-%',))

        result = cursor.fetchone()
        if result:
            last_num = int(result[0].split('-')[-1]) + 1
        else:
            last_num = 1

        return f'{prefix}-{year_str}-{last_num:03d}'

    def add_collection(self, data):
        """
        添加藏品记录
        data: 字典，包含藏品所有字段
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 自动生成ID
        if 'item_id' not in data or not data['item_id']:
            data['item_id'] = self.generate_item_id(data['material'], data.get('year'))

        # 计算克价和总成本
        if 'weight' in data and 'buy_price' in data:
            data['buy_gram_price'] = round(data['buy_price'] / data['weight'], 3)
            buy_fee = data.get('buy_fee', 0)
            data['total_cost'] = round(data['buy_price'] + buy_fee, 2)

        # 设置状态
        data['status'] = '在库'
        data['is_sold'] = 0

        # 构建插入语句
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        sql = f'INSERT INTO collections ({columns}) VALUES ({placeholders})'

        cursor.execute(sql, list(data.values()))
        conn.commit()

        return cursor.lastrowid

    def update_collection(self, item_id, data):
        """
        更新藏品记录
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 重新计算克价
        if 'weight' in data and 'buy_price' in data:
            data['buy_gram_price'] = round(data['buy_price'] / data['weight'], 3)
            buy_fee = data.get('buy_fee', 0)
            data['total_cost'] = round(data['buy_price'] + buy_fee, 2)

        data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        set_clause = ', '.join([f'{k} = ?' for k in data.keys()])
        sql = f'UPDATE collections SET {set_clause} WHERE item_id = ?'

        cursor.execute(sql, list(data.values()) + [item_id])
        conn.commit()

        return cursor.rowcount

    def delete_collection(self, item_id):
        """删除藏品记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM collections WHERE item_id = ?', (item_id,))
        conn.commit()
        return cursor.rowcount

    def get_collections(self, filters=None):
        """
        获取藏品列表
        filters: 可选的过滤条件字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = 'SELECT * FROM collections WHERE 1=1'
        params = []

        if filters:
            if filters.get('material'):
                sql += ' AND material = ?'
                params.append(filters['material'])
            if filters.get('status'):
                sql += ' AND status = ?'
                params.append(filters['status'])
            if filters.get('year'):
                sql += ' AND year = ?'
                params.append(filters['year'])
            if filters.get('series'):
                sql += ' AND series LIKE ?'
                params.append(f"%{filters['series']}%")
            if filters.get('keyword'):
                sql += ' AND (name LIKE ? OR item_id LIKE ? OR tags LIKE ?)'
                keyword = f"%{filters['keyword']}%"
                params.extend([keyword, keyword, keyword])

        sql += ' ORDER BY created_at DESC'

        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_collection_by_id(self, item_id):
        """根据ID获取单个藏品"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM collections WHERE item_id = ?', (item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def record_sell(self, item_id, sell_data):
        """
        记录卖出交易
        自动计算盈亏、持有天数、年化收益率
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取买入记录
        cursor.execute('SELECT * FROM collections WHERE item_id = ?', (item_id,))
        buy_record = dict(cursor.fetchone())

        # 计算盈亏
        total_cost = buy_record['total_cost'] or 0
        sell_amount = sell_data.get('sell_price', 0)
        sell_fee = sell_data.get('sell_fee', 0)
        net_sales = sell_amount - sell_fee

        profit_loss = net_sales - total_cost
        profit_rate = (profit_loss / total_cost * 100) if total_cost > 0 else 0

        # 计算持有天数
        buy_date = datetime.strptime(buy_record['buy_date'], '%Y-%m-%d')
        sell_date = datetime.strptime(sell_data['sell_date'], '%Y-%m-%d')
        hold_days = (sell_date - buy_date).days

        # 计算年化收益率
        if hold_days > 0 and total_cost > 0:
            annual_roi = (profit_loss / total_cost) * (365 / hold_days) * 100
        else:
            annual_roi = 0

        # 计算卖出克价
        weight = buy_record['weight'] or 1
        sell_gram_price = round((sell_amount - sell_fee) / weight, 3)

        # 更新记录
        update_data = {
            'sell_date': sell_data['sell_date'],
            'sell_price': sell_amount,
            'sell_fee': sell_fee,
            'sell_channel': sell_data.get('sell_channel'),
            'sell_notes': sell_data.get('sell_notes'),
            'sell_gram_price': sell_gram_price,
            'net_sales': net_sales,
            'profit_loss': round(profit_loss, 2),
            'profit_rate': round(profit_rate, 2),
            'hold_days': hold_days,
            'annual_roi': round(annual_roi, 2),
            'status': '已售',
            'is_sold': 1
        }

        set_clause = ', '.join([f'{k} = ?' for k in update_data.keys()])
        sql = f'UPDATE collections SET {set_clause}, updated_at = ? WHERE item_id = ?'

        cursor.execute(sql, list(update_data.values()) + [datetime.now().strftime('%Y-%m-%d %H:%M:%S'), item_id])
        conn.commit()

        return update_data

    def get_statistics(self):
        """获取统计数据"""
        conn = self.get_connection()
        cursor = conn.cursor()

        stats = {}

        # 持仓数量和市值
        cursor.execute('''
            SELECT COUNT(*) as count,
                   COALESCE(SUM(total_cost), 0) as total_cost,
                   COALESCE(SUM(CASE WHEN current_market_value THEN current_market_value ELSE total_cost END), 0) as total_value
            FROM collections WHERE is_sold = 0
        ''')
        holding = cursor.fetchone()
        stats['holding_count'] = holding['count']
        stats['total_cost'] = holding['total_cost']
        stats['total_market_value'] = holding['total_value']

        # 已实现盈亏
        cursor.execute('''
            SELECT COALESCE(SUM(profit_loss), 0) as realized_pl,
                   COALESCE(AVG(profit_rate), 0) as avg_profit_rate
            FROM collections WHERE is_sold = 1
        ''')
        realized = cursor.fetchone()
        stats['realized_profit_loss'] = realized['realized_pl']
        stats['avg_profit_rate'] = realized['avg_profit_rate']

        # 按材质统计
        cursor.execute('''
            SELECT material, COUNT(*) as count,
                   COALESCE(SUM(total_cost), 0) as cost,
                   COALESCE(SUM(CASE WHEN current_market_value THEN current_market_value ELSE total_cost END), 0) as value
            FROM collections WHERE is_sold = 0
            GROUP BY material
        ''')
        stats['by_material'] = [dict(row) for row in cursor.fetchall()]

        # 买入总金额
        cursor.execute('SELECT COALESCE(SUM(buy_price * buy_quantity), 0) as total FROM collections')
        stats['total_invested'] = cursor.fetchone()['total']

        return stats

    def get_profit_loss_report(self, year=None):
        """获取盈亏报表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = '''
            SELECT
                CASE
                    WHEN is_sold = 1 THEN '已实现盈亏'
                    ELSE '未实现盈亏'
                END as category,
                material,
                COUNT(*) as count,
                COALESCE(SUM(total_cost), 0) as total_cost,
                COALESCE(SUM(CASE WHEN is_sold = 1 THEN net_sales ELSE current_market_value END), 0) as total_value,
                COALESCE(SUM(CASE WHEN is_sold = 1 THEN profit_loss ELSE current_market_value - total_cost END), 0) as profit_loss
            FROM collections
        '''

        if year:
            sql += f' WHERE strftime("%Y", buy_date) = "{year}"'

        sql += ' GROUP BY is_sold, material ORDER BY category, material'

        cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]

    def export_to_excel(self, filepath):
        """导出数据到Excel"""
        try:
            import pandas as pd

            conn = self.get_connection()
            df = pd.read_sql_query('SELECT * FROM collections', conn)

            # 转换日期格式
            date_columns = ['buy_date', 'sell_date', 'created_at', 'updated_at']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d')

            df.to_excel(filepath, index=False, engine='openpyxl')
            return True
        except Exception as e:
            print(f"导出Excel失败: {e}")
            return False

    def backup_database(self):
        """备份数据库"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(self.backup_dir, f'coin_vault_backup_{timestamp}.db')

        try:
            shutil.copy2(self.db_path, backup_file)

            # 清理旧备份（保留最近7个）
            backups = sorted(os.listdir(self.backup_dir))
            while len(backups) > 7:
                os.remove(os.path.join(self.backup_dir, backups.pop(0)))

            return backup_file
        except Exception as e:
            print(f"备份失败: {e}")
            return None

    def restore_database(self, backup_file):
        """恢复数据库"""
        try:
            shutil.copy2(backup_file, self.db_path)
            return True
        except Exception as e:
            print(f"恢复失败: {e}")
            return False

    def save_gold_price(self, date, prices):
        """保存金价记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO gold_price_records
            (date, gold_price, silver_price, platinum_price, palladium_price)
            VALUES (?, ?, ?, ?, ?)
        ''', (date, prices.get('gold'), prices.get('silver'),
              prices.get('platinum'), prices.get('palladium')))

        conn.commit()

    def get_gold_price(self, date=None):
        """获取金价记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if date:
            cursor.execute('SELECT * FROM gold_price_records WHERE date = ?', (date,))
        else:
            cursor.execute('SELECT * FROM gold_price_records ORDER BY date DESC LIMIT 1')

        row = cursor.fetchone()
        return dict(row) if row else None

    def get_setting(self, key, default=None):
        """获取设置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else default

    def set_setting(self, key, value):
        """保存设置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', (key, value, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None


if __name__ == '__main__':
    # 测试数据库管理器
    db = DatabaseManager()
    db.initialize_database()
    print("数据库测试通过")
