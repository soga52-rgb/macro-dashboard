import urllib.request
url = "https://news.google.com/rss/search?q=(FOMC+OR+%22Federal+Reserve%22)+when:7d&hl=en-US&gl=US&ceid=US:en"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    response = urllib.request.urlopen(req)
    print("Google News Success", len(response.read()))
except Exception as e:
    print("Google News Error", e)

url_yahoo = "https://query1.finance.yahoo.com/v8/finance/chart/^TNX?interval=1d"
req_yahoo = urllib.request.Request(url_yahoo, headers={'User-Agent': 'Mozilla/5.0'})
try:
    response = urllib.request.urlopen(req_yahoo)
    print("Yahoo Success", len(response.read()))
except Exception as e:
    print("Yahoo Error", e)

