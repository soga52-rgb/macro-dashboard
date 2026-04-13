import os, json, urllib.request

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
print("API KEY length:", len(GEMINI_API_KEY) if GEMINI_API_KEY else "None")

prompt = "Hello"
strategies = [
    ("v1beta", "gemini-3-flash-preview"), 
    ("v1beta", "gemini-3.1-flash"),
    ("v1", "gemini-1.5-flash"),
    ("v1beta", "gemini-2.0-flash"),
]

for version, model in strategies:
    print(f"Testing {model}...")
    url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    
    try:
        response = urllib.request.urlopen(req)
        print("Success:", model)
        break
    except Exception as e:
        if hasattr(e, 'read'):
            print("Error:", e.read().decode('utf-8'))
        else:
            print("Error:", e)
