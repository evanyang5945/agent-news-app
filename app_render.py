#!/usr/bin/env python3
"""
AI Agent News Aggregator - Render 部署版本
基于 TiDB Cloud Zero 的中美科技新闻聚合应用
"""

import os
import json
from datetime import datetime
from flask import Flask, render_template_string, jsonify
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)

# TiDB Cloud Zero 数据库配置（从环境变量读取）
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

@app.route('/')
def index():
    """主页 - 展示新闻列表和简报"""
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            # 获取最新10条新闻
            cursor.execute('SELECT * FROM agent_news ORDER BY published_at DESC LIMIT 10')
            news = cursor.fetchall()
            
            # 获取今日简报
            cursor.execute('SELECT * FROM daily_brief WHERE brief_date = CURDATE()')
            brief = cursor.fetchone()
            
            # 获取统计
            cursor.execute('SELECT COUNT(*) as total FROM agent_news')
            total = cursor.fetchone()['total']
            
            cursor.execute('SELECT source, COUNT(*) as cnt FROM agent_news GROUP BY source')
            sources = cursor.fetchall()
        conn.close()
        
        # 渲染页面
        return render_template_string(HTML_TEMPLATE, 
                                     news=news, 
                                     brief=brief,
                                     total=total,
                                     sources=sources,
                                     now=datetime.now())
    except Exception as e:
        return f"<h1>数据库连接错误</h1><p>{str(e)}</p><p>请检查环境变量配置</p>", 500

@app.route('/api/news')
def api_news():
    """API: 获取新闻列表"""
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM agent_news ORDER BY published_at DESC LIMIT 20')
            news = cursor.fetchall()
        conn.close()
        return jsonify({'data': news})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/brief')
def api_brief():
    """API: 获取简报"""
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM daily_brief WHERE brief_date = CURDATE()')
            brief = cursor.fetchone()
        conn.close()
        return jsonify({'data': brief})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def api_stats():
    """API: 获取统计"""
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as total FROM agent_news')
            total = cursor.fetchone()['total']
            
            cursor.execute('SELECT source, COUNT(*) as cnt FROM agent_news GROUP BY source')
            by_source = cursor.fetchall()
        conn.close()
        return jsonify({'total': total, 'by_source': by_source})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

