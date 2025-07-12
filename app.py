from flask import Flask, render_template, request, jsonify
import requests
import re
import threading
import time
from hashlib import md5
import secrets
import datetime
import random
import os

app = Flask(__name__)

# Global variables to track bot status
view_count = 0
target_views = 0
video_id = ''
is_running = False
status_messages = []
view_lock = threading.Lock()

class Signature:
    def __init__(self, params: str, data: str, cookies: str) -> None:
        self.params = params
        self.data = data
        self.cookies = cookies

    def hash(self, data: str) -> str:
        return str(md5(data.encode()).hexdigest())

    def calc_gorgon(self) -> str:
        gorgon = self.hash(self.params)
        gorgon += self.hash(self.data) if self.data else "0" * 32
        gorgon += self.hash(self.cookies) if self.cookies else "0" * 32
        gorgon += "0" * 32
        return gorgon

    def get_value(self):
        gorgon = self.calc_gorgon()
        return self.encrypt(gorgon)

    def encrypt(self, data: str):
        unix = int(time.time())
        key = [
            0xDF, 0x77, 0xB9, 0x40, 0xB9, 0x9B, 0x84, 0x83, 0xD1, 0xB9,
            0xCB, 0xD1, 0xF7, 0xC2, 0xB9, 0x85, 0xC3, 0xD0, 0xFB, 0xC3,
        ]
        param_list = []
        for i in range(0, 12, 4):
            temp = data[8 * i: 8 * (i + 1)]
            for j in range(4):
                H = int(temp[j * 2: (j + 1) * 2], 16)
                param_list.append(H)
        param_list.extend([0x0, 0x6, 0xB, 0x1C])
        H = int(hex(unix), 16)
        param_list.append((H & 0xFF000000) >> 24)
        param_list.append((H & 0x00FF0000) >> 16)
        param_list.append((H & 0x0000FF00) >> 8)
        param_list.append(H & 0x000000FF)
        eor_result_list = []
        for A, B in zip(param_list, key):
            eor_result_list.append(A ^ B)
        for i in range(len(eor_result_list)):
            C = self.reverse(eor_result_list[i])
            D = eor_result_list[(i + 1) % len(eor_result_list)]
            E = C ^ D
            F = self.rbit(E)
            H = ((F ^ 0xFFFFFFFF) ^ len(eor_result_list)) & 0xFF
            eor_result_list[i] = H
        result = ""
        for param in eor_result_list:
            result += self.hex_string(param)
        return {"X-Gorgon": "840280416000" + result, "X-Khronos": str(unix)}

    def rbit(self, num):
        result = ""
        tmp_string = bin(num)[2:]
        while len(tmp_string) < 8:
            tmp_string = "0" + tmp_string
        for i in range(8):
            result += tmp_string[7 - i]
        return int(result, 2)

    def hex_string(self, num):
        tmp_string = hex(num)[2:]
        if len(tmp_string) < 2:
            tmp_string = "0" + tmp_string
        return tmp_string

    def reverse(self, num):
        tmp_string = self.hex_string(num)
        return int(tmp_string[1:] + tmp_string[:1], 16)

def selec_proxy():
    try:
        with open('static/proxy.txt', 'r', encoding='utf8') as f:
            proxy_lines = f.readlines()
            if proxy_lines:
                proxy_line = random.choice(proxy_lines).strip()
                proxy_parts = proxy_line.replace('us 30ng |', '').split(":")
                if len(proxy_parts) < 4:
                    return None
                return {
                    "http": f"http://{proxy_parts[2].strip()}:{proxy_parts[3].strip()}@{proxy_parts[0].strip()}:{proxy_parts[1].strip()}",
                    "https": f"http://{proxy_parts[2].strip()}:{proxy_parts[3].strip()}@{proxy_parts[0].strip()}:{proxy_parts[1].strip()}",
                }
            return None
    except FileNotFoundError:
        status_messages.append({"message": "Lỗi: Không tìm thấy file proxy.txt", "type": "error"})
        return None

def handle_response(resp: dict):
    first_key = next(iter(resp), None)
    if first_key == 'status_code' and resp.get('status_code') == 0:
        extra = resp.get('extra', {})
        log_pb = resp.get('log_pb', {})
        if 'now' in extra and 'impr_id' in log_pb:
            return True
    return False

