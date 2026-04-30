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
print("正在請 AI 撰寫一週回顧腳本...")

prompt = f"""你是一位專業的總經財經新聞主播。請根據以下我們系統收集的「過去一週每日重點摘要」，撰寫一份大約 5 分鐘的「每週總經回顧影片」口白腳本。
日期：{today_str}

【過去一週每日重點摘要】：
{history_text}

【撰寫要求】：
1. 這是影片配音腳本，語氣要像專業主播一樣自然、有起伏、引人入勝。開場白可以是：「各位投資朋友早安，歡迎收看本週的總經戰情室一週回顧...」
2. 長度請控制在約 1200 到 1500 字左右（相當於 4~5 分鐘的語速）。
3. 結構請分為：(1) 總經分析回顧 (2) 重大事件與新聞串聯 (3) 總經指標走勢變化 (4) 下週展望與風險提示。
4. 嚴格輸出純文字口白，不要包含「(畫面顯示...)」、「[音樂漸弱]」等非口白的舞台指示詞。
"""

script_text = "未能生成腳本。"
strategies = [
    ("v1beta", "gemini-3.1-pro-preview"), 
    ("v1beta", "gemini-2.5-pro")
]

import time
success = False
for version, model in strategies:
    if success: break
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"-> 嘗試連線方案：{version} / {model} (第 {attempt + 1} 次)...")
            url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            }
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
            response = urllib.request.urlopen(req, timeout=180)
            result = json.loads(response.read().decode('utf-8'))
            script_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
            print(f"[SUCCESS] {model} 回應成功!")
            success = True
            break
        except urllib.error.HTTPError as e:
            error_data = e.read().decode('utf-8')
            if e.code in [429, 503] and attempt < max_retries - 1:
                wait_time = 90
                print(f"   [WAIT] 伺服器忙碌或配額限制，等待 {wait_time} 秒後重試...")
                time.sleep(wait_time)
                continue
            else:
                print(f"   [FAIL] {model} 錯誤 ({e.code}): {error_data}")
                break
        except Exception as e:
            print(f"   [FAIL] {model} 發生其他錯誤: {e}")
            break

if not success:
    print("❌ 腳本生成失敗")
    sys.exit(1)

# ==============================================================================
# 2. 生成語音檔 (edge-tts)
# ==============================================================================
timestamp_str = now_tw.strftime("%Y%m%d_%H%M%S")
audio_filename = f"weekly_audio_{timestamp_str}.mp3"
audio_path = os.path.join(WORKSPACE_DIR, audio_filename)
temp_txt = os.path.join(WORKSPACE_DIR, "temp_weekly_script.txt")

with open(temp_txt, "w", encoding="utf-8") as f:
    f.write(script_text)

print(f"正在生成配音檔 ({audio_filename})...")
try:
    subprocess.run(['edge-tts', '-f', temp_txt, '--voice', 'zh-TW-HsiaoChenNeural', '--write-media', audio_path], check=True)
    print("✅ 語音生成完畢！")
except Exception as e:
    print(f"❌ 語音生成失敗: {e}")
    sys.exit(1)
finally:
    if os.path.exists(temp_txt):
        os.remove(temp_txt)

# ==============================================================================
# 3. 使用 Pillow 生成文字圖卡 (Slides)
# ==============================================================================
print("正在繪製影片圖卡...")

def create_slide(text, output_name, title="全球總經戰情室 - 一週回顧"):
    # 建立 1920x1080 背景
    width, height = 1920, 1080
    image = Image.new('RGB', (width, height), color=(15, 23, 42)) # 深藍色背景
    draw = ImageDraw.Draw(image)
    
    # 嘗試載入字型，若無則使用預設
    font_large = None
    font_medium = None
    try:
        # Windows 預設微軟正黑體
        font_large = ImageFont.truetype("msjh.ttc", 80)
        font_medium = ImageFont.truetype("msjh.ttc", 60)
    except IOError:
        try:
            # Linux 預設中文字體 (需在 GitHub Actions 安裝)
            font_large = ImageFont.truetype("NotoSansCJK-Regular.ttc", 80)
            font_medium = ImageFont.truetype("NotoSansCJK-Regular.ttc", 60)
        except IOError:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            
    # 繪製標題
    draw.text((100, 80), title, font=font_large, fill=(96, 165, 250))
    draw.line((100, 180, 1820, 180), fill=(51, 65, 85), width=5)
    
    # 文字自動換行處理
    max_width = 30 # 大約字數
    lines = []
    current_line = ""
    for char in text:
        current_line += char
        if len(current_line) >= max_width or char == '\n':
            lines.append(current_line.strip())
            current_line = ""
    if current_line:
        lines.append(current_line.strip())
        
    # 繪製內文
    y_text = 250
    for line in lines:
        if hasattr(font_medium, 'getbbox'):
            bbox = font_medium.getbbox(line)
            h = bbox[3] - bbox[1]
        else:
            h = 40 # fallback
        draw.text((100, y_text), line, font=font_medium, fill=(241, 245, 249))
        y_text += h + 30
        
    # 繪製頁尾
    draw.text((100, 980), f"Generated on {today_str} | AI Driven Macro Analysis", font=font_medium, fill=(100, 116, 139))
    
    image.save(output_name)

