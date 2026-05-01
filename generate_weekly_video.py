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
    from PIL import Image, ImageDraw, ImageFont
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

prompt = f"""你現在是兩位專業的財經 Podcast 主持人：
1. [Tom]：親切、擅長引導話題、會代表觀眾提問的主持人。
2. [Miranda]：專業、理性、數據導向的資深總經首席分析師。

請根據以下「過去一週每日重點摘要」，撰寫一份約 5 分鐘的對話腳本。
日期：{today_str}

【過去一週每日重點摘要】：
{history_text}

【撰寫要求】：
1. 語氣要生動、像 NotebookLM 的 Podcast 對談，有互動感（例如：Tom 會說「哇，這真的很驚人」）。
2. 長度約 1500 字，確保對話自然且包含深度分析。
3. 腳本格式嚴格遵循：
   [Tom]: (口白內容)
   [Miranda]: (口白內容)
4. 結構包含：(1) 週報開場 (2) 關鍵新聞串聯與剖析 (3) 指標走勢解讀 (4) 下週風險預警。
5. **絕對禁止任何具體的投資建議、買賣點位預測或推薦。請專注於「總經趨勢分析」與「市場現象解讀」，並適度加上免責聲明提醒。**
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
# 2. 處理雙聲道配音 (Tom: YunJhe, Miranda: HsiaoMin)
# ==============================================================================
print("正在處理雙人聲配音 (Tom & Miranda)...")

# 解析腳本為片段
dialogue_parts = []
# 匹配 [Tom]: 或 **[Tom]**: 或 Tom： 開頭的內容
pattern = r'(?:\*?\*?\[?(Tom|Miranda)\]?\*?\*?[:：])\s*(.*?)(?=\s*(?:\*?\*?\[?(?:Tom|Miranda)\]?\*?\*?[:：])|$)'
matches = re.findall(pattern, script_text, re.DOTALL)

if not matches:
    print("⚠️ 腳本格式不符，改用單人配音。")
    dialogue_parts = [("Tom", script_text)]
else:
    dialogue_parts = matches

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
        
    subprocess.run([edge_tts_path, '--file', text_file_path, '--voice', voice, '--write-media', seg_path], check=True)
    audio_segments.append(seg_path)

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
bg_video = None
for bg_name in ["bg_market_sunset.mp4", "bg_ticker_night.mp4"]:
    path = os.path.join(WORKSPACE_DIR, bg_name)
    if os.path.exists(path):
        bg_video = path
        break

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

def create_transparent_slide(text, output_name, title, slide_index, total_slides, active_speaker):
    # 720x1280 直式版面
    width, height = 720, 1280
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 繪製全螢幕的簡報卡片
    draw.rounded_rectangle([40, 60, 680, 1220], radius=30, fill=(15, 23, 42, 230))
    # 頂部裝飾線
    draw.rounded_rectangle([40, 60, 680, 75], radius=10, fill=(56, 189, 248, 255))
    
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

    # 標題
    draw.text((70, 100), title, font=font_title, fill=(125, 211, 252, 255))
    draw.line((70, 180, 650, 180), fill=(241, 245, 249, 80), width=3)
    
    # 頁碼
    draw.text((530, 120), f"Slide {slide_index}/{total_slides}", font=font_page, fill=(148, 163, 184, 255))
    
    # 內容文字 (顯示當前發言者的文字)
    y = 220
    # 加入引號特效
    draw.text((70, y), "「", font=font_title, fill=(56, 189, 248, 255))
    y += 50
    for i in range(0, len(text), 14):
        chunk = text[i:i+14]
        draw.text((80, y), chunk, font=font_body, fill=(241, 245, 249, 255))
        y += 60
    draw.text((580, y), "」", font=font_title, fill=(56, 189, 248, 255))
        
    # 加入虛擬主播頭像 (發言者放大且亮，非發言者縮小)
    tom_size = (140, 140) if active_speaker == "Tom" else (100, 100)
    mark_size = (140, 140) if active_speaker == "Miranda" else (100, 100)
    tom_y = 1040 if active_speaker == "Tom" else 1070
    mark_y = 1040 if active_speaker == "Miranda" else 1070
    
    tom_avatar = make_circle_avatar(os.path.join(WORKSPACE_DIR, "tom.png"), tom_size)
    mark_avatar = make_circle_avatar(os.path.join(WORKSPACE_DIR, "miranda.png"), mark_size)
    
    if tom_avatar:
        # 如果不是發言者，降低透明度
        if active_speaker != "Tom":
            alpha = tom_avatar.getchannel('A')
            tom_avatar.putalpha(alpha.point(lambda i: int(i * 0.4)))
        image.paste(tom_avatar, (70, tom_y), tom_avatar)
        
        color = (125, 211, 252, 255) if active_speaker == "Tom" else (148, 163, 184, 255)
        draw.text((100, 1190), "Tom", font=font_name, fill=color)
        
    if mark_avatar:
        if active_speaker != "Miranda":
            alpha = mark_avatar.getchannel('A')
            mark_avatar.putalpha(alpha.point(lambda i: int(i * 0.4)))
        image.paste(mark_avatar, (530, mark_y), mark_avatar)
        
        color = (125, 211, 252, 255) if active_speaker == "Miranda" else (148, 163, 184, 255)
        draw.text((550, 1190), "Miranda", font=font_name, fill=color)
    
    image.save(output_name)

slide_files = []
slide_timings = []
cumulative_time = 0.0

# 每句話生成一張大字報，達到 100% 完美影音同步
for i, (speaker, content) in enumerate(dialogue_parts):
    fname = f"overlay_{i}.png"
    # 取前 150 字作為大字報核心台詞
    display_text = content[:150]
    if len(content) > 150: display_text += "..."
    
    create_transparent_slide(display_text, fname, "總經焦點對談", i+1, len(dialogue_parts), speaker)
    slide_files.append(fname)
    
    # 取得這段音檔的精準長度
    seg_path = audio_segments[i]
    dur = get_audio_duration(seg_path)
    # 微調避免浮點數誤差導致畫面閃爍
    slide_timings.append((cumulative_time, cumulative_time + dur + 0.1))
    cumulative_time += dur

print(f"音軌總長: {cumulative_time:.1f} 秒, 共 {len(slide_files)} 張動態簡報")

# FFmpeg 合成邏輯
ffmpeg_cmd = ['ffmpeg', '-y', '-stream_loop', '-1', '-i', bg_video]
for sf in slide_files:
    ffmpeg_cmd += ['-loop', '1', '-i', sf]

ffmpeg_cmd += ['-i', final_audio]

# 加入動態聲波濾鏡 (適合直式的尺寸)
filter_complex = f"[{len(slide_files)+1}:a]asplit=2[wave_in][a_out];[wave_in]showwaves=s=280x100:mode=cline:colors=0x38bdf8[wave];"
current_input = "[0:v]"
for i in range(len(slide_files)):
    start, end = slide_timings[i]
    # 疊加每張簡報，根據精準時間軸切換
    filter_complex += f"{current_input}[{i+1}:v]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[tmp{i}];"
    current_input = f"[tmp{i}]"

# 最後把聲波疊加在兩位主播中間
filter_complex += f"{current_input}[wave]overlay=220:1060[final_v]"

# 最終合成指令
ffmpeg_cmd += [
    '-filter_complex', filter_complex,
    '-map', '[final_v]',
    '-map', '[a_out]',
    '-c:v', 'libx264',
    '-c:a', 'aac',
    '-pix_fmt', 'yuv420p',
    '-shortest',
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

