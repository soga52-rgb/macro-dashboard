import urllib.request
url = "https://news.google.com/rss/search?q=test&hl=en-US&gl=US&ceid=US:en"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    response = urllib.request.urlopen(req, timeout=10)
    print("Success")
except Exception as e:
    print("Error:", e)
