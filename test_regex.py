import re

html_content = '<div id="weekly-video-container" style="margin-top: 1.5rem; display: none;">'

html_content_new = re.sub(
    r'<div id="weekly-video-container"[^>]*display:\s*none;?["\'][^>]*>',
    r'<div id="weekly-video-container" style="margin-top: 1.5rem; display: block;">',
    html_content
)
print("Result:")
print(html_content_new)

html_content2 = '<source src="" type="video/mp4">'
html_content2_new = re.sub(
    r'<source src="[^"]*" type="video/mp4">',
    f'<source src="weekly_video_123.mp4" type="video/mp4">',
    html_content2
)
print("Result 2:")
print(html_content2_new)
