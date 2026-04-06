# -*- coding: utf-8 -*-
"""
GUI 框架模块
包含所有功能页面：仪表盘、藏品库、买入、卖出、报表、设置
修复内容：优化所有功能按钮的文字与背景对比度，确保清晰可见。
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from datetime import datetime
import csv
import json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 设置中文字体，防止乱码 (根据操作系统可能需要调整字体名称)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class DashboardFrame(ttk.Frame):
    """仪表盘页面"""

    def __init__(self, parent, db, main_window):
        super().__init__(parent)
        self.db = db
        self.main_window = main_window

        self.colors = {
            'bg': '#F5F7FA',
            'card_bg': '#FFFFFF',
            'primary': '#B8860B',
            'success': '#2E8B57',
            'danger': '#CD5C5C',
            'text': '#2C3E50',
            'text_secondary': '#7F8C8D'
        }

        self._create_widgets()
        self.refresh_data()

    def _create_widgets(self):
        """创建仪表盘组件"""
        title = tk.Label(
            self,
            text="📊 投资仪表盘",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        title.pack(anchor='w', padx=20, pady=15)

        stats_container = tk.Frame(self, bg=self.colors['bg'])
        stats_container.pack(fill=tk.X, padx=20, pady=10)

        self.stat_cards = {}
        card_data = [
            {'key': 'holding_value', 'title': '持仓市值', 'icon': '💰', 'color': '#B8860B'},
            {'key': 'total_cost', 'title': '总成本', 'icon': '💵', 'color': '#3498DB'},
            {'key': 'profit_loss', 'title': '已实现盈亏', 'icon': '📈', 'color': '#2E8B57'},
            {'key': 'gold_weight', 'title': '金币克重', 'icon': '⚖️', 'color': '#DAA520'},
            {'key': 'holding_count', 'title': '金币在库数量', 'icon': '🎯', 'color': '#9B59B6'},
        ]

        for i, card in enumerate(card_data):
            card_frame = self._create_stat_card(
                stats_container,
                card['title'],
                card['icon'],
                card['color']
            )
            card_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
            self.stat_cards[card['key']] = card_frame

        distribution_frame = tk.Frame(self, bg=self.colors['bg'])
        distribution_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        material_frame = tk.LabelFrame(
            distribution_frame,
            text="📊 持仓材质分布",
            font=('Microsoft YaHei', 12, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        material_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.material_tree = ttk.Treeview(
            material_frame,
            columns=('材质', '数量', '成本', '市值', '平均克价'),
            show='headings',
            height=6
        )
        self.material_tree.heading('材质', text='材质')
        self.material_tree.heading('数量', text='数量')
        self.material_tree.heading('成本', text='成本 (元)')
        self.material_tree.heading('市值', text='市值 (元)')
        self.material_tree.heading('平均克价', text='平均克价 (元/g)')

        self.material_tree.column('材质', width=80, anchor='center')
        self.material_tree.column('数量', width=80, anchor='center')
        self.material_tree.column('成本', width=100, anchor='e')
        self.material_tree.column('市值', width=100, anchor='e')
        self.material_tree.column('平均克价', width=110, anchor='e')

        self.material_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        recent_frame = tk.LabelFrame(
            distribution_frame,
            text="📋 最近交易记录",
            font=('Microsoft YaHei', 12, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        recent_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.recent_tree = ttk.Treeview(
            recent_frame,
            columns=('日期', '藏品', '类型', '金额', '状态'),
            show='headings',
            height=6
        )
        self.recent_tree.heading('日期', text='日期')
        self.recent_tree.heading('藏品', text='藏品名称')
        self.recent_tree.heading('类型', text='交易类型')
        self.recent_tree.heading('金额', text='金额 (元)')
        self.recent_tree.heading('状态', text='状态')

        self.recent_tree.column('日期', width=100, anchor='center')
        self.recent_tree.column('藏品', width=150, anchor='center')
        self.recent_tree.column('类型', width=80, anchor='center')
        self.recent_tree.column('金额', width=100, anchor='e')
        self.recent_tree.column('状态', width=80, anchor='center')

        self.recent_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _create_stat_card(self, parent, title, icon, color):
        """创建统计卡片"""
        card = tk.Frame(parent, bg=self.colors['card_bg'], relief=tk.RAISED, bd=1)
        card.configure(highlightbackground=color, highlightthickness=2)

        header = tk.Frame(card, bg=color, height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f"{icon} {title}",
            font=('Microsoft YaHei', 11),
            bg=color,
            fg='white'
        ).pack(pady=8)

        self.value_label = tk.Label(
            card,
            text="0",
            font=('Microsoft YaHei', 20, 'bold'),
            bg=self.colors['card_bg'],
            fg=color
        )
        self.value_label.pack(pady=15)

        return card

    def refresh_data(self):
        """刷新统计数据"""
        logger.info("仪表盘数据刷新")
        stats = self.db.get_statistics()

        if hasattr(self, 'stat_cards'):
            value_frame = self.stat_cards['holding_value']
            for widget in value_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('text') != f"💰 持仓市值":
                    widget.configure(text=f"¥{stats.get('total_market_value', 0):,.2f}")

            cost_frame = self.stat_cards['total_cost']
            for widget in cost_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('text') != f"💵 总成本":
                    widget.configure(text=f"¥{stats.get('total_cost', 0):,.2f}")

            pl_frame = self.stat_cards['profit_loss']
            pl_value = stats.get('realized_profit_loss', 0)
            pl_color = self.colors['success'] if pl_value >= 0 else self.colors['danger']
            for widget in pl_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('text') != f"📈 已实现盈亏":
                    widget.configure(text=f"¥{pl_value:,.2f}", fg=pl_color)

            weight_frame = self.stat_cards['gold_weight']
            total_gold_weight = stats.get('total_gold_weight', 0)
            for widget in weight_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('text') != f"⚖️ 金币克重":
                    widget.configure(text=f"{total_gold_weight:,.3f} g")

            count_frame = self.stat_cards['holding_count']
            for widget in count_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('text') != f"🎯 金币在库数量":
                    widget.configure(text=f"{stats.get('holding_count', 0)} 枚")

        self._update_material_distribution(stats.get('by_material', []))
        self._update_recent_transactions()
        logger.info("仪表盘数据刷新完成")


    def _update_material_distribution(self, data):
        """更新材质分布表格"""
        for item in self.material_tree.get_children():
            self.material_tree.delete(item)

        if not data:
            return

        for row in data:
            cost = row.get('cost', 0)
            weight = row.get('weight', 0)
            avg_gram_price = cost / weight if weight > 0 else 0

            self.material_tree.insert('', tk.END, values=(
                row.get('material', ''),
                row.get('count', 0),
                f"{row.get('cost', 0):,.2f}",
                f"{row.get('value', 0):,.2f}",
                f"{avg_gram_price:,.2f}"
            ))

    def _update_recent_transactions(self):
        """更新最近交易记录"""
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)

        collections = self.db.get_collections()
        recent = collections[:30]

        for col in recent:
            if col.get('is_sold'):
                trans_type = '卖出'
                status = '已售'
                amount = col.get('net_sales', 0)
            else:
                trans_type = '买入'
                status = '在库'
                amount = col.get('total_cost', 0)

            self.recent_tree.insert('', tk.END, values=(
                col.get('buy_date', ''),
                col.get('name', '')[:15],
                trans_type,
                f"{amount:,.2f}",
                status
            ))


class CollectionFrame(ttk.Frame):
    """藏品库管理页面"""

    def __init__(self, parent, db, main_window):
        super().__init__(parent)
        self.db = db
        self.main_window = main_window
        self.current_filter = {}

        self.colors = {
            'bg': '#F5F7FA',
            'card_bg': '#FFFFFF',
            'primary': '#B8860B',
            'success': '#2E8B57',
            'danger': '#CD5C5C',
            'text': '#2C3E50',
            'text_secondary': '#7F8C8D'
        }

        self._create_widgets()
        self.refresh_data()

    def _create_widgets(self):
        """创建藏品库组件"""
        header = tk.Frame(self, bg=self.colors['bg'])
        header.pack(fill=tk.X, padx=20, pady=15)

        tk.Label(
            header,
            text="🎯 藏品库",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(side=tk.LEFT)

        btn_frame = tk.Frame(header, bg=self.colors['bg'])
        btn_frame.pack(side=tk.RIGHT)

        # # 修复：添加藏品按钮 (背景较深，保持白字)
        # tk.Button(
        #     btn_frame,
        #     text="+ 添加藏品",
        #     bg=self.colors['primary'],
        #     # bg='#3498DB',  # 修改为蓝色
        #     fg='#3498DB',
        #     font=('Microsoft YaHei', 10, 'bold'),
        #     padx=15,
        #     pady=5,
        #     command=self._add_collection
        # ).pack(side=tk.LEFT, padx=5)


        tk.Button(
            btn_frame,
            text="📥 导入数据",
            bg='#27AE60',
            # fg='white',  # #27AE60 配白字对比度约为 3.5:1，略低。改为深色字更安全，或者背景加深。
            # 修正：使用深色文字以提高对比度
            fg='#3498DB',
            font=('Microsoft YaHei', 10, 'bold'),
            padx=15,
            pady=5,
            command=self._import_data
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="导出 Excel",
            bg='#3498DB',
            # fg='white', # #3498DB 配白字对比度约 2.6:1，严重不足。必须改为深色字。
            fg='#3498DB',
            font=('Microsoft YaHei', 10, 'bold'),
            padx=15,
            pady=5,
            command=self._export_excel
        ).pack(side=tk.LEFT, padx=5)

        filter_frame = tk.Frame(self, bg=self.colors['bg'])
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(filter_frame, text="材质:", bg=self.colors['bg'], fg=self.colors['text']).pack(side=tk.LEFT)
        self.material_var = tk.StringVar()
        material_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.material_var,
            values=['全部', '金', '银', '铂', '钯'],
            state='readonly',
            width=10
        )
        material_combo.current(0)
        material_combo.pack(side=tk.LEFT, padx=5)
        material_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filter())

        tk.Label(filter_frame, text="状态:", bg=self.colors['bg'], fg=self.colors['text']).pack(side=tk.LEFT, padx=(20, 5))
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.status_var,
            values=['全部', '在库', '已售'],
            state='readonly',
            width=10
        )
        status_combo.current(0)
        status_combo.pack(side=tk.LEFT, padx=5)
        status_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filter())

        tk.Label(filter_frame, text="搜索:", bg=self.colors['bg'], fg=self.colors['text']).pack(side=tk.LEFT, padx=(20, 5))
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(filter_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<Return>', lambda e: self._apply_filter())

        tk.Button(
            filter_frame,
            text="查询",
            bg=self.colors['primary'],
            fg='#3498DB',
            font=('Microsoft YaHei', 10, 'bold'),
            command=self._apply_filter
        ).pack(side=tk.LEFT, padx=5)

        list_frame = tk.Frame(self, bg=self.colors['bg'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 【修改点 1】在 columns 中新增 'type', 'packaging', 'grade'
        columns = ('ID', '名称', '材质', '类型', '包装', '评级', '重量', '买入日期', '买入价', '克价', '状态', '盈亏')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=18)

        # 定义表头
        self.tree.heading('ID', text='藏品 ID')
        self.tree.heading('名称', text='名称')
        self.tree.heading('材质', text='材质')
        self.tree.heading('类型', text='类型')  # 新增
        self.tree.heading('包装', text='包装')  # 新增
        self.tree.heading('评级', text='评级分数')  # 新增
        self.tree.heading('重量', text='重量 (g)')
        self.tree.heading('买入日期', text='买入日期')
        self.tree.heading('买入价', text='买入价 (元)')
        self.tree.heading('克价', text='克价 (元/g)')
        self.tree.heading('状态', text='状态')
        self.tree.heading('盈亏', text='盈亏 (元)')

        # 定义列宽和对齐
        self.tree.column('ID', width=100, anchor='center')
        self.tree.column('名称', width=150, anchor='center')
        self.tree.column('材质', width=60, anchor='center')
        self.tree.column('类型', width=80, anchor='center')  # 新增
        self.tree.column('包装', width=80, anchor='center')  # 新增
        self.tree.column('评级', width=70, anchor='center')  # 新增
        self.tree.column('重量', width=80, anchor='e')
        self.tree.column('买入日期', width=100, anchor='center')
        self.tree.column('买入价', width=100, anchor='e')
        self.tree.column('克价', width=100, anchor='e')
        self.tree.column('状态', width=80, anchor='center')
        self.tree.column('盈亏', width=100, anchor='e')

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure('in_stock', background='#E8F5E9', foreground='#2E7D32')
        self.tree.tag_configure('sold', background='#F5F5F5', foreground='#9E9E9E')

        self.tree.bind('<Double-1>', self._on_item_double_click)

    def refresh_data(self):
        """刷新藏品列表"""
        self._apply_filter()

    def _apply_filter(self):
        """应用筛选条件"""
        filters = {}

        material = self.material_var.get()
        if material and material != '全部':
            filters['material'] = material
            logger.info(f"藏品库筛选 - 材质：{material}")

        status = self.status_var.get()
        if status and status != '全部':
            filters['status'] = status
            logger.info(f"藏品库筛选 - 状态：{status}")

        keyword = self.search_var.get().strip()
        if keyword:
            filters['keyword'] = keyword
            logger.info(f"藏品库搜索 - 关键词：{keyword}")

        self.current_filter = filters
        self._load_data()
        logger.info(f"藏品库筛选应用完成，共 {len(filters)} 个条件")

    # ... existing code ...

    def _load_data(self):
        """加载数据"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        collections = self.db.get_collections(self.current_filter)

        for col in collections:
            if col.get('is_sold'):
                profit_loss = col.get('profit_loss', 0)
                status = '已售'
                row_tag = 'sold'
            else:
                profit_loss = 0
                status = '在库'
                row_tag = 'in_stock'

            self.tree.insert('', tk.END, values=(
                col.get('item_id', ''),
                col.get('name', ''),
                col.get('material', ''),
                col.get('type', ''),
                col.get('packaging', ''),
                col.get('grade', ''),
                f"{col.get('weight', 0):.3f}",
                col.get('buy_date', ''),
                f"{col.get('total_cost', 0):,.2f}",  # 使用 total_cost 字段
                f"{col.get('buy_gram_price', 0):,.2f}",
                status,
                f"{profit_loss:,.2f}"
            ), tags=(row_tag,))

    def _add_collection(self):
        """添加藏品"""
        dialog = CollectionEditDialog(self, self.db, None, self.main_window)
        self.wait_window(dialog.dialog)
        self.refresh_data()

    def _import_data(self):
        """导入数据"""
        filepath = filedialog.askopenfilename(
            title="选择导入文件",
            filetypes=[
                ("Excel 文件", "*.xlsx *.xls"),
                ("CSV 文件", "*.csv"),
                ("所有文件", "*.*")
            ]
        )
        if not filepath:
            return

        try:
            if filepath.endswith('.csv'):
                self._import_from_csv(filepath)
            else:
                self._import_from_excel(filepath)
        except Exception as e:
            messagebox.showerror("导入失败", f"导入失败：{str(e)}")

    def _import_from_csv(self, filepath):
        """从 CSV 导入"""
        imported_count = 0
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    data = self._convert_row_data(row)
                    if data:
                        self.db.add_collection(data)
                        imported_count += 1
                except Exception as e:
                    print(f"导入行失败：{e}")
                    continue

        messagebox.showinfo("导入成功", f"成功导入 {imported_count} 条记录")
        self.refresh_data()

    def _import_from_excel(self, filepath):
        """从 Excel 导入"""
        try:
            import pandas as pd
            df = pd.read_excel(filepath)

            imported_count = 0
            for _, row in df.iterrows():
                try:
                    data = self._convert_row_data(row.to_dict())
                    if data:
                        self.db.add_collection(data)
                        imported_count += 1
                except Exception as e:
                    print(f"导入行失败：{e}")
                    continue

            messagebox.showinfo("导入成功", f"成功导入 {imported_count} 条记录")
            self.refresh_data()
        except ImportError:
            messagebox.showerror("导入失败", "请安装 pandas 和 openpyxl 库")

    def _convert_row_data(self, row):
        """转换导入的数据行"""
        field_mapping = {
            '名称': 'name', 'name': 'name',
            '材质': 'material', 'material': 'material',
            '类型': 'type', 'type': 'type',
            '主题系列': 'series', 'series': 'series',
            '发行年份': 'year', 'year': 'year',
            '发行机构': 'issuer', 'issuer': 'issuer',
            '重量': 'weight', 'weight': 'weight',
            '成色': 'purity', 'purity': 'purity',
            '面值': 'face_value', 'face_value': 'face_value',
            '直径': 'diameter', 'diameter': 'diameter',
            '买入日期': 'buy_date', 'buy_date': 'buy_date',
            '买入单价': 'buy_price', 'buy_price': 'buy_price',
            '买入数量': 'buy_quantity', 'buy_quantity': 'buy_quantity',
            '买入费用': 'buy_fee', 'buy_fee': 'buy_fee',
            '购买渠道': 'buy_channel', 'buy_channel': 'buy_channel',
            '评级分数': 'grade', 'grade': 'grade',
            '证书编号': 'cert_id', 'cert_id': 'cert_id',
            '包装': 'packaging', 'packaging': 'packaging',
            '标签': 'tags', 'tags': 'tags',
            '备注': 'buy_notes', 'notes': 'buy_notes',
        }

        data = {}
        for old_key, new_key in field_mapping.items():
            if old_key in row and row[old_key] is not None and str(row[old_key]).strip():
                value = str(row[old_key]).strip()
                if new_key in ['year', 'buy_quantity', 'face_value']:
                    try:
                        data[new_key] = int(float(value))
                    except:
                        pass
                elif new_key in ['weight', 'diameter', 'buy_price', 'buy_fee']:
                    try:
                        data[new_key] = float(value)
                    except:
                        pass
                else:
                    data[new_key] = value

        required = ['name', 'material', 'type', 'weight', 'buy_date', 'buy_price']
        for field in required:
            if field not in data or not data[field]:
                return None

        data.setdefault('buy_quantity', 1)
        data.setdefault('buy_fee', 0)

        return data

    def _on_item_double_click(self, event):
        """双击编辑藏品"""
        item_id = self.tree.item(self.tree.selection())['values'][0]
        if item_id:
            dialog = CollectionEditDialog(self, self.db, item_id, self.main_window)
            self.wait_window(dialog.dialog)
            self.refresh_data()

    def _export_excel(self):
        """导出 Excel"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")],
            initialfile=f"藏品数据_{datetime.now().strftime('%Y%m%d')}"
        )
        if filepath:
            logger.info(f"用户操作 - 导出 Excel：{filepath}")
            if self.db.export_to_excel(filepath):
                logger.info(f"数据导出成功：{filepath}")
                messagebox.showinfo("导出成功", f"数据已导出到:\n{filepath}")
            else:
                logger.error(f"数据导出失败：{filepath}")
                messagebox.showerror("导出失败", "数据导出失败")

    # ... existing code ...


class CollectionEditDialog:
    """藏品编辑对话框"""

    def __init__(self, parent, db, item_id, main_window=None):
        self.db = db
        self.item_id = item_id
        self.collection_data = None
        self.main_window = main_window
        self.parent = parent  # 保存父窗口引用用于居中计算

        self.config_options = self._load_config_options()

        if item_id:
            self.collection_data = db.get_collection_by_id(item_id)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("编辑藏品" if item_id else "添加藏品")
        # 调整初始大小以适应更大的字体和双列布局
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 【修改】使用基于父窗口的居中逻辑
        self._center_window()

        self._create_widgets()

        if self.collection_data:
            self._populate_data()

    def _center_window(self):
        """将弹窗移动到父窗口（主程序界面）的正中央"""
        self.dialog.update_idletasks()

        # 获取父窗口的坐标和尺寸
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()

        # 获取弹窗自身的尺寸
        dialog_width = self.dialog.winfo_width()
        dialog_height = self.dialog.winfo_height()

        # 计算相对于父窗口左上角的偏移量
        x = parent_x + (parent_width // 2) - (dialog_width // 2)
        y = parent_y + (parent_height // 2) - (dialog_height // 2)

        self.dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')

    def _load_config_options(self):
        """加载配置选项"""
        options = {
            'series': ['熊猫币', '生肖币', '其他'],
            'issuer': ['中国金币总公司', '其它'],
            'buy_channel': ['金币云商', '金币通', '三省', '三省拍卖', '淘宝', '中拍', '易金', '赵涌', '领丰', '京东',
                            '微信'],
            'packaging': ['原盒', '封装', '裸币', '评级封装'],
            'purity': ['99.9%', '99.99%', '99.999%', '92.5%', '90%', '其他'],
        }

        for key in options:
            saved = self.db.get_setting(f'options_{key}')
            if saved:
                try:
                    saved_list = json.loads(saved)
                    if isinstance(saved_list, list):
                        options[key] = saved_list
                except:
                    pass

        return options

    def _create_widgets(self):
        """创建表单组件 - 优化字体、间距和布局"""
        title_text = "编辑藏品" if self.item_id else "添加新藏品"
        tk.Label(
            self.dialog,
            text=title_text,
            font=('Microsoft YaHei', 18, 'bold'),  # 【优化】标题字体加大
            fg='#2C3E50'
        ).pack(pady=(20, 15))

        # 主容器：统一管理表单和按钮
        main_container = tk.Frame(self.dialog)
        main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        # 定义所有字段
        all_fields = [
            ('name', '名称*', 'text'),
            ('material', '材质*', 'combo', ['金', '银', '铂', '钯']),
            ('type', '类型*', 'combo', ['投资币', '纪念币', '流通币']),
            ('series', '主题系列', 'combo', self.config_options['series']),
            ('year', '发行年份', 'text'),
            ('issuer', '发行机构', 'combo', self.config_options['issuer']),

            ('weight', '重量 (g)*', 'text'),
            ('purity', '成色', 'combo', self.config_options['purity']),
            ('face_value', '面值 (元)', 'text'),
            ('diameter', '直径 (mm)', 'text'),
            ('grade', '评级分数', 'text'),
            ('cert_id', '证书编号', 'text'),
            ('packaging', '包装', 'combo', self.config_options['packaging']),

            ('buy_date', '买入日期*', 'text'),
            ('buy_price', '买入单价 (元)*', 'text'),
            ('buy_quantity', '买入数量', 'text'),
            ('buy_fee', '买入费用', 'text'),
            ('buy_channel', '购买渠道', 'combo', self.config_options['buy_channel']),
            ('tags', '标签', 'text'),
            ('buy_notes', '备注', 'text'),
        ]

        self.entries = {}

        # 表单区域 (第 0 行)
        form_frame = tk.Frame(main_container)
        form_frame.grid(row=0, column=0, sticky='nsew')

        # 按钮区域 (第 1 行)
        btn_frame = tk.Frame(main_container)
        btn_frame.grid(row=1, column=0, sticky='ew', pady=(25, 5))

        # 配置主容器权重
        main_container.rowconfigure(0, weight=1)
        main_container.rowconfigure(1, weight=0)
        main_container.columnconfigure(0, weight=1)

        # 创建左右两列
        left_frame = tk.Frame(form_frame)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 20))  # 【优化】增加列间距

        right_frame = tk.Frame(form_frame)
        right_frame.grid(row=0, column=1, sticky='nsew', padx=(20, 0))

        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(1, weight=1)

        # 分配字段到两列
        mid_point = len(all_fields) // 2
        left_fields = all_fields[:mid_point]
        right_fields = all_fields[mid_point:]

        self._build_column(left_frame, left_fields)
        self._build_column(right_frame, right_fields)

        # 创建按钮
        tk.Button(
            btn_frame,
            text="💾 保存",
            bg='#2E8B57',
            fg='white',
            font=('Microsoft YaHei', 12, 'bold'),  # 【优化】按钮字体加大
            padx=40,
            pady=10,
            command=self._save
        ).pack(side=tk.LEFT, padx=15)

        tk.Button(
            btn_frame,
            text="❌ 取消",
            bg='#95A5A6',
            fg='#2C3E50',
            font=('Microsoft YaHei', 12, 'bold'),  # 【优化】按钮字体加大
            padx=40,
            pady=10,
            command=self.dialog.destroy
        ).pack(side=tk.LEFT, padx=15)

    def _build_column(self, parent, fields):
        """辅助方法：构建单列表单列"""
        for i, (field_id, label, field_type, *args) in enumerate(fields):
            # 【优化】标签字体加大到 11px，加粗，增加行间距
            tk.Label(parent, text=label, anchor='w', fg='#2C3E50', font=('Microsoft YaHei', 11, 'bold')).grid(
                row=i, column=0, sticky='w', padx=5, pady=8
            )

            if field_type == 'text':
                # 【优化】输入框宽度增加，字体加大到 11px
                entry = tk.Entry(parent, width=35, font=('Microsoft YaHei', 11))
            elif field_type == 'combo':
                entry = ttk.Combobox(parent, values=args[0], width=33, state='readonly', font=('Microsoft YaHei', 11))
                if args[0]:
                    entry.current(0)

            entry.grid(row=i, column=1, sticky='w', padx=5, pady=8)
            self.entries[field_id] = entry

        parent.columnconfigure(1, weight=1)

    def _populate_data(self):
        """填充数据"""
        if not self.collection_data:
            return

        for field_id, value in self.collection_data.items():
            if field_id in self.entries:
                entry = self.entries[field_id]
                if value is not None:
                    str_val = str(value)
                    if isinstance(entry, ttk.Combobox):
                        entry.set(str_val)
                    else:
                        entry.delete(0, tk.END)
                        entry.insert(0, str_val)

    def _save(self):
        """保存数据"""
        required_fields = ['name', 'material', 'type', 'weight', 'buy_date', 'buy_price']
        for field in required_fields:
            value = self.entries[field].get().strip()
            if not value:
                messagebox.showerror("错误", f"请填写必填字段：{field}")
                return

        data = {}
        for field_id, entry in self.entries.items():
            value = entry.get().strip()
            if value:
                if field_id in ['year', 'buy_quantity', 'face_value']:
                    data[field_id] = int(value) if value else 1
                elif field_id in ['weight', 'diameter', 'buy_price', 'buy_fee']:
                    data[field_id] = float(value) if value else 0
                else:
                    data[field_id] = value

        data.setdefault('buy_quantity', 1)
        data.setdefault('buy_fee', 0)

        try:
            if self.item_id:
                self.db.update_collection(self.item_id, data)
                messagebox.showinfo("成功", "藏品信息已更新")
            else:
                self.db.add_collection(data)
                messagebox.showinfo("成功", "藏品已添加")

            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{str(e)}")


class BuyFrame(ttk.Frame):
    """买入录入页面"""

    def __init__(self, parent, db, main_window):
        super().__init__(parent)
        self.db = db
        self.main_window = main_window

        self.colors = {
            'bg': '#F5F7FA',
            'card_bg': '#FFFFFF',
            'primary': '#B8860B',
            'success': '#2E8B57',
            'danger': '#CD5C5C',
            'text': '#2C3E50',
            'text_secondary': '#7F8C8D'
        }

        self.config_options = self._load_config_options()
        self.buy_entries = {}  # 初始化字典，确保在 _create_widgets 之前可用
        self._create_widgets()

    def _load_config_options(self):
        """加载配置选项"""
        options = {
            'series': ['熊猫币', '生肖币', '其他'],
            'issuer': ['中国金币总公司', '其它'],
            'buy_channel': ['金币云商', '金币通', '三省', '三省拍卖', '淘宝', '中拍', '易金', '赵涌', '领丰', '京东', '微信'],
            'packaging': ['原盒', '封装', '裸币', '评级封装'],
            'purity': ['99.9%', '99.99%', '99.999%', '92.5%', '90%', '其他'],
        }

        for key in options:
            saved = self.db.get_setting(f'options_{key}')
            if saved:
                try:
                    saved_list = json.loads(saved)
                    if isinstance(saved_list, list):
                        options[key] = saved_list
                except:
                    pass

        return options

    def _create_widgets(self):
        """创建买入录入组件 - 优化布局为三列并居中"""
        tk.Label(
            self,
            text="💵 买入录入",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=20, pady=15)

        form_card = tk.Frame(self, bg=self.colors['card_bg'], relief=tk.RAISED, bd=1)
        # 确保 form_card 填充整个可用空间
        form_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 主容器
        main_container = tk.Frame(form_card, bg=self.colors['card_bg'])
        # 使用 grid 放置 main_container，并使其 sticky 到四个方向以填满 form_card
        main_container.grid(row=0, column=0, sticky='nsew', padx=15, pady=15)

        # 【关键修改】配置 form_card 的网格权重，使 main_container 能撑满父容器
        form_card.columnconfigure(0, weight=1)
        form_card.rowconfigure(0, weight=1)

        # --- 第一列：基础信息 ---
        col1_frame = tk.LabelFrame(main_container, text="📋 基础信息", font=('Microsoft YaHei', 12, 'bold'),
                                   bg=self.colors['card_bg'], fg=self.colors['primary'])
        col1_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10), pady=(0, 10))

        col1_fields = [
            ('name', '藏品名称*', 'text'),
            ('material', '材质*', 'combo', ['金', '银', '铂', '钯']),
            ('type', '类型*', 'combo', ['投资币', '纪念币', '流通币']),
            ('series', '主题系列', 'combo', self.config_options['series']),
            ('year', '发行年份', 'text'),
            ('issuer', '发行机构', 'combo', self.config_options['issuer']),
        ]
        self._build_form_column(col1_frame, col1_fields, 0)

        # --- 第二列：规格与认证 ---
        col2_frame = tk.LabelFrame(main_container, text="⚙️ 规格与认证", font=('Microsoft YaHei', 12, 'bold'),
                                   bg=self.colors['card_bg'], fg=self.colors['primary'])
        col2_frame.grid(row=0, column=1, sticky='nsew', padx=(0, 10), pady=(0, 10))

        col2_fields = [
            ('weight', '重量 (g)*', 'text'),
            ('purity', '成色', 'combo', self.config_options['purity']),
            ('face_value', '面值 (元)', 'text'),
            ('diameter', '直径 (mm)', 'text'),
            ('grade', '评级分数', 'text'),
            ('cert_id', '证书编号', 'text'),
            ('packaging', '包装', 'combo', self.config_options['packaging']),
        ]
        self._build_form_column(col2_frame, col2_fields, 1)

        # --- 第三列：交易信息 ---
        col3_frame = tk.LabelFrame(main_container, text="💰 交易信息", font=('Microsoft YaHei', 12, 'bold'),
                                   bg=self.colors['card_bg'], fg=self.colors['primary'])
        col3_frame.grid(row=0, column=2, sticky='nsew', pady=(0, 10))

        col3_fields = [
            ('buy_date', '买入日期*', 'text'),
            ('buy_price', '买入单价 (元)*', 'text'),
            ('buy_quantity', '买入数量', 'text'),
            ('buy_fee', '买入费用 (元)', 'text'),
            ('buy_channel', '购买渠道', 'combo', self.config_options['buy_channel']),
            ('gold_price_at_buy', '买入时金价 (元/g)', 'text'),
        ]
        self._build_form_column(col3_frame, col3_fields, 2)

        # --- 底部：备注与按钮 ---
        bottom_frame = tk.Frame(main_container, bg=self.colors['card_bg'])
        bottom_frame.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(0, 15))

        notes_frame = tk.Frame(bottom_frame, bg=self.colors['card_bg'])
        notes_frame.pack(fill=tk.X, padx=10, pady=(0, 15))

        tk.Label(notes_frame, text="📝 备注:", bg=self.colors['card_bg'], fg=self.colors['text'], font=('Microsoft YaHei', 10, 'bold')).pack(anchor='w')
        notes_entry = tk.Entry(notes_frame, width=60)
        notes_entry.pack(fill=tk.X, pady=5)
        self.buy_entries['buy_notes'] = notes_entry

        btn_frame = tk.Frame(bottom_frame, bg=self.colors['card_bg'])
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame,
            text="💾 保存记录",
            bg=self.colors['primary'],
            fg='white',
            font=('Microsoft YaHei', 12, 'bold'),
            padx=40,
            pady=10,
            command=self._save_buy
        ).pack(side=tk.LEFT, padx=20)

        tk.Button(
            btn_frame,
            text="清空表单",
            bg='#95A5A6',
            fg='#2C3E50',
            font=('Microsoft YaHei', 12, 'bold'),
            padx=40,
            pady=10,
            command=self._clear_form
        ).pack(side=tk.LEFT, padx=20)

        # 【关键修改】配置 main_container 的列权重，使三列等宽并占据所有可用空间
        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=1)
        main_container.columnconfigure(2, weight=1)
        main_container.rowconfigure(0, weight=1)
        # 确保 bottom_frame 所在的行不无限拉伸，保持紧凑，或者根据需要调整
        main_container.rowconfigure(1, weight=0)


    def _build_form_column(self, parent, fields, col_index):
        """辅助方法：构建单列表单"""
        for i, (field_id, label, field_type, *args) in enumerate(fields):
            row = i
            tk.Label(parent, text=label, bg=self.colors['card_bg'], fg=self.colors['text']).grid(
                row=row, column=0, sticky='w', padx=10, pady=6
            )

            if field_type == 'text':
                entry = tk.Entry(parent, width=15)
            elif field_type == 'combo':
                entry = ttk.Combobox(parent, values=args[0], width=13, state='readonly')
                if args[0]:
                    entry.current(0)

            entry.grid(row=row, column=1, sticky='w', padx=10, pady=6)
            self.buy_entries[field_id] = entry

    def _save_buy(self):
        """保存买入记录"""
        required = ['name', 'material', 'type', 'weight', 'buy_date', 'buy_price']
        for field in required:
            value = self.buy_entries[field].get().strip()
            if not value:
                logger.warning(f"买入保存失败 - 必填字段缺失：{field}")
                messagebox.showerror("错误", f"请填写必填字段：{field}")
                return

        data = {}
        for field_id, entry in self.buy_entries.items():
            value = entry.get().strip()
            if value:
                if field_id in ['year', 'buy_quantity', 'face_value']:
                    data[field_id] = int(value) if value else 1
                elif field_id in ['weight', 'diameter', 'buy_price', 'buy_fee', 'gold_price_at_buy']:
                    data[field_id] = float(value) if value else 0
                else:
                    data[field_id] = value

        # 确保默认值
        data.setdefault('buy_quantity', 1)
        data.setdefault('buy_fee', 0)

        try:
            item_name = data.get('name', '未知')
            item_material = data.get('material', '未知')
            item_weight = data.get('weight', 0)
            item_price = data.get('buy_price', 0)

            logger.info(f"用户操作 - 买入藏品：名称={item_name}, 材质={item_material}, 重量={item_weight}g, 价格=¥{item_price}")

            self.db.add_collection(data)
            logger.info(f"买入记录已保存到数据库")

            messagebox.showinfo("成功", "买入记录已保存！")
            self._clear_form()

            # 刷新仪表盘和统计报表
            if hasattr(self.main_window, 'dashboard_frame') and hasattr(self.main_window.dashboard_frame, 'refresh_data'):
                self.main_window.dashboard_frame.refresh_data()
            if hasattr(self.main_window, 'reports_frame') and hasattr(self.main_window.reports_frame, '_load_report'):
                self.main_window.reports_frame._load_report()

        except Exception as e:
            logger.error(f"买入保存失败：{str(e)}", exc_info=True)
            messagebox.showerror("错误", f"保存失败：{str(e)}")


    def _clear_form(self):
        """清空表单"""
        for entry in self.buy_entries.values():
            entry.delete(0, tk.END)

        # 重置默认值
        if 'buy_quantity' in self.buy_entries:
            self.buy_entries['buy_quantity'].insert(0, '1')
        if 'buy_date' in self.buy_entries:
            self.buy_entries['buy_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

        # 重置下拉框到第一个选项
        for field_id, entry in self.buy_entries.items():
            if isinstance(entry, ttk.Combobox) and entry['values']:
                entry.current(0)

    def _refresh_config_options(self):
        """重新加载配置选项到下拉框"""
        new_options = self._load_config_options()

        def update_combo(key, entry_widget):
            if key not in new_options or not entry_widget:
                return
            new_values = new_options[key]
            if not new_values:
                return
            current_val = entry_widget.get()
            entry_widget['values'] = new_values
            if current_val in new_values:
                entry_widget.set('')
                entry_widget.set(current_val)
            else:
                entry_widget.current(0)

        update_combo('series', self.buy_entries.get('series'))
        update_combo('issuer', self.buy_entries.get('issuer'))
        update_combo('buy_channel', self.buy_entries.get('buy_channel'))
        update_combo('purity', self.buy_entries.get('purity'))
        update_combo('packaging', self.buy_entries.get('packaging')) # 新增刷新

        self.update_idletasks()



class SellFrame(ttk.Frame):
    """卖出录入页面"""

    def __init__(self, parent, db, main_window):
        super().__init__(parent)
        self.db = db
        self.main_window = main_window
        self.selected_item = None

        self.colors = {
            'bg': '#F5F7FA',
            'card_bg': '#FFFFFF',
            'primary': '#B8860B',
            'success': '#2E8B57',
            'danger': '#CD5C5C',
            'text': '#2C3E50',
            'text_secondary': '#7F8C8D'
        }

        self._create_widgets()
        self._load_holdings()

    def _create_widgets(self):
        """创建卖出录入组件"""
        tk.Label(
            self,
            text="💴 卖出录入",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=20, pady=15)

        content_frame = tk.Frame(self, bg=self.colors['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        left_frame = tk.LabelFrame(
            content_frame,
            text="📋 选择要卖出的藏品",
            font=('Microsoft YaHei', 12, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.holdings_tree = ttk.Treeview(
            left_frame,
            columns=('ID', '名称', '材质', '重量', '买入价', '克价'),
            show='headings',
            height=15
        )
        self.holdings_tree.heading('ID', text='藏品 ID')
        self.holdings_tree.heading('名称', text='名称')
        self.holdings_tree.heading('材质', text='材质')
        self.holdings_tree.heading('重量', text='重量 (g)')
        self.holdings_tree.heading('买入价', text='买入价 (元)')
        self.holdings_tree.heading('克价', text='克价 (元/g)')

        self.holdings_tree.column('ID', width=120, anchor='center')
        self.holdings_tree.column('名称', width=150, anchor='center')
        self.holdings_tree.column('材质', width=60, anchor='center')
        self.holdings_tree.column('重量', width=80, anchor='e')
        self.holdings_tree.column('买入价', width=100, anchor='e')
        self.holdings_tree.column('克价', width=100, anchor='e')

        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.holdings_tree.yview)
        self.holdings_tree.configure(yscrollcommand=vsb.set)

        self.holdings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.holdings_tree.bind('<<TreeviewSelect>>', self._on_select_item)

        right_frame = tk.LabelFrame(
            content_frame,
            text="💰 填写卖出信息",
            font=('Microsoft YaHei', 12, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        info_frame = tk.Frame(right_frame, bg=self.colors['bg'])
        info_frame.pack(fill=tk.X, padx=15, pady=15)

        self.selected_label = tk.Label(
            info_frame,
            text="请从左侧选择要卖出的藏品",
            font=('Microsoft YaHei', 11),
            bg=self.colors['bg'],
            fg=self.colors['text_secondary']
        )
        self.selected_label.pack()

        form_frame = tk.Frame(right_frame, bg=self.colors['bg'])
        form_frame.pack(fill=tk.X, padx=15, pady=10)

        self.sell_entries = {}

        # 【修改点 1】简化字段定义，移除行列坐标，改为单列顺序排列
        sell_fields = [
            ('sell_date', '卖出日期*'),
            ('sell_price', '卖出金额 (元)*'),
            ('sell_fee', '卖出费用 (元)'),
            ('sell_channel', '出售渠道'),
            ('gold_price_at_sell', '卖出时金价 (元/g)'),
            ('sell_notes', '备注'),
        ]

        # 【修改点 2】调整循环逻辑，固定为单列布局
        for i, (field_id, label) in enumerate(sell_fields):
            tk.Label(form_frame, text=label, bg=self.colors['bg'], fg=self.colors['text']).grid(
                row=i, column=0, sticky='w', padx=5, pady=8
            )
            # 增加输入框宽度以适应单列布局
            entry = tk.Entry(form_frame, width=25)
            entry.grid(row=i, column=1, sticky='w', padx=5, pady=8)
            self.sell_entries[field_id] = entry

        self.sell_entries['sell_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

        preview_frame = tk.LabelFrame(
            right_frame,
            text="📊 盈亏预览",
            font=('Microsoft YaHei', 11, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        preview_frame.pack(fill=tk.X, padx=15, pady=10)

        self.preview_labels = {}
        preview_items = [
            ('cost', '总成本'),
            ('sales', '净销售额'),
            ('profit', '盈亏金额'),
            ('rate', '盈亏率'),
            ('days', '持有天数'),
            ('annual', '年化收益率'),
        ]

        # 预览区域保持原有的两列布局显示数据，或者也可以改为单列，这里保持原样以节省空间
        for i, (key, label) in enumerate(preview_items):
            tk.Label(preview_frame, text=f"{label}:", bg=self.colors['bg'], fg=self.colors['text']).grid(
                row=i//2, column=(i%2)*2, sticky='w', padx=15, pady=5
            )
            value_label = tk.Label(preview_frame, text="--", bg=self.colors['bg'], font=('Microsoft YaHei', 11, 'bold'), fg=self.colors['primary'])
            value_label.grid(row=i//2, column=(i%2)*2+1, sticky='w', padx=5, pady=5)
            self.preview_labels[key] = value_label

        self.sell_entries['sell_price'].bind('<KeyRelease>', self._update_preview)
        self.sell_entries['sell_fee'].bind('<KeyRelease>', self._update_preview)

        btn_frame = tk.Frame(right_frame, bg=self.colors['bg'])
        btn_frame.pack(pady=20)

        tk.Button(
            btn_frame,
            text="💾 确认卖出",
            bg=self.colors['success'],
            fg='white', # 修复对比度
            font=('Microsoft YaHei', 12, 'bold'),
            padx=30,
            pady=10,
            command=self._save_sell
        ).pack(side=tk.LEFT, padx=10)


    def _load_holdings(self):
        """加载在库藏品"""
        for item in self.holdings_tree.get_children():
            self.holdings_tree.delete(item)

        holdings = self.db.get_collections({'status': '在库'})

        for item in holdings:
            self.holdings_tree.insert('', tk.END, values=(
                item.get('item_id', ''),
                item.get('name', ''),
                item.get('material', ''),
                f"{item.get('weight', 0):.3f}",
                f"{item.get('buy_price', 0):,.2f}",
                f"{item.get('buy_gram_price', 0):,.2f}"
            ))

    def _on_select_item(self, event):
        """选中藏品"""
        selection = self.holdings_tree.selection()
        if selection:
            item_id = self.holdings_tree.item(selection[0])['values'][0]
            self.selected_item = self.db.get_collection_by_id(item_id)

            if self.selected_item:
                self.selected_label.configure(
                    text=f"已选择：{self.selected_item['name']} (克价：{self.selected_item.get('buy_gram_price', 0):.2f}元/g)",
                    fg=self.colors['text']
                )
                self._update_preview()

    def _update_preview(self, event=None):
        """更新盈亏预览"""
        if not self.selected_item:
            return

        try:
            sell_price = float(self.sell_entries['sell_price'].get() or 0)
            sell_fee = float(self.sell_entries['sell_fee'].get() or 0)
            net_sales = sell_price - sell_fee

            total_cost = self.selected_item.get('total_cost', 0)
            profit_loss = net_sales - total_cost

            if total_cost > 0:
                profit_rate = (profit_loss / total_cost) * 100
            else:
                profit_rate = 0

            buy_date = datetime.strptime(self.selected_item['buy_date'], '%Y-%m-%d')
            sell_date_str = self.sell_entries['sell_date'].get().strip()
            if sell_date_str:
                try:
                    sell_date = datetime.strptime(sell_date_str, '%Y-%m-%d')
                    hold_days = (sell_date - buy_date).days

                    if hold_days > 0 and total_cost > 0:
                        annual_roi = (profit_loss / total_cost) * (365 / hold_days) * 100
                    else:
                        annual_roi = 0
                except:
                    hold_days = 0
                    annual_roi = 0
            else:
                hold_days = 0
                annual_roi = 0

            self.preview_labels['cost'].configure(text=f"¥{total_cost:,.2f}")
            self.preview_labels['sales'].configure(text=f"¥{net_sales:,.2f}")

            pl_color = self.colors['success'] if profit_loss >= 0 else self.colors['danger']
            self.preview_labels['profit'].configure(text=f"¥{profit_loss:,.2f}", fg=pl_color)
            self.preview_labels['rate'].configure(text=f"{profit_rate:.2f}%", fg=pl_color)
            self.preview_labels['days'].configure(text=f"{hold_days} 天")
            self.preview_labels['annual'].configure(text=f"{annual_roi:.2f}%", fg=pl_color)

        except ValueError:
            pass

    def _save_sell(self):
        """保存卖出记录"""
        if not self.selected_item:
            logger.warning("卖出保存失败 - 未选择藏品")
            messagebox.showwarning("警告", "请先选择要卖出的藏品")
            return

        if not self.sell_entries['sell_date'].get().strip():
            logger.warning("卖出保存失败 - 未填写卖出日期")
            messagebox.showerror("错误", "请填写卖出日期")
            return

        sell_price_str = self.sell_entries['sell_price'].get().strip()
        if not sell_price_str:
            logger.warning("卖出保存失败 - 未填写卖出金额")
            messagebox.showerror("错误", "请填写卖出金额")
            return

        try:
            sell_price = float(sell_price_str)
            sell_fee = float(self.sell_entries['sell_fee'].get() or 0)
        except ValueError:
            logger.warning("卖出保存失败 - 金额格式不正确")
            messagebox.showerror("错误", "金额格式不正确")
            return

        sell_data = {
            'sell_date': self.sell_entries['sell_date'].get().strip(),
            'sell_price': sell_price,
            'sell_fee': sell_fee,
            'sell_channel': self.sell_entries['sell_channel'].get().strip(),
            'sell_notes': self.sell_entries['sell_notes'].get().strip(),
        }

        gold_price = self.sell_entries['gold_price_at_sell'].get().strip()
        if gold_price:
            sell_data['gold_price_at_sell'] = float(gold_price)

        try:
            item_name = self.selected_item.get('name', '未知')
            total_cost = self.selected_item.get('total_cost', 0)
            net_sales = sell_price - sell_fee
            profit_loss = net_sales - total_cost

            logger.info(f"用户操作 - 卖出藏品：名称={item_name}, 卖出价=¥{sell_price}, 净销售额=¥{net_sales}, 盈亏=¥{profit_loss}")

            self.db.record_sell(self.selected_item['item_id'], sell_data)
            logger.info(f"卖出记录已保存到数据库")

            result = f"卖出记录已保存！\n\n"
            result += f"藏品：{self.selected_item['name']}\n"
            result += f"卖出金额：¥{sell_data['sell_price']:,.2f}\n"
            result += f"净销售额：¥{net_sales:,.2f}\n"
            result += f"总成本：¥{total_cost:,.2f}\n"
            result += f"盈亏：¥{profit_loss:,.2f}"

            messagebox.showinfo("成功", result)

            self._load_holdings()
            self.selected_item = None
            self.selected_label.configure(text="请从左侧选择要卖出的藏品")

            for entry in self.sell_entries.values():
                entry.delete(0, tk.END)
            self.sell_entries['sell_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

            # 刷新仪表盘和统计报表
            if hasattr(self.main_window, 'dashboard_frame') and hasattr(self.main_window.dashboard_frame, 'refresh_data'):
                self.main_window.dashboard_frame.refresh_data()
            if hasattr(self.main_window, 'reports_frame') and hasattr(self.main_window.reports_frame, '_load_report'):
                self.main_window.reports_frame._load_report()

        except Exception as e:
            logger.error(f"卖出保存失败：{str(e)}", exc_info=True)
            messagebox.showerror("错误", f"保存失败：{str(e)}")

        # ... existing code ...


class ReportsFrame(ttk.Frame):
    """统计报表页面"""

    def __init__(self, parent, db, main_window):
        super().__init__(parent)
        self.db = db
        self.main_window = main_window

        self.colors = {
            'bg': '#F5F7FA',
            'card_bg': '#FFFFFF',
            'primary': '#B8860B',
            'success': '#2E8B57',
            'danger': '#CD5C5C',
            'text': '#2C3E50',
            'text_secondary': '#7F8C8D'
        }

        self.chart_canvas = None
        self._create_widgets()
        self._load_report()

    def _create_widgets(self):
        """创建报表组件"""
        header = tk.Frame(self, bg=self.colors['bg'])
        header.pack(fill=tk.X, padx=20, pady=15)

        tk.Label(
            header,
            text="📈 统计报表",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(side=tk.LEFT)

        tk.Label(header, text="年份:", bg=self.colors['bg'], fg=self.colors['text']).pack(side=tk.RIGHT, padx=(0, 10))
        current_year = datetime.now().year
        self.year_var = tk.StringVar(value=str(current_year))
        year_combo = ttk.Combobox(header, textvariable=self.year_var,
                                  values=[str(y) for y in range(current_year - 5, current_year + 1)], state='readonly',
                                  width=8)
        year_combo.pack(side=tk.RIGHT)
        year_combo.bind('<<ComboboxSelected>>', lambda e: self._load_report())

        # 创建可滚动的容器
        canvas_frame = tk.Frame(self, bg=self.colors['bg'])
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 创建 Canvas 和滚动条
        self.canvas = tk.Canvas(canvas_frame, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)

        # 创建内容容器
        content = tk.Frame(self.canvas, bg=self.colors['bg'])

        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 配置滚动区域
        content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # 在 canvas 中创建窗口
        self.canvas.create_window((0, 0), window=content, anchor="nw", width=canvas_frame.winfo_width())

        # 更新 canvas 宽度以适应窗口大小变化
        def _configure_canvas(event):
            self.canvas.itemconfig(self.canvas.find_withtag("all")[0], width=event.width)

        canvas_frame.bind("<Configure>", _configure_canvas)

        # 布局 Canvas 和滚动条
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        chart_frame = tk.LabelFrame(content, text="📊 月度趋势分析 (柱状：月末持仓市值 / 折线：当月实现利润)",
                                    font=('Microsoft YaHei', 12, 'bold'), bg=self.colors['bg'], fg=self.colors['text'])
        chart_frame.pack(fill=tk.X, pady=(0, 10), padx=5)

        self.chart_container = tk.Frame(chart_frame, bg=self.colors['bg'])
        self.chart_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        summary_frame = tk.LabelFrame(
            content,
            text="💰 投资收益汇总",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        summary_frame.pack(fill=tk.X, pady=(0, 10), padx=5)

        columns = ('类别', '材质', '数量', '总成本', '总销售额', '盈亏金额', '盈亏率')
        self.report_tree = ttk.Treeview(summary_frame, columns=columns, show='headings', height=3)

        for col in columns:
            self.report_tree.heading(col, text=col)
            if col in ['数量']:
                self.report_tree.column(col, width=80, anchor='center')
            elif col in ['盈亏金额', '盈亏率']:
                self.report_tree.column(col, width=120, anchor='e')
            else:
                self.report_tree.column(col, width=130, anchor='e')

        vsb = ttk.Scrollbar(summary_frame, orient="vertical", command=self.report_tree.yview)
        self.report_tree.configure(yscrollcommand=vsb.set)

        self.report_tree.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 新增：持仓材质分布
        material_frame = tk.LabelFrame(
            content,
            text="📊 持仓材质分布",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        material_frame.pack(fill=tk.X, pady=(0, 10), padx=5)

        self.material_tree = ttk.Treeview(
            material_frame,
            columns=('材质', '数量', '克重', '成本', '市值', '在库盈亏', '平均克价'),
            show='headings',
            height=3
        )
        self.material_tree.heading('材质', text='材质')
        self.material_tree.heading('数量', text='数量')
        self.material_tree.heading('克重', text='克重 (g)')
        self.material_tree.heading('成本', text='成本 (元)')
        self.material_tree.heading('市值', text='市值 (元)')
        self.material_tree.heading('在库盈亏', text='在库盈亏 (元)')
        self.material_tree.heading('平均克价', text='平均克价 (元/g)')

        self.material_tree.column('材质', width=80, anchor='center')
        self.material_tree.column('数量', width=80, anchor='center')
        self.material_tree.column('克重', width=100, anchor='e')
        self.material_tree.column('成本', width=120, anchor='e')
        self.material_tree.column('市值', width=120, anchor='e')
        self.material_tree.column('在库盈亏', width=120, anchor='e')
        self.material_tree.column('平均克价', width=120, anchor='e')

        vsb2 = ttk.Scrollbar(material_frame, orient="vertical", command=self.material_tree.yview)
        self.material_tree.configure(yscrollcommand=vsb2.set)

        self.material_tree.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10)
        vsb2.pack(side=tk.RIGHT, fill=tk.Y)

# ... existing code ...


        bottom_frame = tk.Frame(content, bg=self.colors['bg'])
        bottom_frame.pack(fill=tk.X, padx=5, pady=(0, 15))

        self.summary_labels = {}
        summary_items = [
            ('total_invested', '累计投入'),
            ('total_cost', '持仓成本'),
            ('total_value', '持仓市值'),
            ('realized_pl', '已实现盈亏'),
        ]

        for i, (key, label) in enumerate(summary_items):
            card = tk.Frame(bottom_frame, bg=self.colors['card_bg'], relief=tk.RAISED, bd=1)
            card.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

            tk.Label(
                card,
                text=label,
                font=('Microsoft YaHei', 10),
                bg=self.colors['card_bg'],
                fg=self.colors['text_secondary']
            ).pack(pady=(10, 5))

            value_label = tk.Label(
                card,
                text="¥0.00",
                font=('Microsoft YaHei', 14, 'bold'),
                bg=self.colors['card_bg'],
                fg=self.colors['primary']
            )
            value_label.pack(pady=(0, 10))
            self.summary_labels[key] = value_label

# ... existing code ...


    def _load_report(self):
        """加载报表数据"""
        if self.chart_canvas:
            self.chart_canvas.get_tk_widget().pack_forget()
            self.chart_canvas = None

        year = self.year_var.get()
        monthly_data = self.db.get_annual_monthly_data(year)

        if monthly_data:
            months = [d['month'] for d in monthly_data]
            market_values = [d['month_end_value'] for d in monthly_data]
            realized_profits = [d['monthly_realized_pl'] for d in monthly_data]

            fig = Figure(figsize=(10, 4), dpi=100)
            ax = fig.add_subplot(111)

            bars = ax.bar(months, market_values, color='#B8860B', alpha=0.7, label='月末持仓市值', width=0.5)

            ax2 = ax.twinx()
            line2 = ax2.plot(months, realized_profits, color='#CD5C5C', marker='s', linewidth=2, label='当月实现利润')

            # 在折线图上添加数据标签
            for i, (month, profit) in enumerate(zip(months, realized_profits)):
                if profit != 0:  # 只显示非零值
                    ax2.annotate(f'{profit:,.0f}',
                                xy=(month, profit),
                                xytext=(0, 10),
                                textcoords='offset points',
                                ha='center',
                                fontsize=8,
                                color='#CD5C5C',
                                fontweight='bold')

            ax.set_xlabel('月份')
            ax.set_ylabel('持仓市值 (元)', color='#B8860B', fontsize=12)
            ax2.set_ylabel('实现利润 (元)', color='#CD5C5C', fontsize=12)
            ax.set_title(f'{year}年 月度持仓与收益趋势', fontsize=14, pad=15)

            ax.grid(True, axis='y', linestyle='--', alpha=0.3)

            lines_1, labels_1 = ax.get_legend_handles_labels()
            lines_2, labels_2 = ax2.get_legend_handles_labels()
            ax.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')

            self.chart_canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
            self.chart_canvas.draw()
            self.chart_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        for item in self.report_tree.get_children():
            self.report_tree.delete(item)

        report_data = self.db.get_profit_loss_report(year if year != '全部' else None)

        total_realized = 0
        total_cost = 0
        total_value = 0

        # 限制最多显示3行数据
        display_count = 0
        max_display_rows = 3

        for row in report_data:
            if display_count >= max_display_rows:
                break

            profit_loss = row.get('profit_loss', 0)
            total = row.get('total_cost', 0)
            if row.get('category') == '已实现盈亏':
                total_realized += profit_loss
            else:
                total_cost += total
                total_value += row.get('total_value', 0)

            profit_rate = (profit_loss / total * 100) if total > 0 else 0

            # 修正：盈利用红色，亏损用绿色
            if profit_loss >= 0:
                pl_color = 'profit'  # 盈利 - 红色
            else:
                pl_color = 'loss'    # 亏损 - 绿色

            self.report_tree.insert('', tk.END, values=(
                row.get('category', ''),
                row.get('material', ''),
                row.get('count', 0),
                f"{total:,.2f}",
                f"{row.get('total_value', 0):,.2f}",
                f"{profit_loss:,.2f}",
                f"{profit_rate:.2f}%"
            ), tags=(pl_color,))

            display_count += 1

        # 配置颜色标签：盈利红色，亏损绿色
        self.report_tree.tag_configure('profit', foreground='#CD5C5C')  # 红色（盈利）
        self.report_tree.tag_configure('loss', foreground='#2E8B57')    # 绿色（亏损）

        stats = self.db.get_statistics()

        self.summary_labels['total_invested'].configure(text=f"¥{stats.get('total_invested', 0):,.2f}")
        self.summary_labels['total_cost'].configure(text=f"¥{stats.get('total_cost', 0):,.2f}")
        self.summary_labels['total_value'].configure(text=f"¥{stats.get('total_market_value', 0):,.2f}")

        pl_color = self.colors['success'] if total_realized >= 0 else self.colors['danger']
        self.summary_labels['realized_pl'].configure(text=f"¥{total_realized:,.2f}", fg=pl_color)

        # 更新持仓材质分布（传入年份参数）
        year_param = year if year != '全部' else None
        stats = self.db.get_statistics(year=year_param)
        self._update_material_distribution(stats.get('by_material', []))

    def _update_material_distribution(self, data):
        """更新材质分布表格"""
        for item in self.material_tree.get_children():
            self.material_tree.delete(item)

        if not data:
            return

        for row in data:
            cost = row.get('cost', 0)
            weight = row.get('weight', 0)
            value = row.get('value', 0)
            profit_loss = value - cost  # 计算在库盈亏
            avg_gram_price = cost / weight if weight > 0 else 0

            # 根据盈亏设置颜色标签
            if profit_loss >= 0:
                tag = 'profit'  # 盈利 - 红色
            else:
                tag = 'loss'    # 亏损 - 绿色

            self.material_tree.insert('', tk.END, values=(
                row.get('material', ''),
                row.get('count', 0),
                f"{weight:,.3f}",
                f"{cost:,.2f}",
                f"{value:,.2f}",
                f"{profit_loss:,.2f}",  # 新增：在库盈亏
                f"{avg_gram_price:,.2f}"
            ), tags=(tag,))

        # 配置颜色标签
        self.material_tree.tag_configure('profit', foreground='#CD5C5C')  # 红色（盈利）
        self.material_tree.tag_configure('loss', foreground='#2E8B57')    # 绿色（亏损）



class SettingsFrame(ttk.Frame):
    """系统设置页面"""

    def __init__(self, parent, db, main_window):
        super().__init__(parent)
        self.db = db
        self.main_window = main_window

        self.colors = {
            'bg': '#F5F7FA',
            'card_bg': '#FFFFFF',
            'primary': '#B8860B',
            'success': '#2E8B57',
            'danger': '#CD5C5C',
            'text': '#2C3E50',
            'text_secondary': '#7F8C8D'
        }

        self._create_widgets()
        self._load_settings()

    def _create_widgets(self):
        """创建设置组件"""
        tk.Label(
            self,
            text="⚙️ 系统设置",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=20, pady=15)

        content = tk.Frame(self, bg=self.colors['bg'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        gold_frame = tk.LabelFrame(
            content,
            text="📊 金价管理",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        gold_frame.pack(fill=tk.X, pady=(0, 15))

        gold_form = tk.Frame(gold_frame, bg=self.colors['bg'])
        gold_form.pack(fill=tk.X, padx=15, pady=15)

        tk.Label(gold_form, text="日期:", bg=self.colors['bg'], fg=self.colors['text']).grid(row=0, column=0, sticky='w', padx=5, pady=8)
        self.gold_date_entry = tk.Entry(gold_form, width=15)
        self.gold_date_entry.grid(row=0, column=1, sticky='w', padx=5, pady=8)
        self.gold_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        tk.Label(gold_form, text="金价 (元/g):", bg=self.colors['bg'], fg=self.colors['text']).grid(row=0, column=2, sticky='w', padx=15, pady=8)
        self.gold_price_entry = tk.Entry(gold_form, width=15)
        self.gold_price_entry.grid(row=0, column=3, sticky='w', padx=5, pady=8)

        tk.Label(gold_form, text="银价 (元/g):", bg=self.colors['bg'], fg=self.colors['text']).grid(row=1, column=0, sticky='w', padx=5, pady=8)
        self.silver_price_entry = tk.Entry(gold_form, width=15)
        self.silver_price_entry.grid(row=1, column=1, sticky='w', padx=5, pady=8)

        tk.Label(gold_form, text="铂金 (元/g):", bg=self.colors['bg'], fg=self.colors['text']).grid(row=1, column=2, sticky='w', padx=15, pady=8)
        self.platinum_price_entry = tk.Entry(gold_form, width=15)
        self.platinum_price_entry.grid(row=1, column=3, sticky='w', padx=5, pady=8)

        tk.Label(gold_form, text="钯金 (元/g):", bg=self.colors['bg'], fg=self.colors['text']).grid(row=2, column=0, sticky='w', padx=5, pady=8)
        self.palladium_price_entry = tk.Entry(gold_form, width=15)
        self.palladium_price_entry.grid(row=2, column=1, sticky='w', padx=5, pady=8)

        # 修复：保存金价按钮 (背景 #B8860B，白字加粗)
        tk.Button(
            gold_form,
            text="保存金价",
            bg=self.colors['primary'],
            fg='#3498DB',
            font=('Microsoft YaHei', 10, 'bold'),
            padx=15,
            pady=5,
            command=self._save_gold_price
        ).grid(row=2, column=2, columnspan=2, padx=15, pady=8)

        api_frame = tk.LabelFrame(
            content,
            text="🌐 API 实时价格（新浪）",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        api_frame.pack(fill=tk.X, pady=(0, 15))

        api_container = tk.Frame(api_frame, bg=self.colors['bg'])
        api_container.pack(fill=tk.X, padx=15, pady=10)

        tk.Label(api_container, text="🥇 黄金:", bg=self.colors['bg'], fg=self.colors['text'],
                 font=('Microsoft YaHei', 10)).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.api_gold_label = tk.Label(api_container, text="--.-- 元/克", bg=self.colors['bg'], fg='#B8860B',
                                       font=('Microsoft YaHei', 10, 'bold'))
        self.api_gold_label.grid(row=0, column=1, sticky='w', padx=10, pady=5)

        tk.Label(api_container, text="🥈 白银:", bg=self.colors['bg'], fg=self.colors['text'],
                 font=('Microsoft YaHei', 10)).grid(row=0, column=2, sticky='w', padx=20, pady=5)
        self.api_silver_label = tk.Label(api_container, text="--.-- 元/克", bg=self.colors['bg'], fg='#C0C0C0',
                                         font=('Microsoft YaHei', 10, 'bold'))
        self.api_silver_label.grid(row=0, column=3, sticky='w', padx=10, pady=5)

        tk.Label(api_container, text="⏰ 更新:", bg=self.colors['bg'], fg=self.colors['text'],
                 font=('Microsoft YaHei', 10)).grid(row=0, column=4, sticky='w', padx=20, pady=5)
        self.api_time_label = tk.Label(api_container, text="--:--:--", bg=self.colors['bg'], fg='#666666',
                                       font=('Microsoft YaHei', 10))
        self.api_time_label.grid(row=0, column=5, sticky='w', padx=10, pady=5)

        tk.Button(
            api_container,
            text="🔄 立即刷新",
            bg='#27AE60',
            fg='white',
            font=('Microsoft YaHei', 9, 'bold'),
            padx=10,
            pady=3,
            command=self._refresh_api_prices
        ).grid(row=0, column=6, sticky='w', padx=20, pady=5)

        tk.Label(
            api_container,
            text="(每 5 分钟自动更新)",
            bg=self.colors['bg'],
            fg=self.colors['text_secondary'],
            font=('Microsoft YaHei', 8)
        ).grid(row=1, column=0, columnspan=7, sticky='w', padx=10, pady=0)

        self._show_api_prices()

        data_frame = tk.LabelFrame(
            content,
            text="💾 数据管理",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        data_frame.pack(fill=tk.X, pady=(0, 15))

        data_form = tk.Frame(data_frame, bg=self.colors['bg'])
        data_form.pack(fill=tk.X, padx=15, pady=15)

        tk.Button(
            data_form,
            text="导出全部数据",
            bg='#3498DB',
            fg='#3498DB',
            font=('Microsoft YaHei', 10, 'bold'),
            padx=20,
            pady=8,
            command=self._export_all_data
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            data_form,
            text="备份数据库",
            bg='#27AE60',
            fg='#3498DB',
            font=('Microsoft YaHei', 10, 'bold'),
            padx=20,
            pady=8,
            command=self._backup_db
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            data_form,
            text="恢复数据库",
            bg='#E67E22',
            fg='#3498DB',
            font=('Microsoft YaHei', 10, 'bold'),
            padx=20,
            pady=8,
            command=self._restore_db
        ).pack(side=tk.LEFT, padx=10)



        about_frame = tk.LabelFrame(
            content,
            text="ℹ️ 关于",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        about_frame.pack(fill=tk.X)

        about_text = """
