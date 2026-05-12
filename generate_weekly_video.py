import os
import sys
import json
import urllib.request
import urllib.error
import csv
import subprocess
from datetime import datetime, timedelta, timezone

import sys
import os
if r"D:\Lib\site-packages" not in sys.path:
    sys.path.append(r"D:\Lib\site-packages")
os.environ["PYTHONPATH"] = r"D:\Lib\site-packages"

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
except ImportError:
    print("請先安裝 pillow: pip install pillow")
    sys.exit(1)

# ==============================================================================
# 系統設定區
# ==============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "historical_data.json")

# 設定台灣時區
tw_tz = timezone(timedelta(hours=8))
now_tw = datetime.now(tw_tz)

# 只在每週四執行 (0=週一, 1=週二, 2=週三, 3=週四)
# 如果設定強制執行參數，則略過檢查
FORCE_RUN = len(sys.argv) > 1 and sys.argv[1] == "--force"

if now_tw.weekday() != 3 and not FORCE_RUN:
    print(f"今天不是星期四 (今天是星期 {now_tw.weekday() + 1})，跳過週報影片生成。")
    sys.exit(0)

print("====== 開始產製每週總經回顧影片 (Weekly Summary Video) ======")

if not GEMINI_API_KEY:
    print("[錯誤] 找不到 GEMINI_API_KEY 環境變數，無法產製腳本。")
    sys.exit(1)

# 讀取歷史資料
historical_data = []
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            historical_data = json.load(f)
    except Exception as e:
        print(f"讀取歷史資料失敗: {e}")

if not historical_data:
    print("尚無足夠的歷史資料來生成週報影片。")
    sys.exit(0)

# 整理過去一週的素材
recent_history = historical_data[:7]
latest_narrative = recent_history[0].get('weekly_narrative', '市場動態觀察')
# 試著從 JSON 抓取風險提示，如果沒有就給預設值
risk_items = recent_history[0].get('risk_warning', '注意下週市場波動')

history_text = "【過去一週每日重點摘要】\n"
for item in recent_history:
    history_text += f"日期：{item.get('date', '')}\n"
    history_text += f"主旋律摘要：{item.get('weekly_narrative', '')}\n"
    # 簡單清理 HTML 標籤
    focus_raw = item.get('focus_html', '').replace('<div class="focus-card">', '').replace('</div>', '').replace('<h4>', '[').replace('</h4>', '] ')
    import re
    focus_clean = re.sub(r'<[^>]+>', '', focus_raw).strip()
    history_text += f"關鍵事件：{focus_clean}\n\n"

today_str = now_tw.strftime("%Y-%m-%d")

# ==============================================================================
# 1. 呼叫 Gemini 生成 5 分鐘週報專屬腳本
# ==============================================================================
# ==============================================================================
# 1. 呼叫 Gemini 生成「雙主播對談」腳本
# ==============================================================================
print("正在請 AI 撰寫 Tom 與 Miranda 的雙主播回顧腳本...")

