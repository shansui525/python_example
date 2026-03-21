---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 3046022100c3672e62d7055c060f0fa28d2b241f49a1819916802b7582598de9f72f9dd2c8022100c03d68b654467de38f017ac7d8bcac8e213e9933ebb236df71a1e4ca4eb81959
    ReservedCode2: 30450220307d6c86a0d327403e120425d181db24c4ef6508a8fb119434d70186470450a2022100f0303a21ad0e2e107636c3fd73145ec785e4d4788fd32a0e4de9a66c38b4a89d
---

# RSS订阅管理器

一个功能强大的RSS订阅管理桌面应用，支持自动获取新闻、AI摘要生成和一键保存到Obsidian。

## 功能特点

- 📰 **RSS订阅管理**：支持导入和管理多个RSS订阅源
- 🔄 **自动获取**：每日自动访问RSS新闻内容
- 🤖 **AI摘要**：使用OpenAI API为每篇文章生成100-200字的中文摘要
- ✅ **文章勾选**：灵活选择感兴趣的文章
- 📊 **报告生成**：从选中的文章生成完整的Markdown报告
- 💾 **Obsidian集成**：一键保存报告到Obsidian Vault

## 安装

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 运行应用：
```bash
python main.py
```

## 配置

首次使用需要配置以下内容：

1. **OpenAI API Key**: 在设置中输入你的OpenAI API Key（用于生成摘要）
2. **Obsidian Vault路径**: 选择你的Obsidian库文件夹

## 使用方法

### 1. 添加订阅源
- 点击左侧面板的"+"按钮或直接输入RSS链接
- 支持添加多个订阅源

### 2. 获取新闻
- 点击"刷新"按钮获取最新文章
- 应用会自动解析RSS并保存文章

### 3. 生成摘要
- 点击"生成摘要"按钮
- AI会为每篇新文章生成100-200字的中文摘要

### 4. 选择文章
- 在文章列表中勾选想要包含在报告中的文章
- 可以使用"全选"或"取消全选"快速操作

### 5. 生成报告
- 点击右侧面板的"生成报告并保存到Obsidian"按钮
- 报告会自动保存到Obsidian的Daily文件夹

## 项目结构

```
rss_manager/
├── main.py              # 主入口
├── gui.py               # GUI界面
├── database.py          # 数据库模块
├── fetcher.py           # RSS获取和摘要生成
├── obsidian_writer.py   # Obsidian集成
├── config.json          # 配置文件
├── requirements.txt     # 依赖列表
└── rss_data.db          # 数据存储（自动创建）
```

## 配置说明

配置文件 `config.json`：

```json
{
    "openai_api_key": "your-api-key",
    "obsidian_vault_path": "/path/to/obsidian/vault",
    "summary_language": "zh",
    "summary_length": {
        "min": 100,
        "max": 200
    },
    "auto_fetch_on_startup": true
}
```

## 依赖

- PyQt6: GUI框架
- feedparser: RSS解析
- requests: HTTP请求
- beautifulsoup4: HTML解析
- openai: AI接口
- sqlalchemy: 数据库

## 注意事项

- 需要有效的OpenAI API Key才能生成摘要
- 确保Obsidian Vault路径正确且有写入权限
- 首次运行会自动创建数据库文件
