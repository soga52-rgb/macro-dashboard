import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pandas as pd

# ==============================================================================
# 系統設定區
# ==============================================================================
# 安全宣告區：優先從系統環境變數讀取
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 檔案路徑設定 (改用支援雲端主機的跨平台相對路徑)
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(WORKSPACE_DIR, "macro_analysis.csv")
HTML_PATH = os.path.join(WORKSPACE_DIR, "index.html")

# ==============================================================================
# 1. 抓取週度新聞 (Google News RSS - 滾動 7 天視窗)
# ==============================================================================
def fetch_weekly_news():
    print("正在抓取過去七天全球總經深度新聞 (滾動週度視窗)...")
    # 加上 when:7d 參數並使用更精確的「週報專用」關鍵字，避免抓到過時的研究報告
    url = "https://news.google.com/rss/search?q=latest+global+macro+weekly+outlook+OR+fed+interest+rate+DXY+trend+when:7d&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        response = urllib.request.urlopen(req)
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        headlines = []
        # 增加新聞抓取數量到 30 則，提供更多上下文給 AI
        for item in root.findall('.//item')[:30]:
            title_node = item.find('title')
            link_node = item.find('link')
            title = title_node.text if title_node is not None else "新聞標題"
            link = link_node.text if link_node is not None else "#"
            headlines.append({"title": title, "link": link})
        return headlines
    except Exception as e:
        print(f"新聞抓取失敗: {e}")
        return []