prompt = f"""你現在要為一個高品質財經 Podcast 撰寫「Voice-first 純語音腳本」。

這個腳本是為「耳朵」設計的，不是為「眼睛」設計的。

━━━━━━━━━━━━━━━━━━━━
【角色設定】
━━━━━━━━━━━━━━━━━━━━
[Tom]：節目主持人，風格接近 Bloomberg Odd Lots 的 Tracy Alloway。
  - 有自己的觀點，不是提問機器
  - 負責開場 + 每個話題之間的自然轉場
  - 轉場靠追問或感想，不靠喊段落名稱
  - 範例轉場：「不過講到這裡，如果油價一直維持高檔，接下來最麻煩的還是通膨問題吧？」
  - 範例轉場：「既然通膨壓力還在，那央行現在應該很頭痛？」
  - 範例轉場：「如果市場開始重新定價利率，那資產價格接下來怎麼看？」

[Miranda]：資深總經策略師，風格接近 Macro Voices / Real Vision 的分析師受訪者。
  - hedge fund macro strategist 語氣
  - 談市場在信什麼 narrative、資金 positioning、情緒變化
  - 保留不確定空間，不說「市場一定會...」
  - 數字要有脈絡，不直接列數字清單

━━━━━━━━━━━━━━━━━━━━
【本期素材】
━━━━━━━━━━━━━━━━━━━━
日期：{today_str}

過去一週市場摘要：
{history_text}

━━━━━━━━━━━━━━━━━━━━
【🚨 VOICE-FIRST 絕對禁止清單 🚨】
━━━━━━━━━━━━━━━━━━━━
以下內容「絕對不能」出現在腳本的任何角色台詞中：

✗ 禁止輸出段落標題或編號（例：(1)、（一）、第一點）
✗ 禁止讓任何角色唸出章節名稱（例：「全球市場主旋律」「物價與通膨趨勢」「央行與利率動向」「美元與匯率走勢」「關鍵風險與展望」）
✗ 禁止 Markdown 符號（** # ## ---）
✗ 禁止旁白式結構標記（例：[場景切換]、[第二段]）
✗ 禁止免責聲明長段（末尾一句即可）
✗ 禁止播報式開場（例：「各位聽眾大家好，歡迎回到...」）

★ 開場要求（必須）：
Tom 的第一句話必須簡短交代「今天是幾月幾日」+「這週整體市場氛圍一句話定調」，約 2-3 句，
然後自然帶出今天最核心的議題，再邀請 Miranda 展開分析。
範例開場風格：「這週的市場，老實說比我預期的更複雜。Miranda，你怎麼看這週整體的市場情緒？」

━━━━━━━━━━━━━━━━━━━━
【敘事邊界許可表（Narrative Architecture）】
━━━━━━━━━━━━━━━━━━━━
每個段落只負責「回答一個核心問題」。下一段的核心內容必須留到下一段才講。

§1 全球市場主旋律
  ✅ 可談：本週盤面情緒、資金風險偏好、市場在交易什麼 narrative、恐慌/貪婪指標
  ❌ 不可深入：具體通膨數字、央行決策、匯率走勢
  🔗 段尾 Hook：Tom 以一句話引出通膨疑問（「但如果這種情緒是對通膨重燃的恐懼，那接下來最直接的問題就是...」）

§2 物價與通膨趨勢
  ✅ 可談：能源/食品通膨、CPI/PCE數據、薪資通膨、市場通膨預期
  ❌ 不可深入：Fed/ECB 的利率決策、政策利率走向（可「點到為止」提一句，但不展開）
  🔗 段尾 Hook：Tom 以一句話引出央行難題（「那央行現在面對這個數字，應該很頭痛吧？」）

§3 央行與利率動向
  ✅ 可談：Fed/ECB/BOJ 的政策訊號、利率路徑、殖利率曲線、鷹鴿之爭
  ❌ 不可深入：美元指數走勢、黃金原油具體表現
  🔗 段尾 Hook：Tom 以一句話引出資產定價（「如果市場開始重新定價利率，那資產端接下來會怎麼反應？」）

§4 美元與關鍵資產走勢
  ✅ 可談：美元指數、黃金、原油、台幣/日圓/亞幣、資金流向
  ❌ 不可深入：下週具體事件預告
  🔗 段尾 Hook：Tom 以一句話帶出下週風險（「那接下來有哪些數據或事件是真正需要盯緊的？」）

§5 下週風險預警與展望
  ✅ 可談：下週重要數據/事件、尾部風險、市場需觀察的關鍵訊號
  ✅ 結尾：Miranda 自然收尾並帶出免責一句

━━━━━━━━━━━━━━━━━━━━
【寫作準則】
━━━━━━━━━━━━━━━━━━━━
- 市場情緒層：談交易 desk 感受、避險需求、positioning 變化
- 不確定性語氣：「市場看起來像是...」「資金似乎正在...」「這可能意味著...」
- 數字密度：單段不超過兩組具體數字，其餘用「高位震盪」「大幅回落」等定性詞
- 每段結尾由 Tom 拋出 Hook 問題，Miranda 在下一段開頭自然接起

━━━━━━━━━━━━━━━━━━━━
【輸出格式（唯一允許格式）】
━━━━━━━━━━━━━━━━━━━━
每行嚴格遵循：
[Tom]: (台詞)
[Miranda]: (台詞)

★ Section 路標（必須嵌入，每個只用一次）：
在對話自然轉入下一個主題的那一行「之前」，獨立插入一個路標行：
[SECTION:1]   ← 開場與全球市場主旋律開始時插入（第一行之前）
[SECTION:2]   ← 對話自然進入通膨/物價主題時插入
[SECTION:3]   ← 對話自然進入央行/利率主題時插入
[SECTION:4]   ← 對話自然進入美元/匯率/資產主題時插入
[SECTION:5]   ← 對話自然進入下週展望/風險主題時插入

路標規則：
- 路標是獨立的一行，不是對白的一部分
- 每個數字只能出現一次，且必須按 1→2→3→4→5 順序
- 路標本身不會被唸出，只是程式辨識用的隱藏標記

總長約 1500 字。輸出的每一行都必須是可以直接 TTS 朗讀的自然語句。
"""

