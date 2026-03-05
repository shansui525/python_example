# -*- coding: utf-8 -*-
"""
应用程序样式配置
定义颜色、字体和常用样式
"""

class AppStyles:
    """应用程序样式配置类"""

    # 主题颜色
    COLORS = {
        # 主色调
        'primary': '#B8860B',        # 暗金色 - 主色
        'primary_dark': '#8B6914',    # 深暗金
        'primary_light': '#DAA520',   # 亮金色

        # 功能色
        'success': '#2E8B57',         # 收益绿
        'danger': '#CD5C5C',          # 亏损红
        'warning': '#F0AD4E',         # 警告橙
        'info': '#5BC0DE',            # 信息蓝

        # 中性色
        'dark': '#2C3E50',           # 深灰
        'gray': '#95A5A6',           # 中灰
        'light': '#ECF0F1',           # 浅灰
        'white': '#FFFFFF',          # 白色

        # 背景色
        'bg_main': '#F5F7FA',        # 主背景
        'bg_sidebar': '#2C3E50',    # 侧边栏背景
        'bg_card': '#FFFFFF',        # 卡片背景

        # 文字色
        'text_primary': '#2C3E50',   # 主文字
        'text_secondary': '#7F8C8D', # 次要文字
        'text_light': '#BDC3C7',    # 浅文字
        'text_white': '#FFFFFF',     # 白色文字
    }

    # 字体配置
    FONTS = {
        'title': ('Microsoft YaHei', 16, 'bold'),
        'heading': ('Microsoft YaHei', 14, 'bold'),
        'subheading': ('Microsoft YaHei', 12, 'bold'),
        'body': ('Microsoft YaHei', 10),
        'small': ('Microsoft YaHei', 9),
        'mono': ('Consolas', 10),
    }

    # 尺寸配置
    SIZES = {
        'sidebar_width': 220,
        'header_height': 60,
        'padding': 10,
        'margin': 15,
        'border_radius': 5,
    }

    @classmethod
    def get_style_config(cls):
        """获取完整的样式配置字典"""
        return {
            'colors': cls.COLORS,
            'fonts': cls.FONTS,
            'sizes': cls.SIZES
        }


def apply_global_style(root):
    """应用全局样式到根窗口"""
    style_config = AppStyles.get_style_config()

    # 设置主题
    root.style = ttk.Style()
    root.style.theme_use('clam')

    # 配置Treeview样式
    root.style.configure('Treeview',
                         background=AppStyles.COLORS['white'],
                         foreground=AppStyles.COLORS['text_primary'],
                         fieldbackground=AppStyles.COLORS['white'],
                         rowheight=30,
                         font=AppStyles.FONTS['body'])

    root.style.configure('Treeview.Heading',
                         background=AppStyles.COLORS['primary'],
                         foreground=AppStyles.COLORS['text_white'],
                         font=AppStyles.FONTS['subheading'])

    # 配置按钮样式
    root.style.configure('Primary.TButton',
                         background=AppStyles.COLORS['primary'],
                         foreground=AppStyles.COLORS['text_white'],
                         font=AppStyles.FONTS['body'])

    root.style.configure('Success.TButton',
                         background=AppStyles.COLORS['success'],
                         foreground=AppStyles.COLORS['text_white'],
                         font=AppStyles.FONTS['body'])

    root.style.configure('Danger.TButton',
                         background=AppStyles.COLORS['danger'],
                         foreground=AppStyles.COLORS['text_white'],
                         font=AppStyles.FONTS['body'])


# 导入ttk用于样式配置
import tkinter.ttk as ttk
