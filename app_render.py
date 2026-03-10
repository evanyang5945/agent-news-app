#!/usr/bin/env python3
"""
AI Agent News Aggregator - Render 部署版本
支持历史日期浏览
"""

import os
import json
import re
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)

# 时区修复：强制使用北京时间
def get_beijing_now():
    """获取北京时间"""
    from datetime import timezone
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz).replace(tzinfo=None)

# TiDB Cloud Zero 数据库配置
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'gateway01.us-west-2.prod.aws.tidbcloud.com'),
    'port': int(os.environ.get('DB_PORT', '4000')),
    'user': os.environ.get('DB_USER', ''),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_DATABASE', 'test'),
    'charset': 'utf8mb4',
    'cursorclass': DictCursor,
    'autocommit': True,
    'ssl': {'ssl': {}}
}

def get_db():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)

def simplify_brief(content):
    """简化简报格式"""
    if not content:
        return None
    
    # 只移除 Markdown 标记，保留换行
    text = re.sub(r'#+\s*', '', content)
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'---', '', text)
    
    if "详细内容" in text:
        text = text.split("详细内容")[0]
    
    return text.strip()

def get_available_dates():
    """获取有数据的所有日期"""
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT DISTINCT DATE(published_at) as date 
                FROM agent_news 
                ORDER BY date DESC
            ''')
            dates = [row['date'].strftime('%Y-%m-%d') for row in cursor.fetchall()]
        conn.close()
        return dates
    except:
        return []

@app.route('/')
def index():
    """主页 - 支持日期参数"""
    # 获取日期参数，默认为今天（北京时间）
    date_str = request.args.get('date', get_beijing_now().strftime('%Y-%m-%d'))
    
    try:
        current_date = datetime.strptime(date_str, '%Y-%m-%d')
    except:
        current_date = get_beijing_now()
        date_str = current_date.strftime('%Y-%m-%d')
    
    # 计算上一天和下一天
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    today = get_beijing_now().strftime('%Y-%m-%d')
    
    # 检查是否有下一天的数据
    has_next = next_date <= today
    
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            # 获取指定日期的新闻
            cursor.execute('''
                SELECT * FROM agent_news 
                WHERE DATE(published_at) = %s
                ORDER BY published_at DESC 
                LIMIT 10
            ''', (date_str,))
            news = cursor.fetchall()
            
            # 获取指定日期的简报
            cursor.execute('SELECT * FROM daily_brief WHERE brief_date = %s', (date_str,))
            brief = cursor.fetchone()
            
            # 获取统计
            cursor.execute('''
                SELECT COUNT(*) as total FROM agent_news 
                WHERE DATE(published_at) = %s
            ''', (date_str,))
            total = cursor.fetchone()['total']
            
            cursor.execute('''
                SELECT source, COUNT(*) as cnt 
                FROM agent_news 
                WHERE DATE(published_at) = %s
                GROUP BY source
            ''', (date_str,))
            sources = cursor.fetchall()
            
            # 获取有数据的所有日期
            cursor.execute('''
                SELECT DISTINCT DATE(published_at) as date 
                FROM agent_news 
                ORDER BY date DESC
                LIMIT 30
            ''')
            available_dates = [row['date'].strftime('%Y-%m-%d') for row in cursor.fetchall()]
        conn.close()
        
        # 简化简报内容
        brief_text = simplify_brief(brief['content'] if brief else None)
        
        # 渲染页面
        return render_template_string(HTML_TEMPLATE, 
                                     news=news,
                                     brief=brief_text,
                                     total=total,
                                     sources=sources,
                                     current_date=date_str,
                                     prev_date=prev_date,
                                     next_date=next_date,
                                     has_next=has_next,
                                     today=today,
                                     available_dates=available_dates,
                                     now=get_beijing_now())
    except Exception as e:
        return f"<h1>数据库连接错误</h1><p>{str(e)}</p>", 500

@app.route('/api/news')
def api_news():
    """API: 获取新闻列表"""
    date_str = request.args.get('date', get_beijing_now().strftime('%Y-%m-%d'))
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM agent_news 
                WHERE DATE(published_at) = %s
                ORDER BY published_at DESC
            ''', (date_str,))
            news = cursor.fetchall()
        conn.close()
        return jsonify({'data': news, 'date': date_str})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/brief')
def api_brief():
    """API: 获取简报"""
    date_str = request.args.get('date', get_beijing_now().strftime('%Y-%m-%d'))
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM daily_brief WHERE brief_date = %s', (date_str,))
            brief = cursor.fetchone()
        conn.close()
        return jsonify({'data': brief, 'date': date_str})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dates')
def api_dates():
    """API: 获取有数据的所有日期"""
    try:
        dates = get_available_dates()
        return jsonify({'dates': dates})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'timestamp': get_beijing_now().isoformat()})

