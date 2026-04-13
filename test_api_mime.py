import json, urllib.request, os
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=invalid_key"
data = {
    "contents": [{"parts": [{"text": "hello"}]}],
    "generationConfig": {"responseMimeType": "application/json"}
}
req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
try:
    urllib.request.urlopen(req)
except Exception as e:
    print(e.read().decode())
