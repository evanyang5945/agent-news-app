#!/usr/bin/env python3
"""
简化版新闻抓取脚本 - 快速填充数据
"""

import os
import sys
import json
import requests
import pymysql
from datetime import datetime, timedelta
from pymysql.cursors import DictCursor

# 配置
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY', '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')

DB_CONFIG = {
    'host': 'gateway01.us-west-2.prod.aws.tidbcloud.com',
    'port': 4000,
    'user': '2UqG4ELucZkHn87.root',
    'password': os.environ.get('TIDB_PASSWORD', 'thryNZvCBjWiNQVV'),
    'database': 'test',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor,
    'autocommit': True,
    'ssl': {'ssl': {}}
}

# 搜索主题
SEARCH_QUERIES = [
    "OpenClaw AI agent",
    "Kimi Claw intelligent assistant",
    "AI agent 智能体 news",
    "Claude AI agent tools",
    "Cursor AI agent development",
]

# 核心关键词
KEYWORDS = ['claw', 'kimiclaw', 'openclaw', 'kimi claw', 'ai agent', '智能体']

def get_db():
    return pymysql.connect(**DB_CONFIG)

def search_tavily(query):
    """调用 Tavily API"""
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
        "time_range": "week"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("results", [])
        else:
            print(f"  ✗ API 错误: HTTP {resp.status_code}")
            return []
    except Exception as e:
        print(f"  ✗ 请求失败: {e}")
        return []

def check_keywords(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)

def save_articles(articles, target_date):
    if not articles:
        return 0
    
    conn = get_db()
    saved = 0
    
    try:
        with conn.cursor() as cursor:
            for art in articles:
                try:
                    cursor.execute('''
                        INSERT INTO agent_news 
                        (title, link, summary, source, published_at, created_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                        summary = VALUES(summary),
                        updated_at = NOW()
                    ''', (
                        art['title'][:200],
                        art['url'][:500],
                        art.get('content', art.get('snippet', ''))[:500],
                        art.get('source', 'Unknown')[:50],
                        target_date
                    ))
                    saved += 1
                except Exception as e:
                    print(f"  保存失败: {e}")
        
        print(f"✅ 保存 {saved} 条新闻")
        return saved
    except Exception as e:
        print(f"✗ 数据库错误: {e}")
        return 0
    finally:
        conn.close()

def main():
    print("=" * 60)
    print("🚀 新闻抓取 - 快速版")
    print("=" * 60)
    
    # 使用今天的日期
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    print(f"日期: {today_str}")
    
    all_articles = []
    
    for query in SEARCH_QUERIES:
        print(f"\n🔍 搜索: {query}")
        results = search_tavily(query)
        print(f"  找到 {len(results)} 条")
        
        for r in results:
            all_articles.append({
                'title': r.get('title', ''),
                'url': r.get('url', ''),
                'content': r.get('content', r.get('snippet', '')),
                'source': r.get('source', 'Web')
            })
    
    print(f"\n📊 总计: {len(all_articles)} 条")
    
    # 保存到数据库
    saved = save_articles(all_articles, today)
    
    # 生成简报
    if saved > 0:
        print(f"\n✅ 完成! 已保存 {saved} 条新闻到数据库")
    else:
        print("\n⚠️ 没有保存任何新闻")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
