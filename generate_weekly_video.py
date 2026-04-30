import os
import sys
import json
import urllib.request
import urllib.error
import csv
import subprocess
from datetime import datetime, timedelta, timezone

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
print("正在請 AI 撰寫 Tom 與 Mark 的雙主播回顧腳本...")

prompt = f"""你現在是兩位專業的財經 Podcast 主持人：
1. [Tom]：親切、擅長引導話題、會代表觀眾提問的主持人。
2. [Mark]：專業、理性、數據導向的資深總經首席分析師。

請根據以下「過去一週每日重點摘要」，撰寫一份約 5 分鐘的對話腳本。
日期：{today_str}

【過去一週每日重點摘要】：
{history_text}

【撰寫要求】：
1. 語氣要生動、像 NotebookLM 的 Podcast 對談，有互動感（例如：Tom 會說「哇，這真的很驚人」）。
2. 長度約 1500 字，確保對話自然且包含深度分析。
3. 腳本格式嚴格遵循：
   [Tom]: (口白內容)
   [Mark]: (口白內容)
4. 結構包含：(1) 週報開場 (2) 關鍵新聞串聯與剖析 (3) 指標走勢解讀 (4) 下週風險預警。
"""

script_text = ""
strategies = [("v1beta", "gemini-3.1-pro-preview"), ("v1beta", "gemini-2.5-pro")]

import time, re
success = False
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
            success = True
            break
        except Exception as e:
            print(f"   [FAIL] {model} 錯誤: {e}")
            time.sleep(5)

if not success:
    print("❌ 腳本生成失敗")
    sys.exit(1)

# ==============================================================================
# 2. 處理雙聲道配音 (Tom: YunJhe, Mark: HsiaoMin)
# ==============================================================================
print("正在處理雙人聲配音 (Tom & Mark)...")

# 解析腳本為片段
dialogue_parts = []
# 匹配 [Tom]: 或 [Mark]: 開頭的內容
pattern = r"\[(Tom|Mark)\]:\s*(.*?)(?=\s*\[(?:Tom|Mark)\]:|$)"
matches = re.findall(pattern, script_text, re.DOTALL)

if not matches:
    print("⚠️ 腳本格式不符，改用單人配音。")
    dialogue_parts = [("Tom", script_text)]
else:
    dialogue_parts = matches

audio_segments = []
voices = {
    "Tom": "zh-TW-YunJheNeural",
    "Mark": "zh-TW-HsiaoMinNeural"
}

temp_audio_dir = os.path.join(WORKSPACE_DIR, "temp_audio")
if not os.path.exists(temp_audio_dir): os.makedirs(temp_audio_dir)

for i, (speaker, content) in enumerate(dialogue_parts):
    clean_content = content.strip()
    if not clean_content: continue
    
    seg_filename = f"seg_{i:03d}.mp3"
    seg_path = os.path.join(temp_audio_dir, seg_filename)
    voice = voices.get(speaker, "zh-TW-YunJheNeural")
    
    print(f"   正在生成 {speaker} 的配音 ({i+1}/{len(dialogue_parts)})...")
    subprocess.run(['edge-tts', '--text', clean_content, '--voice', voice, '--write-media', seg_path], check=True)
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

# 準備 4 個主要的文字大字報 (配合 Tom & Mark 的討論重點)
def create_transparent_slide(text, output_name, title):
    width, height = 1920, 1080
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 繪製半透明深色裝飾塊 (左側)
    draw.rectangle([50, 50, 800, 1030], fill=(15, 23, 42, 180))
    
    try:
        font_title = ImageFont.truetype("msjh.ttc", 70)
        font_body = ImageFont.truetype("msjh.ttc", 45)
    except:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.text((100, 100), title, font=font_title, fill=(96, 165, 250, 255))
    draw.line((100, 200, 750, 200), fill=(241, 245, 249, 100), width=3)
    
    y = 250
    # 簡單文字換行
    for i in range(0, len(text), 12):
        chunk = text[i:i+12]
        draw.text((100, y), chunk, font=font_body, fill=(241, 245, 249, 255))
        y += 70
    
    image.save(output_name)

slide_files = []
sections = [("總經市場敘事", latest_narrative), ("關鍵事件剖析", focus_clean), ("風險展望", risk_items)]
for i, (title, content) in enumerate(sections):
    fname = f"overlay_{i}.png"
    create_transparent_slide(content[:100], fname, title)
    slide_files.append(fname)

# FFmpeg 合成邏輯
if bg_video:
    print(f"使用背景影片: {os.path.basename(bg_video)}")
    # 使用背景影片循環，並疊加文字圖片
    # 這裡簡化處理：每 20 秒換一張大字報
    filter_complex = ""
    for i in range(len(slide_files)):
        start = i * 20
        end = (i+1) * 20
        filter_complex += f"[{i+1}:v]setpts=PTS-STARTPTS[v{i}];"
    
    # 建立疊加濾鏡鏈
    current_input = "[0:v]"
    for i in range(len(slide_files)):
        start = i * 30
        filter_complex += f"{current_input}[v{i}]overlay=0:0:enable='between(t,{start},{start+30})'[tmp{i}];"
        current_input = f"[tmp{i}]"
    
    filter_complex = filter_complex.rstrip(';')
    
    ffmpeg_cmd = ['ffmpeg', '-y', '-stream_loop', '-1', '-i', bg_video]
    for sf in slide_files:
        ffmpeg_cmd += ['-i', sf]
    ffmpeg_cmd += ['-i', final_audio, '-filter_complex', filter_complex, '-map', current_input.strip('[]'), '-map', f'{len(slide_files)+1}:a', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-shortest', video_path]
    subprocess.run(ffmpeg_cmd, check=True)
else:
    # 備用方案：如果沒影片就用原本的黑底 (已省略，可視需要補回)
    print("未找到背景影片，請確認檔案已放置於目錄。")

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
        html_content = re.sub(r'display:\s*none;?["\']', 'display: block;"', html_content)
        html_content = re.sub(r'<source src="[^"]*" type="video/mp4">', f'<source src="{video_filename}" type="video/mp4">', html_content)
        with open(html_path, "w", encoding="utf-8") as f: f.write(html_content)
except Exception as e: print(f"更新失敗: {e}")

print(f"🎉 Tom & Mark 的 Podcast 影片產製完成！({video_filename})")

