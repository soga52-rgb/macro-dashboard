import urllib.request
import re
import json

def fetch_article(url):
    try:
        # Step 1: follow google news redirect
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
        
        # Google news redirect puts the real link in a tag or meta refresh
        match = re.search(r'<a[^>]*href="(https://[^"]+)"', html)
        if not match:
            return "無法解析新聞連結"
            
        real_url = match.group(1)
        print("Real URL:", real_url)
        
        # Step 2: fetch real page
        req2 = urllib.request.Request(real_url, headers={'User-Agent': 'Mozilla/5.0'})
        html2 = urllib.request.urlopen(req2, timeout=10).read().decode('utf-8', errors='ignore')
        
        # Step 3: extract basic p tags
        # very simple text extraction
        p_tags = re.findall(r'<p[^>]*>(.*?)</p>', html2, re.IGNORECASE | re.DOTALL)
        
        # clean html tags
        text = " ".join(p_tags)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # return first 1000 chars as summary text
        return text[:1000]
    except Exception as e:
        return f"Fetch error: {e}"

print(fetch_article('https://news.google.com/rss/articles/CBMic0FVX3lxTE1jZ0kyZFY2UU1QbGhaeGJaZmF0MlNMZmkySXlITDI3V1RGWnNVU2hBbGtWZWFUTGhpUWk0V29RcmxIcXZsbjIzbzhabExaSWJJV2lWYlVsT2FueTU2ckItU2FzN1ZsQ3Zsa3dYWEg3LVgxOVnSAXhBVV95cUxNRzM0MDlLRExoU3pUbW1hMWppSkYzeER1bzJEWDNwZlVkUml5amRVMnVjUHF6LVlwMGJmaklhUXFER0hBT3RmTzFvaVFHbkJvbjhiOTdWUURHLXBUWFFsZmZaS3B5emNmX0R5VUdXV0dtbGRBOGZJb1o?oc=5'))