script_text = ""
strategies = [("v1beta", "gemini-3.1-pro-preview"), ("v1beta", "gemini-2.5-pro")]

import time, re
success = False

script_cache_path = os.path.join(WORKSPACE_DIR, "temp_script.txt")
if os.path.exists(script_cache_path) and time.time() - os.path.getmtime(script_cache_path) < 3600:
    print("-> 讀取已快取的腳本內容 (一小時內有效)，避免重複耗費 API 額度。")
    with open(script_cache_path, "r", encoding="utf-8") as f:
        script_text = f.read()
    success = True

if not success:
    for version, model in strategies:
        if success: break
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"-> 嘗試連線方案：{version} / {model} (第 {attempt + 1} 次)...")
                url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                data = {"contents": [{"parts": [{"text": prompt}]}]}
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
                response = urllib.request.urlopen(req, timeout=180)
                result = json.loads(response.read().decode('utf-8'))
                script_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                print(f"[SUCCESS] {model} 腳本生成成功!")
                with open(script_cache_path, "w", encoding="utf-8") as f:
                    f.write(script_text)
                success = True
                break
            except Exception as e:
                print(f"   [FAIL] {model} 錯誤: {e}")
                time.sleep(5)

if not success:
    print("❌ 腳本生成失敗")
    sys.exit(1)

# ==============================================================================
# 2. 解析腳本 → 提取 [SECTION:N] 路標 + 組建 dialogue_parts
# ==============================================================================
print("正在解析腳本與 Section 路標...")

# ── Step A：從腳本行掃描 [SECTION:N] 路標，建立對話索引 → section 的映射 ──
section_marker_re = re.compile(r'^\[SECTION:(\d)\]\s*$')
dialogue_line_re  = re.compile(r'^(?:\*{0,2}\[?(Tom|Miranda)\]?\*{0,2}[:：])')

current_marker = 0          # 預設 section 0（全球市場主旋律）
raw_lines = script_text.splitlines()
dialogue_section_map = []   # 每一條 dialogue 對應的 section idx (0-based)

for line in raw_lines:
    m = section_marker_re.match(line.strip())
    if m:
        current_marker = int(m.group(1)) - 1   # 轉為 0-based
    elif dialogue_line_re.match(line.strip()):
        dialogue_section_map.append(current_marker)

print(f"   ✅ 路標解析完成，共 {len(dialogue_section_map)} 條對話，section 分佈: { {i: dialogue_section_map.count(i) for i in range(5)} }")

# ── Step B：清除腳本中的路標行，再進行 TTS 配音解析 ──
clean_script = re.sub(r'\[SECTION:\d\]\n?', '', script_text)
print("正在處理雙人聲配音 (Tom & Miranda)...")

# 解析腳本為片段
dialogue_parts = []
pattern = r'(?:\*?\*?\[?(Tom|Miranda)\]?\*?\*?[:：])\s*(.*?)(?=\s*(?:\*?\*?\[?(?:Tom|Miranda)\]?\*?\*?[:：])|$)'
matches = re.findall(pattern, clean_script, re.DOTALL)

if not matches:
    print("⚠️ 腳本格式不符，改用單人配音。")
    dialogue_parts = [("Tom", script_text.replace("*", "").replace("#", ""))]
else:
    # 移除 Markdown 符號，避免 TTS 唸出「星號」；並移除 (1)~(5) 段落標記，保持對話自然流暢
    clean_re = re.compile(r'[（(][1-5][)）]\s*')
    dialogue_parts = [(s, clean_re.sub('', c).replace("*", "").replace("#", "")) for s, c in matches]