# HTML 模板
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 AI Agent News Aggregator</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #0d1b2a 0%, #1b263b 100%);
            color: #fff;
            min-height: 100vh;
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        header { text-align: center; margin-bottom: 50px; }
        h1 {
            font-size: 3rem;
            font-weight: 800;
            background: linear-gradient(90deg, #00b4d8, #0077b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 15px;
            letter-spacing: -1px;
        }
        .subtitle { color: #a0a0a0; font-size: 1.2rem; font-weight: 300; }
        .badge {
            display: inline-block;
            background: rgba(0, 180, 216, 0.15);
            color: #00b4d8;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin-top: 15px;
            border: 1px solid rgba(0, 180, 216, 0.3);
        }
        .stats-bar {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        .stat-item {
            text-align: center;
            padding: 15px 30px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #00b4d8;
        }
        .stat-label { font-size: 0.9rem; color: #888; margin-top: 5px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
        .card {
            background: rgba(255,255,255,0.03);
            border-radius: 20px;
            padding: 30px;
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .card h2 {
            font-size: 1.4rem;
            margin-bottom: 25px;
            color: #00b4d8;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .news-item {
            padding: 20px 0;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            transition: all 0.3s ease;
        }
        .news-item:hover {
            background: rgba(255,255,255,0.02);
            margin: 0 -15px;
            padding: 20px 15px;
            border-radius: 10px;
        }
        .news-item:last-child { border-bottom: none; }
        .news-item h3 {
            font-size: 1.05rem;
            font-weight: 500;
            margin-bottom: 10px;
            line-height: 1.5;
        }
        .news-item h3 a {
            color: #fff;
            text-decoration: none;
            transition: color 0.2s;
        }
        .news-item h3 a:hover { color: #00b4d8; }
        .meta {
            display: flex;
            gap: 12px;
            font-size: 0.8rem;
            color: #888;
            margin-bottom: 10px;
            flex-wrap: wrap;
            align-items: center;
        }
        .source {
            background: linear-gradient(135deg, rgba(0,180,216,0.2), rgba(0,119,182,0.2));
            padding: 3px 12px;
            border-radius: 15px;
            color: #00b4d8;
            font-weight: 500;
        }
        .date { color: #666; }
        .summary {
            font-size: 0.9rem;
            color: #aaa;
            line-height: 1.6;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .keywords {
            font-size: 0.75rem;
            color: #0077b6;
            margin-top: 10px;
            font-weight: 500;
        }
        .brief-section {
            background: rgba(0,0,0,0.2);
            border-radius: 15px;
            padding: 25px;
            line-height: 1.9;
        }
        .brief-section h1 {
            font-size: 1.6rem;
            margin-bottom: 15px;
            -webkit-text-fill-color: #fff;
            background: none;
        }
        .brief-section h2 {
            font-size: 1.2rem;
            margin: 25px 0 15px;
            color: #00b4d8;
        }
        .brief-section h3 {
            font-size: 1.05rem;
            margin: 20px 0 10px;
            color: #ccc;
        }
        .brief-section ul, .brief-section ol {
            margin: 15px 0 15px 25px;
        }
        .brief-section li { margin: 8px 0; color: #bbb; }
        .brief-section strong { color: #00b4d8; }
        .brief-section p { margin: 12px 0; color: #bbb; }
        .footer {
            text-align: center;
            margin-top: 60px;
            padding: 30px;
            color: #555;
            font-size: 0.9rem;
            border-top: 1px solid rgba(255,255,255,0.05);
        }
        .footer p { margin: 8px 0; }
        .highlight { color: #00b4d8; }
        .pulse {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #00ff88;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; box-shadow: 0 0 0 0 rgba(0,255,136,0.4); }
            70% { opacity: 0.8; box-shadow: 0 0 0 8px rgba(0,255,136,0); }
            100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0,255,136,0); }
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        .empty-state-icon { font-size: 3rem; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 AI Agent News Aggregator</h1>
            <p class="subtitle">中美热门科技网站 Agent 新闻聚合</p>
            
            <div class="stats-bar">
                <div class="stat-item">
                    <div class="stat-value">{{ total }}</div>
                    <div class="stat-label">新闻总数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ sources|length }}</div>
                    <div class="stat-label">数据来源</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ now.strftime('%m/%d') }}</div>
                    <div class="stat-label">最后更新</div>
                </div>
            </div>
        </header>
        
        <div class="grid">
            <div class="card">
                <h2>📰 热门新闻 TOP 10</h2>
                {% if news %}
                    {% for item in news %}
                    <div class="news-item">
                        <h3><a href="{{ item.link }}" target="_blank" rel="noopener">{{ item.title }}</a></h3>
                        <div class="meta">
                            <span class="source">{{ item.source }}</span>
                            <span class="date">{{ item.published_at.strftime('%Y-%m-%d') if item.published_at else '未知' }}</span>
                        </div>
                        <p class="summary">{{ item.summary[:120] if item.summary else '' }}...</p>
                        {% if item.keywords %}
                        <div class="keywords">🏷️ {{ item.keywords }}</div>
                        {% endif %}
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-state">
                        <div class="empty-state-icon">📭</div>
                        <p>暂无新闻数据</p>
                    </div>
                {% endif %}
            </div>
            
            <div class="card">
                <h2>📊 每日简报</h2>
                <div class="brief-section">
                    {% if brief %}
                        {{ brief.content|replace('\n', '<br>')|replace('# ', '<h1>')|replace('## ', '<h2>')|replace('- ', '• ')|safe }}
                    {% else %}
                        <div class="empty-state">
                            <div class="empty-state-icon">📝</div>
                            <p>暂无简报，请先运行数据抓取</p>
                        </div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>数据来源: <span class="highlight">TechCrunch, The Verge, 36氪, 虎嗅, 财新周刊, 小宇宙</span></p>
            <p>构建时间: {{ now.strftime('%Y-%m-%d %H:%M') }} | Render 云端部署</p>
        </div>
    </div>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
