import os
import sys
if r"D:\Lib\site-packages" not in sys.path:
    sys.path.append(r"D:\Lib\site-packages")
os.environ["PYTHONPATH"] = r"D:\Lib\site-packages"

try:
    import json
    import urllib.request
    import xml.etree.ElementTree as ET
    from datetime import datetime, timedelta
    import csv
except Exception as e:
    import traceback
    print("=============================================================")
    print("[啟動失敗] 本機端缺少執行需要的 Python 模組！")
    print(f"詳細錯誤訊息: {e}")
    print("=============================================================")
    print("這通常是因為您尚未在本機安裝必要的套件。")
    print("請關閉此視窗，開啟命令提示字元 (cmd) 並輸入以下指令：")
    print("pip install google-generativeai")
    print("=============================================================")
    sys.exit(1)

# ==============================================================================
# 系統設定區
# ==============================================================================
# 安全宣告區：優先從系統環境變數讀取
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 檔案路徑設定 (改用支援雲端主機的跨平台相對路徑)
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(WORKSPACE_DIR, "macro_analysis.csv")
HTML_PATH = os.path.join(WORKSPACE_DIR, "index.html")
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "historical_data.json")

# ==============================================================================
# 1. 抓取週度新聞 (Google News RSS - 滾動 7 天視窗)
# ==============================================================================
def fetch_weekly_news():
    print("正在抓取過去 48 小時全球總經深度新聞 (滾動日度視窗)...")
    # 核心追蹤事件區 (為避免 Google News 查詢過長導致忽略來源過濾，精簡關鍵字)
    macro_keywords = [
        "Federal Reserve", "interest rate", "rate cut", 
        "CPI", "inflation", "unemployment", 
        "GDP", "macroeconomic", "Treasury yields"
    ]
    
    import urllib.parse
    # 自動將關鍵字組合成標準字串 (以空白與雙引號分隔)
    query_str = " OR ".join([f'"{k}"' if ' ' in k else k for k in macro_keywords])
    # 添加指定媒體
    source_str = "site:bloomberg.com OR site:cnbc.com OR site:investing.com OR site:benzinga.com OR site:cnyes.com"
    # 用標準的 urllib 進行編碼，確保 Google News 伺服器絕對不漏接 when:2d 指令 (移除 AND 讓 site 條件生效)
    encoded_q = urllib.parse.quote(f"({query_str}) ({source_str}) when:2d")
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        response = urllib.request.urlopen(req, timeout=15)
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        headlines = []
        # 改為嚴格挑選最新 3 則，並篩選指定媒體
        for item in root.findall('.//item')[:3]:
            title_node = item.find('title')
            link_node = item.find('link')
            title = title_node.text if title_node is not None else "新聞標題"
            link = link_node.text if link_node is not None else "#"
            
            source_node = item.find('source')
            pubdate_node = item.find('pubDate')
            source = source_node.text if source_node is not None else "新聞媒體"
            pubdate = pubdate_node.text if pubdate_node is not None else datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            
            headlines.append({"title": title, "link": link, "source": source, "pubdate": pubdate})
        return headlines
    except Exception as e:
        print(f"新聞抓取失敗: {e}")
        return []

# ==============================================================================
# 1.5 抓取即時金融數據 (Yahoo Finance API)
# ==============================================================================
def fetch_realtime_data():
    print("正在抓取最新市場報價...")
    symbols = {
        "DXY (美元指數)": "DX-Y.NYB",
        "US10Y (美國十年期公債殖利率, %)": "^TNX",
        "Gold (黃金, USD/oz)": "GC=F",
        "WTI Crude (原油, USD/bbl)": "CL=F",
        "S&P 500 (標普500)": "^GSPC",
        "BTC (比特幣, USD)": "BTC-USD"
    }
    market_data = {}
    import urllib.parse
    for name, symbol in symbols.items():
        try:
            # 加入 URL 編碼與 range=15d 防呆機制
            encoded_symbol = urllib.parse.quote(symbol)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?interval=1d&range=15d"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=15)
            data = json.loads(response.read())
            
            result = data.get('chart', {}).get('result', [])
            if not result:
                raise ValueError("No result data")
                
            meta = result[0].get('meta', {})
            live_price = meta.get('regularMarketPrice')
            
            # 若無即時報價，則往前尋找最近一個有效收盤價
            if live_price is not None:
                price = live_price
            else:
                closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
                valid_closes = [c for c in closes if c is not None]
                if valid_closes:
                    price = valid_closes[-1]
                else:
                    raise ValueError("No valid close price found")

            if symbol == "^TNX":
                market_data[name] = f"{price:.3f} 殖利率%"
            else:
                market_data[name] = f"{price:.2f}" if isinstance(price, (int, float)) else str(price)
        except Exception as e:
            print(f"[{symbol}] 抓取失敗: {e}")
            market_data[name] = "Data Unavailable"
    
    # 格式化輸出
    output = ""
    for k, v in market_data.items():
        output += f"- {k}: {v}\n"
    return output