# ★ 後處理強制修正：只有當 Miranda 的句子「一開頭」就是段落引言標記
#   才代表她在搶 Tom 的帶入角色，才需要強制換成 Tom 說出
#   (若標記在句子中間，是正常的分析引用，不應干涉)
section_intro_pattern = re.compile(r'^\s*[（(][1-5][)）]')
corrected_parts = []
for speaker, content in dialogue_parts:
    if speaker == "Miranda" and section_intro_pattern.search(content.strip()):
        print(f"   ⚠️ 修正角色：Miranda 試圖帶入段落引言，已強制改為 Tom 播報。")
        corrected_parts.append(("Tom", content))
    else:
        corrected_parts.append((speaker, content))
dialogue_parts = corrected_parts

# ★ 移除「純粹宣告段落名稱」的孤立句子 (例如 Tom 說了一句「全球市場主旋律」就沒了)
#   因為螢幕藍圖已呈現段落資訊，對話中不應生硬地喊出段落名稱
bp_title_re = re.compile(r'^[\s　]*(?:好[，,]？？|接下來[，,]？？)?(?:我們|讓我們)?(?:來|來到|進入|討論)?[\s　]*(?:第[一二三四五]個?[點部分主題]|[第]?[1-5][點部份])?[\s　]*(全球市場主旋律|物價與通膨趨勢|央行與利率動向|美元與匯率走勢|關鍵風險與展望)[。！!，,]?[\s　]*$')
filtered_parts = []
for speaker, content in dialogue_parts:
    if bp_title_re.match(content.strip()):
        print(f"   ⚠️ 移除孤立段落宣告: [{speaker}] {content.strip()[:30]}")
        continue
    filtered_parts.append((speaker, content))
dialogue_parts = filtered_parts

audio_segments = []
voices = {
    "Tom": "zh-CN-YunxiNeural", # 改用穩定的大陸男聲，因為台灣男聲近期對英文單字(如Tom)極不穩定會報錯
    "Miranda": "zh-TW-HsiaoChenNeural"
}

temp_audio_dir = os.path.join(WORKSPACE_DIR, "temp_audio")
if not os.path.exists(temp_audio_dir): os.makedirs(temp_audio_dir)

for i, (speaker, content) in enumerate(dialogue_parts):
    clean_content = content.strip()
    if not clean_content: continue
    
    seg_filename = f"seg_{i:03d}.mp3"
    seg_path = os.path.join(temp_audio_dir, seg_filename)
    voice = voices.get(speaker, "zh-CN-YunxiNeural")
    
    print(f"   正在生成 {speaker} 的配音 ({i+1}/{len(dialogue_parts)})...")
    
    # 解決字元逸出問題：將文字寫入暫存檔，讓 edge-tts 讀取檔案
    text_file_path = os.path.join(temp_audio_dir, f"text_{i:03d}.txt")
    with open(text_file_path, "w", encoding="utf-8") as f:
        f.write(clean_content)
        
    # 直接指定正確的 edge-tts 路徑
    edge_tts_path = r"C:\Users\soga52\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\edge-tts.exe"
    if not os.path.exists(edge_tts_path):
        edge_tts_path = "edge-tts"
        
    try:
        subprocess.run([edge_tts_path, '--file', text_file_path, '--voice', voice, '--write-media', seg_path], check=True, timeout=60)
        audio_segments.append(seg_path)
    except subprocess.TimeoutExpired:
        print(f"⚠️ {speaker} 的配音生成超時！跳過此段落。")
    except Exception as e:
        print(f"⚠️ {speaker} 配音發生錯誤: {e}")

# 合併音軌
timestamp_str = now_tw.strftime("%Y%m%d_%H%M%S")
combined_audio = os.path.join(WORKSPACE_DIR, f"weekly_audio_{timestamp_str}.mp3")
print("正在合併音軌...")

with open("audio_list.txt", "w", encoding="utf-8") as f:
    for seg in audio_segments:
        f.write(f"file '{seg}'\n")

subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'audio_list.txt', '-c', 'copy', combined_audio], check=True)

# 混入背景音樂 (如果有 bg_music.mp3)
final_audio = combined_audio
bg_music_path = os.path.join(WORKSPACE_DIR, "bg_music.mp3")
if os.path.exists(bg_music_path):
    print("偵測到背景音樂，正在進行混音...")
    mixed_audio = os.path.join(WORKSPACE_DIR, f"final_audio_{timestamp_str}.mp3")
    # 讓背景音樂循環並調整音量為 0.1
    subprocess.run([
        'ffmpeg', '-y', '-i', combined_audio, '-stream_loop', '-1', '-i', bg_music_path,
        '-filter_complex', '[1:a]volume=0.1[bg];[0:a][bg]amix=inputs=2:duration=first',
        mixed_audio
    ], check=True)
    final_audio = mixed_audio

