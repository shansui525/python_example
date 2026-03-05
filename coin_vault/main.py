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

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import json
import shutil

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from database import DatabaseManager
from gui.main_window import MainWindow

def setup_logging():
    """配置日志输出"""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(PROJECT_ROOT, 'app.log'), encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def main():
    """主函数"""
    # 确保数据目录存在
    data_dir = os.path.join(PROJECT_ROOT, 'data')
    os.makedirs(data_dir, exist_ok=True)

    # 初始化数据库
    db = DatabaseManager()
    db.initialize_database()

    # 创建并运行主窗口
    root = tk.Tk()
    app = MainWindow(root, db)
    root.mainloop()

if __name__ == '__main__':
    main()
