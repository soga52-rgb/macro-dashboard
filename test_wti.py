import urllib.request, json
url = "https://query1.finance.yahoo.com/v8/finance/chart/CL=F?interval=1d&range=1mo"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    prices = data['chart']['result'][0]['indicators']['quote'][0]['close']
    dates = data['chart']['result'][0]['timestamp']
    print(f"Got {len(prices)} prices. Last price: {prices[-1]}")
    import sys
    sys.exit(0)
except Exception as e:
    print(e)
