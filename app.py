from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import re
import threading
import time
from hashlib import md5
import secrets
import datetime
import random
import os
from concurrent.futures import ThreadPoolExecutor
import logging
from functools import lru_cache

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))  # Secure secret key
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '123456')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global state with proper synchronization
class BotState:
    def __init__(self):
        self.view_count = 0
        self.target_views = 0
        self.video_id = ''
        self.is_running = False
        self.status_messages = []
        self.view_lock = threading.Lock()
        self.proxies = self.load_proxies()

    def load_proxies(self):
        try:
            with open('static/proxy.txt', 'r', encoding='utf-8') as f:
                proxies = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.replace('us 30ng |', '').split(':')
                    if len(parts) == 4:
                        proxies.append({
                            'http': f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}',
                            'https': f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                        })
                return proxies
        except FileNotFoundError:
            logger.error("Proxy file not found: static/proxy.txt")
            return []
        except Exception as e:
            logger.error(f"Error loading proxies: {str(e)}")
            return []

    def select_proxy(self):
        return random.choice(self.proxies) if self.proxies else None

bot_state = BotState()

class Signature:
    def __init__(self, params: str, data: str, cookies: str) -> None:
        self.params = params
        self.data = data
        self.cookies = cookies

    def hash(self, data: str) -> str:
        return md5(data.encode()).hexdigest()

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
                try:
                    H = int(temp[j * 2: (j + 1) * 2], 16)
                    param_list.append(H)
                except ValueError:
                    logger.error(f"Invalid hex in signature: {temp}")
                    return None
        param_list.extend([0x0, 0x6, 0xB, 0x1C])
        H = int(hex(unix), 16)
        param_list.extend([(H >> 24) & 0xFF, (H >> 16) & 0xFF, (H >> 8) & 0xFF, H & 0xFF])
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
        tmp_string = bin(num)[2:].zfill(8)
        for i in range(8):
            result += tmp_string[7 - i]
        return int(result, 2)

    def hex_string(self, num):
        tmp_string = hex(num)[2:].zfill(2)
        return tmp_string

    def reverse(self, num):
        tmp_string = self.hex_string(num)
        return int(tmp_string[1:] + tmp_string[:1], 16)

def handle_response(resp: dict):
    try:
        if resp.get('status_code') == 0:
            extra = resp.get('extra', {})
            log_pb = resp.get('log_pb', {})
            return 'now' in extra and 'impr_id' in log_pb
        return False
    except Exception as e:
        logger.error(f"Error handling response: {str(e)}")
        return False

def send_view():
    url_view = 'https://api16-core-c-alisg.tiktokv.com/aweme/v1/aweme/stats/?ac=WIFI&op_region=VN'
    while bot_state.is_running:
        with bot_state.view_lock:
            if bot_state.view_count >= bot_state.target_views:
                bot_state.is_running = False
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
        }
        cookie_view = {'sessionid': random_hex}
        start = datetime.datetime(2020, 1, 1)
        end = datetime.datetime(2024, 12, 31, 23, 59, 59)
        random_dt = start + datetime.timedelta(seconds=random.randint(0, int((end - start).total_seconds())))
        data = {
            'action_time': int(time.time()),
            'aweme_type': 0,
            'first_install_time': int(random_dt.timestamp()),
            'item_id': bot_state.video_id,
            'play_delta': 1,
            'tab_type': 4
        }
        sig = Signature(params='ac=WIFI&op_region=VN', data=str(data), cookies=str(cookie_view)).get_value()
        if not sig:
            bot_state.status_messages.append({"message": "Failed to generate signature", "type": "error"})
            continue
        headers_view.update(sig)
        try:
            proxy = bot_state.select_proxy()
            if not proxy:
                bot_state.status_messages.append({"message": "No valid proxy available", "type": "error"})
                time.sleep(1)
                continue
            r = requests.post(url_view, data=data, headers=headers_view, cookies=cookie_view, proxies=proxy, timeout=5)
            r.raise_for_status()
            if handle_response(r.json()):
                with bot_state.view_lock:
                    bot_state.view_count += 1
                    bot_state.status_messages.append({
                        "message": f"View sent successfully! Total views: {bot_state.view_count}/{bot_state.target_views}",
                        "type": "success"
                    })
            else:
                bot_state.status_messages.append({"message": "Failed to send view", "type": "error"})
        except requests.RequestException as e:
            logger.error(f"Error sending view: {str(e)}")
            bot_state.status_messages.append({"message": f"Error sending view: {str(e)}", "type": "error"})
            time.sleep(1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_bot', methods=['POST'])
def start_bot():
    data = request.get_json()
    link = data.get('videoUrl')
    bot_state.target_views = int(data.get('targetViews', 0))

    if not link:
        return jsonify({"error": "Please provide a TikTok video link"}), 400
    if bot_state.target_views <= 0:
        return jsonify({"error": "Target views must be greater than 0"}), 400

    # Reset state
    with bot_state.view_lock:
        bot_state.view_count = 0
        bot_state.is_running = True
        bot_state.status_messages = []
        bot_state.video_id = ''

    # Get video ID
    headers_id = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36',
        'Accept': 'text/html'
    }
    try:
        page = requests.get(link, headers=headers_id, timeout=10).text
        match = re.search(r'"video":\{"id":"(\d+)"', page)
        if match:
            bot_state.video_id = match.group(1)
            bot_state.status_messages.append({"message": f"Video ID: {bot_state.video_id}", "type": "info"})
        else:
            bot_state.is_running = False
            return jsonify({"error": "Video not found. Check the link."}), 400
    except requests.RequestException as e:
        bot_state.is_running = False
        return jsonify({"error": f"Error fetching video ID: {str(e)}"}), 500

    # Start bot with thread pool
    thread_count = min(50, bot_state.target_views)  # Reduced thread count for stability
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        for _ in range(thread_count):
            executor.submit(send_view)

    return jsonify({"videoId": bot_state.video_id})

@app.route('/bot_status')
def bot_status():
    with bot_state.view_lock:
        messages = bot_state.status_messages[:]
        bot_state.status_messages = []
        return jsonify({
            "viewCount": bot_state.view_count,
            "isRunning": bot_state.is_running,
            "messages": messages
        })

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error='Invalid username or password'), 401
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    with bot_state.view_lock:
        return render_template('admin.html',
                              is_running=bot_state.is_running,
                              target_views=bot_state.target_views,
                              view_count=bot_state.view_count,
                              video_id=bot_state.video_id,
                              access_log=[])  # Access log not implemented in original code

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)  # Debug disabled for production