def send_view():
    global view_count, is_running
    url_view = 'https://api16-core-c-alisg.tiktokv.com/aweme/v1/aweme/stats/?ac=WIFI&op_region=VN'
    sig = Signature(params='', data='', cookies='').get_value()
    while is_running:
        with view_lock:
            if view_count >= target_views:
                is_running = False
                break
        random_hex = secrets.token_hex(16)
        headers_view = {
            'Host': 'api16-core-c-alisg.tiktokv.com',
            'Content-Length': '138',
            'Sdk-Version': '2',
            'Passport-Sdk-Version': '5.12.1',
            'X-Tt-Token': f'01{random_hex}0263ef2c096122cc1a97dec9cd12a6c75d81d3994668adfbb3ffca278855dd15c8056ad18161b26379bbf95d25d1f065abd5dd3a812f149ca11cf57e4b85ebac39d - 1.0.0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'TikTok 37.0.4 rv:174014 (iPhone; iOS 14.2; ar_SA@calendar=gregorian) Cronet',
            'X-Ss-Stub': '727D102356930EE8C1F61B112F038D96',
            'X-Tt-Store-Idc': 'alisg',
            'X-Tt-Store-Region': 'sa',
            'X-Ss-Dp': '1233',
            'X-Tt-Trace-Id': '00-33c8a619105fd09f13b65546057d04d1-33c8a619105fd09f-01',
            'Accept-Encoding': 'gzip, deflate',
            'X-Khronos': sig['X-Khronos'],
            'X-Gorgon': sig['X-Gorgon'],
            'X-Common-Params-V2': (
                "pass-region=1&pass-route=1"
                "&language=ar"
                "&version_code=17.4.0"
                "&app_name=musical_ly"
                "&vid=0F62BF08-8AD6-4A4D-A870-C098F5538A97"
                "&app_version=17.4.0"
                "&carrier_region=VN"
                "&channel=App%20Store"
                "&mcc_mnc=45201"
                "&device_id=6904193135771207173"
                "&tz_offset=25200"
                "&account_region=VN"
                "&sys_region=VN"
                "&aid=1233"
                "&residence=VN"
                "&screen_width=1125"
                "&uoo=1"
                "&openudid=c0c519b4e8148dec69410df9354e6035aa155095"
                "&os_api=18"
                "&os_version=14.2"
                "&app_language=ar"
                "&tz_name=Asia%2FHo_Chi_Minh"
                "¤t_region=VN"
                "&device_platform=iphone"
                "&build_number=174014"
                "&device_type=iPhone14,6"
                "&iid=6958149070179878658"
                "&idfa=00000000-0000-0000-0000-000000000000"
                "&locale=ar"
                "&cdid=D1D404AE-ABDF-4973-983C-CC723EA69906"
                "&content_language="
            ),
        }
        cookie_view = {'sessionid': random_hex}
        start = datetime.datetime(2020, 1, 1, 0, 0, 0)
        end = datetime.datetime(2024, 12, 31, 23, 59, 59)
        delta_seconds = int((end - start).total_seconds())
        random_offset = random.randint(0, delta_seconds)
        random_dt = start + datetime.timedelta(seconds=random_offset)
        data = {
            'action_time': int(time.time()),
            'aweme_type': 0,
            'first_install_time': int(random_dt.timestamp()),
            'item_id': video_id,
            'play_delta': 1,
            'tab_type': 4
        }
        try:
            proxy = selec_proxy()
            r = requests.post(url_view, data=data, headers=headers_view, cookies=cookie_view, proxies=proxy, timeout=10)
            if handle_response(r.json()):
                with view_lock:
                    view_count += 1
                    status_messages.append({"message": f"View tăng thành công! Tổng số views: {view_count}/{target_views}", "type": "success"})
            else:
                status_messages.append({"message": "Lỗi không thể gửi view", "type": "error"})
            sig = Signature(params='ac=WIFI&op_region=VN', data=str(data), cookies=str(cookie_view)).get_value()
        except Exception as e:
            status_messages.append({"message": f"Error sending view: {str(e)}", "type": "error"})
            time.sleep(1)
        time.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_bot', methods=['POST'])
def start_bot():
    global view_count, target_views, video_id, is_running, status_messages
    data = request.get_json()
    link = data.get('videoUrl')
    target_views = int(data.get('targetViews', 0))
    
    if not link:
        return jsonify({"error": "Vui lòng nhập link video TikTok"})
    if target_views <= 0:
        return jsonify({"error": "Số lượng cần lớn hơn 0"})
    
    # Reset state
    view_count = 0
    is_running = True
    status_messages = []
    
    # Get video ID
    headers_id = {
        'Connection': 'close',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36',
        'Accept': 'text/html'
    }
    try:
        page = requests.get(link, headers=headers_id, timeout=10).text
        match = re.search(r'"video":\{"id":"(\d+)"', page)
        if match:
            video_id = match.group(1)
            status_messages.append({"message": f"ID VIDEO: {video_id}", "type": "info"})
        else:
            is_running = False
            return jsonify({"error": "Không tìm thấy video! Kiểm tra lại link."})
    except Exception as e:
        is_running = False
        return jsonify({"error": f"Lỗi rồi: {str(e)}"})
    
    # Start bot threads
    thread_count = min(500, target_views)
    threads = []
    for i in range(thread_count):
        t = threading.Thread(target=send_view)
        t.daemon = True
        t.start()
        threads.append(t)
    
    return jsonify({"videoId": video_id})

@app.route('/bot_status')
def bot_status():
    global view_count, is_running, status_messages
    messages = status_messages[:]
    status_messages = []  # Clear messages after sending
    return jsonify({
        "viewCount": view_count,
        "isRunning": is_running,
        "messages": messages
    })
@app.route('/admin')
def admin_panel():
    return render_template('admin.html',
        is_running=is_running,
        target_views=target_views,
        view_count=view_count,
        video_id=video_id
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
