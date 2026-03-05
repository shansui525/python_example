# -*- coding: utf-8 -*-
"""
GUI框架模块
包含所有功能页面：仪表盘、藏品库、买入、卖出、报表、设置
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from datetime import datetime
from tkinter import ttk
import csv


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
        # 标题
        title = tk.Label(
            self,
            text="📊 投资仪表盘",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        title.pack(anchor='w', padx=20, pady=15)

        # 统计卡片容器
        stats_container = tk.Frame(self, bg=self.colors['bg'])
        stats_container.pack(fill=tk.X, padx=20, pady=10)

        # 创建统计卡片
        self.stat_cards = {}
        card_data = [
            {'key': 'holding_value', 'title': '持仓市值', 'icon': '💰', 'color': '#B8860B'},
            {'key': 'total_cost', 'title': '总成本', 'icon': '💵', 'color': '#3498DB'},
            {'key': 'profit_loss', 'title': '已实现盈亏', 'icon': '📈', 'color': '#2E8B57'},
            {'key': 'holding_count', 'title': '在库数量', 'icon': '🎯', 'color': '#9B59B6'},
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

        # 持仓分布区域
        distribution_frame = tk.Frame(self, bg=self.colors['bg'])
        distribution_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 按材质分布
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
            columns=('材质', '数量', '成本', '市值'),
            show='headings',
            height=6
        )
        self.material_tree.heading('材质', text='材质')
        self.material_tree.heading('数量', text='数量')
        self.material_tree.heading('成本', text='成本(元)')
        self.material_tree.heading('市值', text='市值(元)')

        self.material_tree.column('材质', width=80, anchor='center')
        self.material_tree.column('数量', width=80, anchor='center')
        self.material_tree.column('成本', width=120, anchor='e')
        self.material_tree.column('市值', width=120, anchor='e')

        self.material_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 最近交易记录
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
        self.recent_tree.heading('金额', text='金额(元)')
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

        # 图标和标题
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

        # 数值
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
        stats = self.db.get_statistics()

        # 更新统计卡片
        if hasattr(self, 'stat_cards'):
            # 持仓市值
            value_frame = self.stat_cards['holding_value']
            for widget in value_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('text') != f"💰 持仓市值":
                    widget.configure(text=f"¥{stats.get('total_market_value', 0):,.2f}")

            # 总成本
            cost_frame = self.stat_cards['total_cost']
            for widget in cost_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('text') != f"💵 总成本":
                    widget.configure(text=f"¥{stats.get('total_cost', 0):,.2f}")

            # 已实现盈亏
            pl_frame = self.stat_cards['profit_loss']
            pl_value = stats.get('realized_profit_loss', 0)
            pl_color = self.colors['success'] if pl_value >= 0 else self.colors['danger']
            for widget in pl_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('text') != f"📈 已实现盈亏":
                    widget.configure(text=f"¥{pl_value:,.2f}", fg=pl_color)

            # 在库数量
            count_frame = self.stat_cards['holding_count']
            for widget in count_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('text') != f"🎯 在库数量":
                    widget.configure(text=f"{stats.get('holding_count', 0)} 枚")

        # 更新材质分布
        self._update_material_distribution(stats.get('by_material', []))

        # 更新最近交易
        self._update_recent_transactions()

    def _update_material_distribution(self, data):
        """更新材质分布表格"""
        # 清空现有数据
        for item in self.material_tree.get_children():
            self.material_tree.delete(item)

        # 插入新数据
        for row in data:
            self.material_tree.insert('', tk.END, values=(
                row.get('material', ''),
                row.get('count', 0),
                f"{row.get('cost', 0):,.2f}",
                f"{row.get('value', 0):,.2f}"
            ))

    def _update_recent_transactions(self):
        """更新最近交易记录"""
        # 清空现有数据
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)

        # 获取最近交易
        collections = self.db.get_collections()
        recent = collections[:10]  # 最近10条

        for col in recent:
            # 确定交易类型和状态
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
        # 标题栏
        header = tk.Frame(self, bg=self.colors['bg'])
        header.pack(fill=tk.X, padx=20, pady=15)

        tk.Label(
            header,
            text="🎯 藏品库",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(side=tk.LEFT)

        # 操作按钮
        btn_frame = tk.Frame(header, bg=self.colors['bg'])
        btn_frame.pack(side=tk.RIGHT)

        tk.Button(
            btn_frame,
            text="+ 添加藏品",
            bg=self.colors['primary'],
            fg='white',
            font=('Microsoft YaHei', 10),
            padx=15,
            pady=5,
            command=self._add_collection
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="📥 导入数据",
            bg='#27AE60',
            fg='white',
            font=('Microsoft YaHei', 10),
            padx=15,
            pady=5,
            command=self._import_data
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="导出Excel",
            bg='#3498DB',
            fg='white',
            font=('Microsoft YaHei', 10),
            padx=15,
            pady=5,
            command=self._export_excel
        ).pack(side=tk.LEFT, padx=5)

        # 筛选区域
        filter_frame = tk.Frame(self, bg=self.colors['bg'])
        filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        # 材质筛选
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

        # 状态筛选
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

        # 关键词搜索
        tk.Label(filter_frame, text="搜索:", bg=self.colors['bg'], fg=self.colors['text']).pack(side=tk.LEFT, padx=(20, 5))
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(filter_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<Return>', lambda e: self._apply_filter())

        tk.Button(
            filter_frame,
            text="查询",
            bg=self.colors['primary'],
            fg='white',
            command=self._apply_filter
        ).pack(side=tk.LEFT, padx=5)

        # 藏品列表
        list_frame = tk.Frame(self, bg=self.colors['bg'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 创建树形表格
        columns = ('ID', '名称', '材质', '重量', '买入日期', '买入价', '克价', '状态', '盈亏')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=18)

        # 设置列
        self.tree.heading('ID', text='藏品ID')
        self.tree.heading('名称', text='名称')
        self.tree.heading('材质', text='材质')
        self.tree.heading('重量', text='重量(g)')
        self.tree.heading('买入日期', text='买入日期')
        self.tree.heading('买入价', text='买入价(元)')
        self.tree.heading('克价', text='克价(元/g)')
        self.tree.heading('状态', text='状态')
        self.tree.heading('盈亏', text='盈亏(元)')

        # 列宽
        self.tree.column('ID', width=120, anchor='center')
        self.tree.column('名称', width=150, anchor='center')
        self.tree.column('材质', width=60, anchor='center')
        self.tree.column('重量', width=80, anchor='e')
        self.tree.column('买入日期', width=100, anchor='center')
        self.tree.column('买入价', width=100, anchor='e')
        self.tree.column('克价', width=100, anchor='e')
        self.tree.column('状态', width=80, anchor='center')
        self.tree.column('盈亏', width=100, anchor='e')

        # 滚动条
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 双击编辑
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

        status = self.status_var.get()
        if status and status != '全部':
            filters['status'] = status

        keyword = self.search_var.get().strip()
        if keyword:
            filters['keyword'] = keyword

        self.current_filter = filters
        self._load_data()

    def _load_data(self):
        """加载数据"""
        # 清空现有数据
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 获取数据
        collections = self.db.get_collections(self.current_filter)

        for col in collections:
            # 计算盈亏显示
            if col.get('is_sold'):
                profit_loss = col.get('profit_loss', 0)
                status = '已售'
            else:
                profit_loss = 0
                status = '在库'

            self.tree.insert('', tk.END, values=(
                col.get('item_id', ''),
                col.get('name', ''),
                col.get('material', ''),
                f"{col.get('weight', 0):.3f}",
                col.get('buy_date', ''),
                f"{col.get('buy_price', 0):,.2f}",
                f"{col.get('buy_gram_price', 0):,.2f}",
                status,
                f"{profit_loss:,.2f}"
            ))

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
                ("Excel文件", "*.xlsx *.xls"),
                ("CSV文件", "*.csv"),
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
            messagebox.showerror("导入失败", f"导入失败: {str(e)}")

    def _import_from_csv(self, filepath):
        """从CSV导入"""
        imported_count = 0
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # 转换数据格式
                    data = self._convert_row_data(row)
                    if data:
                        self.db.add_collection(data)
                        imported_count += 1
                except Exception as e:
                    print(f"导入行失败: {e}")
                    continue

        messagebox.showinfo("导入成功", f"成功导入 {imported_count} 条记录")
        self.refresh_data()

    def _import_from_excel(self, filepath):
        """从Excel导入"""
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
                    print(f"导入行失败: {e}")
                    continue

            messagebox.showinfo("导入成功", f"成功导入 {imported_count} 条记录")
            self.refresh_data()
        except ImportError:
            messagebox.showerror("导入失败", "请安装 pandas 和 openpyxl 库")

    def _convert_row_data(self, row):
        """转换导入的数据行"""
        # 字段映射
        field_mapping = {
            '名称': 'name',
            'name': 'name',
            '材质': 'material',
            'material': 'material',
            '类型': 'type',
            'type': 'type',
            '主题系列': 'series',
            'series': 'series',
            '发行年份': 'year',
            'year': 'year',
            '发行机构': 'issuer',
            'issuer': 'issuer',
            '重量': 'weight',
            'weight': 'weight',
            '成色': 'purity',
            'purity': 'purity',
            '面值': 'face_value',
            'face_value': 'face_value',
            '直径': 'diameter',
            'diameter': 'diameter',
            '买入日期': 'buy_date',
            'buy_date': 'buy_date',
            '买入单价': 'buy_price',
            'buy_price': 'buy_price',
            '买入数量': 'buy_quantity',
            'buy_quantity': 'buy_quantity',
            '买入费用': 'buy_fee',
            'buy_fee': 'buy_fee',
            '购买渠道': 'buy_channel',
            'buy_channel': 'buy_channel',
            '评级分数': 'grade',
            'grade': 'grade',
            '证书编号': 'cert_id',
            'cert_id': 'cert_id',
            '包装': 'packaging',
            'packaging': 'packaging',
            '标签': 'tags',
            'tags': 'tags',
            '备注': 'buy_notes',
            'notes': 'buy_notes',
        }

        data = {}
        for old_key, new_key in field_mapping.items():
            if old_key in row and row[old_key] is not None and str(row[old_key]).strip():
                value = str(row[old_key]).strip()
                # 类型转换
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

        # 验证必填字段
        required = ['name', 'material', 'type', 'weight', 'buy_date', 'buy_price']
        for field in required:
            if field not in data or not data[field]:
                return None

        # 设置默认值
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
        """导出Excel"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")],
            initialfile=f"藏品数据_{datetime.now().strftime('%Y%m%d')}"
        )
        if filepath:
            if self.db.export_to_excel(filepath):
                messagebox.showinfo("导出成功", f"数据已导出到:\n{filepath}")
            else:
                messagebox.showerror("导出失败", "数据导出失败")


