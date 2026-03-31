import os
import json
import urllib.request
import xml.etree.ElementTree as ET

# ==============================================================================
# 系統設定區
# ==============================================================================
# 安全宣告區 (不寫死金鑰，而是透過環境變數從 GitHub 金庫中讀取)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 檔案路徑設定 (改用支援雲端主機的跨平台相對路徑)
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(WORKSPACE_DIR, "macro_analysis.csv")
HTML_PATH = os.path.join(WORKSPACE_DIR, "index.html")

# ==============================================================================
# 1. 抓取免費新聞 (Google News RSS)
# ==============================================================================
def fetch_daily_news():
    print("正在抓取今日全球總經新聞...")
    # 加上 when:1d 參數，強迫 Google 新聞只回傳過去 24 小時內發生的最新消息 (今日重點)
    url = "https://news.google.com/rss/search?q=global+economy+macro+interest+rates+dollar+gold+when:1d&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        response = urllib.request.urlopen(req)
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        headlines = []
        for item in root.findall('.//item')[:15]:
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
# 2. 呼叫 Gemini REST API 進行總經分析 (零安裝套件版本)
# ==============================================================================
def analyze_with_gemini(news_data):
    print("正在呼叫 Gemini API 進行智能推論...")
    
    # 根據您的專屬金鑰，使用最新的 Gemini 3.1 Flash Lite 預覽版
    model_name = "gemini-3.1-flash-lite-preview"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    
    if isinstance(news_data, list) and len(news_data) > 0:
        news_text = "\n".join([item['title'] for item in news_data])
    else:
        news_text = "未能抓取新聞，請基於目前全球總體經濟狀況直接進行推論。"

    prompt = f"""你現在是一位華爾街資深總體經濟分析師。
以下是今天最新的全球財經新聞頭條：
{news_text}

請根據新聞與總經知識，分析目前全球三個核心變數的狀態：
1. 物價預期 
2. 美債殖利率 (10年期)
3. 美元指數 (DXY)

請嚴格輸出為 JSON 格式，必須且僅包含以下結構，不要輸出 ```json 等 Markdown 標記，只要輸出純淨的 JSON：
{{
  "summary": "撰寫『當前核心三變數外溢效應』。長度務必保持在100字以內非常精煉，精準說明「物價、美債、美元」目前的交互作用，並具體指出這三個核心的擾動是如何外溢/傳導至其他變數(如原油、黃金或亞幣)的。字字珠璣，不要講廢話。",
  "analysis": [
    {{
      "variable_name": "🔥 物價預期",
      "badge_bg": "rgba(239, 68, 68, 0.15)",
      "badge_color": "#dc2626",
      "badge_text": "例如: 高風險 或 逐漸降溫",
      "status": "例如: 陡升 或 趨穩",
      "status_detail": "例如: (CPI超預期)",
      "trend_class": "trend-up", 
      "trend_icon": "icon-up",
      "trend_text": "例如: 急劇走高",
      "drivers": "一句話描述主要驅動因素",
      "impact": "一句話描述對全球經濟的交互影響"
    }},
    ... (美債請用 📉，trend_class 可用 trend-down/icon-down。美元請用 🦅，trend_class 可用 trend-strong/icon-rocket)
  ]
}}
所有描述請使用繁體中文，語氣專業精煉。
"""
    
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text.strip())
    except Exception as e:
        print(f"[ERROR] API 請求失敗或 JSON 解析錯誤: {e}")
        return None

