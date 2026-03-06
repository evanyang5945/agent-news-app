# AI Agent News Aggregator

基于 **TiDB Cloud Zero** 的中美科技新闻聚合应用，自动抓取热门科技网站中关于 AI Agent 的新闻并生成简报。

## ✨ 功能特性

- 🤖 **智能抓取**: 自动从 TechCrunch, The Verge, 36氪, 虎嗅等中美热门科技媒体抓取 Agent 相关新闻
- 🔍 **智能过滤**: 基于关键词自动识别 Agent 相关内容
- 🗄️ **TiDB Cloud Zero**: 零配置数据库存储，支持向量搜索和全文索引
- 📊 **每日简报**: 自动生成新闻趋势摘要
- 🌐 **Web 展示**: 内置 Web 服务，美观的仪表板展示

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化数据库（一键创建 TiDB Cloud Zero 实例）

```bash
python app.py init
```

这会：
- 调用 TiDB Cloud Zero API 创建数据库
- 自动保存连接配置
- 初始化表结构

### 3. 抓取新闻

```bash
python app.py fetch
```

### 4. 生成简报

```bash
python app.py brief
```

### 5. 启动 Web 服务

```bash
python app.py serve 8080
```

访问 http://localhost:8080 查看结果

### 6. 一键运行全部

```bash
python app.py run 8080
```

## 📡 数据源

### 美国科技媒体 TOP 5
1. **TechCrunch** - 科技创业新闻领军媒体
2. **The Verge** - 综合科技新闻与评测
3. **Wired** - 深度科技报道
4. **Ars Technica** - 技术深度解析
5. **Hacker News** - 技术社区热门话题

### 中国科技媒体 TOP 5
1. **36氪** - 创业与科技资讯平台
2. **虎嗅** - 科技与商业分析
3. **极客公园** - 极客文化与科技产品

## 🛠️ 技术栈

- **Python 3.8+**
- **TiDB Cloud Zero** - Serverless MySQL 数据库
- **PyMySQL** - MySQL 连接库
- **aiohttp** - 异步 HTTP 客户端
- **feedparser** - RSS 解析

## 📁 文件结构

```
agent-news-app/
├── app.py              # 主应用代码
├── requirements.txt    # Python 依赖
├── README.md          # 项目说明
└── db_config.json     # 数据库配置（自动生成）
```

## 🔧 API 端点

- `GET /` - 主页面（新闻列表 + 简报）
- `GET /api/news` - JSON 格式新闻列表
- `GET /api/brief` - JSON 格式每日简报
- `GET /api/stats` - 统计数据

## 📝 License

MIT
