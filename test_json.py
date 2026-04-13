import json
text = '''{
    "a": "line1
line2"
}'''
try:
    print(json.loads(text))
except Exception as e:
    print("Normal failed:", e)

try:
    print(json.loads(text, strict=False))
except Exception as e:
    print("Strict False failed:", e)
