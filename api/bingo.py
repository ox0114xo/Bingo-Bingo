from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import random
import urllib.parse

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 設定 CORS 允許前端呼叫，並宣告回傳 JSON
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0', 'Accept': '*/*'}
        url_official = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/BingoResult"
        url_pilio = "https://www.pilio.idv.tw/bingo/list.asp"
        
        # 多重代理突破策略
        strategies = [
            {"url": f"https://api.codetabs.com/v1/proxy?quest={url_official}", "type": "official"},
            {"url": f"https://api.codetabs.com/v1/proxy?quest={url_pilio}", "type": "html_big5"},
            {"url": url_official, "type": "official"},
            {"url": f"https://api.allorigins.win/raw?url={urllib.parse.quote(url_pilio)}", "type": "html_big5"}
        ]
        
        parsed_data = []
        source = "無"

        for strat in strategies:
            try:
                res = requests.get(strat["url"], headers=headers, timeout=5)
                if res.status_code == 200:
                    if strat["type"] == "official":
                        parsed_data = [{"draw_id": str(i['period']), "time": i['openTime'][:16].replace('T', ' '), "numbers": [int(x) for x in i['drawNumberSize']]} for i in res.json().get('content', [])[:20]]
                    else:
                        soup = BeautifulSoup(res.content.decode('big5', errors='ignore'), 'html.parser')
                        for row in soup.find_all('tr'):
                            text = row.get_text()
                            if '期' in text:
                                nums = [int(n) for n in re.findall(r'\d+', text) if 1 <= int(n) <= 80]
                                draw_ids = re.findall(r'11[0-9]{7}', text)
                                if len(nums) >= 20 and draw_ids:
                                    parsed_data.append({"draw_id": draw_ids[0], "time": "已開獎", "numbers": nums[:20]})
                    
                    if parsed_data:
                        source = strat["type"]
                        break
            except Exception:
                continue

        # 回傳資料給前端
        response_data = {
            "success": len(parsed_data) > 0,
            "source": source,
            "data": parsed_data
        }
        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
