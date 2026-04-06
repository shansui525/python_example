# -*- coding: utf-8 -*-
"""
从新浪 API 获取贵金属价格
每 5 分钟更新一次数据
"""

import requests
import re
import time
import logging
from datetime import datetime
from threading import Thread, Event
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


class SinaGoldAPI:
    """新浪贵金属 API 获取器"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }

        # 使用上海黄金交易所的品种（价格单位：元/克）
        self.symbols = {
            'gold': 'gds_AUTD',      # 黄金延期 Au(T+D) - 元/克
            'silver': 'gds_AGTD',    # 白银延期 Ag(T+D) - 元/克
        }

    def fetch_prices(self):
        """获取贵金属价格"""
        try:
            symbols_list = [self.symbols['gold'], self.symbols['silver']]
            url = f"http://hq.sinajs.cn/list={','.join(symbols_list)}"

            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = 'gb2312'

            prices = self._parse_response(response.text)

            if prices:
                logger.info(f"API 获取金价成功 - 黄金：{prices.get('gold', 0):.2f}, 白银：{prices.get('silver', 0):.2f}")
                return prices
            else:
                logger.warning("API 返回数据为空")
                return None

        except Exception as e:
            logger.error(f"获取 API 金价失败：{str(e)}")
            return None

    def _parse_response(self, text):
        """解析新浪 API 返回的数据"""
        prices = {}

        # 解析格式：var hq_str_gds_AUTD="当前价,昨收,开盘,最高,最低,时间,..."
        pattern = r'var hq_str_(\w+)="([^"]+)"'

        for match in re.findall(pattern, text):
            symbol, data_str = match
            fields = data_str.split(',')

            if len(fields) < 2:
                continue

            # 第一个字段就是当前价格（元/克）
            current_price = float(fields[0]) if fields[0] else 0

            # 上海黄金交易所的价格已经是元/克，不需要转换
            if symbol == 'gds_AUTD':
                prices['gold'] = round(current_price, 2)
                logger.debug(f"解析黄金价格: {current_price} 元/克")
            elif symbol == 'gds_AGTD':
                prices['silver'] = round(current_price/1000, 2)
                logger.debug(f"解析白银价格: {current_price} 元/克")

        return prices

# ... existing code ...



class GoldPriceUpdater:
    """金价定时更新器"""

    def __init__(self, db_manager):
        self.db_path = db_manager.db_path  # 保存数据库路径而不是连接对象
        self.api = SinaGoldAPI()
        self.stop_event = Event()
        self.thread = None
        self.update_interval = 300  # 5 分钟 = 300 秒

    def start(self):
        """启动定时更新"""
        if self.thread and self.thread.is_alive():
            logger.warning("金价更新线程已在运行")
            return

        self.stop_event.clear()
        self.thread = Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        logger.info("金价 API 定时更新已启动（每 5 分钟）")

    def stop(self):
        """停止定时更新"""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("金价 API 定时更新已停止")

    def _get_db_connection(self):
        """获取新的数据库连接（线程安全）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _update_loop(self):
        """更新循环"""
        while not self.stop_event.is_set():
            try:
                # 获取 API 数据
                prices = self.api.fetch_prices()

                if prices:
                    # 创建新的数据库连接（线程安全）
                    conn = self._get_db_connection()
                    try:
                        self._save_to_db(conn, prices)

                        # 通知 GUI 更新显示
                        if hasattr(self, 'gui_callback'):
                            self.gui_callback('gold_price_updated', prices)
                    finally:
                        conn.close()

                # 等待下一个周期
                self.stop_event.wait(self.update_interval)

            except Exception as e:
                logger.error(f"金价更新循环出错：{str(e)}", exc_info=True)
                self.stop_event.wait(60)  # 出错后等待 1 分钟

    def _save_to_db(self, conn, prices):
        """保存到数据库"""
        cursor = conn.cursor()
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

        conn.commit()

    def update_now(self):
        """立即更新一次"""
        try:
            prices = self.api.fetch_prices()
            if prices:
                conn = self._get_db_connection()
                try:
                    self._save_to_db(conn, prices)
                finally:
                    conn.close()
                return prices
        except Exception as e:
            logger.error(f"手动更新金价失败：{str(e)}")
        return None




# 在 api_gold_price.py 文件末尾添加测试代码
if __name__ == "__main__":
    api = SinaGoldAPI()
    print("正在获取金价...")
    prices = api.fetch_prices()

    if prices:
        print(f"\n=== 上海黄金交易所实时价格 ===")
        print(f"黄金 Au(T+D)：¥{prices.get('gold', 0):.2f}/克")
        print(f"白银 Ag(T+D)：¥{prices.get('silver', 0):.2f}/克")
        print(f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("获取价格失败")