# ==============================================================================
# 3. 視覺合成 (動態背景影片 + 文字疊加)
# ==============================================================================
print("正在使用動態背景合成最終影片...")

# 優先順序：sunset -> night -> fallback(深藍背景)
# 取消隨機，固定使用我們專門產製的「資訊圖表結構底圖」
bg_images = ["bg_infographic.png"]
available_bgs = [os.path.join(WORKSPACE_DIR, f) for f in bg_images if os.path.exists(os.path.join(WORKSPACE_DIR, f))]
bg_input = available_bgs[0] if available_bgs else None
is_image_bg = bg_input and bg_input.endswith(".png")

video_filename = f"weekly_video_{timestamp_str}.mp4"
video_path = os.path.join(WORKSPACE_DIR, video_filename)

# 準備主要的文字大字報與虛擬主播畫面
def make_circle_avatar(img_path, size):
    try:
        img = Image.open(img_path).resize(size).convert("RGBA")
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=255)
        result = Image.new('RGBA', size, (0, 0, 0, 0))
        result.paste(img, (0, 0), mask=mask)
        return result
    except:
        return None

def get_audio_duration(file_path):
    try:
        out = subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_entries', 
            'format=duration', '-of', 
            'default=noprint_wrappers=1:nokey=1', file_path
        ])
        return float(out.strip())
    except Exception as e:
        print(f"無法取得音檔長度，預設為 300 秒: {e}")
        return 300.0

# ★ 關鍵字驅動的藍圖段落偵測器
TOPIC_KEYWORDS = [
    # 0: 全球市場主旋律 — 廣義市場情緒、盤面氛圍
    ['全球市場', '市場主旋律', '風險情緒', '避險情緒', 'narrative', '市場敘事',
     '市場波動', '股市', '恐慌', '盤面', '市場氛圍', '多空', '情緒面', '資金面'],
    # 1: 物價與通膨趨勢 — 需要明確通膨語境
    ['通膨預期', 'CPI', 'PCE', '停滯性通膨', 'stagflation', '通膨壓力',
     '通膨數據', '薪資通膨', '能源通膨', '核心通膨'],
    # 2: 央行與利率動向
    ['央行', 'Fed', '聯準會', '利率', '升息', '降息', '歐洲央行', 'ECB',
     'RBA', '澳洲聯準', '日銀', 'BOJ', '貨幣政策', 'higher for longer',
     '殖利率', '政策利率', '緊縮', '寬鬆', '鷹派', '鴿派', 'FOMC'],
    # 3: 美元與匯率走勢
    ['美元指數', 'DXY', '台幣', '日圓', '黃金', '原油', '亞幣', '外匯',
     '匯率走勢', '商品價格', '美元強勢', '美元弱勢'],
    # 4: 關鍵風險與展望
    ['下週', '下一週', '展望', '風險預警', '前景', '不確定性',
     '需要關注', '值得關注', '風險因素', '接下來要觀察', '風險事件'],
]

def detect_topic(text, current_idx=0):
    """
    關鍵字偵測 + 單調推進（只進不退）
    - 需要 >= 2 個關鍵字命中才能推進到下一個主題
    - 候選主題的得分必須高於當前主題才能推進
    - 永遠不會倒退到更早的主題
    """
    scores = [0] * len(TOPIC_KEYWORDS)
    text_lower = text.lower()
    for idx, keywords in enumerate(TOPIC_KEYWORDS):
        for kw in keywords:
            if kw.lower() in text_lower:
                scores[idx] += 1

    # 找出 > current_idx 且得分 >= 2 的最高分主題
    best = current_idx
    for idx in range(current_idx + 1, len(TOPIC_KEYWORDS)):
        if scores[idx] >= 2 and scores[idx] > scores[best]:
            best = idx

    print(f"   [topic] scores={scores} current={current_idx} → {best}")
    return best

