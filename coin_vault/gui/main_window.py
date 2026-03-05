# -*- coding: utf-8 -*-
"""
主窗口模块
包含应用程序主界面、导航框架和核心功能模块
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from datetime import datetime

from .styles import AppStyles
from .frames import (
    DashboardFrame,
    CollectionFrame,
    BuyFrame,
    SellFrame,
    ReportsFrame,
    SettingsFrame
)


class MainWindow:
    """主窗口类"""

    def __init__(self, root, db_manager):
        """初始化主窗口"""
        self.root = root
        self.db = db_manager

        # 窗口配置
        self.root.title("金银币投资管理系统 - CoinVault Pro")
        self.root.geometry("1280x800")
        self.root.minsize(1024, 700)

        # 加载样式
        self.colors = AppStyles.COLORS
        self.fonts = AppStyles.FONTS

        # 设置窗口背景
        self.root.configure(bg=self.colors['bg_main'])

        # 初始化UI
        self._create_layout()

        # 加载默认页面
        self._show_frame('dashboard')

        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_layout(self):
        """创建界面布局"""
        # 顶部标题栏
        self._create_header()

        # 主体布局（侧边栏 + 内容区）
        main_container = tk.Frame(self.root, bg=self.colors['bg_main'])
        main_container.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        # 左侧导航栏
        self._create_sidebar(main_container)

        # 右侧内容区
        self._create_content_area(main_container)

    def _create_header(self):
        """创建顶部标题栏"""
        header = tk.Frame(self.root, bg=self.colors['primary'], height=60)
        header.pack(fill=tk.X, side=tk.TOP)

        # 标题
        title_label = tk.Label(
            header,
            text="💰 金银币投资管理系统",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['primary'],
            fg=self.colors['text_white']
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=15)

        # 右侧信息
        info_frame = tk.Frame(header, bg=self.colors['primary'])
        info_frame.pack(side=tk.RIGHT, padx=20, pady=15)

        # 当前日期
        date_label = tk.Label(
            info_frame,
            text=datetime.now().strftime("%Y年%m月%d日"),
            font=self.fonts['body'],
            bg=self.colors['primary'],
            fg=self.colors['text_white']
        )
        date_label.pack(side=tk.RIGHT)

    def _create_sidebar(self, parent):
        """创建左侧导航栏"""
        sidebar = tk.Frame(
            parent,
            bg=self.colors['bg_sidebar'],
            width=AppStyles.SIZES['sidebar_width']
        )
        sidebar.pack(fill=tk.Y, side=tk.LEFT)
        sidebar.pack_propagate(False)

        # 导航菜单配置
        self.nav_items = [
            {"id": "dashboard", "text": "📊 仪表盘", "frame_class": DashboardFrame},
            {"id": "collections", "text": "🎯 藏品库", "frame_class": CollectionFrame},
            {"id": "buy", "text": "💵 买入录入", "frame_class": BuyFrame},
            {"id": "sell", "text": "💴 卖出录入", "frame_class": SellFrame},
            {"id": "reports", "text": "📈 统计报表", "frame_class": ReportsFrame},
            {"id": "settings", "text": "⚙️ 系统设置", "frame_class": SettingsFrame},
        ]

        # 创建导航按钮
        self.nav_buttons = {}
        for item in self.nav_items:
            btn = tk.Button(
                sidebar,
                text=item['text'],
                font=self.fonts['body'],
                bg=self.colors['bg_sidebar'],
                fg=self.colors['text_light'],
                activebackground=self.colors['primary'],
                activeforeground=self.colors['text_white'],
                bd=0,
                pady=12,
                padx=20,
                anchor='w',
                command=lambda i=item['id']: self._show_frame(i)
            )
            btn.pack(fill=tk.X, pady=1)
            self.nav_buttons[item['id']] = btn

        # 分隔线
        separator = tk.Frame(sidebar, bg='#34495E', height=1)
        separator.pack(fill=tk.X, padx=15, pady=20)

        # 底部操作按钮
        backup_btn = tk.Button(
            sidebar,
            text="💾 备份数据",
            font=self.fonts['small'],
            bg=self.colors['bg_sidebar'],
            fg=self.colors['text_light'],
            activebackground=self.colors['primary'],
            activeforeground=self.colors['text_white'],
            bd=0,
            pady=10,
            command=self._backup_data
        )
        backup_btn.pack(fill=tk.X, padx=20)

    def _create_content_area(self, parent):
        """创建右侧内容区"""
        # 内容容器
        content_container = tk.Frame(parent, bg=self.colors['bg_main'])
        content_container.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=0, pady=0)

        # 创建内容帧字典
        self.frames = {}

        # 为每个导航项创建对应的帧
        for item in self.nav_items:
            frame = item['frame_class'](content_container, self.db, self)
            frame.pack(fill=tk.BOTH, expand=True)
            frame.pack_forget()  # 初始隐藏
            self.frames[item['id']] = frame

    def _show_frame(self, frame_id):
        """显示指定帧"""
        # 隐藏所有帧
        for frame in self.frames.values():
            frame.pack_forget()

        # 显示目标帧
        if frame_id in self.frames:
            self.frames[frame_id].pack(fill=tk.BOTH, expand=True)

            # 更新导航按钮状态
            for nav_id, btn in self.nav_buttons.items():
                if nav_id == frame_id:
                    btn.configure(bg=self.colors['primary'], fg=self.colors['text_white'])
                else:
                    btn.configure(bg=self.colors['bg_sidebar'], fg=self.colors['text_light'])

            # 刷新对应页面的数据
            if frame_id == 'dashboard':
                self.frames['dashboard'].refresh_data()
            elif frame_id == 'collections':
                self.frames['collections'].refresh_data()
            elif frame_id == 'sell':
                # 刷新卖出页面的持仓列表
                self.frames['sell']._load_holdings()
            elif frame_id == 'reports':
                self.frames['reports']._load_report()

    def _backup_data(self):
        """备份数据"""
        backup_file = self.db.backup_database()
        if backup_file:
            messagebox.showinfo("备份成功", f"数据已备份到:\n{backup_file}")
        else:
            messagebox.showerror("备份失败", "数据备份失败，请重试")

    def _on_closing(self):
        """窗口关闭事件"""
        if messagebox.askokcancel("退出", "确定要退出程序吗？"):
            # 自动备份
            self.db.backup_database()
            self.root.destroy()

    def show_notification(self, message, type='info'):
        """显示通知消息"""
        if type == 'success':
            messagebox.showinfo("成功", message)
        elif type == 'error':
            messagebox.showerror("错误", message)
        elif type == 'warning':
            messagebox.showwarning("警告", message)
        else:
            messagebox.showinfo("提示", message)