#!/usr/bin/env python3
"""
Tavily News Fetcher - Render Cron Job
定时抓取 Claw 相关新闻存入 TiDB
"""

import os
import sys
import json
import requests
import pymysql
from datetime import datetime, timedelta
from pymysql.cursors import DictCursor

# 配置
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')
DB_CONFIG = {
    'host': os.environ.get('TIDB_HOST', 'gateway01.us-west-2.prod.aws.tidbcloud.com'),
    'port': int(os.environ.get('TIDB_PORT', '4000')),
    'user': os.environ.get('TIDB_USER', ''),
    'password': os.environ.get('TIDB_PASSWORD', ''),
    'database': os.environ.get('TIDB_DATABASE', 'test'),
    'charset': 'utf8mb4',
    'cursorclass': DictCursor,
    'autocommit': True,
    'ssl': {'ssl': {}}
}

# 搜索主题（中英文）
SEARCH_TOPICS = [
    "OpenClaw AI agent news",
    "Kimi Claw intelligent assistant",
    "AI agent 智能体 最新动态",
    "Claw AI agent technology",
    "Kimi AI agent 大模型应用",
]

# 核心关键词
CORE_KEYWORDS = ['claw', 'kimiclaw', 'openclaw', 'kimi claw']

def get_db():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)

def search_tavily(query, days_back=1, max_retries=3):
    """调用 Tavily API 搜索，带重试"""
    url = "https://api.tavily.com/search"
    
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": True,
        "max_results": 10,
        "time_range": f"d{days_back}"
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url, json=payload, headers={"Content-Type": "application/json"}, timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("results", [])
            else:
                print(f"  ✗ 搜索失败 (HTTP {response.status_code}): {response.text[:100]}")
                
        except Exception as e:
            print(f"  ✗ 搜索异常 (尝试 {attempt+1}/{max_retries}): {e}")
        
        if attempt < max_retries - 1:
            import time
            time.sleep((attempt + 1) * 2)
    
    return []

def contains_keywords(text):
    """检查是否包含核心关键词"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in CORE_KEYWORDS)

def save_news_to_db(articles):
    """保存新闻到数据库"""
    if not articles:
        return 0
    
    conn = get_db()
    saved = 0
    
    try:
        with conn.cursor() as cursor:
            for article in articles:
                try:
                    cursor.execute('''
                        INSERT INTO agent_news 
                        (title, link, summary, source, published_at, language, raw_content, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                        summary = VALUES(summary),
                        raw_content = VALUES(raw_content),
                        updated_at = NOW()
                    ''', (
                        article['title'][:200],
                        article['link'][:500],
                        article['summary'][:1000],
                        article['source'][:50],
                        article['published_at'],
                        article['language'],
                        article.get('raw_content', '')[:2000]
                    ))
                    saved += 1
                except Exception as e:
                    print(f"  ✗ 保存单条失败: {e}")
        
        conn.commit()
        print(f"✅ 成功保存 {saved} 条新闻")
        return saved
        
    except Exception as e:
        print(f"✗ 数据库错误: {e}")
        return 0
    finally:
        conn.close()

def save_daily_brief(date_str, article_count):
    """生成并保存每日简报"""
    conn = get_db()
    
    try:
        # 获取当天新闻用于生成简报
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT title, summary, source, link 
                FROM agent_news 
                WHERE DATE(published_at) = %s
                ORDER BY published_at DESC
            ''', (date_str,))
            news = cursor.fetchall()
        
        # 生成简单简报
        lines = [f"# 📰 Claw 新闻简报 - {date_str}\n", f"**今日更新**: {len(news)} 条相关新闻\n\n"]
        
        if news:
            lines.append("## 📝 今日要点\n\n")
            for i, n in enumerate(news[:5], 1):
                lines.append(f"{i}. **{n['title']}** - {n['summary'][:80]}...\n")
            
            lines.append("\n## 📄 详细内容\n\n")
            for n in news:
                lines.append(f"### {n['title']}\n")
                lines.append(f"来源: {n['source']}\n\n")
                lines.append(f"{n['summary'][:200]}...\n\n")
                lines.append(f"🔗 [查看原文]({n['link']})\n\n---\n\n")
        else:
            lines.append("*今日暂无相关新闻*\n")
        
        brief_content = ''.join(lines)
        
        # 保存简报
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO daily_brief (brief_date, content, article_count, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                content = VALUES(content),
                article_count = VALUES(article_count),
                updated_at = NOW()
            ''', (date_str, brief_content, len(news)))
        
        conn.commit()
        print(f"✅ 简报已保存: {date_str} ({len(news)} 条)")
        
    except Exception as e:
        print(f"✗ 保存简报失败: {e}")
    finally:
        conn.close()

def main():
    print("=" * 60)
    print("🚀 Tavily News Fetcher - Render Cron Job")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查 API Key
    if not TAVILY_API_KEY:
        print("✗ 错误: 未设置 TAVILY_API_KEY")
        return 1
    
    print(f"✓ API Key 已配置")
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    all_articles = []
    seen_urls = set()
    
    # 搜索所有主题
    print(f"\n🔍 开始搜索 {len(SEARCH_TOPICS)} 个主题...\n")
    
    for i, topic in enumerate(SEARCH_TOPICS, 1):
        print(f"[{i}/{len(SEARCH_TOPICS)}] 搜索: {topic}")
        results = search_tavily(topic)
        
        for result in results:
            url = result.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            title = result.get("title", "")
            content = result.get("content", "") or result.get("raw_content", "")
            
            # 关键词过滤
            if not contains_keywords(f"{title} {content}"):
                continue
            
            all_articles.append({
                'title': title,
                'link': url,
                'summary': content[:500] if content else title,
                'source': result.get("source", "Unknown"),
                'published_at': datetime.now(),
                'language': 'zh' if any('\u4e00' <= c <= '\u9fff' for c in title) else 'en',
                'raw_content': content
            })
        
        import time
        time.sleep(1)  # 避免请求过快
    
    print(f"\n📊 搜索完成: 找到 {len(all_articles)} 条相关新闻\n")
    
    # 保存到数据库
    if all_articles:
        save_news_to_db(all_articles)
    
    # 生成简报
    save_daily_brief(today_str, len(all_articles))
    
    print("\n" + "=" * 60)
    print("✅ 任务完成")
    print("=" * 60)
    return 0

if __name__ == '__main__':
    sys.exit(main())