def create_transparent_slide(text, output_name, title, current_topic_idx, active_speaker):
    # 720x1280 直式版面
    width, height = 720, 1280
    
    # 藍圖主題清單
    blueprint_topics = [
        "全球市場主旋律",
        "物價與通膨趨勢",
        "央行與利率動向",
        "美元與匯率走勢",
        "關鍵風險與展望"
    ]
    # current_topic_idx 現在直接從外部傳入（由關鍵字偵測計算）

    # 根據段落動態載入對應的 B-Roll 底圖，並全域暗化處理
    broll_files = ["broll_1_macro.png", "broll_2_inflation.png", "broll_3_rates.png", "broll_4_dollar.png", "broll_5_risk.png"]
    broll_path = os.path.join(WORKSPACE_DIR, broll_files[current_topic_idx])
    
    try:
        bg_img = Image.open(broll_path).convert('RGBA')
        bg_img = ImageOps.fit(bg_img, (width, height))
        # ★ 關鍵修正：先轉 RGB 再暸光，避免 Brightness 把 Alpha 也乘以 0.4
        #    （RGBA 暸光會讓整張圖透明度變 40%，導致 FFmpeg 輸出全黑画面）
        bg_rgb = ImageEnhance.Brightness(bg_img.convert('RGB')).enhance(0.4)
        image = bg_rgb.convert('RGBA')   # 轉回 RGBA，並且所有像素 alpha=255
    except Exception as e:
        print(f"無法載入 B-Roll {broll_path}: {e}")
        image = Image.new('RGBA', (width, height), (15, 23, 42, 255))
        
    draw = ImageDraw.Draw(image)
    
    # 移除全螢幕的簡報卡片，讓底圖可以完美呈現
    
    font_paths = [
        "msjh.ttc",  # Windows JhengHei
        "msjhbd.ttc", # Windows JhengHei Bold
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", # Ubuntu Noto CJK
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc" # Ubuntu Fallback
    ]
    
    font_title = None
    for fp in font_paths:
        try:
            font_title = ImageFont.truetype(fp, 55)
            font_body = ImageFont.truetype(fp, 40)
            font_name = ImageFont.truetype(fp, 25)
            font_page = ImageFont.truetype(fp, 30)
            break
        except Exception:
            continue
            
    if font_title is None:
        print("警告：無法載入中文字型，將使用預設字型，中文字可能變成方塊。")
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_page = ImageFont.load_default()

    # 【新聞台版型設計】
    
    # 1. 頂部標題：無框、無 LIVE，純文字
    #    用微透明陰影矩形讓文字可讀，但不做明顯的框
    draw.rectangle([(0, 0), (720, 80)], fill=(10, 18, 36, 120))
    draw.text((30, 20), "總經快報", font=font_title, fill=(239, 68, 68, 230))

    # 畫一個完全透明的藍圖 (因為背景已經全域暗化了，不需要底框)
    bp_x = 120
    bp_y = 250
    
    for i, topic in enumerate(blueprint_topics):
        row_y = bp_y + i * 90
        if i == current_topic_idx:
            # 正在講：天藍色文字，大字體，最醒目
            draw.text((bp_x, row_y), topic, font=font_body, fill=(56, 189, 248, 255))
            draw.ellipse([bp_x - 22, row_y + 10, bp_x - 6, row_y + 26], fill=(56, 189, 248, 255))
        elif i < current_topic_idx:
            # 已完成：灰色文字，小點，低調
            draw.text((bp_x, row_y), topic, font=font_body, fill=(148, 163, 184, 180))
            draw.ellipse([bp_x - 19, row_y + 12, bp_x - 9, row_y + 22], fill=(148, 163, 184, 160))
        else:
            # 未到：白色文字，偏暗，等待被點亮
            draw.text((bp_x, row_y), topic, font=font_body, fill=(255, 255, 255, 110))
            draw.ellipse([bp_x - 17, row_y + 13, bp_x - 11, row_y + 19], fill=(255, 255, 255, 80))
    
    # 2. 底部字幕條：漸層淡入，避免硬切邊
    bar_top = 1120
    bar_bottom = 1280
    # 用多個漸層矩形模擬由透明到深色的淡入效果
    steps = 12
    for s in range(steps):
        alpha = int(20 + (210 * s / (steps - 1)))  # 20 → 230
        y0 = bar_top + int(s * (bar_bottom - bar_top) / steps)
        y1 = bar_top + int((s + 1) * (bar_bottom - bar_top) / steps)
        draw.rectangle([(0, y0), (720, y1)], fill=(15, 23, 42, alpha))
    # 頂部裝飾亮線
    draw.rectangle([(0, bar_top), (720, bar_top + 3)], fill=(56, 189, 248, 200))
    
    # 3. 加入迷你虛擬主播頭像 (放置在左下角)
    avatar_size = (100, 100)
    avatar_y = bar_top + 20
    
    avatar_img = "tom.png" if active_speaker == "Tom" else "miranda.png"
    avatar = make_circle_avatar(os.path.join(WORKSPACE_DIR, avatar_img), avatar_size)
    
    if avatar:
        # 多層發光環：模擬「說話中」的脈衝光暈效果
        # Tom = 天藍色, Miranda = 紫藍色
        glow_color = (56, 189, 248) if active_speaker == "Tom" else (139, 92, 246)
        ax, ay = 20, avatar_y
        aw, ah = avatar_size
        # 外層暈（最透明）
        draw.ellipse([ax-10, ay-10, ax+aw+10, ay+ah+10], fill=(*glow_color, 35))
        # 中層暈
        draw.ellipse([ax-6,  ay-6,  ax+aw+6,  ay+ah+6],  fill=(*glow_color, 70))
        # 內層亮邊
        draw.ellipse([ax-3,  ay-3,  ax+aw+3,  ay+ah+3],  fill=(*glow_color, 140))
        image.paste(avatar, (20, avatar_y), avatar)

        
        # 主播名字標籤
        name_bg_color = (2, 132, 199, 255) if active_speaker == "Tom" else (71, 85, 105, 255)
        draw.rounded_rectangle([(25, avatar_y + 85), (115, avatar_y + 115)], radius=10, fill=name_bg_color)
        draw.text((45, avatar_y + 88), active_speaker, font=font_name, fill=(255, 255, 255, 255))

    # 4. 播報文字 (兩行跑馬燈字幕，每行 18 字)
    y = bar_top + 30
    chars_per_line = 18
    for ln in range(0, len(text), chars_per_line):
        draw.text((140, y), text[ln:ln+chars_per_line], font=font_page, fill=(241, 245, 249, 255))
        y += 45

    # 轉為 RGB 再存檔，避免 FFmpeg 處理 RGBA 時 alpha 合成出錯
    image.convert('RGB').save(output_name)

