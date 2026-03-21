
"""
PyQt6 GUI 主界面模块
支持现代化 UI 设计、日期范围筛选、文章标星、批量导入及质量审计展示
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QPushButton, QLineEdit,
    QLabel, QTextEdit, QCheckBox, QGroupBox, QDialog, QDialogButtonBox,
    QMessageBox, QProgressBar, QToolBar, QStatusBar, QFrame,
    QScrollArea, QGridLayout, QFileDialog, QComboBox,
    QButtonGroup, QRadioButton, QTextBrowser, QSizePolicy, QDateEdit, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QDate
from PyQt6.QtGui import QAction, QFont, QPalette, QColor, QIntValidator, QIcon

from database import Database
from fetcher import RSSFetcher, Summarizer, BatchImporter
from obsidian_writer import ObsidianWriter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FetchThread(QThread):
    """后台抓取线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    articles_ready_for_summary = pyqtSignal(list)

    def __init__(self, fetcher: RSSFetcher, db: Database):
        super().__init__()
        self.fetcher = fetcher
        self.db = db

    def run(self):
        try:
            self.progress.emit("正在获取订阅源...")
            result = self.fetcher.fetch_all_feeds()
            self.finished.emit(result)

            if result.get('new_articles', 0) > 0:
                self.progress.emit("正在准备生成摘要...")
                new_articles_needing_summary = self.db.get_articles_without_summary(limit=50,days_ago=1)
                if new_articles_needing_summary:
                    self.articles_ready_for_summary.emit(new_articles_needing_summary)

        except Exception as e:
            self.error.emit(str(e))


# 在 gui.py 中找到 SummarizeThread 类

class SummarizeThread(QThread):
    """后台摘要生成线程"""
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str) # 保持信号不变，但我们可以发送更详细的信息

    def __init__(self, summarizer: Summarizer, articles: List[Dict]):
        super().__init__()
        self.summarizer = summarizer
        self.articles = articles

    def run(self):
        try:
            logger.info(f"开始为 {len(self.articles)} 篇文章生成摘要...")
            result = self.summarizer.summarize_articles(self.articles)
            logger.info(f"摘要生成完成：{result}")
            self.finished.emit(result)
        except Exception as e:
            # 【关键修改】记录完整堆栈跟踪到日志
            logger.exception("摘要生成过程中发生严重错误")
            # 发送包含类型和详细信息的错误字符串
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.error.emit(error_msg)


