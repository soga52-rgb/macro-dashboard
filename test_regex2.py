import re

with open('d:/AI資料夾/macro_dashboard/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

html2 = re.sub(
    r'<div id="weekly-video-container"[^>]*display:\s*none;?["\'][^>]*>',
    r'<div id="weekly-video-container" style="margin-top: 1.5rem; display: block;">',
    html
)

print("Matched:", html != html2)