slide_files = []
slide_timings = []
cumulative_time = 0.0
max_chars = 36  # 最多 36 字，分兩行每行 18 字


# section_map 可能因 AI 輸出不完整而比 dialogue_parts 短，補齊以最後已知值
while len(dialogue_section_map) < len(dialogue_parts):
    dialogue_section_map.append(dialogue_section_map[-1] if dialogue_section_map else 0)

for i, (speaker, content) in enumerate(dialogue_parts):
    chunks = [content[j:j+max_chars] for j in range(0, len(content), max_chars)]

    # ★ 直接從 AI 路標映射取得 section，不再猜語意
    seg_topic_idx = dialogue_section_map[i] if i < len(dialogue_section_map) else 0
    seg_topic_idx = max(0, min(seg_topic_idx, 4))  # 夾在合法範圍
    seg_path = audio_segments[i]
    dur = get_audio_duration(seg_path)
    total_chars = sum(len(c) for c in chunks)
    
    for c_idx, chunk_text in enumerate(chunks):
        chunk_ratio = len(chunk_text) / total_chars if total_chars > 0 else 1.0
        chunk_dur = max(dur * chunk_ratio, 0.2)
        
        fname = f"overlay_{i}_{c_idx}.png"
        out_path = os.path.join(WORKSPACE_DIR, fname)
        create_transparent_slide(chunk_text, out_path, "總經焦點對談",
                                 seg_topic_idx, speaker)
        slide_files.append(out_path)
        slide_timings.append((cumulative_time, cumulative_time + chunk_dur))
        cumulative_time += chunk_dur

print(f"音軌總長: {cumulative_time:.1f} 秒, 共 {len(slide_files)} 張動態簡報")

