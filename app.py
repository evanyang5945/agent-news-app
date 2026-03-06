#!/usr/bin/env python3
"""
AI Agent News Aggregator
基于 TiDB Cloud Zero 的中美科技新闻聚合应用
"""

import os
import json
import asyncio
import aiohttp
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pymysql
from pymysql.cursors import DictCursor

# ============ 配置 ============
# 热门科技网站 RSS 源配置
NEWS_SOURCES = {
    # 美国科技媒体
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Wired": "https://www.wired.com/feed/rss",
    "Ars Technica": "http://feeds.arstechnica.com/arstechnica/index",
    "Hacker News": "https://news.ycombinator.com/rss",
    
    # 中国科技媒体 (使用搜索或聚合服务)
    "36氪": "https://36kr.com/feed",
    "虎嗅": "https://www.huxiu.com/rss",
    "极客公园": "https://www.geekpark.net/rss",
}

# AI Agent 相关关键词
AGENT_KEYWORDS = [
    "agent", "ai agent", "智能体", "multi-agent", "autonomous agent",
    "gpt agent", "claude agent", "operator", "manus", "cursor",
    "ai assistant", "digital worker", "虚拟员工", "mcp", "a2a"
]

# ============ TiDB Cloud Zero 数据库操作 ============

class TiDBZeroDB:
    """TiDB Cloud Zero 数据库管理"""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str = "test"):
        self.config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "autocommit": True
        }
        self.conn = None
    
    def connect(self):
        """连接数据库"""
        self.conn = pymysql.connect(**self.config)
        return self
    
    def init_schema(self):
        """初始化表结构"""
        with self.conn.cursor() as cursor:
            # 创建新闻表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_news (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    link VARCHAR(1000) NOT NULL,
                    source VARCHAR(100) NOT NULL,
                    published_at DATETIME,
                    summary TEXT,
                    keywords VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FULLTEXT INDEX idx_title_summary (title, summary),
                    INDEX idx_source (source),
                    INDEX idx_published (published_at)
                )
            """)
            
            # 创建简报表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_brief (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    brief_date DATE NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    news_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        self.conn.commit()
        print("✅ 数据库表结构初始化完成")
    
    def save_news(self, news_item: Dict) -> bool:
        """保存单条新闻"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO agent_news (title, link, source, published_at, summary, keywords)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        summary = VALUES(summary),
                        keywords = VALUES(keywords)
                """, (
                    news_item["title"],
                    news_item["link"],
                    news_item["source"],
                    news_item.get("published_at"),
                    news_item.get("summary", ""),
                    news_item.get("keywords", "")
                ))
            return True
        except Exception as e:
            print(f"❌ 保存新闻失败: {e}")
            return False
    
    def get_top_news(self, limit: int = 10) -> List[Dict]:
        """获取热门新闻"""
        with self.conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM agent_news 
                ORDER BY published_at DESC 
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
    
    def get_news_by_source(self, source: str, limit: int = 5) -> List[Dict]:
        """按来源获取新闻"""
        with self.conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM agent_news 
                WHERE source = %s
                ORDER BY published_at DESC 
                LIMIT %s
            """, (source, limit))
            return cursor.fetchall()
    
    def search_news(self, keyword: str, limit: int = 10) -> List[Dict]:
        """全文搜索新闻"""
        with self.conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM agent_news 
                WHERE MATCH(title, summary) AGAINST(%s IN NATURAL LANGUAGE MODE)
                ORDER BY published_at DESC
                LIMIT %s
            """, (keyword, limit))
            return cursor.fetchall()
    
    def save_brief(self, brief_date: datetime, content: str, news_count: int):
        """保存每日简报"""
        with self.conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO daily_brief (brief_date, content, news_count)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    content = VALUES(content),
                    news_count = VALUES(news_count)
            """, (brief_date.date(), content, news_count))
    
    def get_brief(self, brief_date: datetime) -> Optional[Dict]:
        """获取指定日期的简报"""
        with self.conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM daily_brief WHERE brief_date = %s
            """, (brief_date.date(),))
            return cursor.fetchone()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM agent_news")
            total = cursor.fetchone()["total"]
            
            cursor.execute("SELECT source, COUNT(*) as cnt FROM agent_news GROUP BY source")
            by_source = cursor.fetchall()
            
            cursor.execute("SELECT DISTINCT DATE(published_at) as date FROM agent_news ORDER BY date DESC LIMIT 7")
            dates = cursor.fetchall()
            
        return {
            "total_news": total,
            "by_source": by_source,
            "recent_dates": [d["date"] for d in dates]
        }


# ============ 新闻抓取 ============

class NewsAggregator:
    """新闻聚合器"""
    
    def __init__(self, db: TiDBZeroDB):
        self.db = db
    
    def is_agent_related(self, title: str, summary: str = "") -> tuple:
        """判断是否是 Agent 相关新闻"""
        text = f"{title} {summary}".lower()
        matched_keywords = []
        for kw in AGENT_KEYWORDS:
            if kw.lower() in text:
                matched_keywords.append(kw)
        return len(matched_keywords) > 0, matched_keywords
    
    async def fetch_rss(self, session: aiohttp.ClientSession, source_name: str, url: str) -> List[Dict]:
        """抓取 RSS 源"""
        news_items = []
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    feed = feedparser.parse(content)
                    
                    for entry in feed.entries[:10]:  # 每个源取前10条
                        title = entry.get("title", "")
                        summary = entry.get("summary", "")[:500]
                        
                        is_related, keywords = self.is_agent_related(title, summary)
                        if is_related:
                            # 解析发布时间
                            published = entry.get("published_parsed") or entry.get("updated_parsed")
                            if published:
                                published_dt = datetime(*published[:6])
                            else:
                                published_dt = datetime.now()
                            
                            # 只保留最近7天的新闻
                            if datetime.now() - published_dt < timedelta(days=7):
                                news_items.append({
                                    "title": title,
                                    "link": entry.get("link", ""),
                                    "source": source_name,
                                    "published_at": published_dt,
                                    "summary": summary,
                                    "keywords": ", ".join(keywords)
                                })
        except Exception as e:
            print(f"⚠️ 抓取 {source_name} 失败: {e}")
        
        return news_items
    
    async def fetch_all(self) -> List[Dict]:
        """抓取所有新闻源"""
        all_news = []
        async with aiohttp.ClientSession() as session:
            tasks = []
            for source, url in NEWS_SOURCES.items():
                tasks.append(self.fetch_rss(session, source, url))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
        
        # 去重并按时间排序
        seen_links = set()
        unique_news = []
        for news in sorted(all_news, key=lambda x: x["published_at"], reverse=True):
            if news["link"] not in seen_links:
                seen_links.add(news["link"])
                unique_news.append(news)
        
        return unique_news[:20]  # 返回前20条
    
    def save_to_db(self, news_list: List[Dict]):
        """保存新闻到数据库"""
        saved_count = 0
        for news in news_list:
            if self.db.save_news(news):
                saved_count += 1
        print(f"✅ 成功保存 {saved_count} 条新闻")


# ============ 简报生成 ============

class BriefGenerator:
    """简报生成器"""
    
    def __init__(self, db: TiDBZeroDB):
        self.db = db
    
    def generate_brief(self, news_list: List[Dict]) -> str:
        """生成新闻简报"""
        if not news_list:
            return "暂无相关新闻"
        
        # 按来源分组
        by_source = {}
        for news in news_list:
            source = news["source"]
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(news)
        
        # 生成简报内容
        lines = [
            f"# 🤖 AI Agent 每日简报",
            f"📅 {datetime.now().strftime('%Y年%m月%d日')}",
            f"📊 共收录 {len(news_list)} 条热门新闻\n",
            "---\n"
        ]
        
        # 热门话题关键词统计
        all_keywords = []
        for news in news_list:
            all_keywords.extend(news.get("keywords", "").split(", "))
        
        keyword_counts = {}
        for kw in all_keywords:
            if kw:
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        
        if keyword_counts:
            top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append("## 🔥 热门关键词")
            lines.append(", ".join([f"**{kw}** ({cnt})" for kw, cnt in top_keywords]))
            lines.append("")
        
        # 各来源新闻
        lines.append("## 📰 精选新闻\n")
        
        for source, items in by_source.items():
            lines.append(f"### {source}")
            for item in items[:3]:  # 每个来源最多3条
                lines.append(f"- [{item['title']}]({item['link']})")
            lines.append("")
        
        # 趋势摘要
        lines.append("---\n")
        lines.append("## 💡 趋势摘要\n")
        
        if len(news_list) >= 5:
            lines.append("今日 AI Agent 领域动态活跃，主要关注：")
            lines.append("")
            
            # 美国科技媒体动态
            us_sources = ["TechCrunch", "The Verge", "Wired", "Ars Technica", "Hacker News"]
            us_news = [n for n in news_list if n["source"] in us_sources]
            if us_news:
                lines.append(f"1. **国际市场**：来自 {len(us_news)} 家海外科技媒体的报道显示，")
                companies = self._extract_companies(us_news)
                if companies:
                    lines.append(f"   {', '.join(companies[:3])} 等公司在 Agent 领域有新动作")
                lines.append("")
            
            # 中国科技媒体动态
            cn_sources = ["36氪", "虎嗅", "极客公园"]
            cn_news = [n for n in news_list if n["source"] in cn_sources]
            if cn_news:
                lines.append(f"2. **国内市场**：{len(cn_news)} 条来自国内科技媒体的报道，")
                lines.append("   关注国产 Agent 产品和行业应用进展")
                lines.append("")
            
            lines.append("3. **技术趋势**：Agent 与生产力工具结合、Multi-Agent 协作、")
            lines.append("   模型即 Agent（Model as Agent）成为主要讨论方向")
        else:
            lines.append("今日新闻数量较少，建议持续关注后续动态。")
        
        return "\n".join(lines)
    
    def _extract_companies(self, news_list: List[Dict]) -> List[str]:
        """从新闻标题中提取公司名称（简单规则）"""
        companies = []
        company_keywords = ["OpenAI", "Anthropic", "Google", "Microsoft", "Meta", 
                           "Amazon", "Claude", "ChatGPT", "Gemini", "Cursor",
                           "DeepSeek", "Kimi", "阿里", "腾讯", "字节"]
        for news in news_list:
            title = news["title"]
            for company in company_keywords:
                if company in title and company not in companies:
                    companies.append(company)
        return companies


# ============ Web 展示服务 ============

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

class NewsHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""
    
    db_config = None
    
    def log_message(self, format, *args):
        pass  # 禁用默认日志
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == "/":
            self.show_dashboard()
        elif path == "/api/news":
            self.api_news()
        elif path == "/api/brief":
            self.api_brief()
        elif path == "/api/stats":
            self.api_stats()
        else:
            self.send_error(404)
    
    def show_dashboard(self):
        """展示主页面"""
        db = TiDBZeroDB(**self.db_config).connect()
        news = db.get_top_news(10)
        brief = db.get_brief(datetime.now())
        
        html = self._render_html(news, brief)
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
    
    def api_news(self):
        """API: 获取新闻列表"""
        db = TiDBZeroDB(**self.db_config).connect()
        news = db.get_top_news(20)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({
            "data": [{"title": n["title"], "link": n["link"], 
                     "source": n["source"], "published": str(n["published_at"])} 
                    for n in news]
        }, ensure_ascii=False).encode("utf-8"))
    
    def api_brief(self):
        """API: 获取简报"""
        db = TiDBZeroDB(**self.db_config).connect()
        brief = db.get_brief(datetime.now())
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({
            "data": brief["content"] if brief else "暂无简报"
        }, ensure_ascii=False).encode("utf-8"))
    
    def api_stats(self):
        """API: 获取统计信息"""
        db = TiDBZeroDB(**self.db_config).connect()
        stats = db.get_stats()
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(stats, ensure_ascii=False, default=str).encode("utf-8"))
    
    def _render_html(self, news: List[Dict], brief: Optional[Dict]) -> str:
        """渲染 HTML 页面"""
        news_items_html = ""
        for item in news:
            news_items_html += f"""
            <div class="news-item">
                <h3><a href="{item['link']}" target="_blank">{item['title']}</a></h3>
                <div class="meta">
                    <span class="source">{item['source']}</span>
                    <span class="date">{item['published_at']}</span>
                </div>
                <p class="summary">{item.get('summary', '')[:200]}...</p>
                <div class="keywords">{item.get('keywords', '')}</div>
            </div>
            """
        
        brief_content = brief["content"].replace("\n", "<br>") if brief else "暂无简报，请先运行数据抓取"
        
        return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 AI Agent News Aggregator</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        h1 {{
            font-size: 2.5rem;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #888;
            font-size: 1.1rem;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }}
        @media (max-width: 768px) {{
            .grid {{ grid-template-columns: 1fr; }}
        }}
        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .card h2 {{
            font-size: 1.3rem;
            margin-bottom: 20px;
            color: #00d4ff;
        }}
        .news-item {{
            padding: 16px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .news-item:last-child {{ border-bottom: none; }}
        .news-item h3 {{
            font-size: 1rem;
            margin-bottom: 8px;
        }}
        .news-item h3 a {{
            color: #fff;
            text-decoration: none;
        }}
        .news-item h3 a:hover {{
            color: #00d4ff;
        }}
        .meta {{
            display: flex;
            gap: 15px;
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 8px;
        }}
        .source {{
            background: rgba(0,212,255,0.2);
            padding: 2px 10px;
            border-radius: 12px;
            color: #00d4ff;
        }}
        .summary {{
            font-size: 0.9rem;
            color: #aaa;
            line-height: 1.5;
        }}
        .keywords {{
            font-size: 0.8rem;
            color: #7b2cbf;
            margin-top: 8px;
        }}
        .brief {{
            line-height: 1.8;
            color: #ccc;
        }}
        .brief h1 {{ font-size: 1.5rem; margin-bottom: 10px; }}
        .brief h2 {{ font-size: 1.2rem; margin: 15px 0 10px; color: #00d4ff; }}
        .brief h3 {{ font-size: 1rem; margin: 10px 0; color: #aaa; }}
        .brief ul {{ margin-left: 20px; }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: #666;
            font-size: 0.9rem;
        }}
        .refresh-btn {{
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            color: #fff;
            cursor: pointer;
            font-size: 1rem;
            margin-top: 20px;
        }}
        .refresh-btn:hover {{
            opacity: 0.9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 AI Agent News Aggregator</h1>
            <p class="subtitle">中美热门科技网站 Agent 新闻聚合 | Powered by TiDB Cloud Zero</p>
        </header>
        
        <div class="grid">
            <div class="card">
                <h2>📰 热门新闻 TOP 10</h2>
                {news_items_html}
            </div>
            
            <div class="card">
                <h2>📊 每日简报</h2>
                <div class="brief">{brief_content}</div>
            </div>
        </div>
        
        <div class="footer">
            <p>数据来源: TechCrunch, The Verge, 36氪, 虎嗅, 极客公园 等</p>
            <p>数据库: TiDB Cloud Zero | 向量搜索 + 全文索引</p>
        </div>
    </div>
</body>
</html>
        """