# ==============================================================================
# 2. 呼叫 Gemini REST API 進行總經分析 (具備自動修復功能的版本)
# ==============================================================================
def analyze_with_gemini(news_data, today_str, realtime_data="尚無即時數據"):
    print(f"正在呼叫 Gemini API 進行智能推論 (今日日期: {today_str})...")
    
    if isinstance(news_data, list) and len(news_data) > 0:
        news_text = "\n".join([f"[{item.get('source', '新聞媒體')} | {item.get('pubdate', '')}] {item['title']} (URL: {item['link']})" for item in news_data])
    else:
        news_text = "未能抓取新聞，請基於目前全球總體經濟狀況直接進行推論。"

    # 嘗試讀取現有的 CSV 數據提供給 AI 作為參考 (Context)
    macro_history = "尚無歷史數據"
    try:
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                if len(rows) > 1:
                    macro_history = "\\n".join([",".join(row) for row in rows[-5:]])
    except Exception as e:
        print(f"讀取歷史數據失敗: {e}")
        
    # 定義輸出的 JSON Schema 確保 AI 回傳的結構百分之百合法
    # 🚨 關鍵修正：警告 AI 絕不可在 HTML 內使用雙引號
    prompt = f"""你現在是一位資深的全球總經策略分析師。請根據以下數據與新聞連結進行邏輯推演。

### 🌐 代理人搜尋指令 (Search Grounding):
本次任務中，我們為你啟用了 Google Search Grounding。請務必優先使用該工具，點擊下方【最新新聞頭條】中的 URL，特別鎖定 CNBC, Reuters, 與 Bloomberg 等來源，去閱讀「新聞的全文內容」，而非只依賴標題。這將幫助你取得最新的 Fed 動向與就業/通膨細節。請不要自己寫程式爬網頁，直接利用內建的 Search Grounding 檢索內容。

### 今日日期: {today_str}

### 📊 最新市場即時報價 (絕對精確，請務必參考):
{realtime_data}

### 歷史數據參考:
{macro_history}

### 最新新聞頭條:
{news_text}

### 撰寫指令 (三部曲核心邏輯):
1. **Phase 1 新聞解析 (News Parsing)**: 解析 Fed 利率路徑、通膨 (CPI/PCE) 與就業數據。運用 Search Grounding 補充新聞背後的脈絡。
2. **Phase 2 走勢研判 (Trend Analysis)**: **【核心要求】請詳細研判「十年期公債殖利率」、「美元指數」、「亞洲貨幣 (台幣/日圓)」、「黃金」與「原油」等資產在過去一週（或最近數日）的變化狀況與其背後的驅動邏輯。**
3. **Phase 3 圖表驗證 (Chart Verification)**: 產出結論以對照網頁下方的即時走勢圖。確保你的推論方向符合【最新市場即時報價】的水位。

### 精確報價與防範幻覺 (Data Accuracy): 
   - 🚨 當你在分析中提及具體價格、點位或殖利率時，**必須且只能使用上方【最新市場即時報價】中的數據**。
   - 結合新聞頭條的利多/利空事件進行推演。
   - 絕對禁止憑空捏造上方未提供的數字。對於未提供報價的標的，一律使用「純定性趨勢詞彙」描述（例如：高位震盪、跌破支撐）。

### HTML 格式限制: 
   - 在 next_week_forecast_html 欄位中使用 <details> 標籤與分點結構。
   - 🚨 絕對禁止在 HTML 內容中使用雙引號 (")，所有 class、href 或 style 屬性「必須且只能」使用單引號 (')，否則 JSON 解析會崩潰！

### 輸出格式 (JSON):
請嚴格輸出以下 JSON 格式，不要有任何多餘文字：
{{
  "weekly_narrative": "(約 150 字) 基於市場情緒與 Phase 1、Phase 2 解析撰寫的總經分析摘要，請聚焦於客觀趨勢描述，避開任何主觀投資建議。",
  "focus_items": [ {{
    "category": "事件分類(例:央行政策)",
    "title": "新聞標題",
    "source": "新聞來源",
    "publish_date": "發布時間",
    "price_direction": "物價方向(偏多/偏空/中性)",
    "rate_direction": "利率方向(偏多/偏空/中性)",
    "usd_direction": "美元指數方向(偏多/偏空/中性)",
    "short_summary": "一句話總結",
    "original_summary": "新聞原始摘要",
    "one_sentence_conclusion": "一句話結論",
    "news_summary": "新聞詳細摘要",
    "transmission_path": "傳導路徑",
    "price_reason": "物價變動原因",
    "rate_reason": "利率變動原因",
    "usd_reason": "美元變動原因",
    "original_focus": "原始重點",
    "original_link": "新聞原始連結網址"
  }} ],
  "fx_rates_linkage": "(120 字) Phase 2 走勢研判，拆解利率與匯率的實際傳導。",
  "outlook_risks": [ {{ "title": "...", "content": "..." }}, {{ "title": "...", "content": "..." }} ],
  "analysis": [
    {{ 
      "variable_name": "🔥 通膨預期", 
      "badge_text": "CPI/PPI Outlook", 
      "status": "簡短摘要(例: 能源成本攀升)", 
      "status_detail": "報價數據(例: WTI原油報94.0 USD/bbl)", 
      "trend_class": "trend-up", 
      "trend_text": "...", 
      "drivers": "...", 
      "impact": "..." 
    }},
    {{ 
      "variable_name": "📉 利率預期", 
      "badge_text": "Fed Funds / US10Y", 
      "status": "簡短摘要(例: 殖利率創波段新高)", 
      "status_detail": "報價數據(例: 4.292%)", 
      "trend_class": "trend-up", 
      "trend_text": "...", 
      "drivers": "...", 
      "impact": "..." 
    }},
    {{ 
      "variable_name": "🦅 美元指數", 
      "badge_text": "DXY Strength", 
      "status": "簡短摘要(例: 避險情緒推升)", 
      "status_detail": "報價數據(例: 逼近百元大關)", 
      "trend_class": "trend-up", 
      "trend_text": "...", 
      "drivers": "...", 
      "impact": "..." 
    }}
  ],
  "next_week_forecast_html": "<details class='analysis-container'><summary>📢 下週預測：[主旋律]</summary><div class='analysis-content'><strong>⛓️ 市場邏輯傳導：</strong><p>[因子] ➔ 影響<strong>通膨/利率預期</strong> ➔ 最終定價<strong>美元走勢</strong>。</p><hr><strong>📉 資產動態預測：</strong><ul><li><strong>亞洲貨幣 (TWD/JPY/KRW)：</strong>...</li><li><strong>避險成本與鋼鐵業：</strong>...</li></ul></div></details>",
  "podcast_script": "(約 800 字) 以『各位聽眾大家好，歡迎回到全球總經戰情室...』開場。🚨【嚴格規定】1. 必須分為雙階段播報：第一階段「摘要 CNBC/Reuters 等全網新聞重點」，第二階段「解析市場客觀情緒與走勢研判」。 2. 播報中『絕對不要』提及任何投資建議，也『絕對不要』提及具體的價格或點位數值，以免與網頁產生落差。"
}}
"""
    
    # 更新為 2026 Agentic 2.0 模型
    strategies = [
        ("v1beta", "gemini-3.1-pro-preview"), 
        ("v1beta", "gemini-2.5-pro")
    ]
    
    import time
    for version, model in strategies:
        # 內層重試機制 (針對 503/429)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"-> 嘗試連線方案: {version} / {model} (第 {attempt+1} 次)...")
                url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                # 加入 tools 以啟動 Search Grounding
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "tools": [
                        {
                            "googleSearch": {}
                        }
                    ],
                    "safetySettings": [
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                    ]
                }
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
                
                try:
                    response = urllib.request.urlopen(req, timeout=180)
                    result = json.loads(response.read().decode('utf-8'))
                    
                    # 💡 關鍵修正：增加 API 回傳結構的安全檢查
                    if 'candidates' not in result or not result['candidates']:
                        prompt_feedback = result.get('promptFeedback', {})
                        print(f"   [FAIL] {model} 未產生有效回應 (可能被安全過濾器攔截)。Feedback: {prompt_feedback}")
                        break

                    text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    # 💡 關鍵修正：更強健的 JSON 提取 (支持包含前言或後記的 AI 輸出)
                    start_idx = text.find('{')
                    end_idx = text.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        text = text[start_idx:end_idx+1]
                    
                    # 取代可能在 JSON 內引發解析錯誤的控制字元
                    text = text.replace('\\n', ' ').replace('\\r', '')
                    
                    print(f"[SUCCESS] {model} 回應成功！")
                    return json.loads(text, strict=False)
                except urllib.error.HTTPError as e:
                    error_data = e.read().decode('utf-8')
                    # 如果是 503 (系統忙碌) 或 429 (配額滿)，我們稍微休息一下再試
                    if e.code in [429, 503] and attempt < max_retries - 1:
                        wait_time = 90  # 預設至少等待超過一分鐘
                        if "Please retry in" in error_data:
                            try:
                                import re
                                match = re.search(r"Please retry in (\d+\.\d+)s", error_data)
                                if match:
                                    wait_time = int(float(match.group(1))) + 5
                            except:
                                pass
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
    
    analysis_data = ai_response.get('analysis') or []
    weekly_narrative = ai_response.get('weekly_narrative') or '本週尚無綜合摘要。'
    focus_items = ai_response.get('focus_items') or []
    fx_rates_linkage = ai_response.get('fx_rates_linkage') or '尚無傳導分析。'
    outlook_risks = ai_response.get('outlook_risks') or []
    next_week_forecast_html = ai_response.get('next_week_forecast_html') or ''
    podcast_script = ai_response.get('podcast_script') or '本日尚無語音戰情腳本。'
    
    # 產生 podcast mp3 (使用 edge-tts)
    podcast_filename = "podcast.mp3"
    try:
        import subprocess
        from datetime import datetime
        curr_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        podcast_filename = f"podcast_{curr_time_str}.mp3"
        podcast_path = os.path.join(WORKSPACE_DIR, podcast_filename)
        temp_txt = os.path.join(WORKSPACE_DIR, "temp_podcast.txt")
        with open(temp_txt, "w", encoding="utf-8") as f:
            f.write(podcast_script)
        print(f"正在生成 Podcast 語音檔 ({podcast_filename})...")
        subprocess.run(['edge-tts', '-f', temp_txt, '--voice', 'zh-TW-HsiaoChenNeural', '--write-media', podcast_path], check=True)
        print("🔈 Podcast 語音生成完畢！")
        if os.path.exists(temp_txt):
            os.remove(temp_txt)
            
        # 清理超過 7 天前產生的 podcast_{timestamp}.mp3 檔案
        current_time = datetime.now()
        for f_name in os.listdir(WORKSPACE_DIR):
            if f_name.startswith("podcast_") and f_name.endswith(".mp3"):
                file_path = os.path.join(WORKSPACE_DIR, f_name)
                # 取得檔案最後修改時間
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if (current_time - file_mtime).days > 7:
                    try:
                        os.remove(file_path)
                        print(f"清理過期語音檔: {f_name}")
                    except Exception as ex:
                        print(f"清理過期語音檔失敗: {ex}")
    except Exception as e:
        print(f"⚠️ Podcast 語音生成失敗 (請確認是否安裝 edge-tts): {e}")
    
    # 更新 CSV (維持基本數據結構)
    csv_content = "變數與項目,當前狀態,短期趨勢,主要驅動因素,全球經濟交互影響\n"
    for item in analysis_data:
        drivers = str(item.get('drivers', '')).replace(',', '，')
        impact = str(item.get('impact', '')).replace(',', '，')
        var_name = item.get('variable_name', '')
        status = item.get('status', '')
        status_detail = item.get('status_detail', '')
        trend_text = item.get('trend_text', '')
        csv_content += f"{var_name},{status} {status_detail},{trend_text},{drivers},{impact}\n"
    
    with open(CSV_PATH, "w", encoding="utf-8") as f:
        f.write(csv_content)

    # 準備焦點事件 HTML
    focus_html = ""
    for idx, item in enumerate(focus_items):
        cat = item.get('category', '總經動態')
        title = item.get('title', '無標題')
        source = item.get('source', '網路新聞')
        pubdate = item.get('publish_date', today_str)
        price_dir = item.get('price_direction', '中性')
        rate_dir = item.get('rate_direction', '中性')
        usd_dir = item.get('usd_direction', '中性')
        short_sum = item.get('short_summary', '')
        orig_sum = item.get('original_summary', '')
        one_sent = item.get('one_sentence_conclusion', '')
        news_sum = item.get('news_summary', '')
        trans_path = item.get('transmission_path', '')
        price_rsn = item.get('price_reason', '')
        rate_rsn = item.get('rate_reason', '')
        usd_rsn = item.get('usd_reason', '')
        orig_focus = item.get('original_focus', '')
        orig_link = item.get('original_link', '#')
        
        focus_html += f"""
        <div class="news-detail-card">
            <div class="nd-header">
                <span class="nd-category">{cat}</span>
                <h3 class="nd-title">{title}</h3>
                <div class="nd-meta">{source} | 發布 {pubdate}</div>
                <div class="nd-pills">
                    <span class="nd-pill">物價{price_dir}</span>
                    <span class="nd-pill">利率{rate_dir}</span>
                    <span class="nd-pill">美元{usd_dir}</span>
                </div>
                <div class="nd-short-summary">{short_sum}</div>
            </div>
            <details class="nd-details">
                <summary></summary>
                <div class="nd-content">
                    <div class="nd-orig-summary">{orig_sum}</div>
                    <div class="nd-meta-tags">
                        <span>新聞來源: {source}</span>
                        <span>新聞發布時間: {pubdate}</span>
                        <span>分析執行時間: {today_str}</span>
                        <span>事件分類: {cat}</span>
                    </div>
                    <div class="nd-directions">
                        <div class="nd-dir-box"><div class="nd-dir-label">物價方向</div><div class="nd-dir-value">{price_dir}</div></div>
                        <div class="nd-dir-box"><div class="nd-dir-label">利率方向</div><div class="nd-dir-value">{rate_dir}</div></div>
                        <div class="nd-dir-box"><div class="nd-dir-label">美元指數方向</div><div class="nd-dir-value">{usd_dir}</div></div>
                    </div>
                    <div class="nd-conclusion">
                        <div class="nd-box-title">一句話結論</div>
                        <p>{one_sent}</p>
                    </div>
                    <div class="nd-grid">
                        <div class="nd-grid-box">
                            <div class="nd-box-title">新聞摘要</div>
                            <p>{news_sum}</p>
                        </div>
                        <div class="nd-grid-box">
                            <div class="nd-box-title">傳導路徑</div>
                            <p>{trans_path}</p>
                        </div>
                        <div class="nd-grid-box">
                            <div class="nd-box-title">物價原因</div>
                            <p>{price_rsn}</p>
                        </div>
                        <div class="nd-grid-box">
                            <div class="nd-box-title">利率原因</div>
                            <p>{rate_rsn}</p>
                        </div>
                        <div class="nd-grid-box">
                            <div class="nd-box-title">美元原因</div>
                            <p>{usd_rsn}</p>
                        </div>
                        <div class="nd-grid-box">
                            <div class="nd-box-title">原始重點</div>
                            <p>{orig_focus}</p>
                            <a href="{orig_link}" target="_blank" class="nd-btn">查看原文</a>
                        </div>
                    </div>
                </div>
            </details>
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
        var_name = item.get('variable_name', '')
        badge = item.get('badge_text', '')
        status = item.get('status', '')
        status_det = item.get('status_detail', '')
        trend = item.get('trend_text', '')
        trend_icon = item.get('trend_icon', '')
        drivers = item.get('drivers', '')
        
        tbody_html += f"""
                <tr>
                    <td data-label="核心變數">
                        <div class="var-name">{var_name}</div>
                        <span class="badge">{badge}</span>
                    </td>
                    <td data-label="當前狀態"><div class="status">{status} <span class="status-detail">{status_det}</span></div></td>
                    <td data-label="趨勢"><span class="{trend_class} {trend_icon}">{trend}</span></td>
                    <td data-label="驅動因素" class="desc-text">{drivers}</td>
                </tr>"""

    # 尋找最新的週報影片 (僅週四才帶入影片連結，與影片產製排程一致)
    weekly_video_filename = ""
    try:
        from datetime import timezone, timedelta
        tw_tz = timezone(timedelta(hours=8))
        now_tw = datetime.now(tw_tz)
        # 週四 = weekday() 3
        is_thursday = (now_tw.weekday() == 3)
        
        if is_thursday:
            video_files = [f for f in os.listdir(WORKSPACE_DIR) if f.startswith("weekly_video_") and f.endswith(".mp4")]
            if video_files:
                video_files.sort(reverse=True)
                weekly_video_filename = video_files[0]
                print(f"📹 今天是週四，載入本週影片: {weekly_video_filename}")
        else:
            print(f"📅 今天是星期 {now_tw.weekday() + 1}（非週四），不載入影片連結。")
    except Exception as e:
        pass

    # === 歷史資料存檔 (保留過去 7 天) ===
    historical_data = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                historical_data = json.load(f)
        except:
            pass
            
    today_pack = {
        "date": today_str,
        "weekly_narrative": weekly_narrative,
        "next_week_forecast_html": next_week_forecast_html,
        "focus_html": focus_html,
        "fx_rates_linkage": fx_rates_linkage,
        "tbody_html": tbody_html,
        "risk_html": risk_html,
        "news_html": news_html,
        "podcast_file": podcast_filename,
        "weekly_video": weekly_video_filename
    }
    
    # 若當日(取日期前綴)已存在則更新，否則新增於最前面
    existing_idx = next((i for i, v in enumerate(historical_data) if v["date"].split()[0] == today_str.split()[0]), None)
    if existing_idx is not None:
        historical_data[existing_idx] = today_pack
    else:
        historical_data.insert(0, today_pack)
        
    # 強制依日期由新到舊排序 (防呆機制，確保最新的一定在最前面)
    historical_data.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    # 保留前 7 筆 (最舊的第 8 筆會被自動淘汰)
    historical_data = historical_data[:7]
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(historical_data, f, ensure_ascii=False, indent=2)

    html_template = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>【全球總經報導】宏觀趨勢與資產配置分析</title>
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
        
        .trend-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin-bottom: 3rem; }}
        .trend-card {{ background: #fff; border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem; box-shadow: var(--shadow-md); min-height: 550px; display: flex; flex-direction: column; }}
        .trend-card h4 {{ font-size: 1.05rem; font-weight: 700; color: var(--text-secondary); margin-bottom: 0.8rem; text-align: center; }}
        .trend-widget-container {{ flex-grow: 1; width: 100%; height: 500px; }}

        .focus-grid {{ display: flex; flex-direction: column; gap: 1rem; margin-bottom: 3rem; }}
        .news-detail-card {{ background: #fff; border: 1px solid #edf2f7; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 10px rgba(0,0,0,0.02); }}
        .nd-category {{ background: #e0f2fe; color: #0284c7; padding: 0.2rem 0.8rem; border-radius: 20px; font-size: 0.85rem; font-weight: 600; display: inline-block; margin-bottom: 0.8rem; }}
        .nd-title {{ font-size: 1.3rem; font-weight: 700; color: #1e293b; margin-bottom: 0.5rem; line-height: 1.4; }}
        .nd-meta {{ font-size: 0.85rem; color: #64748b; margin-bottom: 1rem; }}
        .nd-pills {{ display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; }}
        .nd-pill {{ background: #64748b; color: #fff; padding: 0.2rem 0.8rem; border-radius: 20px; font-size: 0.8rem; font-weight: 500; }}
        .nd-short-summary {{ font-size: 1.05rem; color: #334155; margin-bottom: 0.5rem; }}
        .nd-details summary {{ color: #0284c7; font-weight: 600; cursor: pointer; list-style: none; font-size: 0.95rem; outline: none; margin-top: 0.5rem; display: inline-block; }}
        .nd-details summary::-webkit-details-marker {{ display: none; }}
        .nd-details summary::before {{ content: "展開詳情 ▼"; }}
        .nd-details[open] summary::before {{ content: "收合詳情 ▲"; }}
        .nd-content {{ margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid #edf2f7; }}
        .nd-orig-summary {{ font-size: 1.05rem; color: #475569; margin-bottom: 1.5rem; }}
        .nd-meta-tags {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.5rem; }}
        .nd-meta-tags span {{ background: #f8fafc; border: 1px solid #e2e8f0; color: #64748b; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem; }}
        .nd-directions {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }}
        .nd-dir-box {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; text-align: left; }}
        .nd-dir-label {{ font-size: 0.85rem; color: #64748b; margin-bottom: 0.5rem; }}
        .nd-dir-value {{ font-size: 1.5rem; font-weight: 700; color: #64748b; }}
        .nd-conclusion {{ background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 1.2rem; margin-bottom: 1.5rem; }}
        .nd-box-title {{ font-size: 0.9rem; font-weight: 700; color: #0284c7; margin-bottom: 0.5rem; }}
        .nd-conclusion p {{ font-size: 1.05rem; color: #0f172a; font-weight: 500; }}
        .nd-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
        .nd-grid-box {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.2rem; display: flex; flex-direction: column; }}
        .nd-grid-box p {{ font-size: 0.95rem; color: #334155; flex-grow: 1; }}
        .nd-btn {{ display: inline-block; background: #0284c7; color: #fff; text-decoration: none; padding: 0.5rem 1rem; border-radius: 6px; font-size: 0.9rem; font-weight: 600; align-self: flex-start; margin-top: 1rem; }}
        .nd-btn:hover {{ background: #0369a1; }}

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
        .var-name {{ font-weight: 700; color: var(--text-primary); margin-bottom: 0.2rem; }}
        .badge {{ font-size: 0.75rem; background: #f1f5f9; padding: 3px 8px; border-radius: 4px; color: #64748b; display: inline-block; white-space: nowrap; }}
        .trend-up {{ color: var(--up-color); font-weight: 600; }}
        .trend-down {{ color: var(--down-color); font-weight: 600; }}
        .status {{ font-weight: 600; color: var(--text-primary); }}
        .status-detail {{ display: block; font-size: 0.9rem; font-weight: 400; color: #475569; margin-top: 0.4rem; line-height: 1.5; }}
        
        /* 專業分析收合方塊樣式 */
        .analysis-container {{
            margin: 20px 0;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background: #ffffff;
            overflow: hidden;
            box-shadow: var(--shadow-md);
        }}

        .analysis-container summary {{
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
        }}

        .analysis-container[open] summary {{
            border-bottom: 1px solid #edf2f7;
            background: #ffffff;
        }}

        /* 自定義小箭頭 */
        .analysis-container summary::after {{
            content: "▼";
            font-size: 0.8rem;
            color: var(--text-secondary);
            transition: transform 0.3s ease;
        }}

        .analysis-container[open] summary::after {{
            transform: rotate(180deg);
        }}

        .analysis-content {{
            padding: 1.5rem 2rem;
            line-height: 1.8;
            color: #334155;
            background: #ffffff;
        }}
        .analysis-content hr {{ border: 0; border-top: 1px solid #f1f5f9; margin: 1.5rem 0; }}
        .analysis-content ul {{ padding-left: 20px; }}
        .analysis-content li {{ margin-bottom: 10px; }}
        .analysis-content strong {{ color: var(--accent-color); }}

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
        .news-item a {{ text-decoration: none; color: var(--accent-color); font-size: 0.95rem; font-weight: 500; transition: color 0.2s; }}
        .news-item a:hover {{ text-decoration: underline; color: #1e3a8a; }}

        .podcast-container {{ margin-top: 1.5rem; background: #f8fafc; padding: 1rem 1.5rem; border-radius: 50px; display: inline-flex; align-items: center; gap: 1rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; max-width: 100%; }}
        .podcast-icon {{ font-size: 2rem; flex-shrink: 0; }}
        .podcast-text {{ text-align: left; line-height: 1.3; }}
        .podcast-title {{ font-weight: 700; font-size: 1.1rem; color: #1e293b; }}
        .podcast-subtitle {{ font-size: 0.9rem; color: #64748b; margin-top: 0.2rem; }}
        .podcast-audio-element {{ height: 40px; outline: none; margin-left: 0.5rem; max-width: 100%; }}

        @media (max-width: 768px) {{
            .nd-directions {{ grid-template-columns: 1fr; }}
            .nd-grid {{ grid-template-columns: 1fr; }}
            .newsletter-wrapper {{ padding: 2rem 1.5rem; }}
            .risk-grid {{ grid-template-columns: 1fr; }}
            table, thead, tbody, th, td, tr {{ display: block; }}
            thead {{ display: none; }}
            tr {{ margin-bottom: 1.5rem; border: 1px solid #edf2f7; padding: 1rem; }}
            td {{ padding: 0.5rem 0; border: none; }}
            td::before {{ content: attr(data-label); font-weight: 600; color: #94a3b8; display: block; font-size: 0.8rem; }}
            .podcast-container {{ flex-direction: column; border-radius: 20px; padding: 1.5rem 1rem; gap: 0.8rem; }}
            .podcast-text {{ text-align: center; }}
            .podcast-audio-element {{ margin-left: 0; width: 100%; }}
        }}

    </style>
</head>
<body>
    <div class="newsletter-wrapper">
        <header class="report-header">
            <span class="date">GLOBAL MACRO WEEKLY INSIGHTS</span>
            <h1>全球總經報導 <span style="font-size: 0.8rem; color: #94a3b8; font-weight: 400;">[PRO-ENGINE V3.0]</span></h1>
            <p style="color: #94a3b8;">由 AI 驅動的自動化全域分析 (Rolling 48-Hour Window)</p>
            <p style="font-size: 1rem; color: #ef4444; font-weight: 800; margin-top: 0.5rem; text-decoration: underline;" class="date-display">🕒 最後更新時間：{today_str}</p>
            
            <!-- 日期選單與狀態列 -->
            <div style="margin-top: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px;">
                <label for="history-selector" style="font-weight: 600; color: #475569;">📅 歷史回顧：</label>
                <select id="history-selector" style="padding: 0.5rem; border-radius: 4px; border: 1px solid #cbd5e1; outline: none; font-family: inherit; font-size: 0.95rem; background: #fffcf0;">
                    <option value="0">{today_str} (最新)</option>
                </select>
            </div>
            
            <!-- Podcast 播放器 -->
            <div class="podcast-container">
                <span class="podcast-icon">🎙️</span>
                <div class="podcast-text">
                    <div class="podcast-title">全域總經戰情室廣播</div>
                    <div class="podcast-subtitle">AI 主播 | 每日精準解析</div>
                </div>
                <audio id="podcast-audio" class="podcast-audio-element" controls>
                    <source src="{podcast_filename}" type="audio/mpeg">
                    您的瀏覽器不支援音訊元素。
                </audio>
            </div>
            
            <!-- 每週回顧影片 (若存在) -->
            <div id="weekly-video-container" style="margin-top: 1.5rem; display: {'block' if weekly_video_filename else 'none'};">
                <div style="background: #fffcf0; padding: 1rem; border-radius: 12px; border: 1px solid #fef3c7; box-shadow: var(--shadow-md);">
                    <h3 style="font-size: 1.1rem; color: #92400e; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
                        <span>🎬</span> 本週總經動態回顧影片
                    </h3>
                    <video id="weekly-video-player" controls style="width: 100%; border-radius: 8px; max-height: 400px; background: #000;">
                        <source src="{weekly_video_filename}" type="video/mp4">
                        您的瀏覽器不支援影片元素。
                    </video>
                </div>
            </div>

            <div style="margin-top: 1.5rem;" class="tradingview-widget-container"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>{{"symbols": [ {{"proName": "FOREXCOM:SPXUSD", "title": "S&P 500"}}, {{"proName": "FOREXCOM:NSXUSD", "title": "Nasdaq 100"}}, {{"proName": "FX_IDC:EURUSD", "title": "EUR/USD"}}, {{"proName": "FX:USDJPY", "title": "USD/JPY"}}, {{"proName": "FX_IDC:USDTWD", "title": "USD/TWD"}}, {{"proName": "SGX:FEF1!", "title": "Iron Ore"}}, {{"proName": "OTC:NPSCY", "title": "Nippon Steel"}}, {{"proName": "NYSE:NUE", "title": "Nucor"}}, {{"proName": "FRED:DGS10", "title": "US10Y"}} ], "showSymbolLogo": true, "colorTheme": "light", "isTransparent": true, "displayMode": "adaptive", "locale": "zh_TW"}}</script></div>
        </header>

        <section>
            <h2 class="section-h2">🎯 新聞剖析</h2>
            <div class="focus-grid" id="focus-grid">
                {focus_html}
            </div>
        </section>

        <section>
            <h2 class="section-h2">📻 總經分析</h2>
            <div class="narrative-box" id="narrative-box">
                {weekly_narrative}
            </div>
            <div id="forecast-box">{next_week_forecast_html}</div>
        </section>

        <section>
            <h2 class="section-h2">📈 宏觀指標動態走勢</h2>
            <div class="trend-grid">
                <div class="trend-card">
                    <h4>US 10Y Yield (十年期公債)</h4>
                    <div class="trend-widget-container" style="height: 500px; width: 100%;"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>{{"symbols": [["美國十年期公債", "FRED:DGS10"]], "chartOnly": false, "width": "100%", "height": "100%", "locale": "zh_TW", "colorTheme": "light", "autosize": true, "showVolume": false, "showMA": false, "hideDateRanges": false, "hideMarketStatus": false, "hideSymbolLogo": false, "scalePosition": "right", "scaleMode": "Normal", "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif", "fontSize": "10", "noTimeScale": false, "valuesTracking": "1", "changeMode": "price-and-percent", "chartType": "area", "lineWidth": 2, "lineType": 0, "dateRanges": ["12m|1D", "60m|1W", "all|1M"], "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>Dollar Index (美元指數)</h4>
                    <div class="trend-widget-container" style="height: 500px; width: 100%;"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>{{"symbols": [["美元指數", "CAPITALCOM:DXY"]], "chartOnly": false, "width": "100%", "height": "100%", "locale": "zh_TW", "colorTheme": "light", "autosize": true, "showVolume": false, "showMA": false, "hideDateRanges": false, "hideMarketStatus": false, "hideSymbolLogo": false, "scalePosition": "right", "scaleMode": "Normal", "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif", "fontSize": "10", "noTimeScale": false, "valuesTracking": "1", "changeMode": "price-and-percent", "chartType": "area", "lineWidth": 2, "lineType": 0, "dateRanges": ["1m|30", "3m|60", "12m|1D", "60m|1W", "all|1M"], "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>Gold Spot (黃金)</h4>
                    <div class="trend-widget-container" style="height: 500px; width: 100%;"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>{{"symbols": [["TVC:GOLD|1M"]], "chartOnly": false, "width": "100%", "height": "100%", "locale": "zh_TW", "colorTheme": "light", "autosize": true, "showVolume": false, "showMA": false, "hideDateRanges": false, "hideMarketStatus": false, "hideSymbolLogo": false, "scalePosition": "right", "scaleMode": "Normal", "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif", "fontSize": "10", "noTimeScale": false, "valuesTracking": "1", "changeMode": "price-and-percent", "chartType": "area", "lineWidth": 2, "lineType": 0, "dateRanges": ["1m|30", "3m|60", "12m|1D", "60m|1W", "all|1M"], "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>WTI Crude (西德州原油)</h4>
                    <div class="trend-widget-container" style="height: 500px; width: 100%;"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>{{"symbols": [["原油期貨 (WTI)", "TVC:USOIL|1M"]], "chartOnly": false, "width": "100%", "height": "100%", "locale": "zh_TW", "colorTheme": "light", "autosize": true, "showVolume": false, "showMA": false, "hideDateRanges": false, "hideMarketStatus": false, "hideSymbolLogo": false, "scalePosition": "right", "scaleMode": "Normal", "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif", "fontSize": "10", "noTimeScale": false, "valuesTracking": "1", "changeMode": "price-and-percent", "chartType": "area", "lineWidth": 2, "lineType": 0, "dateRanges": ["1m|30", "3m|60", "12m|1D", "60m|1W", "all|1M"], "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>Brent Crude (布蘭特原油)</h4>
                    <div class="trend-widget-container" style="height: 500px; width: 100%;"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>{{"symbols": [["布蘭特原油", "TVC:UKOIL|1M"]], "chartOnly": false, "width": "100%", "height": "100%", "locale": "zh_TW", "colorTheme": "light", "autosize": true, "showVolume": false, "showMA": false, "hideDateRanges": false, "hideMarketStatus": false, "hideSymbolLogo": false, "scalePosition": "right", "scaleMode": "Normal", "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif", "fontSize": "10", "noTimeScale": false, "valuesTracking": "1", "changeMode": "price-and-percent", "chartType": "area", "lineWidth": 2, "lineType": 0, "dateRanges": ["1m|30", "3m|60", "12m|1D", "60m|1W", "all|1M"], "isTransparent": true}}</script></div>
                </div>
                <!-- 亞洲貨幣 -->
                <div class="trend-card">
                    <h4>USD / JPY (美元/日圓)</h4>
                    <div class="trend-widget-container" style="height: 500px; width: 100%;"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>{{"symbols": [["FX:USDJPY|1M"]], "chartOnly": false, "width": "100%", "height": "100%", "locale": "zh_TW", "colorTheme": "light", "autosize": true, "showVolume": false, "showMA": false, "hideDateRanges": false, "hideMarketStatus": false, "hideSymbolLogo": false, "scalePosition": "right", "scaleMode": "Normal", "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif", "fontSize": "10", "noTimeScale": false, "valuesTracking": "1", "changeMode": "price-and-percent", "chartType": "area", "lineWidth": 2, "lineType": 0, "dateRanges": ["1m|30", "3m|60", "12m|1D", "60m|1W", "all|1M"], "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>USD / TWD (美元/台幣)</h4>
                    <div class="trend-widget-container" style="height: 500px; width: 100%;"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>{{"symbols": [["FX_IDC:USDTWD|1M"]], "chartOnly": false, "width": "100%", "height": "100%", "locale": "zh_TW", "colorTheme": "light", "autosize": true, "showVolume": false, "showMA": false, "hideDateRanges": false, "hideMarketStatus": false, "hideSymbolLogo": false, "scalePosition": "right", "scaleMode": "Normal", "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif", "fontSize": "10", "noTimeScale": false, "valuesTracking": "1", "changeMode": "price-and-percent", "chartType": "area", "lineWidth": 2, "lineType": 0, "dateRanges": ["1m|30", "3m|60", "12m|1D", "60m|1W", "all|1M"], "isTransparent": true}}</script></div>
                </div>
                <div class="trend-card">
                    <h4>USD / KRW (美元/韓元)</h4>
                    <div class="trend-widget-container" style="height: 500px; width: 100%;"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js" async>{{"symbols": [["FX_IDC:USDKRW|1M"]], "chartOnly": false, "width": "100%", "height": "100%", "locale": "zh_TW", "colorTheme": "light", "autosize": true, "showVolume": false, "showMA": false, "hideDateRanges": false, "hideMarketStatus": false, "hideSymbolLogo": false, "scalePosition": "right", "scaleMode": "Normal", "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif", "fontSize": "10", "noTimeScale": false, "valuesTracking": "1", "changeMode": "price-and-percent", "chartType": "area", "lineWidth": 2, "lineType": 0, "dateRanges": ["1m|30", "3m|60", "12m|1D", "60m|1W", "all|1M"], "isTransparent": true}}</script></div>
                </div>
            </div>
        </section>



        <section style="display: none;">
            <h2 class="section-h2">⛓️ 利率與匯率傳導矩陣</h2>
            <div class="deep-dive-box">
                <h3>Macro Linkage Analysis</h3>
                <div id="linkage-box">{fx_rates_linkage}</div>
            </div>
        </section>

        <section style="display: none;">
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
                    <tbody id="tbody-html">
                        {tbody_html}
                    </tbody>
                </table>
            </div>
        </section>

        <section style="display: none;">
            <h2 class="section-h2">🧭 下週風險預警</h2>
            <div class="risk-grid" id="risk-grid">
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
                <summary>查看本週參考新聞原文 (動態更新)</summary>
                <ul class="news-list" id="news-list">
                    {news_html}
                </ul>
            </details>
            <p style="text-align: center; color: #cbd5e1; font-size: 0.8rem; margin-top: 2rem;">© 2026 Macro Strategy Lab. 最後更新：<span class="date-display">{today_str}</span></p>
        </footer>
    </div>
    <script>
    // 歷史資料切換邏輯
    document.addEventListener('DOMContentLoaded', async () => {{
        try {{
            // 加上時間戳防止快取
            const response = await fetch('historical_data.json?t=' + new Date().getTime());
            if (!response.ok) return;
            const data = await response.json();
            const selector = document.getElementById('history-selector');
            
            // 重新填寫選項
            selector.innerHTML = '';
            data.forEach((item, idx) => {{
                const option = document.createElement('option');
                option.value = idx;
                option.textContent = item.date + (idx === 0 ? ' (最新)' : '');
                selector.appendChild(option);
            }});

            // 綁定選單事件
            selector.addEventListener('change', (e) => {{
                const selectedItem = data[e.target.value];
                if (!selectedItem) return;
                
                // 動態替換各區塊內容
                document.getElementById('narrative-box').innerHTML = selectedItem.weekly_narrative;
                document.getElementById('forecast-box').innerHTML = selectedItem.next_week_forecast_html || '';
                document.getElementById('focus-grid').innerHTML = selectedItem.focus_html;
                document.getElementById('linkage-box').innerHTML = selectedItem.fx_rates_linkage;
                document.getElementById('tbody-html').innerHTML = selectedItem.tbody_html;
                document.getElementById('risk-grid').innerHTML = selectedItem.risk_html;
                document.getElementById('news-list').innerHTML = selectedItem.news_html;
                
                // 動態更新 Podcast 音訊來源
                const audioPlayer = document.getElementById('podcast-audio');
                const audioSource = audioPlayer.querySelector('source');
                const newSrc = selectedItem.podcast_file || 'podcast.mp3';
                if (!audioSource.src.endsWith(newSrc)) {{
                    audioSource.src = newSrc;
                    audioPlayer.load();
                }}
                
                // 動態更新影片來源
                const videoContainer = document.getElementById('weekly-video-container');
                const videoPlayer = document.getElementById('weekly-video-player');
                const videoSource = videoPlayer.querySelector('source');
                if (selectedItem.weekly_video) {{
                    videoContainer.style.display = 'block';
                    if (!videoSource.src.endsWith(selectedItem.weekly_video)) {{
                        videoSource.src = selectedItem.weekly_video;
                        videoPlayer.load();
                    }}
                }} else {{
                    videoContainer.style.display = 'none';
                }}
                
                // 更新時間戳記
                document.querySelectorAll('.date-display').forEach(el => el.textContent = selectedItem.date);
            }});
        }} catch (error) {{
            console.log('無法載入歷史資料:', error);
        }}
    }});
    </script>
</body>
</html>"""

    # 加入全台統一時區標記 (方便在原始碼檢查是否更新)
    html_template += f"\n<!-- Build Trace (TPE): {today_str} -->"

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
            realtime_data = fetch_realtime_data()
            ai_response = analyze_with_gemini(news_list, today_str, realtime_data)
            
            # 安全性檢查：確保 AI 回傳內容正確
            if ai_response and isinstance(ai_response, dict) and 'analysis' in ai_response:
                update_dashboard(ai_response, news_list, today_str)
                print(f"\n[OK] 雲端戰情室更新腳本執行完畢 (更新時間: {today_str})。")
            else:
                print("\n[ERROR] AI 回傳內容格式不全，已中斷更新。")
                import sys
                sys.exit(1)
            
    except Exception as e:
        import traceback
        print(f"\n[CRASH] 程式發生未預期錯誤: {e}")
        traceback.print_exc()
        import sys
        sys.exit(1)