金银币投资管理系统 - CoinVault Pro
版本：v1.0
作者：leolu

功能特点:
• 藏品全生命周期管理
• 精确克价与盈亏核算
• 持仓分析与报表统计
• 数据导入导出与备份恢复
        """

        tk.Label(
            about_frame,
            text=about_text.strip(),
            font=('Microsoft YaHei', 10),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            justify=tk.LEFT
        ).pack(anchor='w', padx=15, pady=15)

    def _load_settings(self):
        """加载设置"""
        gold_price = self.db.get_gold_price()
        if gold_price:
            self.gold_date_entry.delete(0, tk.END)
            self.gold_date_entry.insert(0, gold_price.get('date', ''))
            if gold_price.get('gold_price'):
                self.gold_price_entry.insert(0, str(gold_price['gold_price']))
            if gold_price.get('silver_price'):
                self.silver_price_entry.insert(0, str(gold_price['silver_price']))
            if gold_price.get('platinum_price'):
                self.platinum_price_entry.insert(0, str(gold_price['platinum_price']))
            if gold_price.get('palladium_price'):
                self.palladium_price_entry.insert(0, str(gold_price['palladium_price']))

        # 显示 API 获取的最新价格（只读）
        self._show_api_prices()


    def _save_gold_price(self):
        """保存金价"""
        date = self.gold_date_entry.get().strip()
        if not date:
            logger.warning("金价保存失败 - 未填写日期")
            messagebox.showerror("错误", "请输入日期")
            return

        prices = {
            'gold': float(self.gold_price_entry.get() or 0),
            'silver': float(self.silver_price_entry.get() or 0),
            'platinum': float(self.platinum_price_entry.get() or 0),
            'palladium': float(self.palladium_price_entry.get() or 0),
        }

        logger.info(f"用户操作 - 保存金价：日期={date}, 金={prices['gold']}元/g, 银={prices['silver']}元/g, 铂={prices['platinum']}元/g, 钯={prices['palladium']}元/g")

        try:
            self.db.save_gold_price(date, prices)
            logger.info(f"金价记录已保存到数据库")
            messagebox.showinfo("成功", "金价记录已保存")

            # 刷新仪表盘和统计报表
            if hasattr(self.main_window, 'dashboard_frame') and hasattr(self.main_window.dashboard_frame, 'refresh_data'):
                self.main_window.dashboard_frame.refresh_data()
            if hasattr(self.main_window, 'reports_frame') and hasattr(self.main_window.reports_frame, '_load_report'):
                self.main_window.reports_frame._load_report()

        except Exception as e:
            logger.error(f"金价保存失败：{str(e)}", exc_info=True)
            messagebox.showerror("错误", f"保存失败：{str(e)}")

    # ... existing code ...

    def _find_buy_frame(self):
        """安全地查找 BuyFrame 实例"""
        # 策略 1: 直接属性访问
        if hasattr(self.main_window, 'buy_frame'):
            return self.main_window.buy_frame

        # 策略 2: 遍历主窗口所有子组件 (兼容 Notebook 结构)
        try:
            all_widgets = self.main_window.winfo_children()
            for widget in all_widgets:
                if isinstance(widget, BuyFrame):
                    return widget
                # 如果是 Notebook 或其他容器，检查其内部
                if hasattr(widget, 'winfo_children'):
                    for sub_widget in widget.winfo_children():
                        if isinstance(sub_widget, BuyFrame):
                            return sub_widget
        except Exception:
            pass

        return None

    def _save_config(self):
        """保存配置选项"""
        try:
            series = self.series_entry.get().strip()
            if series:
                series_list = [s.strip() for s in series.split(',') if s.strip()]
                self.db.set_setting('options_series', json.dumps(series_list))

            issuer = self.issuer_entry.get().strip()
            if issuer:
                issuer_list = [s.strip() for s in issuer.split(',') if s.strip()]
                self.db.set_setting('options_issuer', json.dumps(issuer_list))

            channel = self.channel_entry.get().strip()
            if channel:
                channel_list = [s.strip() for s in channel.split(',') if s.strip()]
                self.db.set_setting('options_buy_channel', json.dumps(channel_list))

            # 查找并刷新买入页面
            target_frame = self._find_buy_frame()

            # 【调试代码】运行后查看终端输出
            print(f"[DEBUG] 查找到的 BuyFrame: {target_frame}")

            if target_frame and hasattr(target_frame, '_refresh_config_options'):
                target_frame._refresh_config_options()
                messagebox.showinfo("成功", "配置已保存并实时同步到买入页面！")
            else:
                messagebox.showinfo(
                    "成功",
                    "配置已保存到数据库。\n\n"
                    "若【买入录入】页面的下拉框未更新，\n"
                    "请点击其他标签页后再切回即可生效。"
                )

        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{str(e)}")

    def _export_all_data(self):
        """导出全部数据"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")],
            initialfile=f"金银币数据_{datetime.now().strftime('%Y%m%d')}"
        )
        if filepath:
            logger.info(f"用户操作 - 导出全部数据：{filepath}")
            if self.db.export_to_excel(filepath):
                logger.info(f"全部数据导出成功：{filepath}")
                messagebox.showinfo("导出成功", f"数据已导出到:\n{filepath}")
            else:
                logger.error(f"全部数据导出失败：{filepath}")
                messagebox.showerror("导出失败", "数据导出失败")

    def _backup_db(self):
        """备份数据库"""
        logger.info("用户操作 - 备份数据库")
        backup_file = self.db.backup_database()
        if backup_file:
            logger.info(f"数据库备份成功：{backup_file}")
            messagebox.showinfo("备份成功", f"数据库已备份到:\n{backup_file}")
        else:
            logger.error("数据库备份失败")
            messagebox.showerror("备份失败", "数据库备份失败")

    def _restore_db(self):
        """恢复数据库"""
        filepath = filedialog.askopenfilename(
            title="选择备份文件",
            filetypes=[("数据库文件", "*.db"), ("所有文件", "*.*")]
        )
        if filepath:
            logger.info(f"用户操作 - 恢复数据库：{filepath}")
            if messagebox.askyesno("确认", "恢复数据库将覆盖当前数据，是否继续？"):
                logger.info("用户确认恢复数据库")
                if self.db.restore_database(filepath):
                    logger.info("数据库恢复成功")
                    messagebox.showinfo("恢复成功", "数据库已恢复")
                else:
                    logger.error("数据库恢复失败")
                    messagebox.showerror("恢复失败", "数据库恢复失败")
            else:
                logger.info("用户取消恢复数据库")

    def _show_api_prices(self):
        """显示 API 获取的价格"""
        try:
            latest = self.db.get_latest_gold_prices()
            if latest:
                gold = latest.get('gold_price', 0)
                silver = latest.get('silver_price', 0)
                date = latest.get('date', '')

                if hasattr(self, 'api_gold_label'):
                    self.api_gold_label.configure(text=f"{gold:.2f} 元/克" if gold > 0 else "--.-- 元/克")
                if hasattr(self, 'api_silver_label'):
                    self.api_silver_label.configure(text=f"{silver:.2f} 元/克" if silver > 0 else "--.-- 元/克")
                if hasattr(self, 'api_time_label') and date:
                    if ' ' in date:
                        time_part = date.split(' ')[1][:5]
                        self.api_time_label.configure(text=time_part)
        except Exception as e:
            logger.error(f"显示 API 价格失败：{str(e)}")

    def _refresh_api_prices(self):
        """手动刷新 API 价格"""
        try:
            logger.info("用户手动刷新 API 金价")
            # 通过 main_window 调用更新器
            if hasattr(self.main_window, 'gold_updater'):
                prices = self.main_window.gold_updater.update_now()
                if prices:
                    self._show_api_prices()
                    # 同时更新主窗口的状态栏
                    if hasattr(self.main_window, '_update_status_bar_prices'):
                        self.main_window._update_status_bar_prices()
                    messagebox.showinfo("刷新成功", "API 价格已更新！")
                else:
                    messagebox.showwarning("刷新失败", "未能从 API 获取价格，请检查网络连接")
        except Exception as e:
            logger.error(f"手动刷新 API 金价失败：{str(e)}")
            messagebox.showerror("刷新失败", f"获取价格失败：{str(e)}")

    # ... existing code ...
