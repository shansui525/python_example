# -*- coding: utf-8 -*-
"""
金银币投资管理系统 - 主程序入口
CoinVault Pro - Personal Gold & Silver Coin Investment Management System

功能：
- 藏品信息管理
- 交易记录管理（买入/卖出）
- 克价与成本核算
- 盈亏核算
- 持仓分析
- 报表与导出

作者：MiniMax Agent
版本：v1.0
"""
import tkinter as tk
from tkinter import ttk
import sys
import os
import logging
from datetime import datetime

# 确保能导入 gui 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 创建 log 目录（如果不存在）
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log')
os.makedirs(log_dir, exist_ok=True)

# 配置全局日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            os.path.join(log_dir, f'coin_vault_{datetime.now().strftime("%Y%m%d")}.log'),
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


from gui.frames import (
    DashboardFrame,
    CollectionFrame,
    BuyFrame,
    SellFrame,
    ReportsFrame,
    SettingsFrame
)
from database import DatabaseManager
from api_gold_price import GoldPriceUpdater


class MainWindow(tk.Tk):
    """主窗口类"""

    def __init__(self):
        super().__init__()

        logger.info("=" * 60)
        logger.info("系统启动 - CoinVault Pro 启动")
        logger.info("=" * 60)

        self.title("金银币投资管理系统 - CoinVault Pro")
        self.geometry("1200x800")

        # 设置最小窗口大小
        self.minsize(1024, 768)

        # 初始化数据库
        self.db = DatabaseManager()
        self.db.initialize_database()
        logger.info("数据库初始化完成")

        # 验证必要的表是否存在
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gold_price_records'")
        if not cursor.fetchone():
            logger.warning("gold_price_records 表不存在，重新初始化")
            self.db.initialize_database()
        else:
            logger.info("gold_price_records 表已存在")

        # 【关键修改】先创建底部状态栏，再创建 Notebook
        # 这样状态栏会固定在底部，不会被 Notebook 遮挡
        self._create_status_bar()
        logger.info("底部状态栏创建完成")

        # 创建主容器 (Notebook)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        logger.info("主界面 Notebook 创建完成")

        # --- 创建页面并赋值给实例属性 ---

        # 1. 仪表盘
        self.dashboard_frame = DashboardFrame(self.notebook, self.db, self)
        self.notebook.add(self.dashboard_frame, text="📊 仪表盘")
        logger.info("页面加载：仪表盘")

        # 2. 藏品库
        self.collection_frame = CollectionFrame(self.notebook, self.db, self)
        self.notebook.add(self.collection_frame, text="🎯 藏品库")
        logger.info("页面加载：藏品库")

        # 3. 买入录入
        self.buy_frame = BuyFrame(self.notebook, self.db, self)
        self.notebook.add(self.buy_frame, text="💵 买入录入")
        logger.info("页面加载：买入录入")

        # 4. 卖出录入
        self.sell_frame = SellFrame(self.notebook, self.db, self)
        self.notebook.add(self.sell_frame, text="💴 卖出录入")
        logger.info("页面加载：卖出录入")

        # 5. 统计报表
        self.reports_frame = ReportsFrame(self.notebook, self.db, self)
        self.notebook.add(self.reports_frame, text="📈 统计报表")
        logger.info("页面加载：统计报表")

        # 6. 系统设置
        self.settings_frame = SettingsFrame(self.notebook, self.db, self)
        self.notebook.add(self.settings_frame, text="⚙️ 系统设置")
        logger.info("页面加载：系统设置")

        # 绑定选项卡切换事件
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
        logger.info("选项卡切换事件绑定完成")

        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        logger.info("窗口关闭事件绑定完成")

        # 初始化金价 API 更新器
        self.gold_updater = GoldPriceUpdater(self.db)
        self.gold_updater.start()
        logger.info("金价 API 更新器已启动")

        # 初始获取一次金价
        self.after(1000, self._initial_gold_price_update)

    def _create_status_bar(self):
        """创建底部状态栏显示实时金价"""
        # 使用 pack(side=BOTTOM) 确保状态栏固定在底部
        self.status_frame = tk.Frame(self, bg='#E8F4F8', height=35)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_frame.pack_propagate(False)  # 防止框架收缩

        # 添加一个分隔线，让状态栏更明显
        separator = tk.Frame(self.status_frame, bg='#CCCCCC', height=2)
        separator.pack(fill=tk.X)

        # 内容区域
        content_frame = tk.Frame(self.status_frame, bg='#E8F4F8')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        # 使用 grid 布局
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_columnconfigure(2, weight=0)
        content_frame.grid_columnconfigure(3, weight=0)

        # 黄金价格显示 - 增加字体大小和对比度
        self.gold_label = tk.Label(
            content_frame,
            text="🥇 黄金: --.--",
            font=('Microsoft YaHei', 10, 'bold'),
            bg='#E8F4F8',
            fg='#B8860B',
            anchor='w',
            padx=5
        )
        self.gold_label.grid(row=0, column=0, sticky='w', padx=5)

        # 白银价格显示
        self.silver_label = tk.Label(
            content_frame,
            text="🥈 白银: --.--",
            font=('Microsoft YaHei', 10, 'bold'),
            bg='#E8F4F8',
            fg='#7F8C8D',
            anchor='w',
            padx=5
        )
        self.silver_label.grid(row=0, column=1, sticky='w', padx=5)

        # 更新时间显示
        self.time_label = tk.Label(
            content_frame,
            text="更新: --:--",
            font=('Microsoft YaHei', 9),
            bg='#E8F4F8',
            fg='#666666',
            anchor='e',
            padx=5
        )
        self.time_label.grid(row=0, column=2, sticky='e', padx=5)

        # 数据来源标签 - 增加背景色使其更明显
        self.source_label = tk.Label(
            content_frame,
            text="📡 API",
            font=('Microsoft YaHei', 8),
            bg='#D5E8D4',
            fg='#2E7D32',
            anchor='e',
            padx=8,
            pady=2,
            relief=tk.RAISED,
            bd=1
        )
        self.source_label.grid(row=0, column=3, sticky='e', padx=5)

        # 强制刷新显示
        self.status_frame.update_idletasks()

    def _initial_gold_price_update(self):
        """初始更新金价"""
        self._update_status_bar_prices()
        # 之后每 5 分钟更新一次
        self._schedule_gold_price_update()

    def _schedule_gold_price_update(self):
        """定时更新金价显示"""
        self._update_status_bar_prices()
        # 5 分钟后再次更新
        self.after(300000, self._schedule_gold_price_update)

    def _update_status_bar_prices(self):
        """更新状态栏金价显示"""
        try:
            latest_prices = self.db.get_latest_gold_prices()

            if latest_prices:
                gold_price = latest_prices.get('gold_price', 0)
                silver_price = latest_prices.get('silver_price', 0)
                date = latest_prices.get('date', '')

                if gold_price > 0:
                    self.gold_label.configure(text=f"🥇 黄金: {gold_price:.2f}")
                    logger.debug(f"黄金价格更新: {gold_price:.2f}")
                else:
                    self.gold_label.configure(text="🥇 黄金: --.--")

                if silver_price > 0:
                    self.silver_label.configure(text=f"🥈 白银: {silver_price:.2f}")
                    logger.debug(f"白银价格更新: {silver_price:.2f}")
                else:
                    self.silver_label.configure(text="🥈 白银: --.--")

                # 提取时间部分
                if date:
                    if ' ' in date:
                        time_part = date.split(' ')[1][:5]
                        self.time_label.configure(text=f"更新: {time_part}")
                    else:
                        self.time_label.configure(text=f"更新: {date[-5:]}")

                logger.info(f"状态栏金价已更新 - 黄金：{gold_price:.2f}, 白银：{silver_price:.2f}")
            else:
                logger.warning("未获取到金价数据")
        except Exception as e:
            logger.error(f"更新状态栏金价失败：{str(e)}", exc_info=True)

    def on_gold_price_updated(self, prices):
        """金价更新回调"""
        try:
            if prices.get('gold'):
                self.gold_label.configure(text=f"🥇 黄金: {prices['gold']:.2f}")
            if prices.get('silver'):
                self.silver_label.configure(text=f"🥈 白银: {prices['silver']:.2f}")

            now_str = datetime.now().strftime('%H:%M')
            self.time_label.configure(text=f"更新: {now_str}")

            logger.info(f"API 回调更新金价 - 黄金：{prices.get('gold', 0):.2f}, 白银：{prices.get('silver', 0):.2f}")

        except Exception as e:
            logger.error(f"回调更新金价显示失败：{str(e)}")

    # ... existing code ...

    def _on_tab_changed(self, event):
        """选项卡切换时的日志记录"""
        selected_tab = self.notebook.select()
        tab_name = self.notebook.tab(selected_tab, "text")
        logger.info(f"用户切换页面：{tab_name}")

    def _on_closing(self):
        """窗口关闭处理"""
        if messagebox.askokcancel("退出", "确定要退出系统吗？"):
            logger.info("用户确认退出系统")
            # 停止金价更新器
            if hasattr(self, 'gold_updater'):
                self.gold_updater.stop()
            logger.info("金价更新器已停止")
            logger.info("=" * 60)
            self.db.close_connection()
            self.destroy()
            sys.exit(0)
        else:
            logger.info("用户取消退出")


if __name__ == "__main__":
    # 导入 messagebox 用于关闭确认
    from tkinter import messagebox

    logger.info("程序开始执行")
    app = MainWindow()
    logger.info("主窗口创建完成，进入消息循环")
    app.mainloop()