# FFmpeg 合成邏輯：使用高效 concat demuxer
slides_txt_path = os.path.join(WORKSPACE_DIR, "slides.txt")
with open(slides_txt_path, "w", encoding="utf-8") as f:
    for i, sf in enumerate(slide_files):
        # 注意路徑處理，避免反斜線逸出問題
        safe_sf = sf.replace("\\", "/")
        f.write(f"file '{safe_sf}'\n")
        duration = slide_timings[i][1] - slide_timings[i][0]
        f.write(f"duration {duration:.3f}\n")
    # 最後一幀需要補上
    safe_last_sf = slide_files[-1].replace('\\', '/')
    f.write(f"file '{safe_last_sf}'\n")

ffmpeg_cmd = [
    'ffmpeg', '-y',
    '-f', 'concat', '-safe', '0', '-i', slides_txt_path,  # VFR 輸入（尊重 slides.txt 的 duration）
    '-i', final_audio
]

# 先用 fps=30 把 VFR 轉成 CFR，再疊加聲波濾鏡
# 注意：-r 30 不能加在 input 前，否則會覆蓋 duration 讓每張只顯示 1/30 秒
filter_complex = (
    "[0:v]fps=30[v30];"
    "[1:a]asplit=2[wave_in][a_out];"
    # 音波縮小至 560x38，貼齊字幕條右下角（x=160, y=1242），不遮擋文字
    "[wave_in]showwaves=s=560x38:mode=cline:colors=0x38bdf8:rate=30[wave];"
    "[v30][wave]overlay=160:1242[final_v]"
)

ffmpeg_cmd += [
    '-filter_complex', filter_complex,
    '-map', '[final_v]',
    '-map', '[a_out]',
    '-c:v', 'libx264',
    '-preset', 'fast',
    '-crf', '28',
    '-c:a', 'aac',
    '-b:a', '96k',
    '-pix_fmt', 'yuv420p',
    '-shortest',
    '-movflags', '+faststart',
    video_path
]

print("正在執行 FFmpeg 合成...")
subprocess.run(ffmpeg_cmd, check=True)

# ==============================================================================
# 4. 清理與更新
# ==============================================================================
import shutil
if os.path.exists(temp_audio_dir): shutil.rmtree(temp_audio_dir)
if os.path.exists("audio_list.txt"): os.remove("audio_list.txt")
for sf in slide_files: 
    if os.path.exists(sf): os.remove(sf)

# 清理舊的週報影片，只保留最新 3 支
try:
    video_files_all = sorted(
        [f for f in os.listdir(WORKSPACE_DIR) if f.startswith("weekly_video_") and f.endswith(".mp4")],
        reverse=True
    )
    for old_video in video_files_all[3:]:  # 保留最新 3 支
        old_path = os.path.join(WORKSPACE_DIR, old_video)
        try:
            os.remove(old_path)
            print(f"清理舊影片: {old_video}")
        except Exception as ex:
            print(f"清理舊影片失敗: {ex}")
except Exception as e:
    print(f"清理週報影片時發生錯誤: {e}")

# 同樣清理舊的 weekly_audio 合成音訊
try:
    audio_files_all = sorted(
        [f for f in os.listdir(WORKSPACE_DIR) if f.startswith("weekly_audio_") and f.endswith(".mp3")],
        reverse=True
    )
    for old_audio in audio_files_all[3:]:
        old_path = os.path.join(WORKSPACE_DIR, old_audio)
        try:
            os.remove(old_path)
            print(f"清理舊音訊: {old_audio}")
        except Exception as ex:
            print(f"清理舊音訊失敗: {ex}")
except Exception as e:
    print(f"清理週報音訊時發生錯誤: {e}")

print("正在更新儀表板連結...")
try:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            hist_data = json.load(f)
        if hist_data:
            hist_data[0]["weekly_video"] = video_filename
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(hist_data, f, ensure_ascii=False, indent=2)

    html_path = os.path.join(WORKSPACE_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        html_content = re.sub(
            r'(<div id="weekly-video-container"[^>]*style="[^"]*)display:\s*none;?([^"]*">)',
            r'\1display: block;\2',
            html_content
        )
        html_content = re.sub(
            r'(<video id="weekly-video-player"[^>]*>.*?<source src=")[^"]*(" type="video/mp4">)',
            rf'\g<1>{video_filename}\g<2>',
            html_content,
            flags=re.DOTALL
        )
        with open(html_path, "w", encoding="utf-8") as f: f.write(html_content)
except Exception as e: print(f"更新失敗: {e}")

print(f"Tom & Miranda 的 Podcast 影片產製完成！({video_filename})")

