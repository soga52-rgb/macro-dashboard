import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

macro_keywords = ['FOMC', 'Federal Reserve', 'ECB', 'BOJ', 'interest rate', 'rate cut', 'CPI', 'PCE', 'PPI', 'inflation', 'NFP', 'nonfarm payrolls', 'jobless claims', 'unemployment', 'GDP', 'Retail Sales', 'PMI', 'soft landing', 'macroeconomic', 'DXY', 'Treasury yields']
query_str = ' OR '.join([f'"{k}"' if ' ' in k else k for k in macro_keywords])
source_str = 'site:bloomberg.com OR site:cnbc.com OR site:investing.com OR site:benzinga.com OR site:cnyes.com'
encoded_q = urllib.parse.quote(f'({query_str}) AND ({source_str}) when:2d')
url = f'https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en'
print(url)
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    response = urllib.request.urlopen(req, timeout=15)
    xml_data = response.read()
    root = ET.fromstring(xml_data)
    for item in root.findall('.//item')[:5]:
        print(item.find('title').text)
        print(item.find('link').text)
except Exception as e:
    print(e)
