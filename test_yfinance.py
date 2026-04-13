import urllib.request, json
url = "https://query1.finance.yahoo.com/v8/finance/chart/^TNX?interval=1d"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print("TNX price:", data['chart']['result'][0]['meta']['regularMarketPrice'])