# ============ 主程序 ============

def provision_database() -> Dict:
    """使用 TiDB Cloud Zero API 创建数据库"""
    import urllib.request
    import ssl
    
    req = urllib.request.Request(
        "https://zero.tidbapi.com/v1alpha1/instances",
        data=json.dumps({"tag": "agent-news-aggregator"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    # 禁用 SSL 验证（用于测试环境）
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result["instance"]["connection"]
    except Exception as e:
        print(f"创建数据库失败: {e}")
        return None


def main():
    """主入口"""
    import sys
    
    if len(sys.argv) < 2:
        print("""
🤖 AI Agent News Aggregator - 使用方法

1. 首次运行 - 创建数据库并初始化:
   python app.py init

2. 抓取新闻数据:
   python app.py fetch

3. 生成简报:
   python app.py brief

4. 启动 Web 服务:
   python app.py serve [port]

5. 一键运行全部:
   python app.py run
        """)
        return
    
    command = sys.argv[1]
    
    if command == "init":
        print("🚀 正在使用 TiDB Cloud Zero 创建数据库...")
        conn_info = provision_database()
        if conn_info:
            print(f"✅ 数据库创建成功!")
            print(f"   Host: {conn_info['host']}")
            print(f"   Port: {conn_info['port']}")
            print(f"   User: {conn_info['username']}")
            print(f"   Password: {conn_info['password']}")
            
            # 保存配置
            config = {
                "host": conn_info["host"],
                "port": conn_info["port"],
                "user": conn_info["username"],
                "password": conn_info["password"],
                "database": "test"
            }
            with open("db_config.json", "w") as f:
                json.dump(config, f)
            
            # 初始化表结构
            db = TiDBZeroDB(**config).connect()
            db.init_schema()
            print("\n💾 配置已保存到 db_config.json")
        
    elif command in ["fetch", "crawl"]:
        with open("db_config.json", "r") as f:
            config = json.load(f)
        
        print("📡 正在抓取新闻...")
        db = TiDBZeroDB(**config).connect()
        aggregator = NewsAggregator(db)
        
        news = asyncio.run(aggregator.fetch_all())
        aggregator.save_to_db(news)
        print(f"✅ 共抓取 {len(news)} 条 Agent 相关新闻")
        
    elif command == "brief":
        with open("db_config.json", "r") as f:
            config = json.load(f)
        
        print("📝 正在生成简报...")
        db = TiDBZeroDB(**config).connect()
        
        # 获取最近新闻
        news = db.get_top_news(10)
        
        # 生成简报
        generator = BriefGenerator(db)
        brief_content = generator.generate_brief(news)
        
        # 保存简报
        db.save_brief(datetime.now(), brief_content, len(news))
        
        print("\n" + "="*60)
        print(brief_content)
        print("="*60)
        
    elif command == "serve":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
        
        with open("db_config.json", "r") as f:
            config = json.load(f)
        
        NewsHandler.db_config = config
        
        server = HTTPServer(("", port), NewsHandler)
        print(f"🌐 服务已启动: http://localhost:{port}")
        print("按 Ctrl+C 停止服务")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 服务已停止")
    
    elif command == "run":
        # 一键运行
        print("🚀 启动 AI Agent News Aggregator...")
        
        # 检查配置
        if not os.path.exists("db_config.json"):
            print("首先创建数据库...")
            conn_info = provision_database()
            if conn_info:
                config = {
                    "host": conn_info["host"],
                    "port": conn_info["port"],
                    "user": conn_info["username"],
                    "password": conn_info["password"],
                    "database": "test"
                }
                with open("db_config.json", "w") as f:
                    json.dump(config, f)
                db = TiDBZeroDB(**config).connect()
                db.init_schema()
        
        with open("db_config.json", "r") as f:
            config = json.load(f)
        
        db = TiDBZeroDB(**config).connect()
        
        # 抓取新闻
        print("📡 抓取新闻中...")
        aggregator = NewsAggregator(db)
        news = asyncio.run(aggregator.fetch_all())
        aggregator.save_to_db(news)
        
        # 生成简报
        print("📝 生成简报...")
        generator = BriefGenerator(db)
        brief_content = generator.generate_brief(news)
        db.save_brief(datetime.now(), brief_content, len(news))
        
        # 启动服务
        print("🌐 启动 Web 服务...")
        NewsHandler.db_config = config
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
        server = HTTPServer(("", port), NewsHandler)
        print(f"\n✅ 全部完成! 访问 http://localhost:{port} 查看结果")
        server.serve_forever()


if __name__ == "__main__":
    main()