class BatchImportThread(QThread):
    """后台批量导入线程"""
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, importer: BatchImporter, urls: List[str]):
        super().__init__()
        self.importer = importer
        self.urls = urls

    def run(self):
        try:
            result = self.importer.import_urls(self.urls)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.db = Database()

        # 【修改】先加载配置，再初始化组件
        self.config = self._load_config()

        # 从配置中获取 API key 和 base_url
        api_key = self.config.get('openai_api_key', '')
        base_url = self.config.get('openai_base_url', 'http://localhost:11434/v1')
        model_name = self.config.get('openai_model_name', 'qwen3:8b')

        self.fetcher = RSSFetcher(self.db, api_key=api_key, base_url=base_url)
        self.summarizer = Summarizer(self.db, api_key=api_key, base_url=base_url, model_name=model_name)
        self.batch_importer = BatchImporter(self.db, self.fetcher)
        self.obsidian_writer = ObsidianWriter()

        # --- 新增：自动刷新定时器 (30 秒) ---
        # self.auto_refresh_timer = QTimer()
        # self.auto_refresh_timer.timeout.connect(self.trigger_auto_refresh)
        # self.auto_refresh_timer.start(30000 * 2)  # 30000 毫秒 = 30 秒
        # ----------------------------------

        self.auto_fetch_timer = QTimer()
        self.auto_fetch_timer.timeout.connect(self.fetch_all_feeds)

        self.current_feed_id = None
        self.current_view = "all"

        self.current_page = 1
        self.page_size = 50
        self.total_pages = 1
        self.current_articles = []

        if self.config.get('obsidian_vault_path'):
            self.obsidian_writer.set_vault_path(self.config['obsidian_vault_path'])

        self.init_ui()
        self.apply_styles()

        self.load_feeds()
        self.load_articles()

        self._start_auto_fetch_scheduler()

        if self.config.get('auto_fetch_on_startup', True):
            QTimer.singleShot(500, self.fetch_all_feeds)

    def trigger_auto_refresh(self):
        # 检查是否已有抓取任务在运行
        if hasattr(self, '_fetch_worker') and self._fetch_worker.isRunning():
            return

        # 检查是否已有摘要生成任务在运行 (原 summarize_thread)
        if hasattr(self, '_summarize_worker') and self._summarize_worker.isRunning():
            return

        # 检查是否已有批量导入任务在运行 (原 batch_import_thread)
        if hasattr(self, '_import_worker') and self._import_worker.isRunning():
            return

        # 执行静默刷新
        self.statusBar().showMessage("🔄 定时检查更新...", 3000)
        self.fetch_all_feeds()


    # 【新增】窗口关闭时清理定时器
    def closeEvent(self, event):
        # if hasattr(self, 'auto_refresh_timer'):
        #     self.auto_refresh_timer.stop()
        if hasattr(self, 'auto_fetch_timer'):
            self.auto_fetch_timer.stop()
        event.accept()

    def _load_config(self) -> Dict:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def _start_auto_fetch_scheduler(self):
        self.auto_fetch_timer.stop()
        interval_hours = self.config.get('fetch_interval_hours', 24)
        if interval_hours <= 0:
            logger.info("自动抓取已禁用 (interval <= 0)")
            return
        interval_ms = int(interval_hours * 60 * 60 * 1000)
        self.auto_fetch_timer.start(interval_ms)
        logger.info(f"自动抓取已启动，间隔：{interval_hours} 小时")
        self.statusBar().showMessage(f"自动抓取已启用：每 {interval_hours} 小时一次")

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QWidget { font-family: "Microsoft YaHei", "Segoe UI", sans-serif; font-size: 13px; }
            QPushButton {
                background-color: #3b82f6; color: white; border: none;
                padding: 8px 16px; border-radius: 6px; font-weight: 500;
            }
            QPushButton:hover { background-color: #2563eb; }
            QPushButton:pressed { background-color: #1d4ed8; }
            QPushButton:disabled { background-color: #9ca3af; }
            QLineEdit {
                padding: 8px 12px; border: 1px solid #d1d5db;
                border-radius: 6px; background-color: white;
            }
            QLineEdit:focus { border-color: #3b82f6; }
            QDateEdit, QSpinBox {
                padding: 6px 10px; border: 1px solid #d1d5db;
                border-radius: 6px; background-color: white;
            }
            QDateEdit:focus, QSpinBox:focus { border-color: #3b82f6; }
            QListWidget { border: none; background-color: white; border-radius: 8px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #f3f4f6; }
            QListWidget::item:selected { background-color: #eff6ff; }
            QScrollArea { border: none; }
            QLabel { color: #374151; }
            QTextEdit, QTextBrowser {
                border: none; background-color: white;
                border-radius: 8px; padding: 12px;
            }
            QCheckBox { spacing: 8px; }
            QToolBar { background-color: white; border: none; spacing: 8px; padding: 8px; }
            QStatusBar { background-color: white; border-top: 1px solid #e5e7eb; }
            QGroupBox {
                border: 1px solid #e5e7eb; border-radius: 8px;
                margin-top: 8px; padding-top: 8px; font-weight: 500;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

    def init_ui(self):
        self.setWindowTitle('RSS 订阅管理器 (AI 审计版)')
        self.setGeometry(100, 100, 1400, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        splitter.addWidget(self._create_left_panel())
        splitter.addWidget(self._create_center_panel())
        splitter.addWidget(self._create_right_panel())

        splitter.setSizes([250, 400, 450])

        self._create_toolbar()
        self.statusBar().showMessage("就绪")

    def _create_left_panel(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background-color: white; border-radius: 8px;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("导航")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f2937;")
        layout.addWidget(title)

        self.nav_all_btn = QPushButton("📋 全部文章")
        self.nav_all_btn.setStyleSheet("text-align: left; background-color: #eff6ff; color: #3b82f6;")
        self.nav_all_btn.clicked.connect(lambda: self.switch_view("all"))
        layout.addWidget(self.nav_all_btn)

        self.nav_starred_btn = QPushButton("⭐ 标星文章")
        self.nav_starred_btn.setStyleSheet("text-align: left;")
        self.nav_starred_btn.clicked.connect(lambda: self.switch_view("starred"))
        layout.addWidget(self.nav_starred_btn)

        self.nav_selected_btn = QPushButton("✅ 已选文章")
        self.nav_selected_btn.setStyleSheet("text-align: left;")
        self.nav_selected_btn.clicked.connect(lambda: self.switch_view("selected"))
        layout.addWidget(self.nav_selected_btn)

        layout.addSpacing(10)

        feeds_title = QLabel("订阅源")
        feeds_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f2937;")
        layout.addWidget(feeds_title)

        self.feed_list = QListWidget()
        self.feed_list.itemClicked.connect(self.on_feed_clicked)
        self.feed_list.setStyleSheet("border: 1px solid #e5e7eb;")
        layout.addWidget(self.feed_list)

        add_group = QGroupBox("添加订阅源")
        add_layout = QVBoxLayout(add_group)

        self.batch_import_btn = QPushButton("📥 批量导入 RSS")
        self.batch_import_btn.setStyleSheet("background-color: #3b82f6; color: white;")
        self.batch_import_btn.clicked.connect(self.show_batch_import_dialog)
        add_layout.addWidget(self.batch_import_btn)

        single_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入 RSS 链接...")
        self.url_input.returnPressed.connect(self.add_feed)
        single_layout.addWidget(self.url_input)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(40)
        add_btn.clicked.connect(self.add_feed)
        single_layout.addWidget(add_btn)
        add_layout.addLayout(single_layout)

        del_btn = QPushButton("删除选中")
        del_btn.setStyleSheet("background-color: #ef4444; color: white;")
        del_btn.clicked.connect(self.delete_feed)
        add_layout.addWidget(del_btn)

        layout.addWidget(add_group)
        return widget

    def _create_center_panel(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background-color: white; border-radius: 8px;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- 顶部标题栏 ---
        header = QHBoxLayout()
        title = QLabel("文章列表")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f2937;")
        header.addWidget(title)
        header.addStretch()

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("background-color: #f59e0b; color: white;")
        self.refresh_btn.clicked.connect(self.fetch_all_feeds)
        header.addWidget(self.refresh_btn)

        self.summarize_btn = QPushButton("🤖 生成摘要")
        self.summarize_btn.setStyleSheet("background-color: #8b5cf6; color: white;")
        self.summarize_btn.clicked.connect(self.generate_summaries)
        header.addWidget(self.summarize_btn)
        layout.addLayout(header)

        # --- 筛选区域 (重新排版) ---
        filter_group = QGroupBox("筛选")
        filter_layout = QGridLayout(filter_group)
        filter_layout.setSpacing(10) # 增加控件间距

        # === Row 0: 日期范围 & 摘要状态 ===
        row = 0

        # 日期开关
        self.enable_date_filter = QCheckBox("日期:")
        self.enable_date_filter.setChecked(True)
        filter_layout.addWidget(self.enable_date_filter, row, 0)

        # 开始日期
        self.start_date_input = QDateEdit()
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDisplayFormat("yyyy-MM-dd")
        self.start_date_input.setDate(QDate.currentDate()) # 默认近一个月
        filter_layout.addWidget(self.start_date_input, row, 1)

        # 分隔符
        filter_layout.addWidget(QLabel("-"), row, 2)

        # 结束日期
        self.end_date_input = QDateEdit()
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDisplayFormat("yyyy-MM-dd")
        self.end_date_input.setDate(QDate.currentDate())
        filter_layout.addWidget(self.end_date_input, row, 3)

        # 摘要筛选标签
        filter_layout.addWidget(QLabel("摘要:"), row, 4)

        # 有摘要
        self.has_summary_checkbox = QCheckBox("有")
        filter_layout.addWidget(self.has_summary_checkbox, row, 5)

        # 无摘要
        self.no_summary_checkbox = QCheckBox("无")
        filter_layout.addWidget(self.no_summary_checkbox, row, 6)

        # 占位，保持右侧对齐美观
        filter_layout.addWidget(QLabel(""), row, 7)

        # === Row 1: 推荐建议 & 搜索 ===
        row = 1

        # 推荐建议标签
        filter_layout.addWidget(QLabel("推荐:"), row, 0)

        # 推荐下拉框 (横跨 3 列)
        self.recommend_filter_combo = QComboBox()
        self.recommend_filter_combo.addItem("全部", "")
        self.recommend_filter_combo.addItem("强烈推荐", "强烈推荐")
        self.recommend_filter_combo.addItem("推荐阅读", "推荐阅读")
        self.recommend_filter_combo.addItem("一般浏览", "一般浏览")
        self.recommend_filter_combo.addItem("快速浏览", "快速浏览")
        self.recommend_filter_combo.addItem("标题党慎入", "标题党慎入")
        self.recommend_filter_combo.setCurrentIndex(0)
        self.recommend_filter_combo.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.recommend_filter_combo, row, 1, 1, 3)

        # 搜索标签
        filter_layout.addWidget(QLabel("搜索:"), row, 4)

        # 搜索输入框
        self.search_keyword_input = QLineEdit()
        self.search_keyword_input.setPlaceholderText("标题/摘要/关键字")
        self.search_keyword_input.returnPressed.connect(self.apply_filters)
        filter_layout.addWidget(self.search_keyword_input, row, 5, 1, 2) # 横跨 2 列

        # 搜索按钮
        self.apply_filter_btn = QPushButton("🔍")
        self.apply_filter_btn.setFixedWidth(40)
        self.apply_filter_btn.setStyleSheet("background-color: #10b981; color: white;")
        self.apply_filter_btn.clicked.connect(self.apply_filters)
        filter_layout.addWidget(self.apply_filter_btn, row, 7)

        # === Row 2: 排序 & 清除 & 分页设置 ===
        row = 2

        # 排序标签
        filter_layout.addWidget(QLabel("排序:"), row, 0)

        # 排序下拉框 (横跨 3 列)
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("🕒 时间倒序", "time")
        self.sort_combo.addItem("⭐ 分数优先", "time_score")
        self.sort_combo.addItem("🔥 仅按评分", "score")
        self.sort_combo.setCurrentIndex(0)
        self.sort_combo.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.sort_combo, row, 1, 1, 3)

        # 清除按钮
        clear_btn = QPushButton("清除筛选")
        clear_btn.setStyleSheet("background-color: #6b7280; color: white;")
        clear_btn.clicked.connect(self.clear_filters)
        filter_layout.addWidget(clear_btn, row, 4)

        # 每页数量标签
        filter_layout.addWidget(QLabel("每页:"), row, 5)

        # 每页数量 SpinBox
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(20, 200)
        self.page_size_spin.setValue(self.page_size)
        self.page_size_spin.valueChanged.connect(self.on_page_size_changed)
        filter_layout.addWidget(self.page_size_spin, row, 6)

        # 占位
        filter_layout.addWidget(QLabel(""), row, 7)

        layout.addWidget(filter_group)

        # --- 文章列表 ---
        self.article_list = QListWidget()
        self.article_list.itemClicked.connect(self.on_article_clicked)
        layout.addWidget(self.article_list)

        # --- 分页控制 ---
        pagination_layout = QHBoxLayout()
        self.prev_page_btn = QPushButton("◀ 上一页")
        self.prev_page_btn.setStyleSheet("background-color: #6366f1; color: white; font-weight: bold;")
        self.prev_page_btn.clicked.connect(self.prev_page)
        pagination_layout.addWidget(self.prev_page_btn)

        self.page_info_label = QLabel("第 1 / 1 页")
        self.page_info_label.setStyleSheet("font-weight: bold; color: #3b82f6; padding: 0 10px;")
        pagination_layout.addWidget(self.page_info_label)

        self.next_page_btn = QPushButton("下一页 ▶")
        self.next_page_btn.setStyleSheet("background-color: #6366f1; color: white; font-weight: bold;")
        self.next_page_btn.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_page_btn)

        pagination_layout.addStretch()
        self.total_count_label = QLabel("总计：0 条")
        self.total_count_label.setStyleSheet("color: #6b7280;")
        pagination_layout.addWidget(self.total_count_label)
        layout.addLayout(pagination_layout)

        # --- 底部操作栏 ---
        bottom = QHBoxLayout()
        self.select_all_btn = QPushButton("☑ 全选当前页")
        self.select_all_btn.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold;")
        self.select_all_btn.clicked.connect(self.select_all_articles)
        bottom.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("☐ 取消全选")
        self.deselect_all_btn.setStyleSheet("background-color: #6b7280; color: white; font-weight: bold;")
        self.deselect_all_btn.clicked.connect(self.clear_selections)
        bottom.addWidget(self.deselect_all_btn)

        self.generate_report_btn = QPushButton("📊 生成报告")
        self.generate_report_btn.setStyleSheet("background-color: #7c3aed; color: white; font-weight: bold;")
        self.generate_report_btn.clicked.connect(self.generate_report)
        bottom.addWidget(self.generate_report_btn)

        bottom.addStretch()
        self.selected_count_label = QLabel("已选择：0")
        self.selected_count_label.setStyleSheet("font-weight: bold; color: #3b82f6;")
        bottom.addWidget(self.selected_count_label)
        layout.addLayout(bottom)

        return widget



    def _create_right_panel(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background-color: white; border-radius: 8px;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("文章详情")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f2937; padding: 5px;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: 1px solid #e5e7eb; border-radius: 8px;")

        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setSpacing(10)

        action_layout = QHBoxLayout()
        self.star_btn = QPushButton("⭐ 标星")
        self.star_btn.setStyleSheet("background-color: #f59e0b; color: white;")
        self.star_btn.clicked.connect(self.toggle_article_star)
        action_layout.addWidget(self.star_btn)

        self.toggle_select_btn = QPushButton("☑️ 选中")
        self.toggle_select_btn.setStyleSheet("background-color: #10b981; color: white;")
        self.toggle_select_btn.clicked.connect(self.toggle_current_article_selection)
        action_layout.addWidget(self.toggle_select_btn)
        action_layout.addStretch()
        detail_layout.addLayout(action_layout)

        self.detail_title = QLabel("请选择一篇文章")
        self.detail_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        self.detail_title.setWordWrap(True)
        detail_layout.addWidget(self.detail_title)

        self.detail_keywords = QLabel("")
        self.detail_keywords.setStyleSheet("color: #6366f1; font-weight: 500; padding: 4px 8px; background-color: #eef2ff; border-radius: 4px;")
        self.detail_keywords.setWordWrap(True)
        detail_layout.addWidget(self.detail_keywords)

        self.detail_source = QLabel("")
        self.detail_source.setStyleSheet("color: #6b7280; font-size: 12px;")
        detail_layout.addWidget(self.detail_source)

        self.detail_link = QLabel("")
        self.detail_link.setOpenExternalLinks(True)
        self.detail_link.setStyleSheet("color: #3b82f6;")
        detail_layout.addWidget(self.detail_link)

        detail_layout.addWidget(QLabel("📝 摘要:"))
        self.detail_summary = QLabel("")
        self.detail_summary.setWordWrap(True)
        self.detail_summary.setStyleSheet("padding: 10px; background: #f9fafb; border-radius: 6px; line-height: 1.5;")
        detail_layout.addWidget(self.detail_summary)

        # 【新增】质量审计展示区
        self.detail_quality_label = QLabel("")
        self.detail_quality_label.setWordWrap(True)
        self.detail_quality_label.setTextFormat(Qt.TextFormat.RichText)
        self.detail_quality_label.setVisible(False)
        self.detail_quality_label.setStyleSheet("padding: 5px;")
        detail_layout.addWidget(self.detail_quality_label)

        detail_layout.addWidget(QLabel("📄 原文:"))
        self.detail_content = QTextEdit()
        self.detail_content.setReadOnly(True)
        self.detail_content.setStyleSheet("background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px;")
        detail_layout.addWidget(self.detail_content)

        detail_layout.addStretch()
        scroll.setWidget(self.detail_widget)
        layout.addWidget(scroll)

        return widget

    def _create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        settings_action = QAction("⚙️ 设置", self)
        settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(settings_action)
        toolbar.addSeparator()
        about_action = QAction("ℹ️ 关于", self)
        about_action.triggered.connect(self.show_about)
        toolbar.addAction(about_action)

    def switch_view(self, view: str):
        self.current_view = view
        self.current_page = 1
        self.nav_all_btn.setStyleSheet("text-align: left;")
        self.nav_starred_btn.setStyleSheet("text-align: left;")
        self.nav_selected_btn.setStyleSheet("text-align: left;")

        if view == "all":
            self.nav_all_btn.setStyleSheet("text-align: left; background-color: #eff6ff; color: #3b82f6;")
        elif view == "starred":
            self.nav_starred_btn.setStyleSheet("text-align: left; background-color: #fffbeb; color: #f59e0b;")
        elif view == "selected":
            self.nav_selected_btn.setStyleSheet("text-align: left; background-color: #ecfdf5; color: #10b981;")

        self.feed_list.clearSelection()
        self.current_feed_id = None
        self.load_articles()

    def load_feeds(self):
        self.feed_list.clear()
        feeds = self.db.get_all_feeds()
        for feed in feeds:
            item = QListWidgetItem(f"📰 {feed['name']}")
            item.setData(Qt.ItemDataRole.UserRole, feed)
            item.setToolTip(f"{feed['url']}\n分类：{feed.get('category', '未分类')}")
            self.feed_list.addItem(item)
        self.statusBar().showMessage(f"已加载 {len(feeds)} 个订阅源")

    def load_articles(self):
        self.article_list.clear()

        # 日期筛选
        has_date_filter = self.enable_date_filter.isChecked()
        start_date = self.start_date_input.date().toString("yyyy-MM-dd") if has_date_filter else None
        end_date = self.end_date_input.date().toString("yyyy-MM-dd") if has_date_filter else None

        # 摘要筛选
        has_summary = None
        if self.has_summary_checkbox.isChecked() and not self.no_summary_checkbox.isChecked():
            has_summary = True
        elif not self.has_summary_checkbox.isChecked() and self.no_summary_checkbox.isChecked():
            has_summary = False

        # 【新增】推荐建议筛选
        quality_recommendation = self.recommend_filter_combo.currentData()
        if not quality_recommendation:
            quality_recommendation = None

        # 排序方式
        sort_by = self.sort_combo.currentData()

        # 搜索关键词
        search_keyword = self.search_keyword_input.text().strip()

        # 视图状态
        selected_only = (self.current_view == "selected")
        starred_only = (self.current_view == "starred")

        # 获取总数 (传递新参数)
        total_count = self.db.get_articles_count(
            feed_id=self.current_feed_id,
            selected_only=selected_only,
            starred_only=starred_only,
            start_date=start_date,
            end_date=end_date,
            has_summary=has_summary,
            search_keyword=search_keyword,
            quality_recommendation=quality_recommendation  # 【新增】
        )

        self.total_pages = max(1, (total_count + self.page_size - 1) // self.page_size)
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages

        # 获取文章列表 (传递新参数)
        articles = self.db.get_articles_paginated(
            feed_id=self.current_feed_id,
            selected_only=selected_only,
            starred_only=starred_only,
            start_date=start_date,
            end_date=end_date,
            has_summary=has_summary,
            search_keyword=search_keyword,
            page=self.current_page,
            page_size=self.page_size,
            sort_by=sort_by,
            quality_recommendation=quality_recommendation  # 【新增】
        )

        self.current_articles = articles
        self.update_pagination_info(total_count)

        for article in articles:
            self._add_article_item(article)

        # 更新状态栏提示
        filter_info = []
        if quality_recommendation:
            filter_info.append(f"推荐:{quality_recommendation}")
        if search_keyword:
            filter_info.append(f"搜索:{search_keyword}")

        status_msg = f"已加载 {len(articles)} / {total_count} 篇"
        if filter_info:
            status_msg += f" ({', '.join(filter_info)})"
        self.statusBar().showMessage(status_msg)


    def update_pagination_info(self, total_count: int):
        self.page_info_label.setText(f"第 {self.current_page} / {self.total_pages} 页")
        self.total_count_label.setText(f"总计：{total_count} 条")
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_articles()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_articles()

    def on_page_size_changed(self, value: int):
        self.page_size = value
        self.current_page = 1
        self.load_articles()

    def _add_article_item(self, article: Dict):
        item_widget = QWidget()
        # 【优化 1】设置大小策略，允许垂直扩展，强制水平受限
        item_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(item_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        title_layout = QHBoxLayout()
        title_layout.setSpacing(8) # 增加内部间距

        is_starred = article.get('is_starred', 0) == 1 # 修复逻辑判断
        star_icon = "⭐" if is_starred else "☆"

        checkbox = QCheckBox()
        checkbox.setChecked(article.get('is_selected', 0) == 1)
        checkbox.stateChanged.connect(lambda state, aid=article['id']: self.on_article_toggled(aid, state))
        # 防止 checkbox 挤压空间
        checkbox.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        title_layout.addWidget(checkbox)

        star_label = QLabel(star_icon)
        star_label.setStyleSheet("font-size: 14px;")
        star_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        title_layout.addWidget(star_label)

        title = QLabel(article.get('title', '无标题'))
        # 【优化 2】核心修复：强制换行和字数限制
        title.setStyleSheet("font-weight: 600; color: #1f2937; font-size: 13px;")
        title.setWordWrap(True)          # 开启自动换行
        title.setMinimumWidth(100)       # 设置最小宽度，防止被压缩成一条线
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred) # 允许水平扩展
        title_layout.addWidget(title)

        # 将标题设为拉伸因子，让它占据剩余空间
        title_layout.setStretchFactor(title, 1)

        layout.addLayout(title_layout)

        # 【新增】解析并显示质量评分徽章
        score = article.get('quality_score', 0) or 0
        rec = article.get('quality_recommendation', '') or ''
        score_badge = ""
        if score > 0:
            color = "#10b981" if score >= 75 else ("#f59e0b" if score >= 60 else "#ef4444")
            badge_text = f"[{score}分]"
            if rec:
                badge_text += f" ({rec})"
            score_badge = f" <span style='color:{color}; font-weight:bold; font-size:10px;'>{badge_text}</span> | "

        keywords = article.get('keywords', '') or ''
        info_text = f"📰 {article.get('feed_name', '未知')} | {article.get('published_at', '')[:10]} {score_badge}"
        if keywords:
            info_text += f"🔑 {keywords}"

        info = QLabel(info_text)
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        info.setWordWrap(True) # 信息栏也允许换行
        layout.addWidget(info)

        summary = article.get('summary', '')
        if summary:
            # 如果包含质量分隔符，只取前半部分作为预览
            preview_text = summary.split('---QUALITY---')[0].strip() if '---QUALITY---' in summary else summary
            # 稍微增加预览长度，因为现在空间更充裕了
            summary_preview = preview_text[:100] + "..." if len(preview_text) > 100 else preview_text
            summary_label = QLabel(f"📝 {summary_preview}")
            summary_label.setStyleSheet("color: #4b5563; font-size: 11px; line-height: 1.4;")
            summary_label.setWordWrap(True)
            layout.addWidget(summary_label)
        else:
            summary_label = QLabel("⏳ 等待生成摘要...")
            summary_label.setStyleSheet("color: #f59e0b; font-size: 11px;")
            layout.addWidget(summary_label)

        item = QListWidgetItem()
        # 【优化 3】关键：根据内容计算正确的高度提示
        # 先让 layout 计算所需大小，然后设置为 item 的 size hint
        item.setSizeHint(item_widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, article)

        self.article_list.addItem(item)
        self.article_list.setItemWidget(item, item_widget)

    def on_feed_clicked(self, item):
        feed = item.data(Qt.ItemDataRole.UserRole)
        if feed:
            self.current_feed_id = feed['id']
            self.current_view = "all"
            self.current_page = 1
            self.nav_all_btn.setStyleSheet("text-align: left; background-color: #eff6ff; color: #3b82f6;")
            self.nav_starred_btn.setStyleSheet("text-align: left;")
            self.nav_selected_btn.setStyleSheet("text-align: left;")
            self.load_articles()

    def on_article_clicked(self, item):
        article = item.data(Qt.ItemDataRole.UserRole)
        if article:
            self.show_article_detail(article)

    def on_article_toggled(self, article_id: int, state):
        is_checked = (state == Qt.CheckState.Checked.value)
        self.db.select_article(article_id, is_checked)
        self.update_selected_count()

    def show_article_detail(self, article: Dict):
        self.current_article = article
        self.detail_title.setText(article.get('title', '无标题'))

        keywords = article.get('keywords', '')
        if keywords:
            self.detail_keywords.setText(f"🔑 {keywords}")
            self.detail_keywords.setVisible(True)
        else:
            self.detail_keywords.setVisible(False)

        is_starred = article.get('is_starred', 0) == 1
        star_status = "⭐ 已标星" if is_starred else "☆ 未标星"
        self.detail_source.setText(f"📰 来源：{article.get('feed_name', '未知')} | {star_status}")

        url = article.get('url', '')
        if url:
            display_url = url[:50] + "..." if len(url) > 50 else url
            self.detail_link.setText(f"🔗 <a href='{url}'>{display_url}</a>")
            self.detail_link.setVisible(True)
        else:
            self.detail_link.setVisible(False)

        # === 核心修改：解析摘要和质量信息 ===
        raw_summary = article.get('summary', '') or ''  # 处理 None 的情况
        summary_text = raw_summary
        quality_info = {}

        if raw_summary and '---QUALITY---' in raw_summary:  # 确保 raw_summary 不为空
            parts = raw_summary.split('---QUALITY---', 1)
            summary_text = parts[0].strip()
            try:
                quality_info = json.loads(parts[1].strip())
            except Exception as e:
                logger.error(f"解析质量 JSON 失败：{e}")

        self.detail_summary.setText(f"📝 {summary_text}")

        # === 渲染质量审计面板 ===
        if quality_info:
            score = quality_info.get('score', 0)
            rec = quality_info.get('recommendation', '')
            honesty = quality_info.get('honesty_level', '')
            category = quality_info.get('category', '其他')

            # 根据评分确定颜色
            color = "#10b981" if score >= 75 else ("#f59e0b" if score >= 60 else "#ef4444")

            audit_html = f"""
            <div style='background:#f3f4f6; padding:12px; border-radius:6px; margin-top:10px; border-left: 5px solid {color};'>
                <div style='font-weight:bold; color:#374151; margin-bottom:8px; font-size:14px;'>
                    📊 AI 质量审计报告
                </div>
                <table style='width:100%; font-size:12px; color:#4b5563; line-height:1.6;'>
                    <tr>
                        <td width='80'><b>综合评分:</b></td>
                        <td style='color:{color}; font-weight:bold; font-size:15px;'>{score} / 100</td>
                    </tr>
                    <tr>
                        <td><b>推荐建议:</b></td>
                        <td>{rec}</td>
                    </tr>
                    <tr>
                        <td><b>标题诚信:</b></td>
                        <td>{honesty}</td>
                    </tr>
                    <tr>
                        <td><b>文章分类:</b></td>
                        <td>{category}</td>
                    </tr>
                </table>
            </div>
            """
            self.detail_quality_label.setText(audit_html)
            self.detail_quality_label.setVisible(True)
        else:
            self.detail_quality_label.setVisible(False)

        content = article.get('content', '')
        self.detail_content.setPlainText(content or "无原始内容")

        if is_starred:
            self.star_btn.setText("⭐ 已标星")
            self.star_btn.setStyleSheet("background-color: #d97706; color: white;")
        else:
            self.star_btn.setText("⭐ 标星")
            self.star_btn.setStyleSheet("background-color: #f59e0b; color: white;")

        is_selected = article.get('is_selected', 0) == 1
        self.toggle_select_btn.setText("☑️ 取消选中" if is_selected else "☑️ 选中")

    def toggle_article_star(self):
        if hasattr(self, 'current_article') and self.current_article:
            self.db.toggle_article_star(self.current_article['id'])
            self.load_articles()
            self._refresh_current_article_detail()

    def toggle_current_article_selection(self):
        if hasattr(self, 'current_article') and self.current_article:
            self.db.toggle_article_selection(self.current_article['id'])
            self.load_articles()
            self.update_selected_count()
            self._refresh_current_article_detail()

    def _refresh_current_article_detail(self):
        article = self.db.get_articles(feed_id=self.current_article['feed_id'])
        for a in article:
            if a['id'] == self.current_article['id']:
                self.current_article = a
                break
        self.show_article_detail(self.current_article)

    def update_selected_count(self):
        selected = self.db.get_selected_articles()
        self.selected_count_label.setText(f"已选择：{len(selected)}")

    def add_feed(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.statusBar().showMessage("正在解析 RSS 源...")
        result = self.fetcher.fetch_feed(url)
        if result:
            name = result['title']
            self.db.add_feed(url, name)
            self.url_input.clear()
            self.load_feeds()
            self.fetch_all_feeds()
            QMessageBox.information(self, "成功", f"已添加订阅源：{name}")
        else:
            QMessageBox.warning(self, "错误", "无法解析 RSS 链接")
        self.statusBar().showMessage("就绪")

    def delete_feed(self):
        current = self.feed_list.currentItem()
        if not current:
            return
        feed = current.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "确认", f"确定要删除订阅源 '{feed['name']}' 吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_feed(feed['id'])
            self.load_feeds()
            self.load_articles()

    def show_batch_import_dialog(self):
        dialog = BatchImportDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            urls = dialog.get_urls()
            if urls:
                self.batch_import(urls)

    def batch_import(self, urls: List[str]):
        self.batch_import_btn.setEnabled(False)
        self.batch_import_btn.setText("导入中...")

        # 【修复】使用更具体的变量名 _import_worker
        self._import_worker = BatchImportThread(self.batch_importer, urls)
        self._import_worker.progress.connect(self.statusBar().showMessage)
        self._import_worker.finished.connect(self.on_batch_import_finished)
        self._import_worker.error.connect(self.on_batch_import_error)
        self._import_worker.start()


    def on_batch_import_finished(self, result: Dict):
        self.batch_import_btn.setEnabled(True)
        self.batch_import_btn.setText("📥 批量导入 RSS")
        added = result.get('added', 0)
        duplicates = result.get('duplicates', 0)
        failed = result.get('failed', 0)
        failed_urls = result.get('failed_urls', [])
        self.load_feeds()
        msg = f"导入完成！\n新增：{added}\n重复：{duplicates}\n失败：{failed}"
        if failed_urls:
            msg += f"\n\n失败的 URL:\n" + "\n".join(failed_urls[:5])
        QMessageBox.information(self, "批量导入结果", msg)

    def on_batch_import_error(self, error: str):
        self.batch_import_btn.setEnabled(True)
        self.batch_import_btn.setText("📥 批量导入 RSS")
        QMessageBox.warning(self, "错误", f"批量导入失败：{error}")

    def fetch_all_feeds(self):
        logger.debug("触发自动/手动抓取任务")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("抓取中...")

        # 【修复】使用更具体的变量名 _fetch_worker
        self._fetch_worker = FetchThread(self.fetcher, self.db)
        self._fetch_worker.progress.connect(self.statusBar().showMessage)
        self._fetch_worker.finished.connect(self.on_fetch_finished)
        self._fetch_worker.error.connect(self.on_fetch_error)
        self._fetch_worker.articles_ready_for_summary.connect(self.auto_summarize_new_articles)
        self._fetch_worker.start()


    def auto_summarize_new_articles(self, articles: List[Dict]):
        if not self.summarizer.api_key and 'localhost' not in getattr(self.summarizer, 'base_url', ''):
            logger.info("未配置 API Key，跳过自动摘要生成")
            return
        logger.info(f"检测到 {len(articles)} 篇新文章，开始自动生成摘要...")
        self.statusBar().showMessage(f"正在为新文章生成摘要 ({len(articles)}篇)...")

        # 【修复】使用更具体的变量名 _summarize_worker
        self._summarize_worker = SummarizeThread(self.summarizer, articles)
        self._summarize_worker.progress.connect(lambda msg, c, t: self.statusBar().showMessage(msg))
        self._summarize_worker.finished.connect(self.on_auto_summarize_finished)
        self._summarize_worker.error.connect(self.on_summarize_error)
        self._summarize_worker.start()


    def on_auto_summarize_finished(self, result: Dict):
        success = result.get('success', 0)
        total = result.get('total', 0)
        logger.info(f"自动摘要完成：成功{success}/{total}")
        self.statusBar().showMessage(f"自动摘要完成：{success}篇成功")
        self.load_articles()

    def on_fetch_finished(self, result: Dict):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 刷新")
        self.load_articles()
        total = result.get('new_articles', 0)
        msg = f"抓取完成，新增 {total} 篇文章"
        self.statusBar().showMessage(msg)
        logger.info(msg)

    def on_fetch_error(self, error: str):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 刷新")
        QMessageBox.warning(self, "错误", f"抓取失败：{error}")

    def generate_summaries(self):
        """生成摘要 - 支持本地 Ollama 和 OpenAI"""

        # 【修改点 1】不再强制检查 config 中的 openai_api_key
        # 而是检查 self.summarizer 是否具备可用配置 (有 Key 或者 是本地地址)
        is_local_mode = 'localhost' in getattr(self.summarizer, 'base_url', '') or '127.0.0.1' in getattr(self.summarizer, 'base_url', '')
        has_api_key = bool(self.summarizer.api_key and self.summarizer.api_key != 'ollama') # 'ollama' 是占位符

        if not is_local_mode and not has_api_key:
            QMessageBox.warning(
                self, "未配置 API",
                "未检测到有效的 API 密钥，且未使用本地 Ollama 模式。\n"
                "请在设置中配置 OpenAI API Key，或确保 fetcher.py 中 Summarizer 指向本地 Ollama。"
            )
            self.show_settings()
            return

        try:
            ui_count_text = self.selected_count_label.text().split(":")[1].strip()
            ui_count = int(ui_count_text)
        except Exception:
            ui_count = 0

        # 获取选中的文章
        all_selected_articles = self.db.get_selected_articles()

        # 数据同步检查
        if len(all_selected_articles) == 0 and ui_count > 0:
            import time
            time.sleep(0.1)
            all_selected_articles = self.db.get_selected_articles()
            if len(all_selected_articles) == 0:
                QMessageBox.warning(self, "数据同步异常", "界面显示已选择但系统无法获取数据。")
                return

        # 过滤掉已经有摘要的文章
        articles_to_process = []
        for article in all_selected_articles:
            summary = article.get('summary')
            # 如果有摘要且包含内容（排除只有分隔符的情况）
            if summary and summary.strip() and '---QUALITY---' not in summary:
                 # 如果已有摘要但没有质量信息，理论上也可以重新生成，这里简单跳过
                 pass

            if not summary or not summary.strip():
                articles_to_process.append(article)
            elif '---QUALITY---' in summary:
                # 如果已有摘要和质量信息，跳过
                continue
            else:
                # 有摘要但可能不完整，视情况决定是否加入，这里暂时跳过以免重复
                continue

        if not articles_to_process:
            QMessageBox.information(self, "提示", "所选文章都已存在摘要，无需重复生成")
            return

        reply = QMessageBox.question(
            self, "确认",
            f"将为 {len(articles_to_process)} 篇已选中的文章生成摘要（跳过已有摘要的文章）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.summarize_btn.setEnabled(False)
        self.summarize_btn.setText("生成中...")

        # 【修改点 2】如果是手动点击，且当前是本地模式但 api_key 是空的，确保传入占位符
        # 虽然 Summarizer 初始化时处理了，但这里显式确保一下
        if is_local_mode and not self.summarizer.api_key:
            self.summarizer.api_key = 'ollama'
        elif not is_local_mode:
            # 如果是云端模式，尝试从 config 获取 key 覆盖
            config_key = self.config.get('openai_api_key')
            if config_key:
                self.summarizer.api_key = config_key

        # 启动线程
        # 【修复】使用 _summarize_worker
        self._summarize_worker = SummarizeThread(self.summarizer, articles_to_process)
        self._summarize_worker.progress.connect(self.statusBar().showMessage)
        self._summarize_worker.finished.connect(self.on_summarize_finished)
        self._summarize_worker.error.connect(self.on_summarize_error)
        self._summarize_worker.start()

    def on_summarize_finished(self, result: Dict):
        self.summarize_btn.setEnabled(True)
        self.summarize_btn.setText("🤖 生成摘要")
        success = result.get('success', 0)
        failed = result.get('failed', 0)
        self.load_articles()
        QMessageBox.information(self, "完成", f"摘要生成完成\n成功：{success}\n失败：{failed}")

    def on_summarize_error(self, error: str):
        # 【关键修改】再次记录错误到日志，确保即使线程内漏掉也能捕获
        logger.error(f"UI 接收到摘要生成错误：{error}")

        # 恢复按钮状态
        self.summarize_btn.setEnabled(True)
        self.summarize_btn.setText("🤖 生成摘要")

        # 【优化】在弹窗中显示更详细的错误信息，建议用户查看日志
        detailed_msg = (
            f"生成摘要失败：\n{error}\n\n"
            f"请检查终端日志或 log 文件以获取完整堆栈跟踪信息。\n"
            f"常见原因：API Key 无效、网络连接超时、本地 Ollama 未启动。"
        )

        QMessageBox.warning(self, "错误", detailed_msg)


    def select_all_articles(self):
        for article in self.current_articles:
            self.db.select_article(article['id'], True)
        self.load_articles()
        self.update_selected_count()

    def clear_selections(self):
        for article in self.current_articles:
            self.db.deselect_article(article['id'])
        self.load_articles()
        self.update_selected_count()

    def apply_filters(self):
        self.current_page = 1
        self.load_articles()

    def clear_filters(self):
        self.enable_date_filter.setChecked(True)
        self.start_date_input.setDate(QDate.currentDate().addMonths(-1))
        self.end_date_input.setDate(QDate.currentDate())

        self.has_summary_checkbox.setChecked(False)
        self.no_summary_checkbox.setChecked(False)

        # 【新增】重置推荐筛选
        self.recommend_filter_combo.setCurrentIndex(0)

        self.search_keyword_input.clear()
        self.current_page = 1
        self.load_articles()


    def generate_report(self):
        if not self.obsidian_writer.check_vault_exists():
            reply = QMessageBox.question(self, "未配置 Obsidian", "未设置 Obsidian Vault 路径，是否现在设置？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.show_settings()
                return
        selected = self.db.get_selected_articles()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择要包含在报告中的文章")
            return

        date_str = datetime.now().strftime('%Y.%m.%d')
        title = f"RSS 日报 {date_str}"
        content = self.obsidian_writer.generate_report(selected, title)
        preview = self.obsidian_writer.get_report_preview(selected)

        reply = QMessageBox.question(self, "报告预览",
                                     f"报告将包含 {len(selected)} 篇文章\n\n{preview[:500]}...\n\n是否保存到 Obsidian？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            result = self.obsidian_writer.save_report(content)
            if result['success']:
                QMessageBox.information(self, "成功", f"报告已保存到:\n{result['file_path']}")
            else:
                QMessageBox.warning(self, "错误", f"保存失败：{result.get('error')}")

    def show_settings(self):
        dialog = SettingsDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            old_interval = self.config.get('fetch_interval_hours', 24)
            self.config = dialog.get_config()
            self._save_config()
            if self.config.get('obsidian_vault_path'):
                self.obsidian_writer.set_vault_path(self.config['obsidian_vault_path'])
            new_interval = self.config.get('fetch_interval_hours', 24)
            if old_interval != new_interval:
                self._start_auto_fetch_scheduler()

    def show_about(self):
        QMessageBox.about(self, "关于",
                          "RSS 订阅管理器 (AI 审计版)\n\n"
                          "功能:\n"
                          "• RSS 订阅源管理\n"
                          "• AI 生成文章摘要与质量评分\n"
                          "• 标题诚信度审计\n"
                          "• 文章标星与筛选\n"
                          "• 一键保存到 Obsidian")


class BatchImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量导入 RSS")
        self.setMinimumSize(600, 400)
        layout = QVBoxLayout(self)
        info = QLabel("请输入 RSS 链接，每行一个。")
        info.setStyleSheet("color: #6b7280; padding: 10px;")
        layout.addWidget(info)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("https://example.com/rss1\nhttps://example.com/rss2")
        layout.addWidget(self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_urls(self) -> List[str]:
        text = self.text_edit.toPlainText()
        return [line.strip() for line in text.split('\n') if line.strip()]


class SettingsDialog(QDialog):
    def __init__(self, parent, config: Dict):
        super().__init__(parent)
        self.config = config.copy()
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        # 【修改】添加 API Base URL 配置项
        layout.addWidget(QLabel("OpenAI API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.config.get('openai_api_key', ''))
        self.api_key_input.setPlaceholderText("sk-...")
        layout.addWidget(self.api_key_input)

        layout.addWidget(QLabel("OpenAI API Base URL:"))
        self.base_url_input = QLineEdit()
        self.base_url_input.setText(self.config.get('openai_base_url', 'http://localhost:11434/v1'))
        self.base_url_input.setPlaceholderText("http://localhost:11434/v1")
        layout.addWidget(self.base_url_input)

        # 【新增】添加 Model Name 配置项
        layout.addWidget(QLabel("OpenAI Model Name:"))
        self.model_name_input = QLineEdit()
        self.model_name_input.setText(self.config.get('openai_model_name', 'qwen3:8b'))
        self.model_name_input.setPlaceholderText("qwen3:8b")
        layout.addWidget(self.model_name_input)

        layout.addWidget(QLabel("Obsidian Vault 路径:"))
        vault_layout = QHBoxLayout()
        self.vault_path_input = QLineEdit()
        self.vault_path_input.setText(self.config.get('obsidian_vault_path', ''))
        vault_layout.addWidget(self.vault_path_input)
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self.browse_vault)
        vault_layout.addWidget(browse_btn)
        layout.addLayout(vault_layout)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("自动抓取间隔 (小时):"))
        self.interval_input = QLineEdit()
        self.interval_input.setText(str(self.config.get('fetch_interval_hours', 24)))
        self.interval_input.setValidator(QIntValidator(0, 1000, self))
        interval_layout.addWidget(self.interval_input)
        layout.addLayout(interval_layout)

        layout.addWidget(QLabel("摘要语言:"))
        self.lang_input = QLineEdit()
        self.lang_input.setText(self.config.get('summary_language', 'zh'))
        layout.addWidget(self.lang_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_vault(self):
        path = QFileDialog.getExistingDirectory(self, "选择 Obsidian Vault 文件夹")
        if path:
            self.vault_path_input.setText(path)

    def get_config(self) -> Dict:
        self.config['openai_api_key'] = self.api_key_input.text().strip()
        self.config['openai_base_url'] = self.base_url_input.text().strip()
        self.config['openai_model_name'] = self.model_name_input.text().strip()
        self.config['obsidian_vault_path'] = self.vault_path_input.text().strip()
        self.config['summary_language'] = self.lang_input.text().strip()
        try:
            self.config['fetch_interval_hours'] = int(self.interval_input.text())
        except ValueError:
            self.config['fetch_interval_hours'] = 24
        return self.config


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont("Microsoft YaHei", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
