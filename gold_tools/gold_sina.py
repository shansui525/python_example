import time
import requests
import re
from datetime import datetime

class SinaGoldParser:
    """新浪贵金属数据解析器（简化版）"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn'
        }

    def parse_single(self, symbol: str, data_str: str) -> dict:
        """解析单个品种数据"""
        fields = data_str.split(',')

        # 基本字段
        price = float(fields[0]) if fields[0] else 0
        bid = float(fields[2]) if fields[2] else price
        ask = float(fields[3]) if fields[3] else price
        high = float(fields[4]) if fields[4] else price
        low = float(fields[5]) if fields[5] else price
        time_str = fields[6] if fields[6] else "00:00:00"
        open_price = float(fields[7]) if fields[7] else price
        prev_close = float(fields[8]) if fields[8] else price
        date = fields[12] if len(fields) > 12 else datetime.now().strftime('%Y-%m-%d')

        # 品种名称
        name = fields[13] if len(fields) > 13 else symbol

        # 计算涨跌
        change = price - prev_close
        change_percent = (change / prev_close * 100) if prev_close > 0 else 0

        return {
            'symbol': symbol,
            'name': name,
            'price': price,
            'change': change,
            'change_percent': change_percent,
            'bid': bid,
            'ask': ask,
            'high': high,
            'low': low,
            'open': open_price,
            'prev_close': prev_close,
            'time': time_str,
            'date': date,
            'spread': ask - bid
        }

    def parse_all(self, raw_text: str) -> dict:
        """解析全部数据"""
        results = {}
        pattern = r'var hq_str_(\w+)="([^"]+)"'

        for match in re.findall(pattern, raw_text):
            symbol, data_str = match
            # print(symbol,'---',data_str)
            results[symbol] = self.parse_single(symbol, data_str)

        return results

    def fetch_realtime(self, symbols=None):
        """获取实时数据"""
        if symbols is None:
            symbols = ['hf_XAU', 'hf_XAG', 'hf_GC', 'hf_SI']

        url = f"http://hq.sinajs.cn/etag.php?list={','.join(symbols)}"

        try:
            resp = requests.get(url, headers=self.headers, timeout=5)
            resp.encoding = 'gb2312'
            return self.parse_all(resp.text)
        except Exception as e:
            print(f"获取数据失败: {e}")
            return {}


def getPrice(data):
    """主函数 - 简单使用示例"""
    parser = SinaGoldParser()

    realtime_data = parser.fetch_realtime([data])

    if realtime_data:
        for symbol, info in realtime_data.items():
            arrow = "↑" if info['change'] >= 0 else "↓"
            print(f"  {info['name']}: ${info['price']:.2f} {arrow} ({info['change_percent']:+.2f}%)")
            return info['price']


if __name__ == "__main__":
    data = 'gds_AUTD'
    gold_price = getPrice(data)
    print(gold_price)