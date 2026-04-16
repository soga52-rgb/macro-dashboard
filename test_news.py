import urllib.request
import xml.etree.ElementTree as ET

macro_keywords = [
    "FOMC", "Federal Reserve", "ECB", "BOJ", "interest rate", "rate cut",
    "CPI", "PCE", "PPI", "inflation",
    "NFP", "nonfarm payrolls", "jobless claims", "unemployment",
    "GDP", "Retail Sales", "PMI", "soft landing", "macroeconomic",
    "DXY", "Treasury yields"
]
query_str = "+OR+".join([f"%22{k.replace(' ', '+')}%22" if ' ' in k else k for k in macro_keywords])
source_str = "site:bloomberg.com+OR+site:cnbc.com+OR+site:investing.com+OR+site:benzinga.com+OR+site:cnyes.com"
url = f"https://news.google.com/rss/search?q=({query_str})+AND+({source_str})+when:2d&hl=en-US&gl=US&ceid=US:en"
print("New URL:", url)
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req)
xml_data = response.read()
root = ET.fromstring(xml_data)
items = root.findall('.//item')
print(f"Total items found: {len(items)}")
for item in items[:5]:
    print("-", item.find('title').text)
    print("  Date:", item.find('pubDate').text)
