import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

macro_keywords = ['FOMC', '"Federal Reserve"', 'inflation', 'unemployment']
query_str = ' OR '.join(macro_keywords)
# Try just CNBC
source_str = 'site:cnbc.com'
encoded_q = urllib.parse.quote(f'({query_str}) AND {source_str} when:2d')
url = f'https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en'
print("Query 1:", url)
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    response = urllib.request.urlopen(req, timeout=15)
    xml_data = response.read()
    root = ET.fromstring(xml_data)
    for item in root.findall('.//item')[:5]:
        print(item.find('title').text)
except Exception as e:
    print(e)