# ==============================================================================
# 3. 渲染並覆寫 HTML 網頁與 CSV 資料表
# ==============================================================================
def update_dashboard(ai_response, news_list):
    if not ai_response or 'analysis' not in ai_response:
        print("沒有最新的分析資料可供更新。")
        return
        
    print("正在將分析結果寫入儀表板與 CSV 檔案...")
    
    analysis_data = ai_response['analysis']
    summary_text = ai_response.get('summary', '今日尚無綜合摘要。')
    
    #更新 CSV
    csv_content = "變數與項目,當前狀態,短期趨勢,主要驅動因素,全球經濟交互影響\n"
    for item in analysis_data:
        drivers = str(item['drivers']).replace(',', '，')
        impact = str(item['impact']).replace(',', '，')
        csv_content += f"{item['variable_name']},{item['status']} {item['status_detail']},{item['trend_text']},{drivers},{impact}\n"
    
    with open(CSV_PATH, "w", encoding="utf-8") as f:
        f.write(csv_content)

    # 準備新聞 HTML (取消單行省略，設定更寬鬆的行距)
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
        # 特別修改針對淺色模式的顏色，讓 up/down 顏色更深一些以利閱讀
        trend_class = item['trend_class']
        badge_bg = item.get('badge_bg', '#f1f5f9')
        badge_color = item.get('badge_color', '#334155')
        
        tbody_html += f"""
                <tr>
                    <td>
                        <div class="var-name">{item['variable_name']}</div>
                        <span class="badge" style="background: {badge_bg}; color: {badge_color};">{item['badge_text']}</span>
                    </td>
                    <td><div class="status {trend_class}">{item['status']} <span class="status-detail">{item['status_detail']}</span></div></td>
                    <td><span class="{trend_class} {item['trend_icon']}">{item['trend_text']}</span></td>
                    <td class="desc-text">{item['drivers']}</td>
                    <td class="desc-text">{item['impact']}</td>
                </tr>"""

    html_template = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>全球總經局勢即時分析與市場面板</title>
    <!-- 引入易讀的 Google Font -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            /* 淺色明亮模式專用色彩 (彭博/華爾街日報白底風格) */
            --bg-color: #f8fafc;
            --surface-color: #ffffff;
            --border-color: #e2e8f0;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --accent-color: #0284c7;
            --accent-glow: rgba(2, 132, 199, 0.1);
            --up-color: #dc2626;  /* 比較深的紅色提升對比 */
            --down-color: #16a34a; /* 比較深的綠色提升對比 */
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            /* Apple 官方字型設計 (-apple-system / PingFang TC) */
            font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", "SF Pro TC", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 3rem 2rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}
        
        .header {{ text-align: center; margin-bottom: 2.5rem; }}
        .header h1 {{ 
            font-size: 2.2rem; 
            font-weight: 700; 
            color: #0f172a; 
            letter-spacing: -0.025em;
        }}
        .header p {{ 
            color: var(--text-secondary); 
            font-size: 1.15rem; 
            margin-top: 0.5rem; 
            font-weight: 500;
        }}
        
        .dashboard-container {{ 
            width: 100%; 
            max-width: 1200px; 
            background: var(--surface-color); 
            border: 1px solid var(--border-color); 
            border-radius: 16px; 
            padding: 2.5rem; 
            margin-bottom: 2rem; 
            box-shadow: var(--shadow-md); 
        }}
        
        .section-title {{ 
            font-size: 1.35rem; 
            margin-bottom: 1.5rem; 
            padding-bottom: 0.8rem; 
            border-bottom: 2px solid #f1f5f9; 
            display: flex; 
            align-items: center; 
            gap: 10px; 
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        /* 早報與新聞樣式 */
        .summary-box {{
            background: #f0f9ff;
            border-left: 5px solid var(--accent-color);
            padding: 1.8rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            line-height: 1.8;
            font-size: 1.1rem;
            color: #0c4a6e;
            box-shadow: var(--shadow-sm);
        }}
        .summary-box b {{ color: var(--accent-color); font-size: 1.15rem; }}
        
        .news-list {{
            list-style: none;
            display: grid;
            /* 將寬欄改為更實用的兩欄文字佈局，或在手機上變為單欄 */
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 1.2rem;
        }}
        
        .news-item a {{
            color: #334155;
            text-decoration: none;
            display: block;
            padding: 1.2rem;
            border-radius: 8px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            transition: all 0.2s ease;
            font-size: 1.05rem;
            font-weight: 500;
            line-height: 1.5;
            /* 解除 nowrap 的截斷，允許文字自然換行！ */
            white-space: normal; 
        }}
        .news-item a:hover {{
            background: #ffffff;
            color: var(--accent-color);
            border-color: #bae6fd;
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }}

        /* 表格樣式優化 */
        table {{ 
            width: 100%; 
            border-collapse: separate; 
            border-spacing: 0; 
        }}
        th, td {{ 
            padding: 1.5rem 1.2rem; /* 拉寬儲存格內部留白 */
            text-align: left; 
            border-bottom: 1px solid var(--border-color); 
            vertical-align: top; /* 讓文字靠上對齊方便掃描 */
        }}
        th {{ 
            font-weight: 600; 
            color: var(--text-secondary); 
            font-size: 0.95rem; 
            text-transform: uppercase;
            letter-spacing: 0.05em;
            background: #f8fafc; /* 表頭加一點淺底色分離區塊 */
        }}
        tbody tr:hover {{ 
            background-color: #f8fafc; 
        }}
        tbody tr:last-child td {{ border-bottom: none; }}
        
        .var-name {{ 
            font-weight: 700; 
            font-size: 1.15rem; 
            display: flex; 
            align-items: center; 
            gap: 10px; 
            color: var(--text-primary);
        }}
        .status {{ font-size: 1.1rem; font-weight: 600; margin-top: 4px; }}
        .status-detail {{ font-size: 0.95rem; color: var(--text-secondary); font-weight: 400; display: block; margin-top: 4px; }}
        
        .trend-up {{ color: var(--up-color); display: flex; align-items: center; gap: 4px; font-weight: 600; }}
        .trend-down {{ color: var(--down-color); display: flex; align-items: center; gap: 4px; font-weight: 600; }}
        .trend-strong {{ color: var(--accent-color); display: flex; align-items: center; gap: 4px; font-weight: 600; }}
        
        .badge {{ 
            display: inline-block; 
            padding: 0.35rem 0.8rem; 
            border-radius: 9999px; 
            font-size: 0.8rem; 
            font-weight: 600; 
            background: #f1f5f9;
            margin-top: 0.8rem;
            border: 1px solid rgba(0,0,0,0.05);
        }}
        
        .desc-text {{ 
            color: #334155; 
            font-size: 1.05rem; 
            line-height: 1.7; 
            max-width: 320px; 
        }}
        
        /* 圖表區塊 */
        .charts-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); 
            gap: 1.5rem; 
            margin-top: 1rem; 
        }}
        .chart-widget {{ 
            background: #ffffff; 
            border: 1px solid var(--border-color); 
            border-radius: 12px; 
            height: 320px; 
            overflow: hidden; 
            box-shadow: var(--shadow-sm); 
        }}
        .icon-up::before {{ content: '▲'; }} .icon-down::before {{ content: '▼'; }} .icon-rocket::before {{ content: '🚀'; }}

        /* --- 折疊選單 (Accordion) 樣式 --- */
        .news-accordion summary {{
            cursor: pointer; font-size: 1.05rem; font-weight: 600; color: var(--text-primary);
            padding: 1rem 1.5rem; background: #f1f5f9; border-radius: 8px;
            list-style: none; user-select: none; transition: background 0.2s ease;
        }}
        .news-accordion summary::-webkit-details-marker {{ display: none; }}
        .news-accordion summary:hover {{ background: #e2e8f0; }}
        .news-accordion summary::after {{
            content: "▼"; float: right; font-size: 0.9rem; color: var(--text-secondary); transition: transform 0.3s ease;
        }}
        .news-accordion[open] summary::after {{ transform: rotate(-180deg); }}

        /* --- 手機版響應式設計 (Apple-like Mobile UI) --- */
        @media (max-width: 768px) {{
            body {{ padding: 1.5rem 1rem; }}
            .header h1 {{ font-size: 1.8rem; letter-spacing: -0.01em; }}
            .dashboard-container {{ padding: 1.5rem; }}
            
            /* 將傳統 Table 轉換為流暢的手機讀取卡片 */
            table, thead, tbody, th, td, tr {{ display: block; }}
            thead tr {{ display: none; }}
            tr {{ margin-bottom: 2rem; border: 1px solid var(--border-color); border-radius: 12px; background: #fff; box-shadow: var(--shadow-md); }}
            td {{ padding: 1rem; padding-left: 35%; position: relative; border-bottom: 1px solid #f1f5f9; }}
            td:last-child {{ border-bottom: none; }}
            
            td::before {{
                position: absolute; left: 1rem; top: 1rem; width: 30%; white-space: nowrap;
                font-size: 0.85rem; font-weight: 600; color: var(--text-secondary);
            }}
            td:nth-of-type(1)::before {{ content: "核心變數"; }}
            td:nth-of-type(2)::before {{ content: "當前狀態"; }}
            td:nth-of-type(3)::before {{ content: "短期趨勢"; }}
            td:nth-of-type(4)::before {{ content: "主要因素"; }}
            td:nth-of-type(5)::before {{ content: "交互影響"; }}
            
            td:nth-of-type(1) {{ padding-left: 1rem; padding-top: 3rem; background: #f8fafc; border-top-left-radius: 12px; border-top-right-radius: 12px; }}
            td:nth-of-type(1)::before {{ top: 1rem; color: var(--accent-color); }}
            
            .news-list {{ grid-template-columns: 1fr; }}
            .charts-grid {{ grid-template-columns: 1fr; }}
            .chart-widget {{ height: 280px; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>全球總經局勢 綜合戰情室</h1>
        <p>結合 AI 趨勢早報與即時市場動態 (圖表自動更新)</p>
    </div>
    
    <!-- AI 綜合精煉早報 -->
    <div class="dashboard-container">
        <h2 class="section-title">📰 AI 總經情勢早報</h2>
        <div class="summary-box" style="margin-bottom: 0;">
            <b>專家短評：</b><br>
            {summary_text}
        </div>
    </div>
    
    <!-- 總經變數分析 -->
    <div class="dashboard-container">
        <h2 class="section-title">📊 總經變數深入分析 (由 Gemini 自動推論)</h2>
        <table>
            <thead>
                <tr>
                    <th>核心變數</th>
                    <th>當前狀態</th>
                    <th>短期趨勢</th>
                    <th>主要驅動因素</th>
                    <th>全球經濟交互影響</th>
                </tr>
            </thead>
            <tbody>
                {tbody_html}
            </tbody>
        </table>
    </div>

    <!-- 即時走勢圖 -->
    <div class="dashboard-container">
        <h2 class="section-title">💹 全球核心資產 即時走勢圖</h2>
        <div class="charts-grid">
            <div class="chart-widget"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "FRED:DGS10","width": "100%","height": "100%","locale": "zh_TW","dateRange": "1M","colorTheme": "light","isTransparent": true,"autosize": true}}</script></div></div>
            <div class="chart-widget"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "CAPITALCOM:DXY","width": "100%","height": "100%","locale": "zh_TW","dateRange": "1M","colorTheme": "light","isTransparent": true,"autosize": true}}</script></div></div>
            <div class="chart-widget"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "OANDA:XAUUSD","width": "100%","height": "100%","locale": "zh_TW","dateRange": "1M","colorTheme": "light","isTransparent": true,"autosize": true}}</script></div></div>
            <div class="chart-widget"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "FX:USDJPY","width": "100%","height": "100%","locale": "zh_TW","dateRange": "1M","colorTheme": "light","isTransparent": true,"autosize": true}}</script></div></div>
            <div class="chart-widget"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "FX_IDC:USDTWD","width": "100%","height": "100%","locale": "zh_TW","dateRange": "1M","colorTheme": "light","isTransparent": true,"autosize": true}}</script></div></div>
            <div class="chart-widget"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "FX_IDC:USDKRW","width": "100%","height": "100%","locale": "zh_TW","dateRange": "1M","colorTheme": "light","isTransparent": true,"autosize": true}}</script></div></div>
            <div class="chart-widget"><div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "OANDA:WTICOUSD","width": "100%","height": "100%","locale": "zh_TW","dateRange": "1M","colorTheme": "light","isTransparent": true,"autosize": true}}</script></div></div>
        </div>
    </div>

    <!-- 原文新聞附錄區 (可折疊收納) -->
    <div class="dashboard-container" style="padding: 1.5rem 2.5rem; margin-top: -1rem;">
        <details class="news-accordion">
            <summary>📌 點擊展開今日 15 則焦點新聞原文 (參考出處)</summary>
            <ul class="news-list" style="margin-top: 1.5rem;">
                {news_html}
            </ul>
        </details>
    </div>
</body>
</html>"""

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_template)
    
    print(f"[OK] 更新成功！請打開 {HTML_PATH} 查看最新儀表板。")

# ==============================================================================
# 主程式執行區 (機器人自動呼叫進入點)
# ==============================================================================
if __name__ == "__main__":
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("[ERROR] 嚴重安全性錯誤：找不到 GEMINI_API_KEY 環境變數。")
        print("-> 如果您是在地端測試，請先用指令設定金鑰 (set GEMINI_API_KEY=YOUR_KEY)")
        print("-> 如果您是在 GitHub 雲端執行，請確認您已經在專案的 Settings -> Secrets and variables 中加入了金鑰！")
        exit(1)
        
    news_list = fetch_daily_news()
    ai_response = analyze_with_gemini(news_list)
    update_dashboard(ai_response, news_list)
    
    print("\n[OK] 雲端戰情室更新腳本執行完畢。")
