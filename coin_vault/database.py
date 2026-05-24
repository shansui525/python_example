# -*- coding: utf-8 -*-
"""
数据库管理模块
负责SQLite数据库的初始化、数据操作和备份恢复
"""

import sqlite3
import os
import json
from datetime import datetime,timedelta
import shutil
import logging
# 配置日志
logger = logging.getLogger(__name__)

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

    # 【新增】添加关闭连接的方法
    def close_connection(self):
        """关闭数据库连接"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.conn = None

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
        # buy_price 是单价，需要乘以数量
        if 'weight' in data and 'buy_price' in data:
            buy_quantity = data.get('buy_quantity', 1)
            buy_fee = data.get('buy_fee', 0)

            # 单价（用于计算克价）
            unit_price = data['buy_price']
            data['buy_gram_price'] = round(unit_price / data['weight'], 3)

            # 总成本 = 单价 × 数量 + 费用
            data['total_cost'] = round((unit_price * buy_quantity) + buy_fee, 2)

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

        # 重新计算克价和总成本
        if 'weight' in data and 'buy_price' in data:
            buy_quantity = data.get('buy_quantity', 1)
            buy_fee = data.get('buy_fee', 0)

            # 单价（用于计算克价）
            unit_price = data['buy_price']
            data['buy_gram_price'] = round(unit_price / data['weight'], 3)

            # 总成本 = 单价 × 数量 + 费用
            data['total_cost'] = round((unit_price * buy_quantity) + buy_fee, 2)

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

    def get_statistics(self, year=None):
        """获取统计数据（修复：区分投资币和纪念币计算市值）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. 获取最新的市场价格 (用于投资币)
        cursor.execute('''
            SELECT gold_price, silver_price, platinum_price, palladium_price 
            FROM gold_price_records 
            ORDER BY date DESC LIMIT 1
        ''')
        latest_prices = cursor.fetchone()

        p_gold = latest_prices[0] if latest_prices and latest_prices[0] else 0
        p_silver = latest_prices[1] if latest_prices and latest_prices[1] else 0
        p_platinum = latest_prices[2] if latest_prices and latest_prices[2] else 0
        p_palladium = latest_prices[3] if latest_prices and latest_prices[3] else 0

        price_map = {
            '金': p_gold,
            '银': p_silver,
            '铂': p_platinum,
            '钯': p_palladium
        }

        # 2. 查询在库藏品，支持按年份筛选（截止到该年年底仍在库）
        sql = '''
            SELECT material, weight, total_cost, type, current_market_value, buy_quantity
            FROM collections 
            WHERE is_sold = 0
        '''
        params = []

        if year:
            # 截止到该年年底：买入日期 <= 该年12月31日 AND (未卖出 OR 卖出日期 > 该年12月31日)
            # 但由于我们只查 is_sold = 0 的，所以只需要：买入日期 <= 该年12月31日
            year_end = f"{year}-12-31"
            sql += ' AND buy_date <= ?'
            params.append(year_end)

        cursor.execute(sql, params)
        holdings = cursor.fetchall()

        total_market_value = 0.0
        total_cost_sum = 0.0
        total_gold_weight = 0.0
        holding_count = 0
        material_stats = {}

        for row in holdings:
            material = row['material']
            weight = row['weight'] or 0
            cost = row['total_cost'] or 0
            item_type = row['type']
            current_mv = row['current_market_value']
            quantity = row['buy_quantity'] or 1  # 获取数量，默认为1

            # 【修改】累加金币数量
            if material == '金':
                holding_count += quantity

            # 累加总成本
            total_cost_sum += cost

            # 【核心修改】根据类型计算市值
            current_item_value = 0

            if item_type == '投资币':
                # 投资币：重量 × 数量 × 对应材质金价
                unit_price = price_map.get(material, 0)
                current_item_value = weight * quantity * unit_price

            # 统计黄金克重 (总克重 = 单枚重量 × 数量)
            if material == '金':
                total_gold_weight += weight * quantity

            elif item_type == '纪念币':
                # 纪念币：优先使用 current_market_value，若为空则使用 total_cost (购买价)
                if current_mv is not None and current_mv > 0:
                    current_item_value = current_mv
                else:
                    current_item_value = cost
                # 纪念币通常不按克重统计金属价值，故不累加到 total_gold_weight

            # 累加总市值
            total_market_value += current_item_value

            # 统计各材质/类型分布数据
            key = material
            if key not in material_stats:
                material_stats[key] = {'count': 0, 'cost': 0, 'value': 0, 'weight': 0}

            material_stats[key]['count'] += quantity  # 修改：累加数量而不是记录数
            material_stats[key]['cost'] += cost
            material_stats[key]['value'] += current_item_value
            material_stats[key]['weight'] += weight * quantity  # 累加总重量


        # 3. 计算已实现盈亏 (保持不变)
        cursor.execute('''
            SELECT COALESCE(SUM(profit_loss), 0) as realized_pl
            FROM collections 
            WHERE is_sold = 1
        ''')
        realized_result = cursor.fetchone()
        realized_pl = realized_result['realized_pl'] if realized_result else 0

        by_material_list = [
            {
                'material': mat,
                'count': data['count'],
                'cost': data['cost'],
                'value': data['value'],
                'weight': data['weight']
            } for mat, data in material_stats.items()
        ]

        cursor.execute('SELECT COALESCE(SUM(total_cost), 0) as total FROM collections')
        total_invested = cursor.fetchone()['total']

        return {
            'total_market_value': round(total_market_value, 2),
            'total_cost': round(total_cost_sum, 2),
            'realized_profit_loss': round(realized_pl, 2),
            'holding_count': holding_count,
            'total_gold_weight': round(total_gold_weight, 3),
            'by_material': by_material_list,
            'total_invested': round(total_invested, 2)
        }



    def get_profit_loss_report(self, year=None):
        """获取盈亏报表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取最新金价用于动态计算投资币市值
        cursor.execute('''
            SELECT gold_price, silver_price, platinum_price, palladium_price 
            FROM gold_price_records 
            ORDER BY date DESC LIMIT 1
        ''')
        latest_prices = cursor.fetchone()

        p_gold = latest_prices[0] if latest_prices and latest_prices[0] else 0
        p_silver = latest_prices[1] if latest_prices and latest_prices[1] else 0
        p_platinum = latest_prices[2] if latest_prices and latest_prices[2] else 0
        p_palladium = latest_prices[3] if latest_prices and latest_prices[3] else 0

        sql = '''
            SELECT
                CASE
                    WHEN is_sold = 1 THEN '已实现盈亏'
                    ELSE '未实现盈亏'
                END as category,
                material,
                SUM(buy_quantity) as count,
                COALESCE(SUM(total_cost), 0) as total_cost,
                COALESCE(SUM(CASE 
                    WHEN is_sold = 1 THEN net_sales 
                    ELSE 
                        CASE 
                            WHEN type = '投资币' THEN (weight * buy_quantity * 
                                CASE material 
                                    WHEN '金' THEN ? 
                                    WHEN '银' THEN ? 
                                    WHEN '铂' THEN ? 
                                    WHEN '钯' THEN ? 
                                    ELSE 0 
                                END)
                            WHEN current_market_value IS NOT NULL AND current_market_value > 0 THEN current_market_value
                            ELSE total_cost
                        END
                END), 0) as total_value,
                COALESCE(SUM(CASE 
                    WHEN is_sold = 1 THEN profit_loss 
                    ELSE 
                        CASE 
                            WHEN type = '投资币' THEN (weight * buy_quantity * 
                                CASE material 
                                    WHEN '金' THEN ? 
                                    WHEN '银' THEN ? 
                                    WHEN '铂' THEN ? 
                                    WHEN '钯' THEN ? 
                                    ELSE 0 
                                END) - total_cost
                            WHEN current_market_value IS NOT NULL AND current_market_value > 0 THEN current_market_value - total_cost
                            ELSE 0
                        END
                END), 0) as profit_loss
            FROM collections
        '''


        params = [p_gold, p_silver, p_platinum, p_palladium,  # total_value 计算用
                  p_gold, p_silver, p_platinum, p_palladium]  # profit_loss 计算用

        if year:
            sql += f' WHERE strftime("%Y", sell_date) = ?'
            params.append(year)

        sql += ' GROUP BY is_sold, material ORDER BY category, material'

        cursor.execute(sql, params)
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
        cursor = self.conn.cursor()

        # 检查是否已存在该日期的记录
        cursor.execute("SELECT id FROM gold_price_records WHERE date=?", (date,))
        existing = cursor.fetchone()

        if existing:
            # 更新现有记录
            cursor.execute("""
                UPDATE gold_price_records 
                SET gold_price=?, silver_price=?, platinum_price=?, palladium_price=?, notes=?, created_at=?
                WHERE date=?
            """, (
                prices.get('gold', 0),
                prices.get('silver', 0),
                prices.get('platinum', 0),
                prices.get('palladium', 0),
                prices.get('notes', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                date
            ))
        else:
            # 插入新记录
            cursor.execute("""
                INSERT INTO gold_price_records (date, gold_price, silver_price, platinum_price, palladium_price, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                date,
                prices.get('gold', 0),
                prices.get('silver', 0),
                prices.get('platinum', 0),
                prices.get('palladium', 0),
                prices.get('notes', '')
            ))

        self.conn.commit()
        logger.info(f"金价已保存 - 日期：{date}, 金：{prices.get('gold', 0)}, 银：{prices.get('silver', 0)}")

    def get_latest_gold_prices(self):
        """获取最新的金价数据"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT date, gold_price, silver_price, platinum_price, palladium_price
            FROM gold_price_records
            ORDER BY date DESC
            LIMIT 1
        """)
        row = cursor.fetchone()

        if row:
            return {
                'date': row[0],
                'gold_price': row[1],
                'silver_price': row[2],
                'platinum_price': row[3],
                'palladium_price': row[4]
            }
        return None

    def save_api_gold_price(self, prices):
        """保存从 API 获取的金价（带来源标记）"""
        cursor = self.conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 检查今天是否已有记录
        cursor.execute("SELECT id FROM gold_price_records WHERE date=?", (today,))
        existing = cursor.fetchone()

        if existing:
            # 更新今天的记录
            cursor.execute("""
                UPDATE gold_price_records 
                SET gold_price=?, silver_price=?, platinum_price=?, palladium_price=?, notes='API自动更新', created_at=?
                WHERE date=?
            """, (
                prices.get('gold', 0),
                prices.get('silver', 0),
                prices.get('platinum', 0),
                prices.get('palladium', 0),
                now,
                today
            ))
            logger.info(f"API 金价已更新 - 金：{prices.get('gold', 0):.2f}, 银：{prices.get('silver', 0):.2f}")
        else:
            # 插入今日新记录
            cursor.execute("""
                INSERT INTO gold_price_records (date, gold_price, silver_price, platinum_price, palladium_price, notes)
                VALUES (?, ?, ?, ?, ?, 'API自动更新')
            """, (
                today,
                prices.get('gold', 0),
                prices.get('silver', 0),
                prices.get('platinum', 0),
                prices.get('palladium', 0)
            ))
            logger.info(f"API 金价已保存 - 金：{prices.get('gold', 0):.2f}, 银：{prices.get('silver', 0):.2f}")

        self.conn.commit()

    # ... existing code ...


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

    def get_annual_monthly_data(self, year):
        """
        获取指定年份每月的：
        1. 月末持仓市值 (基于该月最后一天的金价计算在库物品)
           逻辑：买入 <= 月底 AND (未卖出 OR 卖出日期 > 月底)
        2. 当月实现利润 (该月内卖出物品的 profit_loss 总和)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        result = []

        try:
            year_int = int(year)
        except ValueError:
            return []

        for month in range(1, 13):
            month_str = f"{month:02d}"
            ym = f"{year}-{month_str}"

            # 计算该月起止时间
            first_day = f"{ym}-01"
            # 计算下月第一天减一天得到月底
            if month == 12:
                next_month_dt = datetime(year_int + 1, 1, 1)
            else:
                next_month_dt = datetime(year_int, month + 1, 1)
            last_day = (next_month_dt - timedelta(days=1)).strftime('%Y-%m-%d')

            # --- 1. 获取该月月底的金价 ---
            cursor.execute('''
                            SELECT gold_price, silver_price, platinum_price, palladium_price 
                            FROM gold_price_records 
                            WHERE date <= ? 
                            ORDER BY date DESC LIMIT 1
                        ''', (last_day,))
            prices = cursor.fetchone()

            p_gold = prices[0] if prices and prices[0] else 0
            p_silver = prices[1] if prices and prices[1] else 0
            p_platinum = prices[2] if prices and prices[2] else 0
            p_palladium = prices[3] if prices and prices[3] else 0

            # 【新增】构建当月价格映射表，供下方循环使用
            price_map = {
                '金': p_gold,
                '银': p_silver,
                '铂': p_platinum,
                '钯': p_palladium
            }

            # --- 2. 计算月末持仓市值 ---
            # 查询物品明细
            cursor.execute('''
                                SELECT material, weight, type, current_market_value, total_cost
                                FROM collections
                                WHERE buy_date <= ? 
                                AND (sell_date IS NULL OR sell_date > ?)
                            ''', (last_day, last_day))
            items = cursor.fetchall()

            hold_val = 0
            for item in items:
                m_type = item['type']
                m_mat = item['material']
                m_weight = item['weight'] or 0
                m_mv = item['current_market_value']
                m_cost = item['total_cost'] or 0

                val = 0
                if m_type == '投资币':
                    # 现在 price_map 已定义，且包含的是该月月底的历史金价
                    unit_p = price_map.get(m_mat, 0)
                    val = m_weight * unit_p
                elif m_type == '纪念币':
                    val = m_mv if (m_mv is not None and m_mv > 0) else m_cost

                hold_val += val

            # --- 3. 计算当月实现利润 ---
            # 逻辑：卖出日期在 [first_day, last_day] 之间
            sql_pl = '''
                SELECT COALESCE(SUM(profit_loss), 0) as pl
                FROM collections
                WHERE is_sold = 1 
                AND sell_date >= ? AND sell_date <= ?
            '''
            cursor.execute(sql_pl, (first_day, last_day))
            pl_val = cursor.fetchone()['pl']

            result.append({
                'month': month_str,
                'month_end_value': round(hold_val, 2),
                'monthly_realized_pl': round(pl_val, 2)
            })

        return result

    # def get_setting(self, key, default=None):
    #     """获取设置"""
    #     conn = self.get_connection()
    #     cursor = conn.cursor()
    #     cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    #     row = cursor.fetchone()
    #     return row['value'] if row else default

    def get_setting(self, key, default=None):
        """获取设置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()

        if row:
            val = row['value']
            # 尝试解析 JSON，如果失败则返回原始字符串
            try:
                # 如果存储的是 JSON 格式的列表或字典，将其还原
                if val.startswith('[') or val.startswith('{'):
                    return json.loads(val)
            except (json.JSONDecodeError, AttributeError):
                pass
            return val
        return default

    def set_setting(self, key, value):
        """保存设置"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 确保 value 是字符串类型，如果是列表或字典，序列化为 JSON
        if not isinstance(value, str):
            try:
                value = json.dumps(value, ensure_ascii=False)
            except Exception:
                value = str(value)

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