class CollectionEditDialog:
    """藏品编辑对话框"""

    def __init__(self, parent, db, item_id, main_window=None):
        self.db = db
        self.item_id = item_id
        self.collection_data = None
        self.main_window = main_window

        # 获取配置选项
        self.config_options = self._load_config_options()

        if item_id:
            self.collection_data = db.get_collection_by_id(item_id)

        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("编辑藏品" if item_id else "添加藏品")
        self.dialog.geometry("600x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

        if self.collection_data:
            self._populate_data()

    def _load_config_options(self):
        """加载配置选项"""
        options = {
            'series': ['熊猫币', '生肖币', '贺岁币', '山水币', '人物币', '动物币', '花卉币', '体育币', '航天币', '其他'],
            'issuer': ['中国人民银行', '中国金币总公司', '上海金币', '深圳国宝', '国外造币厂'],
            'buy_channel': ['银行', '金店', '电商平台', '拍卖行', '收藏品市场', '朋友转让', '其他'],
            'packaging': ['原盒', '封装', '裸币', '评级封装'],
            'purity': ['99.9%', '99.99%', '99.999%', '92.5%', '90%', '其他'],
        }

        # 从数据库加载自定义选项
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
        """创建表单组件"""
        # 标题
        title_text = "编辑藏品" if self.item_id else "添加新藏品"
        tk.Label(
            self.dialog,
            text=title_text,
            font=('Microsoft YaHei', 16, 'bold'),
            fg='#2C3E50'
        ).pack(pady=15)

        # 表单容器
        form_frame = tk.Frame(self.dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 表单字段配置
        fields = [
            ('name', '名称*', 'text'),
            ('material', '材质*', 'combo', ['金', '银', '铂', '钯']),
            ('type', '类型*', 'combo', ['投资币', '纪念币', '流通币']),
            ('series', '主题系列', 'combo', self.config_options['series']),
            ('year', '发行年份', 'text'),
            ('issuer', '发行机构', 'combo', self.config_options['issuer']),
            ('weight', '重量(g)*', 'text'),
            ('purity', '成色', 'combo', self.config_options['purity']),
            ('face_value', '面值(元)', 'text'),
            ('diameter', '直径(mm)', 'text'),
            ('buy_date', '买入日期*', 'text'),
            ('buy_price', '买入单价(元)*', 'text'),
            ('buy_quantity', '买入数量', 'text'),
            ('buy_fee', '买入费用', 'text'),
            ('buy_channel', '购买渠道', 'combo', self.config_options['buy_channel']),
            ('grade', '评级分数', 'text'),
            ('cert_id', '证书编号', 'text'),
            ('packaging', '包装', 'combo', self.config_options['packaging']),
            ('tags', '标签', 'text'),
            ('buy_notes', '备注', 'text'),
        ]

        self.entries = {}
        row = 0

        for field_id, label, field_type, *args in fields:
            tk.Label(form_frame, text=label, anchor='w', fg='#2C3E50').grid(
                row=row, column=0, sticky='w', padx=5, pady=5
            )

            if field_type == 'text':
                entry = tk.Entry(form_frame, width=30)
            elif field_type == 'combo':
                entry = ttk.Combobox(form_frame, values=args[0], width=28, state='readonly')
                if args[0]:
                    entry.current(0)

            entry.grid(row=row, column=1, sticky='w', padx=5, pady=5)
            self.entries[field_id] = entry
            row += 1

        # 按钮区域
        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(pady=20)

        tk.Button(
            btn_frame,
            text="保存",
            bg='#2E8B57',
            fg='white',
            font=('Microsoft YaHei', 11),
            padx=30,
            pady=8,
            command=self._save
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            btn_frame,
            text="取消",
            bg='#95A5A6',
            fg='white',
            font=('Microsoft YaHei', 11),
            padx=30,
            pady=8,
            command=self.dialog.destroy
        ).pack(side=tk.LEFT, padx=10)

    def _populate_data(self):
        """填充数据"""
        if not self.collection_data:
            return

        for field_id, entry in self.entries.items():
            value = self.collection_data.get(field_id, '')
            if value is not None:
                if isinstance(entry, ttk.Combobox):
                    entry.set(str(value))
                else:
                    entry.insert(0, str(value))

    def _save(self):
        """保存数据"""
        # 验证必填字段
        required_fields = ['name', 'material', 'type', 'weight', 'buy_date', 'buy_price']
        for field in required_fields:
            value = self.entries[field].get().strip()
            if not value:
                messagebox.showerror("错误", f"请填写必填字段: {field}")
                return

        # 构建数据字典
        data = {}
        for field_id, entry in self.entries.items():
            value = entry.get().strip()
            if value:
                # 转换数值类型
                if field_id in ['year', 'buy_quantity', 'face_value']:
                    data[field_id] = int(value) if value else 1
                elif field_id in ['weight', 'diameter', 'buy_price', 'buy_fee']:
                    data[field_id] = float(value) if value else 0
                else:
                    data[field_id] = value

        # 设置默认值
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
            messagebox.showerror("错误", f"保存失败: {str(e)}")


# 导入 json 模块
import json


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

        # 加载配置选项
        self.config_options = self._load_config_options()

        self._create_widgets()

    def _load_config_options(self):
        """加载配置选项"""
        options = {
            'series': ['熊猫币', '生肖币', '贺岁币', '山水币', '人物币', '动物币', '花卉币', '体育币', '航天币', '其他'],
            'issuer': ['中国人民银行', '中国金币总公司', '上海金币', '深圳国宝', '国外造币厂'],
            'buy_channel': ['银行', '金店', '电商平台', '拍卖行', '收藏品市场', '朋友转让', '其他'],
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
        """创建买入录入组件"""
        # 标题
        tk.Label(
            self,
            text="💵 买入录入",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=20, pady=15)

        # 录入表单
        form_card = tk.Frame(self, bg=self.colors['card_bg'], relief=tk.RAISED, bd=1)
        form_card.pack(fill=tk.X, padx=20, pady=10)

        # 基础信息
        tk.Label(
            form_card,
            text="📋 基础信息",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['primary']
        ).pack(anchor='w', padx=15, pady=10)

        # 表单字段
        fields_frame = tk.Frame(form_card, bg=self.colors['card_bg'])
        fields_frame.pack(fill=tk.X, padx=15, pady=10)

        self.buy_entries = {}
        buy_fields = [
            ('name', '藏品名称*', 0, 0),
            ('material', '材质*', 0, 2),
            ('type', '类型*', 1, 0),
            ('series', '主题系列', 1, 2),
            ('year', '发行年份', 2, 0),
            ('issuer', '发行机构', 2, 2),
        ]

        for field_id, label, row, col in buy_fields:
            tk.Label(fields_frame, text=label, bg=self.colors['card_bg'], fg=self.colors['text']).grid(
                row=row, column=col, sticky='w', padx=5, pady=8
            )
            if field_id == 'material':
                entry = ttk.Combobox(fields_frame, width=12, state='readonly')
                entry['values'] = ['金', '银', '铂', '钯']
                entry.current(0)
            elif field_id == 'type':
                entry = ttk.Combobox(fields_frame, width=12, state='readonly')
                entry['values'] = ['投资币', '纪念币', '流通币']
                entry.current(0)
            elif field_id == 'series':
                entry = ttk.Combobox(fields_frame, width=12, values=self.config_options['series'], state='readonly')
                if self.config_options['series']:
                    entry.current(0)
            elif field_id == 'issuer':
                entry = ttk.Combobox(fields_frame, width=12, values=self.config_options['issuer'], state='readonly')
                if self.config_options['issuer']:
                    entry.current(0)
            else:
                entry = tk.Entry(fields_frame, width=15)
            entry.grid(row=row, column=col+1, sticky='w', padx=5, pady=8)
            self.buy_entries[field_id] = entry

        # 规格信息
        tk.Label(
            form_card,
            text="⚙️ 规格参数",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['primary']
        ).pack(anchor='w', padx=15, pady=(20, 10))

        spec_frame = tk.Frame(form_card, bg=self.colors['card_bg'])
        spec_frame.pack(fill=tk.X, padx=15, pady=10)

        spec_fields = [
            ('weight', '重量(g)*', 0, 0),
            ('purity', '成色', 0, 2),
            ('face_value', '面值(元)', 1, 0),
            ('diameter', '直径(mm)', 1, 2),
        ]

        for field_id, label, row, col in spec_fields:
            tk.Label(spec_frame, text=label, bg=self.colors['card_bg'], fg=self.colors['text']).grid(
                row=row, column=col, sticky='w', padx=5, pady=8
            )
            if field_id == 'purity':
                entry = ttk.Combobox(spec_frame, width=12, values=self.config_options['purity'], state='readonly')
                entry.current(0)
            else:
                entry = tk.Entry(spec_frame, width=15)
            entry.grid(row=row, column=col+1, sticky='w', padx=5, pady=8)
            self.buy_entries[field_id] = entry

        # 交易信息
        tk.Label(
            form_card,
            text="💰 交易信息",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['primary']
        ).pack(anchor='w', padx=15, pady=(20, 10))

        trade_frame = tk.Frame(form_card, bg=self.colors['card_bg'])
        trade_frame.pack(fill=tk.X, padx=15, pady=10)

        trade_fields = [
            ('buy_date', '买入日期*', 0, 0),
            ('buy_price', '买入单价(元)*', 0, 2),
            ('buy_quantity', '买入数量', 1, 0),
            ('buy_fee', '买入费用(元)', 1, 2),
            ('buy_channel', '购买渠道', 2, 0),
            ('gold_price_at_buy', '买入时金价(元/g)', 2, 2),
        ]

        for field_id, label, row, col in trade_fields:
            tk.Label(trade_frame, text=label, bg=self.colors['card_bg'], fg=self.colors['text']).grid(
                row=row, column=col, sticky='w', padx=5, pady=8
            )
            if field_id == 'buy_channel':
                entry = ttk.Combobox(trade_frame, width=12, values=self.config_options['buy_channel'], state='readonly')
                entry.current(0)
            else:
                entry = tk.Entry(trade_frame, width=15)
            entry.grid(row=row, column=col+1, sticky='w', padx=5, pady=8)
            self.buy_entries[field_id] = entry

        # 设置默认值
        self.buy_entries['buy_quantity'].insert(0, '1')
        self.buy_entries['buy_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

        # 按钮
        btn_frame = tk.Frame(form_card, bg=self.colors['card_bg'])
        btn_frame.pack(pady=20)

        tk.Button(
            btn_frame,
            text="💾 保存记录",
            bg=self.colors['primary'],
            fg='white',
            font=('Microsoft YaHei', 12),
            padx=30,
            pady=10,
            command=self._save_buy
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            btn_frame,
            text="清空表单",
            bg='#95A5A6',
            fg='white',
            font=('Microsoft YaHei', 12),
            padx=30,
            pady=10,
            command=self._clear_form
        ).pack(side=tk.LEFT, padx=10)

    def _save_buy(self):
        """保存买入记录"""
        # 验证必填字段
        required = ['name', 'material', 'type', 'weight', 'buy_date', 'buy_price']
        for field in required:
            value = self.buy_entries[field].get().strip()
            if not value:
                messagebox.showerror("错误", f"请填写必填字段: {field}")
                return

        # 构建数据
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

        try:
            self.db.add_collection(data)
            messagebox.showinfo("成功", "买入记录已保存！")
            self._clear_form()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")

    def _clear_form(self):
        """清空表单"""
        for entry in self.buy_entries.values():
            entry.delete(0, tk.END)
        self.buy_entries['buy_quantity'].insert(0, '1')
        self.buy_entries['buy_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))


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
        # 标题
        tk.Label(
            self,
            text="💴 卖出录入",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=20, pady=15)

        # 主体布局：左侧持仓列表 + 右侧卖出表单
        content_frame = tk.Frame(self, bg=self.colors['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 左侧：在库藏品列表
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
        self.holdings_tree.heading('ID', text='藏品ID')
        self.holdings_tree.heading('名称', text='名称')
        self.holdings_tree.heading('材质', text='材质')
        self.holdings_tree.heading('重量', text='重量(g)')
        self.holdings_tree.heading('买入价', text='买入价(元)')
        self.holdings_tree.heading('克价', text='克价(元/g)')

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

        # 右侧：卖出表单
        right_frame = tk.LabelFrame(
            content_frame,
            text="💰 填写卖出信息",
            font=('Microsoft YaHei', 12, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 选中藏品信息
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

        # 卖出表单
        form_frame = tk.Frame(right_frame, bg=self.colors['bg'])
        form_frame.pack(fill=tk.X, padx=15, pady=10)

        self.sell_entries = {}
        sell_fields = [
            ('sell_date', '卖出日期*', 0, 0),
            ('sell_price', '卖出金额(元)*', 0, 2),
            ('sell_fee', '卖出费用(元)', 1, 0),
            ('sell_channel', '出售渠道', 1, 2),
            ('gold_price_at_sell', '卖出时金价(元/g)', 2, 0),
            ('sell_notes', '备注', 2, 2),
        ]

        for field_id, label, row, col in sell_fields:
            tk.Label(form_frame, text=label, bg=self.colors['bg'], fg=self.colors['text']).grid(
                row=row, column=col, sticky='w', padx=5, pady=10
            )
            entry = tk.Entry(form_frame, width=15)
            entry.grid(row=row, column=col+1, sticky='w', padx=5, pady=10)
            self.sell_entries[field_id] = entry

        # 设置默认值
        self.sell_entries['sell_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

        # 预览区域
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

        for i, (key, label) in enumerate(preview_items):
            tk.Label(preview_frame, text=f"{label}:", bg=self.colors['bg'], fg=self.colors['text']).grid(
                row=i//2, column=(i%2)*2, sticky='w', padx=15, pady=5
            )
            value_label = tk.Label(preview_frame, text="--", bg=self.colors['bg'], font=('Microsoft YaHei', 11, 'bold'), fg=self.colors['primary'])
            value_label.grid(row=i//2, column=(i%2)*2+1, sticky='w', padx=5, pady=5)
            self.preview_labels[key] = value_label

        # 绑定预览事件
        self.sell_entries['sell_price'].bind('<KeyRelease>', self._update_preview)
        self.sell_entries['sell_fee'].bind('<KeyRelease>', self._update_preview)

        # 按钮
        btn_frame = tk.Frame(right_frame, bg=self.colors['bg'])
        btn_frame.pack(pady=20)

        tk.Button(
            btn_frame,
            text="💾 确认卖出",
            bg=self.colors['success'],
            fg='white',
            font=('Microsoft YaHei', 12),
            padx=30,
            pady=10,
            command=self._save_sell
        ).pack(side=tk.LEFT, padx=10)

    def _load_holdings(self):
        """加载在库藏品"""
        # 清空现有数据
        for item in self.holdings_tree.get_children():
            self.holdings_tree.delete(item)

        # 获取在库藏品
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
                    text=f"已选择: {self.selected_item['name']} (克价: {self.selected_item.get('buy_gram_price', 0):.2f}元/g)",
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

            # 计算持有天数
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

            # 更新显示
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
            messagebox.showwarning("警告", "请先选择要卖出的藏品")
            return

        # 验证必填字段
        if not self.sell_entries['sell_date'].get().strip():
            messagebox.showerror("错误", "请填写卖出日期")
            return

        sell_price = self.sell_entries['sell_price'].get().strip()
        if not sell_price:
            messagebox.showerror("错误", "请填写卖出金额")
            return

        # 构建卖出数据
        sell_data = {
            'sell_date': self.sell_entries['sell_date'].get().strip(),
            'sell_price': float(sell_price),
            'sell_fee': float(self.sell_entries['sell_fee'].get() or 0),
            'sell_channel': self.sell_entries['sell_channel'].get().strip(),
            'sell_notes': self.sell_entries['sell_notes'].get().strip(),
        }

        # 可选的金价
        gold_price = self.sell_entries['gold_price_at_sell'].get().strip()
        if gold_price:
            sell_data['gold_price_at_sell'] = float(gold_price)

        try:
            self.db.record_sell(self.selected_item['item_id'], sell_data)

            # 显示结果
            result = f"卖出记录已保存！\n\n"
            result += f"藏品: {self.selected_item['name']}\n"
            result += f"卖出金额: ¥{sell_data['sell_price']:,.2f}\n"
            result += f"盈亏: ¥{sell_data.get('profit_loss', 0):,.2f}"

            messagebox.showinfo("成功", result)

            # 刷新列表
            self._load_holdings()
            self.selected_item = None
            self.selected_label.configure(text="请从左侧选择要卖出的藏品")

            # 清空表单
            for entry in self.sell_entries.values():
                entry.delete(0, tk.END)
            self.sell_entries['sell_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")


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

        self._create_widgets()
        self._load_report()

    def _create_widgets(self):
        """创建报表组件"""
        # 标题栏
        header = tk.Frame(self, bg=self.colors['bg'])
        header.pack(fill=tk.X, padx=20, pady=15)

        tk.Label(
            header,
            text="📈 统计报表",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(side=tk.LEFT)

        # 年份选择
        tk.Label(header, text="年份:", bg=self.colors['bg'], fg=self.colors['text']).pack(side=tk.RIGHT, padx=(0, 10))
        self.year_var = tk.StringVar(value="全部")
        year_combo = ttk.Combobox(
            header,
            textvariable=self.year_var,
            values=['全部', '2026', '2025', '2024', '2023', '2022', '2021'],
            state='readonly',
            width=8
        )
        year_combo.pack(side=tk.RIGHT)
        year_combo.bind('<<ComboboxSelected>>', lambda e: self._load_report())

        # 报表内容区域
        content = tk.Frame(self, bg=self.colors['bg'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 收益汇总报表
        summary_frame = tk.LabelFrame(
            content,
            text="💰 投资收益汇总",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        summary_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('类别', '材质', '数量', '总成本', '总销售额', '盈亏金额', '盈亏率')
        self.report_tree = ttk.Treeview(summary_frame, columns=columns, show='headings', height=10)

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

        self.report_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 底部统计
        bottom_frame = tk.Frame(self, bg=self.colors['bg'])
        bottom_frame.pack(fill=tk.X, padx=20, pady=(0, 15))

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

    def _load_report(self):
        """加载报表数据"""
        # 清空现有数据
        for item in self.report_tree.get_children():
            self.report_tree.delete(item)

        # 获取年份
        year = self.year_var.get()
        year = None if year == '全部' else year

        # 获取报表数据
        report_data = self.db.get_profit_loss_report(year)

        total_realized = 0
        total_cost = 0
        total_value = 0

        for row in report_data:
            profit_loss = row.get('profit_loss', 0)
            total = row.get('total_cost', 0)

            if row.get('category') == '已实现盈亏':
                total_realized += profit_loss
            else:
                total_cost += total
                total_value += row.get('total_value', 0)

            profit_rate = (profit_loss / total * 100) if total > 0 else 0
            pl_color = 'green' if profit_loss >= 0 else 'red'

            self.report_tree.insert('', tk.END, values=(
                row.get('category', ''),
                row.get('material', ''),
                row.get('count', 0),
                f"{total:,.2f}",
                f"{row.get('total_value', 0):,.2f}",
                f"{profit_loss:,.2f}",
                f"{profit_rate:.2f}%"
            ), tags=(pl_color,))

        self.report_tree.tag_configure('green', foreground=self.colors['success'])
        self.report_tree.tag_configure('red', foreground=self.colors['danger'])

        # 获取统计数据
        stats = self.db.get_statistics()

        # 更新底部统计
        self.summary_labels['total_invested'].configure(text=f"¥{stats.get('total_invested', 0):,.2f}")
        self.summary_labels['total_cost'].configure(text=f"¥{stats.get('total_cost', 0):,.2f}")
        self.summary_labels['total_value'].configure(text=f"¥{stats.get('total_market_value', 0):,.2f}")

        pl_color = self.colors['success'] if total_realized >= 0 else self.colors['danger']
        self.summary_labels['realized_pl'].configure(text=f"¥{total_realized:,.2f}", fg=pl_color)


class SettingsFrame(ttk.Frame):
    """系统设置页面"""

    def __init__(self, parent, db, main_window):
        super().__init__(parent)
        self.db = db
        self.main_window = main_window

        # 修复：添加 text_secondary 键
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
        # 标题
        tk.Label(
            self,
            text="⚙️ 系统设置",
            font=('Microsoft YaHei', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack(anchor='w', padx=20, pady=15)

        # 设置内容
        content = tk.Frame(self, bg=self.colors['bg'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 金价管理
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

        tk.Label(gold_form, text="金价(元/g):", bg=self.colors['bg'], fg=self.colors['text']).grid(row=0, column=2, sticky='w', padx=15, pady=8)
        self.gold_price_entry = tk.Entry(gold_form, width=15)
        self.gold_price_entry.grid(row=0, column=3, sticky='w', padx=5, pady=8)

        tk.Label(gold_form, text="银价(元/g):", bg=self.colors['bg'], fg=self.colors['text']).grid(row=1, column=0, sticky='w', padx=5, pady=8)
        self.silver_price_entry = tk.Entry(gold_form, width=15)
        self.silver_price_entry.grid(row=1, column=1, sticky='w', padx=5, pady=8)

        tk.Label(gold_form, text="铂金(元/g):", bg=self.colors['bg'], fg=self.colors['text']).grid(row=1, column=2, sticky='w', padx=15, pady=8)
        self.platinum_price_entry = tk.Entry(gold_form, width=15)
        self.platinum_price_entry.grid(row=1, column=3, sticky='w', padx=5, pady=8)

        tk.Label(gold_form, text="钯金(元/g):", bg=self.colors['bg'], fg=self.colors['text']).grid(row=2, column=0, sticky='w', padx=5, pady=8)
        self.palladium_price_entry = tk.Entry(gold_form, width=15)
        self.palladium_price_entry.grid(row=2, column=1, sticky='w', padx=5, pady=8)

        tk.Button(
            gold_form,
            text="保存金价",
            bg=self.colors['primary'],
            fg='white',
            padx=15,
            pady=5,
            command=self._save_gold_price
        ).grid(row=2, column=2, columnspan=2, padx=15, pady=8)

        # 配置管理
        config_frame = tk.LabelFrame(
            content,
            text="🔧 选项配置",
            font=('Microsoft YaHei', 14, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        config_frame.pack(fill=tk.X, pady=(0, 15))

        config_form = tk.Frame(config_frame, bg=self.colors['bg'])
        config_form.pack(fill=tk.X, padx=15, pady=15)

        # 主题系列配置
        tk.Label(config_form, text="主题系列:", bg=self.colors['bg'], fg=self.colors['text']).grid(row=0, column=0, sticky='w', padx=5, pady=8)
        self.series_entry = tk.Entry(config_form, width=40)
        self.series_entry.grid(row=0, column=1, sticky='w', padx=5, pady=8)
        tk.Label(config_form, text="(用逗号分隔)", bg=self.colors['bg'], fg=self.colors['text_secondary'], font=('Microsoft YaHei', 9)).grid(row=0, column=2, sticky='w', padx=5)

        # 发行机构配置
        tk.Label(config_form, text="发行机构:", bg=self.colors['bg'], fg=self.colors['text']).grid(row=1, column=0, sticky='w', padx=5, pady=8)
        self.issuer_entry = tk.Entry(config_form, width=40)
        self.issuer_entry.grid(row=1, column=1, sticky='w', padx=5, pady=8)

        # 购买渠道配置
        tk.Label(config_form, text="购买渠道:", bg=self.colors['bg'], fg=self.colors['text']).grid(row=2, column=0, sticky='w', padx=5, pady=8)
        self.channel_entry = tk.Entry(config_form, width=40)
        self.channel_entry.grid(row=2, column=1, sticky='w', padx=5, pady=8)

        tk.Button(
            config_form,
            text="保存配置",
            bg=self.colors['primary'],
            fg='white',
            padx=15,
            pady=5,
            command=self._save_config
        ).grid(row=3, column=1, sticky='w', padx=5, pady=15)

        # 数据管理
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
            fg='white',
            padx=20,
            pady=8,
            command=self._export_all_data
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            data_form,
            text="备份数据库",
            bg='#27AE60',
            fg='white',
            padx=20,
            pady=8,
            command=self._backup_db
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            data_form,
            text="恢复数据库",
            bg='#E67E22',
            fg='white',
            padx=20,
            pady=8,
            command=self._restore_db
        ).pack(side=tk.LEFT, padx=10)

        # 关于
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
版本: v1.0
作者: MiniMax Agent

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
        # 加载最新金价
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

        # 加载配置选项
        series = self.db.get_setting('options_series')
        if series:
            self.series_entry.insert(0, series)
        else:
            self.series_entry.insert(0, '熊猫币,生肖币,贺岁币,山水币,人物币,动物币,花卉币,体育币,航天币')

        issuer = self.db.get_setting('options_issuer')
        if issuer:
            self.issuer_entry.insert(0, issuer)
        else:
            self.issuer_entry.insert(0, '中国人民银行,中国金币总公司,上海金币,深圳国宝')

        channel = self.db.get_setting('options_buy_channel')
        if channel:
            self.channel_entry.insert(0, channel)
        else:
            self.channel_entry.insert(0, '银行,金店,电商平台,拍卖行,收藏品市场,朋友转让')

    def _save_gold_price(self):
        """保存金价"""
        date = self.gold_date_entry.get().strip()
        if not date:
            messagebox.showerror("错误", "请输入日期")
            return

        prices = {
            'gold': float(self.gold_price_entry.get() or 0),
            'silver': float(self.silver_price_entry.get() or 0),
            'platinum': float(self.platinum_price_entry.get() or 0),
            'palladium': float(self.palladium_price_entry.get() or 0),
        }

        try:
            self.db.save_gold_price(date, prices)
            messagebox.showinfo("成功", "金价记录已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")

    def _save_config(self):
        """保存配置选项"""
        try:
            # 保存主题系列
            series = self.series_entry.get().strip()
            if series:
                series_list = [s.strip() for s in series.split(',') if s.strip()]
                self.db.set_setting('options_series', json.dumps(series_list))

            # 保存发行机构
            issuer = self.issuer_entry.get().strip()
            if issuer:
                issuer_list = [s.strip() for s in issuer.split(',') if s.strip()]
                self.db.set_setting('options_issuer', json.dumps(issuer_list))

            # 保存购买渠道
            channel = self.channel_entry.get().strip()
            if channel:
                channel_list = [s.strip() for s in channel.split(',') if s.strip()]
                self.db.set_setting('options_buy_channel', json.dumps(channel_list))

            messagebox.showinfo("成功", "配置已保存，请重启程序生效")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")

    def _export_all_data(self):
        """导出全部数据"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")],
            initialfile=f"金银币数据_{datetime.now().strftime('%Y%m%d')}"
        )
        if filepath:
            if self.db.export_to_excel(filepath):
                messagebox.showinfo("导出成功", f"数据已导出到:\n{filepath}")
            else:
                messagebox.showerror("导出失败", "数据导出失败")

    def _backup_db(self):
        """备份数据库"""
        backup_file = self.db.backup_database()
        if backup_file:
            messagebox.showinfo("备份成功", f"数据库已备份到:\n{backup_file}")
        else:
            messagebox.showerror("备份失败", "数据库备份失败")

    def _restore_db(self):
        """恢复数据库"""
        filepath = filedialog.askopenfilename(
            title="选择备份文件",
            filetypes=[("数据库文件", "*.db"), ("所有文件", "*.*")]
        )
        if filepath:
            if messagebox.askyesno("确认", "恢复数据库将覆盖当前数据，是否继续？"):
                if self.db.restore_database(filepath):
                    messagebox.showinfo("恢复成功", "数据库已恢复")
                else:
                    messagebox.showerror("恢复失败", "数据库恢复失败")