# HTML 模板 - 支持日期导航
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AI Agent News</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html { font-size: 16px; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0d1b2a;
            color: #fff;
            min-height: 100vh;
            line-height: 1.6;
            word-wrap: break-word;
            overflow-wrap: break-word;
            -webkit-text-size-adjust: 100%;
        }
        .container { 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 1rem; 
        }
        header { 
            text-align: center; 
            margin-bottom: 1rem; 
            padding: 1rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        h1 {
            font-size: 1.5rem;
            font-weight: 700;
            color: #00b4d8;
            margin-bottom: 0.3rem;
        }
        .subtitle { 
            color: #888; 
            font-size: 0.85rem; 
        }
        
        /* 日期导航 */
        .date-nav {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.5rem;
            margin: 1rem 0;
            flex-wrap: wrap;
        }
        .date-nav a {
            color: #00b4d8;
            text-decoration: none;
            padding: 0.4rem 0.8rem;
            border: 1px solid rgba(0,180,216,0.3);
            border-radius: 6px;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        .date-nav a:hover {
            background: rgba(0,180,216,0.1);
        }
        .date-nav a.disabled {
            color: #444;
            border-color: #333;
            pointer-events: none;
        }
        .current-date {
            font-size: 1.1rem;
            font-weight: 600;
            color: #fff;
            padding: 0.3rem 0.8rem;
            background: rgba(0,180,216,0.2);
            border-radius: 6px;
            min-width: 100px;
            text-align: center;
        }
        .date-picker {
            margin-top: 0.5rem;
            padding: 0.4rem;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 6px;
            color: #fff;
            font-size: 0.9rem;
        }
        .date-picker option {
            background: #1b263b;
        }
        
        .stats {
            display: flex;
            justify-content: center;
            gap: 1.5rem;
            margin: 1rem 0;
            font-size: 0.8rem;
            color: #666;
        }
        .stat span { color: #00b4d8; font-weight: 600; }
        
        /* 简报部分 */
        .brief-card {
            background: rgba(0,180,216,0.1);
            border: 1px solid rgba(0,180,216,0.2);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1.5rem;
        }
        .brief-card h2 {
            font-size: 1rem;
            color: #00b4d8;
            margin-bottom: 0.5rem;
        }
        .brief-content {
            font-size: 0.9rem;
            color: #ccc;
            line-height: 1.7;
            white-space: pre-line;
        }
        .no-content {
            color: #666;
            font-style: italic;
            padding: 1rem 0;
        }
        
        /* 新闻列表 */
        .news-card {
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 1rem;
        }
        .news-card h2 {
            font-size: 1rem;
            color: #00b4d8;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .news-item {
            padding: 0.8rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .news-item:last-child { border-bottom: none; }
        .news-title {
            font-size: 0.95rem;
            font-weight: 500;
            margin-bottom: 0.3rem;
            line-height: 1.5;
        }
        .news-title a {
            color: #fff;
            text-decoration: none;
        }
        .news-title a:hover { color: #00b4d8; }
        .news-meta {
            font-size: 0.75rem;
            color: #666;
        }
        .news-meta .source {
            color: #00b4d8;
            margin-right: 0.5rem;
        }
        
        .empty {
            text-align: center;
            padding: 2rem;
            color: #555;
        }
        .footer {
            text-align: center;
            margin-top: 2rem;
            padding: 1rem;
            font-size: 0.75rem;
            color: #444;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 AI Agent News</h1>
            <p class="subtitle">每日 AI Agent 新闻聚合</p>
            
            <!-- 日期导航 -->
            <div class="date-nav">
                <a href="/?date={{ prev_date }}">◀ 上一天</a>
                <span class="current-date">{{ current_date }}</span>
                {% if has_next %}
                <a href="/?date={{ next_date }}">下一天 ▶</a>
                {% else %}
                <a class="disabled">下一天 ▶</a>
                {% endif %}
            </div>
            
            <!-- 日期选择器 -->
            <select class="date-picker" onchange="window.location.href='/?date=' + this.value">
                <option value="">选择日期...</option>
                {% for d in available_dates %}
                <option value="{{ d }}" {% if d == current_date %}selected{% endif %}>{{ d }}</option>
                {% endfor %}
            </select>
            
            <div class="stats">
                <div class="stat"><span>{{ total }}</span> 条新闻</div>
                <div class="stat"><span>{{ sources|length }}</span> 个来源</div>
            </div>
        </header>
        
        <!-- 简报 -->
        <div class="brief-card">
            <h2>📋 简报</h2>
            {% if brief %}
            <div class="brief-content">{{ brief }}</div>
            {% else %}
            <div class="no-content">{{ current_date }} 暂无简报内容</div>
            {% endif %}
        </div>
        
        <!-- 新闻列表 -->
        <div class="news-card">
            <h2>📰 新闻列表</h2>
            {% if news %}
                {% for item in news %}
                <div class="news-item">
                    <div class="news-title">
                        <a href="{{ item.link }}" target="_blank">{{ item.title }}</a>
                    </div>
                    <div class="news-meta">
                        <span class="source">{{ item.source }}</span>
                        <span>{{ item.published_at.strftime('%m-%d %H:%M') if item.published_at else '' }}</span>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty">{{ current_date }} 没有抓到新闻内容</div>
            {% endif %}
        </div>
        
        <div class="footer">
            {% if current_date == today %}今天{% else %}{{ current_date }}{% endif %}更新
        </div>
    </div>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