slide_files = []
# 從本週最新的 narrative 中萃取重點來做字卡
latest_narrative = recent_history[0].get('weekly_narrative', '本週宏觀重點')
slide1_text = latest_narrative[:150] + "..." if len(latest_narrative) > 150 else latest_narrative
create_slide(slide1_text, "slide_01.png", "總經分析")
slide_files.append("slide_01.png")

# 從焦點事件萃取
focus_items = re.sub(r'<[^>]+>', ' ', recent_history[0].get('focus_html', '')).split('02')
slide2_text = focus_items[0][:150].strip() if focus_items else "本週無特殊焦點"
create_slide(slide2_text, "slide_02.png", "關鍵事件剖析")
slide_files.append("slide_02.png")

# 從風險提示萃取
risk_items = re.sub(r'<[^>]+>', ' ', recent_history[0].get('risk_html', ''))
slide3_text = risk_items[:150].strip() if risk_items else "密切關注市場動態"
create_slide(slide3_text, "slide_03.png", "下週風險預警")
slide_files.append("slide_03.png")

# ==============================================================================
# 4. 使用 FFmpeg 合成影片
# ==============================================================================
print("正在使用 FFmpeg 合成最終影片...")
video_filename = f"weekly_video_{timestamp_str}.mp4"
video_path = os.path.join(WORKSPACE_DIR, video_filename)

# 取得語音長度 (透過 ffprobe)
try:
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    duration = float(result.stdout.strip())
except Exception as e:
    print(f"無法取得音訊長度，預設為 300 秒: {e}")
    duration = 300.0

time_per_slide = duration / len(slide_files)

# 建立 FFmpeg concat 腳本
concat_file = "slides.txt"
with open(concat_file, "w", encoding="utf-8") as f:
    for slide in slide_files:
        f.write(f"file '{slide}'\n")
        f.write(f"duration {time_per_slide:.2f}\n")
    # FFmpeg concat 要求最後一個 file 重複一次，不需要加 duration
    f.write(f"file '{slide_files[-1]}'\n")

# 執行 FFmpeg
# -vsync vfr (或 -fps_mode vfr) 將靜態圖片轉為影片
# -pix_fmt yuv420p 確保瀏覽器相容性
try:
    subprocess.run([
        'ffmpeg', '-y', '-f', 'concat', '-i', concat_file, '-i', audio_path,
        '-vsync', 'vfr', '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-c:a', 'aac',
        '-shortest', video_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    print(f"✅ 影片生成成功！({video_filename})")
except subprocess.CalledProcessError as e:
    print(f"❌ FFmpeg 合成失敗: {e}")
    sys.exit(1)
finally:
    # 清理暫存檔
    if os.path.exists(concat_file): os.remove(concat_file)
    for slide in slide_files:
        if os.path.exists(slide): os.remove(slide)
    if os.path.exists(audio_path): os.remove(audio_path) # 視需求可保留，這邊我們合進影片就刪除

# ==============================================================================
# 5. 清理舊影片 (保留最近 4 週)
# ==============================================================================
print("正在清理舊影片...")
current_time = datetime.now()
for f_name in os.listdir(WORKSPACE_DIR):
    if f_name.startswith("weekly_video_") and f_name.endswith(".mp4"):
        file_p = os.path.join(WORKSPACE_DIR, f_name)
        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_p))
        if (current_time - file_mtime).days > 30:
            try:
                os.remove(file_p)
                print(f"已清理過期影片: {f_name}")
            except Exception as ex:
                pass

print("🎉 所有作業完成！")