# ==============================================================================
# 2. 呼叫 Gemini REST API 進行總經分析 (具備自動修復功能的版本)
# ==============================================================================
def analyze_with_gemini(news_data, today_str):
    print(f"正在呼叫 Gemini API 進行智能推論 (今日日期: {today_str})...")
    
    if isinstance(news_data, list) and len(news_data) > 0:
        news_text = "\n".join([item['title'] for item in news_data])
    else:
        news_text = "未能抓取新聞，請基於目前全球總體經濟狀況直接進行推論。"

    # 嘗試讀取現有的 CSV 數據提供給 AI 作為參考 (Context)
    macro_history = "尚無歷史數據"
    try:
        if os.path.exists(CSV_PATH):
            df_history = pd.read_csv(CSV_PATH)
            macro_history = df_history.tail(5).to_string()
    except Exception as e:
        print(f"讀取歷史數據失敗: {e}")

    prompt = f"""你現在是一位資深的全球總經策略分析師。請根據以下數據進行邏輯推演。

### 今日日期: {today_str}
### 歷史數據參考:
{macro_history}

### 最新新聞頭條:
{news_text}

### 撰寫指令 (核心邏輯):
1. **定位發動點 (Trigger Point)**: 從本週數據或新聞中，找出最具影響力的因子（如：Fed 談話、公債震盪或地緣政治）。
2. **彈性傳導鏈 (Elastic Chain)**: 靈活建構因果邏輯（例如：[因子] ➔ 影響通膨/利率預期 ➔ 最終定價美元走勢）。若無顯著新聞請跳過通膨環節。
3. **數據準確性**: 嚴禁虛構數值。若 DXY < 100，嚴禁說「突破 100」。
4. **HTML 格式限制**: 在 next_week_forecast_html 欄位中使用 <details> 標籤與分點結構。

### 輸出格式 (JSON):
請嚴格輸出以下 JSON 格式，不要有任何多餘文字：
{{
  "weekly_narrative": "(約 150 字) 基於市場情緒撰寫的本週摘要。",
  "focus_items": [ {{ "title": "...", "content": "..." }}, {{ "title": "...", "content": "..." }} ],
  "fx_rates_linkage": "(120 字) 拆解利率與匯率的實際傳導。",
  "outlook_risks": [ {{ "title": "...", "content": "..." }}, {{ "title": "...", "content": "..." }} ],
  "analysis": [
    {{ 
      "variable_name": "🔥 通膨預期", 
      "badge_text": "CPI/PPI Outlook", 
      "status": "...", 
      "status_detail": "...", 
      "trend_class": "trend-up", 
      "trend_text": "...", 
      "drivers": "...", 
      "impact": "..." 
    }},
    {{ 
      "variable_name": "📉 利率預期", 
      "badge_text": "Fed Funds / US10Y", 
      "status": "...", 
      "status_detail": "...", 
      "trend_class": "trend-up", 
      "trend_text": "...", 
      "drivers": "...", 
      "impact": "..." 
    }},
    {{ 
      "variable_name": "🦅 美元指數", 
      "badge_text": "DXY Strength", 
      "status": "...", 
      "status_detail": "...", 
      "trend_class": "trend-up", 
      "trend_text": "...", 
      "drivers": "...", 
      "impact": "..." 
    }}
  ],
  "next_week_forecast_html": "<details class='analysis-container'><summary>📢 下週預測：[主旋律]</summary><div class='analysis-content'><strong>⛓️ 市場邏輯傳導：</strong><p>[因子] ➔ 影響<strong>通膨/利率預期</strong> ➔ 最終定價<strong>美元走勢</strong>。</p><hr><strong>📉 資產動態預測：</strong><ul><li><strong>亞洲貨幣 (TWD/JPY/KRW)：</strong>...</li><li><strong>避險成本與鋼鐵業：</strong>...</li></ul></div></details>"
}}
"""
    
    # 恢復原本使用的 2026 最新型號
    strategies = [
        ("v1beta", "gemini-3-flash-preview"), 
        ("v1beta", "gemini-3.1-flash"),
        ("v1", "gemini-1.5-flash"),
        ("v1beta", "gemini-2.0-flash"),
    ]
    
    import time
    for version, model in strategies:
        # 內層重試機制 (針對 503/429)
        max_retries = 2
        for attempt in range(max_retries):
            try:
                print(f"-> 嘗試連線方案: {version} / {model} (第 {attempt+1} 次)...")
                url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                data = {"contents": [{"parts": [{"text": prompt}]}]}
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
                
                try:
                    response = urllib.request.urlopen(req)
                    result = json.loads(response.read().decode('utf-8'))
                    text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    if text.startswith("```json"): text = text[7:]
                    if text.startswith("```"): text = text[3:]
                    if text.endswith("```"): text = text[:-3]
                    
                    print(f"[SUCCESS] {model} 回應成功！")
                    return json.loads(text.strip())
                except urllib.error.HTTPError as e:
                    error_data = e.read().decode('utf-8')
                    # 如果是 503 (系統忙碌) 或 429 (配額滿)，我們稍微休息一下再試
                    if e.code in [429, 503] and attempt < max_retries - 1:
                        wait_time = 7
                        print(f"   [WAIT] 伺服器忙碌或配額限制，等待 {wait_time} 秒後重試...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"   [FAIL] {model} 錯誤 ({e.code}): {error_data}")
                        break # 跳出重試，換下一個型號
            except Exception as e:
                print(f"   [FAIL] {model} 發生其他錯誤: {e}")
                break
            
    print("\n[CRITICAL ERROR] 所有連線方案均告失敗。")
    return None

# ==============================================================================
# 3. 渲染並覆寫 HTML 網頁與 CSV 資料表
# ==============================================================================
def update_dashboard(ai_response, news_list, today_str):
    if not ai_response or not isinstance(ai_response, dict) or 'analysis' not in ai_response:
        print("[ERROR] 戰情分析資料格式不正確，無法更新儀表板。")
        return
        
    print("正在將深度週報結果寫入儀表板與 CSV 檔案...")
    
    analysis_data = ai_response['analysis']
    weekly_narrative = ai_response.get('weekly_narrative', '本週尚無綜合摘要。')
    focus_items = ai_response.get('focus_items', [])
    fx_rates_linkage = ai_response.get('fx_rates_linkage', '尚無傳導分析。')
    outlook_risks = ai_response.get('outlook_risks', [])
    next_week_forecast_html = ai_response.get('next_week_forecast_html', '')
    
    # 更新 CSV (維持基本數據結構)
    csv_content = "變數與項目,當前狀態,短期趨勢,主要驅動因素,全球經濟交互影響\n"
    for item in analysis_data:
        drivers = str(item['drivers']).replace(',', '，')
        impact = str(item['impact']).replace(',', '，')
        csv_content += f"{item['variable_name']},{item['status']} {item['status_detail']},{item['trend_text']},{drivers},{impact}\n"
    
    with open(CSV_PATH, "w", encoding="utf-8") as f:
        f.write(csv_content)

    # 準備焦點事件 HTML
    focus_html = ""
    for idx, item in enumerate(focus_items):
        focus_html += f"""
        <div class="focus-card">
            <div class="focus-idx">0{idx+1}</div>
            <div class="focus-content">
                <h4>{item['title']}</h4>
                <p>{item['content']}</p>
            </div>
        </div>"""

    # 準備風險預警 HTML
    risk_html = ""
    for item in outlook_risks:
        risk_html += f"""
        <div class="risk-item">
            <span class="risk-title">⚠️ {item.get('title', '未知風險')}</span>
            <p class="risk-content">{item.get('content', '')}</p>
        </div>"""

    # 準備新聞 HTML
    news_html = ""
    if isinstance(news_list, list) and news_list:
        for news in news_list:
            news_html += f"""
                <li class="news-item">
                    <a href="{news['link']}" target="_blank">📄 {news['title']}</a>
                </li>"""
    else:
        news_html = "<li class='news-item'><a href='#'>暫無新聞。</a></li>"

    # 準備分析表格 HTML
    tbody_html = ""
    for item in analysis_data:
        trend_class = item.get('trend_class', '')
        tbody_html += f"""
                <tr>
                    <td data-label="核心變數">
                        <div class="var-name">{item['variable_name']}</div>
                        <span class="badge">{item['badge_text']}</span>
                    </td>
                    <td data-label="當前狀態"><div class="status {trend_class}">{item['status']} <span class="status-detail">{item['status_detail']}</span></div></td>
                    <td data-label="趨勢"><span class="{trend_class} {item.get('trend_icon', '')}">{item['trend_text']}</span></td>
                    <td data-label="驅動因素" class="desc-text">{item['drivers']}</td>
                </tr>"""

    html_template = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>【全球總經週報】宏觀趨勢與資產配置分析</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #f4f7f9;
            --surface-color: #ffffff;
            --border-color: #e2e8f0;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --accent-color: #2563eb;
            --up-color: #be123c;
            --down-color: #15803d;
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.05);
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", "Helvetica Neue", sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.8;
            padding: 4rem 1rem;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .newsletter-wrapper {{
            width: 100%;
            max-width: 850px;
            background: var(--surface-color);
            border-radius: 4px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            padding: 4rem;
            border-top: 8px solid var(--accent-color);
        }}

        .report-header {{ border-bottom: 2px solid #f1f5f9; padding-bottom: 2rem; margin-bottom: 3rem; text-align: center; }}
        .report-header h1 {{ font-size: 2.2rem; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.5rem; }}
        .report-header .date {{ color: var(--text-secondary); font-weight: 500; text-transform: uppercase; letter-spacing: 0.1em; font-size: 0.9rem; }}

        .section-h2 {{ 
            font-size: 1.5rem; font-weight: 700; margin: 3rem 0 1.5rem 0; 
            display: flex; align-items: center; gap: 0.8rem;
            color: #0f172a;
        }}
        .section-h2::after {{ content: ""; height: 2px; flex: 1; background: #f1f5f9; }}

        .narrative-box {{ font-size: 1.15rem; color: #334155; text-align: justify; margin-bottom: 2.5rem; }}
        
        .focus-grid {{ display: flex; flex-direction: column; gap: 1rem; margin-bottom: 3rem; }}
        .focus-card {{ 
            display: flex; gap: 1.5rem; padding: 1.5rem; background: #f8fafc; border-radius: 8px; border: 1px solid #edf2f7;
        }}
        .focus-idx {{ font-size: 2rem; font-weight: 800; color: #cbd5e1; line-height: 1; }}
        .focus-content h4 {{ font-size: 1.15rem; margin-bottom: 0.5rem; color: var(--accent-color); }}
        .focus-content p {{ font-size: 1.05rem; color: #475569; }}

        .deep-dive-box {{ 
            background: #fffcf0; border: 1px solid #fef3c7; padding: 2rem; border-radius: 12px; margin-bottom: 3rem;
            line-height: 1.9; font-size: 1.1rem; color: #92400e;
        }}
        .deep-dive-box h3 {{ margin-bottom: 1rem; color: #78350f; font-weight: 700; }}

        .risk-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 3rem; }}
        .risk-item {{ padding: 1.2rem; background: #fff5f5; border-radius: 8px; border-left: 4px solid #f87171; }}
        .risk-title {{ font-weight: 700; color: #991b1b; display: block; margin-bottom: 0.5rem; }}
        .risk-content {{ font-size: 0.95rem; color: #b91c1c; }}

        .table-container {{ overflow-x: auto; margin-bottom: 3rem; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
        th {{ padding: 1rem; text-align: left; border-bottom: 2px solid #f1f5f9; color: var(--text-secondary); }}
        td {{ padding: 1.2rem 1rem; border-bottom: 1px solid #f1f5f9; }}
        .var-name {{ font-weight: 700; color: var(--text-primary); }}
        .badge {{ font-size: 0.75rem; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; color: #64748b; }}
        .trend-up {{ color: var(--up-color); font-weight: 600; }}
        .trend-down {{ color: var(--down-color); font-weight: 600; }}
        
        /* 專業分析收合方塊樣式 */
        .analysis-container {
            margin: 20px 0;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background: #ffffff;
            overflow: hidden;
            box-shadow: var(--shadow-md);
        }

        .analysis-container summary {
            padding: 1.2rem;
            background: #f8fafc;
            cursor: pointer;
            font-weight: 700;
            font-size: 1.1rem;
            list-style: none; /* 隱藏原生箭頭 */
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid transparent;
            transition: all 0.3s ease;
        }

        .analysis-container[open] summary {
            border-bottom: 1px solid #edf2f7;
            background: #ffffff;
        }

        /* 自定義小箭頭 */
        .analysis-container summary::after {
            content: "▼";
            font-size: 0.8rem;
            color: var(--text-secondary);
            transition: transform 0.3s ease;
        }

        .analysis-container[open] summary::after {
            transform: rotate(180deg);
        }

        .analysis-content {
            padding: 1.5rem 2rem;
            line-height: 1.8;
            color: #334155;
            background: #ffffff;
        }
        .analysis-content hr { border: 0; border-top: 1px solid #f1f5f9; margin: 1.5rem 0; }
        .analysis-content ul { padding-left: 20px; }
        .analysis-content li { margin-bottom: 10px; }
        .analysis-content strong { color: var(--accent-color); }

        .visual-tools {{ display: grid; grid-template-columns: 1fr; gap: 2rem; margin-top: 2rem; }}
        .widget-box {{ 
            background: #fff; border: 1px solid var(--border-color); border-radius: 8px; 
            padding: 1rem; box-shadow: var(--shadow-md); 
        }}
        .widget-title {{ font-size: 1rem; font-weight: 700; margin-bottom: 1rem; color: var(--text-secondary); }}

        .news-accordion summary {{
            cursor: pointer; padding: 1rem; background: #f8fafc; border-radius: 6px; font-weight: 600;
            list-style: none; display: flex; justify-content: space-between; align-items: center;
        }}
        .news-accordion summary::after {{ content: "+"; font-size: 1.2rem; }}
        .news-accordion[open] summary::after {{ content: "-"; }}
        .news-list {{ list-style: none; padding: 1rem; }}
        .news-item {{ margin-bottom: 0.8rem; border-bottom: 1px dashed #e2e8f0; padding-bottom: 0.5rem; }}
        .news-item a {{ text-decoration: none; color: #475569; font-size: 0.95rem; }}

        @media (max-width: 768px) {{
            .newsletter-wrapper {{ padding: 2rem 1.5rem; }}
            .risk-grid {{ grid-template-columns: 1fr; }}
            table, thead, tbody, th, td, tr {{ display: block; }}
            thead {{ display: none; }}
            tr {{ margin-bottom: 1.5rem; border: 1px solid #edf2f7; padding: 1rem; }}
            td {{ padding: 0.5rem 0; border: none; }}
            td::before {{ content: attr(data-label); font-weight: 600; color: #94a3b8; display: block; font-size: 0.8rem; }}
        }}

        /* 專業分析收合方塊樣式 */
        .analysis-container {{
            margin: 20px 0;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background: #ffffff;
            overflow: hidden;
        }}

        .analysis-container summary {{
            padding: 15px;
            background: #f8f9fa;
            cursor: pointer;
            font-weight: bold;
            font-size: 1.1rem;
            list-style: none; /* 隱藏原生箭頭 */
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        /* 自定義小箭頭 */
        .analysis-container summary::after {{
            content: "▼";
            font-size: 0.8rem;
            color: #666;
            transition: transform 0.3s;
        }}

        .analysis-container[open] summary::after {{
            transform: rotate(180deg);
        }}

        .analysis-content {{
            padding: 20px;
            line-height: 1.6;
            border-top: 1px solid #eee;
            color: #444;
        }}
        .analysis-content ul {{ padding-left: 20px; }}
        .analysis-content li {{ margin-bottom: 8px; }}
    </style>
</head>
<body>
    <div class="newsletter-wrapper">
        <header class="report-header">
            <span class="date">GLOBAL MACRO WEEKLY INSIGHTS</span>
            <h1>全球總經週報</h1>
            <p style="color: #94a3b8;">由 AI 驅動的自動化全域分析 (Rolling 7-Day Window)</p>
            <p style="font-size: 0.85rem; color: var(--accent-color); font-weight: 600; margin-top: 0.5rem;">🕒 最後更新時間：{today_str}</p>
            <div style="margin-top: 1.5rem;" class="tradingview-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>{{"symbols": [ {{"proName": "FOREXCOM:SPXUSD", "title": "S&P 500"}}, {{"proName": "FOREXCOM:NSXUSD", "title": "Nasdaq 100"}}, {{"proName": "FX_IDC:EURUSD", "title": "EUR/USD"}}, {{"proName": "BITSTAMP:BTCUSD", "title": "BTC/USD"}}, {{"proName": "BITSTAMP:ETHUSD", "title": "ETH/USD"}} ], "showSymbolLogo": true, "colorTheme": "light", "isTransparent": true, "displayMode": "adaptive", "locale": "zh_TW"}}</script></div>
        </header>

        <section>
            <h2 class="section-h2">📻 本週市場主旋律 (Narrative)</h2>
            <div class="narrative-box">
                {weekly_narrative}
            </div>
            {next_week_forecast_html}
        </section>

        <section>
            <h2 class="section-h2">📈 宏觀指標動態走勢 (4-Week Trend)</h2>
            <div class="trend-grid">
                <div class="trend-card">
                    <h4>US 10Y Yield</h4>
                    <div class="trend-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "FRED:DGS10", "width": "100%", "height": "100%", "locale": "zh_TW", "dateRange": "1M", "colorTheme": "light", "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>Dollar Index</h4>
                    <div class="trend-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "CAPITALCOM:DXY", "width": "100%", "height": "100%", "locale": "zh_TW", "dateRange": "1M", "colorTheme": "light", "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>Gold Spot</h4>
                    <div class="trend-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "TVC:GOLD", "width": "100%", "height": "100%", "locale": "zh_TW", "dateRange": "1M", "colorTheme": "light", "isTransparent": true}}</script></div>
                </div>
                <!-- 亞洲貨幣 -->
                <div class="trend-card">
                    <h4>USD / JPY</h4>
                    <div class="trend-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "FX:USDJPY", "width": "100%", "height": "100%", "locale": "zh_TW", "dateRange": "1M", "colorTheme": "light", "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>USD / TWD</h4>
                    <div class="trend-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "FX_IDC:USDTWD", "width": "100%", "height": "100%", "locale": "zh_TW", "dateRange": "1M", "colorTheme": "light", "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>USD / KRW</h4>
                    <div class="trend-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "FX_IDC:USDKRW", "width": "100%", "height": "100%", "locale": "zh_TW", "dateRange": "1M", "colorTheme": "light", "isTransparent": true}}</script></div>
                </div>
            </div>
        </section>


        <section>
            <h2 class="section-h2">🎯 關鍵事件深度剖析</h2>
            <div class="focus-grid">
                {focus_html}
            </div>
        </section>

        <section>
            <h2 class="section-h2">⛓️ 利率與匯率傳導矩陣</h2>
            <div class="deep-dive-box">
                <h3>Macro Linkage Analysis</h3>
                {fx_rates_linkage}
            </div>
        </section>

        <section>
            <h2 class="section-h2">📊 核心變數數據監測</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>核心變數</th>
                            <th>當前狀態</th>
                            <th>趨勢</th>
                            <th>驅動因素</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tbody_html}
                    </tbody>
                </table>
            </div>
        </section>

        <section>
            <h2 class="section-h2">🧭 下週風險預警</h2>
            <div class="risk-grid">
                {risk_html}
            </div>
        </section>

        <section>
            <h2 class="section-h2">📊 全球市場熱力圖</h2>
            <div class="visual-tools">
                <div class="widget-box">
                    <div class="widget-title">美股 S&P 500 板塊熱圖</div>
                    <div class="tradingview-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>{{ "exchanges": [], "dataSource": "S&P500", "grouping": "sector", "blockSize": "market_cap", "blockColor": "change", "locale": "zh_TW", "symbolUrl": "", "colorTheme": "light", "hasTopBar": false, "isTransparent": true, "hasSymbolTooltip": true, "width": "100%", "height": "450" }}</script></div>
                </div>
                <div class="widget-box">
                    <div class="widget-title">主要貨幣對強弱熱力圖 (Forex Heat Map)</div>
                    <div class="tradingview-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-forex-heat-map.js" async>{{"width": "100%","height": "400","currencies": ["EUR","USD","JPY","GBP","CHF","AUD","CAD","NZD","CNY"],"isTransparent": true,"colorTheme": "light","locale": "zh_TW"}}</script></div>
                </div>
            </div>
        </section>

        <footer style="margin-top: 5rem; border-top: 1px solid #f1f5f9; padding-top: 2rem;">
            <details class="news-accordion">
                <summary>查看本週參考新聞原文 (共 {len(news_list)} 則)</summary>
                <ul class="news-list">
                    {news_html}
                </ul>
            </details>
            <p style="text-align: center; color: #cbd5e1; font-size: 0.8rem; margin-top: 2rem;">© 2026 Macro Strategy Lab. 最後更新：{today_str}</p>
        </footer>
    </div>
</body>
</html>"""


    # 加入強制更新標記 (避免 Git 因內容重複而跳過 Commit)
    html_template += f"\n<!-- Build Trace: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->"

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_template)
    
    print(f"[OK] 更新成功！請打開 {HTML_PATH} 查看最新儀表板。")

# ==============================================================================
# 主程式執行區 (機器人自動呼叫進入點)
# ==============================================================================
if __name__ == "__main__":
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            print("[ERROR] 嚴重安全性錯誤：找不到 GEMINI_API_KEY 環境變數。")
            print("-> 如果您是在地端測試，請先用指令設定金鑰 (set GEMINI_API_KEY=YOUR_KEY)")
            print("-> 如果您是在 GitHub 雲端執行，請確認您已經在專案的 Settings -> Secrets and variables 中加入了金鑰！")
        else:
            # 取得今日日期字串 (調整為台灣時間 UTC+8)
            today_str = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
            
            # 呼叫正確的週報抓取函式
            news_list = fetch_weekly_news()
            ai_response = analyze_with_gemini(news_list, today_str)
            
            # 安全性檢查：確保 AI 回傳內容正確
            if ai_response and isinstance(ai_response, dict) and 'analysis' in ai_response:
                update_dashboard(ai_response, news_list, today_str)
                print(f"\n[OK] 雲端戰情室更新腳本執行完畢 (更新時間: {today_str})。")
            else:
                print("\n[ERROR] AI 回傳內容格式不全，已中斷更新。")
                import sys
                sys.exit(1)
            
    except Exception as e:
        print(f"\n[CRASH] 程式發生未預期錯誤: {e}")
    
    # input("\n請按 Enter 鍵結束程式...")
