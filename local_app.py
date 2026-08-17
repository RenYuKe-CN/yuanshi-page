#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import cgi
import hashlib
import hmac
import html
import io
import ipaddress
import json
import os
import re
import secrets
import smtplib
import sqlite3
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "local_data")
DB_PATH = os.path.join(DATA_DIR, "yuanshi_jinshouzhi.db")
OLD_DB_PATH = os.path.join(DATA_DIR, "zm_dingsheng.db")
LEGACY_DB_PATH = os.path.join(DATA_DIR, "ipguard.db")
ADMIN_FILE = os.path.join(DATA_DIR, "admin.txt")
CMC_KEY_FILE = os.path.join(DATA_DIR, "cmc_api_key.txt")
CMC_ICON_DIR = os.path.join(DATA_DIR, "exchange_icons")
CMC_ICON_MAP_FILE = os.path.join(DATA_DIR, "exchange_icons.json")
EXCHANGE_CATALOG_FILE = os.path.join(DATA_DIR, "exchange_catalog.json")
WEB3_RISK_CONFIG_FILE = os.path.join(DATA_DIR, "web3_risk.json")
IP_RISK_CONFIG_FILE = os.path.join(DATA_DIR, "ip_risk.json")
SYSTEM_CONFIG_FILE = os.path.join(DATA_DIR, "system.json")
BRAND_LOGO_FILE = os.path.join(DATA_DIR, "site_logo.png")
PAYMENT_RECEIVER = "0x04bCA584834489C26d6474701400c88D954B7782"
BSC_RPC_URL = os.environ.get("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
# Wallet risk queries intentionally do not fall back to fabricated demo data. Configure
# an audited node/API in the server environment before exposing live wallet balances.
EVM_RPC_URL = os.environ.get("EVM_RPC_URL", "").strip()
SOLANA_RPC_URL = os.environ.get("SOLANA_RPC_URL", "").strip()
TRON_API_URL = os.environ.get("TRON_API_URL", "").strip()
BTC_API_URL = os.environ.get("BTC_API_URL", "").strip()
TOKEN_CONTRACTS = {
    "USDT": "0x55d398326f99059ff775485246999027b3197955",
    "USDC": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
}
PLAN_CONFIG = {
    "STARSHIP": {"name": "星舰会员", "price": 12.0, "limits": {"ip": 10, "device": 10, "wallet": 5}, "days": 30},
    "PRO": {"name": "旗舰 PRO", "price": 39.9, "limits": {"ip": 60, "device": 60, "wallet": 60}, "days": 30},
    "MAX": {"name": "旗舰 MAX", "price": 128.88, "limits": {"ip": -1, "device": -1, "wallet": -1}, "days": 30},
}
QUERY_QUOTA_FIELDS = {
    "ip": ("ip_query_limit", "ip_query_used", "IP 查询"),
    "device": ("device_query_limit", "device_query_used", "设备查询"),
    "wallet": ("wallet_query_limit", "wallet_query_used", "钱包查询"),
}
MEMBERSHIP_PERIODS = {
    1: {"name": "1 个月", "prices": {"STARSHIP": 12.0, "PRO": 39.9, "MAX": 128.88}},
    3: {"name": "3 个月", "prices": {"STARSHIP": 33.0, "PRO": 109.0, "MAX": 347.98}},
    6: {"name": "6 个月", "prices": {"STARSHIP": 60.0, "PRO": 199.0, "MAX": 541.30}},
    12: {"name": "年会员", "prices": {"STARSHIP": 96.0, "PRO": 319.0, "MAX": 1031.04}},
}
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
SMTP_MODE = os.environ.get("SMTP_MODE", "starttls")
BRAND_DIR = os.path.join(BASE_DIR, "public", "brand")
EXCHANGE_DATA_PATH = os.path.join(BASE_DIR, "data", "exchanges.json")
ASSETS = {
    "/assets/ck-logo.jpg": (os.path.join(BRAND_DIR, "ck-logo.jpg"), "image/jpeg"),
    "/assets/site-logo": (BRAND_LOGO_FILE, "image/png"),
    "/assets/crypto-background.jpg": (os.path.join(BRAND_DIR, "crypto-background.jpg"), "image/jpeg"),
    "/assets/exchange-picker.js": (os.path.join(BRAND_DIR, "exchange-picker.js"), "text/javascript; charset=utf-8"),
    "/assets/market-ticker.js": (os.path.join(BRAND_DIR, "market-ticker.js"), "text/javascript; charset=utf-8"),
    "/assets/exchange-fx-protocol.png": (os.path.join(BRAND_DIR, "exchanges", "fx-protocol.png"), "image/png"),
    "/assets/exchange-fx100.png": (os.path.join(BRAND_DIR, "exchanges", "fx100.png"), "image/png"),
}
MANUAL_EXCHANGE_ICONS = {
    "f(x) Protocol": "/assets/exchange-fx-protocol.png",
    "FX100": "/assets/exchange-fx100.png",
}
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "3000"))
SESSIONS = {}
RATE_LIMITS = {}
with open(EXCHANGE_DATA_PATH, "r", encoding="utf-8") as exchange_file:
    EXCHANGE_DATA = json.load(exchange_file)
CEX_EXCHANGES = EXCHANGE_DATA["cex"]
DEX_EXCHANGES = EXCHANGE_DATA["dex"]
EXCHANGE_GROUPS = (("CEX 中心化交易所", CEX_EXCHANGES), ("DEX 去中心化交易所", DEX_EXCHANGES), ("其他", ["其他"]))
EXCHANGES = {name: name for _, names in EXCHANGE_GROUPS for name in names}
LEGACY_EXCHANGES = {"BITRUE": "Bitrue", "HOTCOIN": "Hotcoin", "MGBX": "MGBX", "OTHER": "其他"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-\u4e00-\u9fff]{3,40}$")
ALLOWED_EMAIL_DOMAINS = (
    "gmail.com",
    "qq.com",
    "outlook.com",
    "hotmail.com",
    "163.com",
    "icloud.com",
    "me.com",
    "yahoo.com",
    "proton.me",
    "protonmail.com",
    "aliyun.com",
    "zoho.com",
)
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")
EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
SOLANA_ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
TRON_ADDRESS_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
BTC_ADDRESS_RE = re.compile(r"^(?:bc1[ac-hj-np-z02-9]{11,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")

# Centralized metadata prevents chain, wallet, exchange and protocol icons from being
# guessed in components. Assets may be added later; until then a neutral fallback is
# rendered and iconVerified remains false.
FALLBACK_ICON = {"name": "未知", "symbol": "?", "icon": "", "type": "unknown", "fallbackIcon": "?", "iconVerified": False}
CHAIN_ICON_MAP = {
    "ethereum": {"name": "Ethereum", "symbol": "ETH", "icon": "", "type": "chain", "fallbackIcon": "ETH", "iconVerified": False},
    "bnb": {"name": "BNB Chain", "symbol": "BNB", "icon": "", "type": "chain", "fallbackIcon": "BNB", "iconVerified": False},
    "polygon": {"name": "Polygon", "symbol": "POL", "icon": "", "type": "chain", "fallbackIcon": "POL", "iconVerified": False},
    "arbitrum": {"name": "Arbitrum", "symbol": "ARB", "icon": "", "type": "chain", "fallbackIcon": "ARB", "iconVerified": False},
    "optimism": {"name": "Optimism", "symbol": "OP", "icon": "", "type": "chain", "fallbackIcon": "OP", "iconVerified": False},
    "base": {"name": "Base", "symbol": "BASE", "icon": "", "type": "chain", "fallbackIcon": "BASE", "iconVerified": False},
    "avalanche": {"name": "Avalanche", "symbol": "AVAX", "icon": "", "type": "chain", "fallbackIcon": "AVAX", "iconVerified": False},
    "solana": {"name": "Solana", "symbol": "SOL", "icon": "", "type": "chain", "fallbackIcon": "SOL", "iconVerified": False},
    "tron": {"name": "TRON", "symbol": "TRX", "icon": "", "type": "chain", "fallbackIcon": "TRX", "iconVerified": False},
    "bitcoin": {"name": "Bitcoin", "symbol": "BTC", "icon": "", "type": "chain", "fallbackIcon": "BTC", "iconVerified": False},
    "ton": {"name": "Ton", "symbol": "TON", "icon": "", "type": "chain", "fallbackIcon": "TON", "iconVerified": False},
    "aptos": {"name": "Aptos", "symbol": "APT", "icon": "", "type": "chain", "fallbackIcon": "APT", "iconVerified": False},
    "sui": {"name": "Sui", "symbol": "SUI", "icon": "", "type": "chain", "fallbackIcon": "SUI", "iconVerified": False},
    "cosmos": {"name": "Cosmos", "symbol": "ATOM", "icon": "", "type": "chain", "fallbackIcon": "ATOM", "iconVerified": False},
}
WALLET_ICON_MAP = {name: {"name": name, "symbol": name[:3].upper(), "icon": "", "type": "wallet", "fallbackIcon": "W", "iconVerified": False} for name in ("MetaMask", "Phantom", "TronLink", "OKX Wallet", "Binance Web3 Wallet", "Coinbase Wallet", "Trust Wallet", "TokenPocket", "imToken", "Ledger", "Safe")}
EXCHANGE_ICON_MAP = {name: {"name": name, "symbol": name[:4].upper(), "icon": "", "type": "cex", "fallbackIcon": "CEX", "iconVerified": False} for name in ("Binance", "OKX", "Bybit", "Coinbase", "Kraken", "Gate", "KuCoin", "HTX", "Bitget", "MEXC")}
PROTOCOL_ICON_MAP = {name: {"name": name, "symbol": name[:4].upper(), "icon": "", "type": "dex", "fallbackIcon": "DEX", "iconVerified": False} for name in ("Uniswap", "PancakeSwap", "Curve", "Balancer", "SushiSwap", "Raydium", "Jupiter", "1inch", "GMX", "Aave", "Compound", "MakerDAO", "Lido", "EigenLayer")}
CHECK_TYPES = {
    "ip": {"label": "IP 地址检测", "placeholder": "请输入 IPv4 / IPv6 地址", "chain": "", "kind": "ip"},
    "wallet": {"label": "钱包地址检测", "placeholder": "请输入钱包地址", "chain": "", "kind": "wallet"},
    "interaction": {"label": "钱包交互地址检测", "placeholder": "请输入需要分析的钱包地址", "chain": "", "kind": "interaction"},
    "evm": {"label": "EVM 地址检测", "placeholder": "请输入 0x 开头的钱包地址", "chain": "ethereum", "kind": "wallet"},
    "solana": {"label": "Solana 地址检测", "placeholder": "请输入 Solana 钱包地址", "chain": "solana", "kind": "wallet"},
    "tron": {"label": "TRON / 波场地址检测", "placeholder": "请输入 T 开头的波场地址", "chain": "tron", "kind": "wallet"},
    "btc": {"label": "BTC 地址检测", "placeholder": "请输入 BTC 地址", "chain": "bitcoin", "kind": "wallet"},
    "other": {"label": "其他链地址检测", "placeholder": "请输入其他链钱包地址", "chain": "", "kind": "wallet"},
}
BUSINESS_ITEMS = (
    ("⛁", "EFTT新增"),
    ("⌕", "交易所流动性提供"),
    ("◇", "流动性策略"),
    ("▣", "BD保职 & BD入职"),
    ("▤", "项目社区运营"),
    ("◎", "推特运营"),
    ("❉", "客户留存"),
    ("⬡", "合约量化开发"),
    ("◷", "后续直播、转化等业务"),
)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def db():
    if not os.path.exists(DB_PATH) and os.path.exists(OLD_DB_PATH):
        os.replace(OLD_DB_PATH, DB_PATH)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
    return "pbkdf2_sha256$310000$%s$%s" % (salt.hex(), digest.hex())


def verify_password(password, encoded):
    try:
        algorithm, rounds, salt_hex, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH) and os.path.exists(LEGACY_DB_PATH):
        source = sqlite3.connect(LEGACY_DB_PATH)
        target = sqlite3.connect(DB_PATH)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE,
          email TEXT UNIQUE,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('ADMIN','USER')),
          is_owner INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','DISABLED')),
          last_login_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ip_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          full_ip TEXT NOT NULL,
          segment_a INTEGER NOT NULL,
          segment_b INTEGER NOT NULL,
          segment_c INTEGER NOT NULL,
          segment_d INTEGER NOT NULL,
          exchange TEXT NOT NULL,
          user_id INTEGER NOT NULL REFERENCES users(id),
          query_count INTEGER NOT NULL DEFAULT 1,
          last_similarity INTEGER NOT NULL DEFAULT 0,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(full_ip, exchange)
        );
        CREATE TABLE IF NOT EXISTS operation_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER REFERENCES users(id),
          action TEXT NOT NULL,
          target_type TEXT NOT NULL,
          target_id TEXT,
          detail TEXT,
          ip_address TEXT,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ip_full ON ip_records(full_ip);
        CREATE INDEX IF NOT EXISTS idx_ip_segments ON ip_records(segment_a,segment_b,segment_c,segment_d);
        CREATE INDEX IF NOT EXISTS idx_ip_exchange ON ip_records(exchange);
        CREATE INDEX IF NOT EXISTS idx_ip_user ON ip_records(user_id);
        CREATE INDEX IF NOT EXISTS idx_ip_created ON ip_records(created_at);
        CREATE TABLE IF NOT EXISTS email_verification_codes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT NOT NULL,
          code_hash TEXT NOT NULL,
          purpose TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          used_at TEXT,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_email_codes_email ON email_verification_codes(email, purpose, created_at);
        CREATE TABLE IF NOT EXISTS membership_orders (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          order_no TEXT NOT NULL UNIQUE,
          user_id INTEGER NOT NULL REFERENCES users(id),
          plan TEXT NOT NULL,
          token TEXT NOT NULL,
          amount REAL NOT NULL,
          receiver TEXT NOT NULL,
          tx_hash TEXT UNIQUE,
          status TEXT NOT NULL DEFAULT 'PENDING',
          verify_detail TEXT,
          paid_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_membership_orders_user ON membership_orders(user_id, created_at);
        CREATE TABLE IF NOT EXISTS wallet_checks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          address TEXT NOT NULL,
          check_type TEXT NOT NULL,
          user_id INTEGER NOT NULL REFERENCES users(id),
          risk_score INTEGER NOT NULL,
          result TEXT,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_wallet_checks_address ON wallet_checks(address);
        CREATE TABLE IF NOT EXISTS email_announcements (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          sender_user_id INTEGER NOT NULL REFERENCES users(id),
          subject TEXT NOT NULL,
          audience TEXT NOT NULL,
          recipient_count INTEGER NOT NULL DEFAULT 0,
          sent_count INTEGER NOT NULL DEFAULT 0,
          failed_count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_email_announcements_created ON email_announcements(created_at);
        CREATE TABLE IF NOT EXISTS site_announcements (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          sender_user_id INTEGER NOT NULL REFERENCES users(id),
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          popup_enabled INTEGER NOT NULL DEFAULT 1,
          status TEXT NOT NULL DEFAULT 'PUBLISHED' CHECK(status IN ('PUBLISHED','ARCHIVED')),
          published_at TEXT NOT NULL,
          expires_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_site_announcements_active ON site_announcements(status,popup_enabled,published_at);
        CREATE TABLE IF NOT EXISTS site_announcement_receipts (
          announcement_id INTEGER NOT NULL REFERENCES site_announcements(id),
          user_id INTEGER NOT NULL REFERENCES users(id),
          seen_at TEXT,
          muted_at TEXT,
          deleted_at TEXT,
          PRIMARY KEY (announcement_id,user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_site_announcement_receipts_user ON site_announcement_receipts(user_id,announcement_id);
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "recovery_hash" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN recovery_hash TEXT")
        if "email" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if "deleted_at" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN deleted_at TEXT")
        if "is_owner" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_owner INTEGER NOT NULL DEFAULT 0")
        for column, ddl in [
            ("membership_plan", "ALTER TABLE users ADD COLUMN membership_plan TEXT NOT NULL DEFAULT 'FREE'"),
            ("membership_status", "ALTER TABLE users ADD COLUMN membership_status TEXT NOT NULL DEFAULT 'FREE'"),
            ("query_limit", "ALTER TABLE users ADD COLUMN query_limit INTEGER NOT NULL DEFAULT 0"),
            ("query_used", "ALTER TABLE users ADD COLUMN query_used INTEGER NOT NULL DEFAULT 0"),
            ("ip_query_limit", "ALTER TABLE users ADD COLUMN ip_query_limit INTEGER NOT NULL DEFAULT 0"),
            ("ip_query_used", "ALTER TABLE users ADD COLUMN ip_query_used INTEGER NOT NULL DEFAULT 0"),
            ("device_query_limit", "ALTER TABLE users ADD COLUMN device_query_limit INTEGER NOT NULL DEFAULT 0"),
            ("device_query_used", "ALTER TABLE users ADD COLUMN device_query_used INTEGER NOT NULL DEFAULT 0"),
            ("wallet_query_limit", "ALTER TABLE users ADD COLUMN wallet_query_limit INTEGER NOT NULL DEFAULT 0"),
            ("wallet_query_used", "ALTER TABLE users ADD COLUMN wallet_query_used INTEGER NOT NULL DEFAULT 0"),
            ("membership_expires_at", "ALTER TABLE users ADD COLUMN membership_expires_at TEXT"),
            ("bound_device_token", "ALTER TABLE users ADD COLUMN bound_device_token TEXT"),
            ("email_verified_at", "ALTER TABLE users ADD COLUMN email_verified_at TEXT"),
        ]:
            if column not in columns:
                conn.execute(ddl)
        # Migrate the legacy shared quota to per-query quotas without discarding
        # already consumed IP checks. New purchases always reset all quotas.
        conn.execute("""UPDATE users SET ip_query_used=query_used
                        WHERE ip_query_used=0 AND query_used>0""")
        # Do not reapply plan defaults at startup. Membership activation is the
        # only reset point, while administrator top-ups must survive restarts.
        order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(membership_orders)").fetchall()}
        if "months" not in order_columns:
            conn.execute("ALTER TABLE membership_orders ADD COLUMN months INTEGER NOT NULL DEFAULT 1")
        ip_columns = {row["name"] for row in conn.execute("PRAGMA table_info(ip_records)").fetchall()}
        for column, ddl in [
            ("country", "ALTER TABLE ip_records ADD COLUMN country TEXT"),
            ("region", "ALTER TABLE ip_records ADD COLUMN region TEXT"),
            ("city", "ALTER TABLE ip_records ADD COLUMN city TEXT"),
            ("isp", "ALTER TABLE ip_records ADD COLUMN isp TEXT"),
            ("asn", "ALTER TABLE ip_records ADD COLUMN asn TEXT"),
            ("ip_type", "ALTER TABLE ip_records ADD COLUMN ip_type TEXT"),
            ("purity_score", "ALTER TABLE ip_records ADD COLUMN purity_score INTEGER"),
            ("is_proxy", "ALTER TABLE ip_records ADD COLUMN is_proxy INTEGER"),
            ("is_vpn", "ALTER TABLE ip_records ADD COLUMN is_vpn INTEGER"),
            ("is_tor", "ALTER TABLE ip_records ADD COLUMN is_tor INTEGER"),
            ("is_datacenter", "ALTER TABLE ip_records ADD COLUMN is_datacenter INTEGER"),
            ("ip_source", "ALTER TABLE ip_records ADD COLUMN ip_source TEXT"),
            ("ip_checked_at", "ALTER TABLE ip_records ADD COLUMN ip_checked_at TEXT"),
        ]:
            if column not in ip_columns:
                conn.execute(ddl)
        announcement_receipt_columns = {row["name"] for row in conn.execute("PRAGMA table_info(site_announcement_receipts)").fetchall()}
        if "deleted_at" not in announcement_receipt_columns:
            conn.execute("ALTER TABLE site_announcement_receipts ADD COLUMN deleted_at TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        for legacy, current in LEGACY_EXCHANGES.items():
            conn.execute("UPDATE ip_records SET exchange=? WHERE exchange=?", (current, legacy))
        if not conn.execute("SELECT id FROM users LIMIT 1").fetchone():
            password = secrets.token_urlsafe(12)
            recovery_code = secrets.token_urlsafe(18)
            ts = now()
            conn.execute(
                "INSERT INTO users(username,password_hash,recovery_hash,role,is_owner,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                ("admin", hash_password(password), hash_password(recovery_code), "ADMIN", 1, "ACTIVE", ts, ts),
            )
            with open(ADMIN_FILE, "w", encoding="utf-8") as f:
                f.write("总管理员账号：admin\n总管理员密码：%s\n总管理员恢复码：%s\n" % (password, recovery_code))
            os.chmod(ADMIN_FILE, 0o600)
        if not conn.execute("SELECT id FROM users WHERE is_owner=1 AND deleted_at IS NULL LIMIT 1").fetchone():
            first_admin = conn.execute("SELECT id FROM users WHERE role='ADMIN' AND deleted_at IS NULL ORDER BY id LIMIT 1").fetchone()
            if first_admin:
                conn.execute("UPDATE users SET is_owner=1 WHERE id=?", (first_admin["id"],))
        owner = conn.execute("SELECT id,username,recovery_hash FROM users WHERE is_owner=1 AND deleted_at IS NULL LIMIT 1").fetchone()
        if owner and not owner["recovery_hash"]:
            recovery_code = secrets.token_urlsafe(18)
            conn.execute("UPDATE users SET recovery_hash=?,updated_at=? WHERE id=?", (hash_password(recovery_code), now(), owner["id"]))
            with open(ADMIN_FILE, "a", encoding="utf-8") as f:
                f.write("总管理员恢复码：%s\n" % recovery_code)
            os.chmod(ADMIN_FILE, 0o600)
        if owner and os.path.exists(ADMIN_FILE):
            with open(ADMIN_FILE, "r", encoding="utf-8") as f:
                admin_text = f.read()
            admin_lines = []
            for line in admin_text.splitlines(keepends=True):
                if line.startswith("管理员账号："):
                    line = "总" + line
                elif line.startswith("管理员密码："):
                    line = "总" + line
                admin_lines.append(line)
            with open(ADMIN_FILE, "w", encoding="utf-8") as f:
                f.write("".join(admin_lines))
            os.chmod(ADMIN_FILE, 0o600)


def esc(value):
    return html.escape(str(value if value is not None else ""))


def allowed_email(value):
    email = (value or "").strip().lower()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        return False
    return email.rsplit("@", 1)[-1] in ALLOWED_EMAIL_DOMAINS


def email_suffix_options(selected="@gmail.com"):
    return "".join(
        '<option value="@%s"%s>@%s</option>' % (
            esc(domain),
            " selected" if selected == ("@" + domain) else "",
            esc(domain),
        )
        for domain in ALLOWED_EMAIL_DOMAINS
    )


def smtp_config_file():
    return os.path.join(DATA_DIR, "smtp.json")


def load_smtp_config():
    config = {}
    try:
        with open(smtp_config_file(), "r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            config = loaded
    except (OSError, ValueError):
        pass
    return {
        "host": str(config.get("host") or SMTP_HOST).strip(),
        "port": int(config.get("port") or SMTP_PORT),
        "user": str(config.get("user") or SMTP_USER).strip(),
        "password": str(config.get("password") or SMTP_PASSWORD),
        "from": str(config.get("from") or SMTP_FROM).strip(),
        "mode": str(config.get("mode") or SMTP_MODE).strip().lower(),
    }


def save_smtp_config(config):
    path = smtp_config_file()
    with open(path, "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
    os.chmod(path, 0o600)


def load_web3_risk_config():
    defaults = {
        "evm_rpc_url": EVM_RPC_URL,
        "solana_rpc_url": SOLANA_RPC_URL,
        "goplus_enabled": False,
        "goplus_base_url": "https://api.gopluslabs.io/api/v1",
        "goplus_api_key": "",
        "label_api_url": "",
        "label_api_key": "",
        "profile_api_url": "",
        "profile_api_key": "",
    }
    try:
        with open(WEB3_RISK_CONFIG_FILE, "r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            defaults.update({key: value for key, value in loaded.items() if key in defaults})
    except (OSError, ValueError):
        pass
    return defaults


def save_web3_risk_config(config):
    with open(WEB3_RISK_CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
    os.chmod(WEB3_RISK_CONFIG_FILE, 0o600)


def load_ip_risk_config():
    defaults = {"enabled": False, "provider": "IPQualityScore", "api_url": "", "api_key": ""}
    try:
        with open(IP_RISK_CONFIG_FILE, "r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            defaults.update({key: value for key, value in loaded.items() if key in defaults})
    except (OSError, ValueError):
        pass
    return defaults


def save_ip_risk_config(config):
    with open(IP_RISK_CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
    os.chmod(IP_RISK_CONFIG_FILE, 0o600)


def load_system_config():
    defaults = {
        "payment_receiver": PAYMENT_RECEIVER,
        "site_name": "OriginX",
        "site_tagline": "WEB3 风控终端",
        "site_logo": "/assets/site-logo",
    }
    try:
        with open(SYSTEM_CONFIG_FILE, "r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            if EVM_ADDRESS_RE.fullmatch(str(loaded.get("payment_receiver", ""))):
                defaults["payment_receiver"] = loaded["payment_receiver"]
            if isinstance(loaded.get("site_name"), str) and loaded["site_name"].strip():
                defaults["site_name"] = loaded["site_name"].strip()[:80]
            if isinstance(loaded.get("site_tagline"), str):
                defaults["site_tagline"] = loaded["site_tagline"].strip()[:120]
            if loaded.get("site_logo") == "/assets/site-logo" and os.path.exists(BRAND_LOGO_FILE):
                defaults["site_logo"] = "/assets/site-logo"
    except (OSError, ValueError):
        pass
    return defaults


def save_system_config(config):
    current = load_system_config()
    current.update(config)
    with open(SYSTEM_CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(current, file, ensure_ascii=False, indent=2)
    os.chmod(SYSTEM_CONFIG_FILE, 0o600)


def site_brand_config():
    config = load_system_config()
    has_uploaded_logo = config.get("site_logo") == "/assets/site-logo" and os.path.exists(BRAND_LOGO_FILE)
    if has_uploaded_logo:
        # The URL changes only after an upload, so browsers can cache it indefinitely.
        logo = "/assets/site-logo?v=%s" % os.stat(BRAND_LOGO_FILE).st_mtime_ns
    else:
        logo = "/assets/ck-logo.jpg"
    return {
        "name": config.get("site_name") or "OriginX",
        "tagline": config.get("site_tagline") or "WEB3 风控终端",
        "logo": logo,
    }


def save_uploaded_brand_logo(data):
    """Normalize an owner-uploaded site logo into a private PNG asset."""
    if not data or len(data) > EXCHANGE_ICON_UPLOAD_MAX_BYTES:
        raise ValueError("Logo 文件不能为空，且不能超过 4 MB。")
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise ValueError("服务器未安装图片处理组件，请联系管理员安装 Pillow 后重试。")
    try:
        source = Image.open(io.BytesIO(data))
        image_format = (source.format or "").upper()
        if image_format not in ("PNG", "JPEG", "WEBP"):
            raise ValueError("仅支持 PNG、JPG 或 WebP Logo。")
        if source.width * source.height > EXCHANGE_ICON_UPLOAD_MAX_PIXELS:
            raise ValueError("Logo 像素过大，请上传小于 1600 万像素的图片。")
        source = ImageOps.exif_transpose(source).convert("RGBA")
        source.load()
        # Uploads frequently include transparent export margins. Trim them so the
        # responsive rounded logo frame can preserve the actual brand proportions.
        alpha_bounds = source.getchannel("A").getbbox()
        if alpha_bounds:
            source = source.crop(alpha_bounds)
        source.thumbnail((512, 512), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        source.save(output, format="PNG", optimize=True)
    except ValueError:
        raise
    except Exception:
        raise ValueError("图片内容无法读取，可能是文件损坏、扩展名与真实格式不符，或尚未下载完整。请重新导出为标准 PNG、JPG 或 WebP 后上传。")
    os.makedirs(DATA_DIR, mode=0o700, exist_ok=True)
    temporary = BRAND_LOGO_FILE + ".tmp"
    with open(temporary, "wb") as file:
        file.write(output.getvalue())
    os.chmod(temporary, 0o600)
    os.replace(temporary, BRAND_LOGO_FILE)
    return "/assets/site-logo"


EXCHANGE_GROUP_META = {
    "cex": {"label": "CEX 中心化交易所", "short": "CEX"},
    "dex": {"label": "DEX 去中心化交易所", "short": "DEX"},
    "other": {"label": "其他", "short": "其他"},
}
EXCHANGE_ICON_FILE_RE = re.compile(r"^[0-9a-f]{32}\.png$")
EXCHANGE_ICON_UPLOAD_MAX_BYTES = 4 * 1024 * 1024
EXCHANGE_ICON_UPLOAD_MAX_PIXELS = 16 * 1024 * 1024


def exchange_catalog_seed():
    """Turn the versioned base list into a server-local editable catalog."""
    items = []
    for group, names in (("cex", CEX_EXCHANGES), ("dex", DEX_EXCHANGES), ("other", ["其他"])):
        for order, name in enumerate(names, 1):
            items.append({
                "id": "%s-%s" % (group, hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]),
                "name": name,
                "group": group,
                "order": order,
                "aliases": [],
                "icon_file": "",
                "icon_text": "",
                "enabled": True,
                "created_at": now(),
                "updated_at": now(),
            })
    return {"version": 1, "items": items}


def normalize_exchange_catalog(raw):
    items = raw.get("items", []) if isinstance(raw, dict) else []
    normalized, names, ids = [], set(), set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        group = str(item.get("group") or "").lower()
        item_id = str(item.get("id") or "").strip()
        if not name or len(name) > 80 or group not in EXCHANGE_GROUP_META or not item_id or item_id in ids:
            continue
        name_key = name.casefold()
        if name_key in names:
            continue
        aliases = []
        for value in item.get("aliases", []):
            value = str(value).strip()
            if value and len(value) <= 80 and value.casefold() != name_key and value.casefold() not in {v.casefold() for v in aliases}:
                aliases.append(value)
        try:
            order = max(1, int(item.get("order", index + 1)))
        except (TypeError, ValueError):
            order = index + 1
        icon_file = str(item.get("icon_file") or "").strip().lower()
        normalized.append({
            "id": item_id,
            "name": name,
            "group": group,
            "order": order,
            "aliases": aliases,
            "icon_file": icon_file if EXCHANGE_ICON_FILE_RE.fullmatch(icon_file) else "",
            "icon_text": str(item.get("icon_text") or "").strip()[:6],
            "enabled": bool(item.get("enabled", True)),
            "created_at": str(item.get("created_at") or now()),
            "updated_at": str(item.get("updated_at") or now()),
        })
        names.add(name_key)
        ids.add(item_id)
    for group in EXCHANGE_GROUP_META:
        group_items = sorted((item for item in normalized if item["group"] == group), key=lambda item: (item["order"], item["name"].casefold()))
        for order, item in enumerate(group_items, 1):
            item["order"] = order
    return {"version": 1, "items": normalized}


def load_exchange_catalog():
    try:
        with open(EXCHANGE_CATALOG_FILE, "r", encoding="utf-8") as file:
            catalog = normalize_exchange_catalog(json.load(file))
        if catalog["items"]:
            return catalog
    except (OSError, ValueError):
        pass
    catalog = exchange_catalog_seed()
    save_exchange_catalog(catalog)
    return catalog


def save_exchange_catalog(catalog):
    catalog = normalize_exchange_catalog(catalog)
    os.makedirs(DATA_DIR, exist_ok=True)
    temporary = EXCHANGE_CATALOG_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(catalog, file, ensure_ascii=False, indent=2)
    os.chmod(temporary, 0o600)
    os.replace(temporary, EXCHANGE_CATALOG_FILE)
    return catalog


def exchange_catalog_items(enabled_only=True):
    items = load_exchange_catalog()["items"]
    if enabled_only:
        items = [item for item in items if item["enabled"]]
    return sorted(items, key=lambda item: (list(EXCHANGE_GROUP_META).index(item["group"]), item["order"], item["name"].casefold()))


def exchange_groups(enabled_only=True):
    items = exchange_catalog_items(enabled_only)
    return tuple((meta["label"], [item for item in items if item["group"] == group]) for group, meta in EXCHANGE_GROUP_META.items())


def exchange_catalog_by_name(name, enabled_only=True):
    key = str(name or "").casefold()
    return next((item for item in exchange_catalog_items(enabled_only) if item["name"].casefold() == key), None)


def active_exchanges():
    return {item["name"] for item in exchange_catalog_items(True)}


def save_uploaded_exchange_icon(data):
    """Validate and normalize an administrator-uploaded icon into a local PNG asset."""
    if not data or len(data) > EXCHANGE_ICON_UPLOAD_MAX_BYTES:
        raise ValueError("图标文件不能为空，且不能超过 4 MB。")
    try:
        from PIL import Image, ImageOps
        source = Image.open(io.BytesIO(data))
        source.verify()
        source = Image.open(io.BytesIO(data))
        if source.format not in ("PNG", "JPEG", "WEBP"):
            raise ValueError("仅支持 PNG、JPG 或 WebP 图标。")
        if source.width * source.height > EXCHANGE_ICON_UPLOAD_MAX_PIXELS:
            raise ValueError("图标像素过大，请上传小于 1600 万像素的图片。")
        source = ImageOps.exif_transpose(source).convert("RGBA")
        source.thumbnail((192, 192), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        canvas.alpha_composite(source, ((256 - source.width) // 2, (256 - source.height) // 2))
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=True)
    except ValueError:
        raise
    except Exception:
        raise ValueError("无法读取该图片，请上传有效的 PNG、JPG 或 WebP 文件。")
    os.makedirs(CMC_ICON_DIR, mode=0o700, exist_ok=True)
    filename = hashlib.sha256(output.getvalue()).hexdigest()[:32] + ".png"
    target = os.path.join(CMC_ICON_DIR, filename)
    if not os.path.exists(target):
        temporary = target + ".tmp"
        with open(temporary, "wb") as file:
            file.write(output.getvalue())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    return filename


def current_payment_receiver():
    return load_system_config()["payment_receiver"]


def ip_risk_snapshot(ip_value):
    """Use a configured provider only; never infer geographic or proxy attributes locally."""
    result = {"country": None, "region": None, "city": None, "isp": None, "asn": None, "ip_type": "待检测", "purity_score": None, "is_proxy": None, "is_vpn": None, "is_tor": None, "is_datacenter": None, "source": "未接入 IP 风控数据源", "checked_at": now(), "message": "未配置 IP 归属地与纯净度 API，系统只保存 IP 记录，不会推测归属地、网络类型或代理状态。"}
    config = load_ip_risk_config()
    key_required = config["provider"].strip().lower() not in ("ipwho.is", "ipwhois")
    if not (config["enabled"] and config["api_url"] and (config["api_key"] or not key_required)):
        return result
    try:
        url = config["api_url"].replace("{ip}", urllib.parse.quote(ip_value, safe=""))
        separator = "&" if "?" in url else "?"
        if "{key}" in url and config["api_key"]:
            url = url.replace("{key}", urllib.parse.quote(config["api_key"], safe=""))
        elif config["api_key"]:
            url += separator + "key=" + urllib.parse.quote(config["api_key"], safe="")
        request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "YuanShi-JinShouZhi/1.0"})
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.load(response)
        # Supports IPQualityScore-like response keys; use a custom adapter URL for another vendor.
        if payload.get("success") is False:
            raise RuntimeError(payload.get("message", "IP 数据源拒绝请求"))
        security = payload.get("security") or {}
        connection = payload.get("connection") or {}
        proxy = bool(payload.get("proxy") or security.get("proxy"))
        vpn = bool(payload.get("vpn") or security.get("vpn"))
        tor = bool(payload.get("tor") or security.get("tor"))
        datacenter = bool(payload.get("hosting") or payload.get("datacenter") or security.get("hosting"))
        fraud_score = payload.get("fraud_score")
        try:
            purity = max(0, min(100, 100 - int(fraud_score))) if fraud_score is not None else None
        except (TypeError, ValueError):
            purity = None
        ip_type = "Tor" if tor else ("VPN" if vpn else ("代理 IP" if proxy else ("数据中心 IP" if datacenter else "住宅 / 普通 IP")))
        score_note = "已返回欺诈分并换算为 IP 纯净度。" if purity is not None else "该数据源未返回欺诈分，无法提供 IP 纯净度评分。"
        return {"country": payload.get("country_code") or payload.get("country"), "region": payload.get("region"), "city": payload.get("city"), "isp": payload.get("ISP") or payload.get("isp") or connection.get("isp"), "asn": str(payload.get("ASN") or payload.get("asn") or connection.get("asn") or "") or None, "ip_type": ip_type, "purity_score": purity, "is_proxy": int(proxy), "is_vpn": int(vpn), "is_tor": int(tor), "is_datacenter": int(datacenter), "source": config["provider"], "checked_at": now(), "message": "已通过 %s 完成 IP 归属地与网络类型检测。%s" % (config["provider"], score_note)}
    except Exception as exc:
        detail = str(exc)
        if "insufficient credits" in detail.lower() or "insufficient credit" in detail.lower():
            detail = "IPQualityScore 账户查询额度不足，请充值、升级套餐或更换数据源。"
        result.update({"source": "数据源异常", "message": "IP 风控数据源异常：%s" % detail})
        return result


def deliver_email(to, subject, body):
    config = load_smtp_config()
    if not (config["host"] and config["user"] and config["password"] and config["from"]):
        raise RuntimeError("邮箱验证码服务未配置，请先在系统设置中填写 SMTP 参数。")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["from"]
    message["To"] = to
    message.set_content(body)
    if config["mode"] == "ssl":
        with smtplib.SMTP_SSL(config["host"], config["port"], timeout=12) as smtp:
            smtp.login(config["user"], config["password"])
            smtp.send_message(message)
    else:
        with smtplib.SMTP(config["host"], config["port"], timeout=12) as smtp:
            if config["mode"] != "none":
                smtp.starttls()
            smtp.login(config["user"], config["password"])
            smtp.send_message(message)


def send_verification_email(email, code):
    deliver_email(
        email,
        "原石金手指 · 注册验证码",
        "您的注册验证码是：%s\n\n验证码 10 分钟内有效。若非本人操作，请忽略此邮件。" % code,
    )


def mask_username(value):
    value = str(value or "")
    if len(value) <= 2:
        return value[:1] + "*" * max(0, len(value) - 1)
    return value[0] + "*" * max(6, len(value) - 2) + value[-1]


def mask_email(value):
    value = str(value or "")
    if "@" not in value:
        return mask_username(value)
    local, domain = value.rsplit("@", 1)
    if len(local) <= 2:
        masked = local[:1] + "*" * max(0, len(local) - 1)
    else:
        masked = local[0] + "*" * max(5, len(local) - 2) + local[-1]
    return masked + "@" + domain


def mask_wallet_address(value):
    value = str(value or "")
    return value if len(value) <= 10 else value[:6] + "..." + value[-4:]


def display_ip_for_viewer(value, viewer):
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        return "已脱敏"
    if viewer and (viewer["role"] == "ADMIN" or user_display_label(viewer) in ("星舰会员", "旗舰 PRO")):
        return str(parsed)
    if parsed.version == 4:
        return ".".join(str(parsed).split(".")[:2]) + ".xxx.xxx"
    pieces = parsed.exploded.split(":")
    return ":".join(pieces[:3]) + ":xxxx:xxxx:xxxx:xxxx:xxxx"


def user_identity(row, viewer=None):
    full = bool(viewer and viewer["is_owner"])
    username = row["username"] if full else mask_username(row["username"])
    if not full:
        return '<div><strong>%s</strong></div>' % esc(username)
    email = row["email"] if "email" in row.keys() and row["email"] else "未绑定邮箱"
    return '<div><strong>%s</strong><br><small class="muted">%s</small></div>' % (esc(username), esc(email))


def quota_limits_for_user(user):
    if user["is_owner"]:
        return {kind: -1 for kind in QUERY_QUOTA_FIELDS}
    if user["role"] == "ADMIN":
        return PLAN_CONFIG["STARSHIP"]["limits"]
    plan = user["membership_plan"] if "membership_plan" in user.keys() else "FREE"
    return PLAN_CONFIG.get(plan, {}).get("limits", {})


def remaining_query_quota(user, query_kind):
    """Return remaining checks, or None when the category is unlimited."""
    if query_kind not in QUERY_QUOTA_FIELDS:
        raise ValueError("不支持的查询类型")
    if user["is_owner"]:
        return None
    limit_field, used_field, _ = QUERY_QUOTA_FIELDS[query_kind]
    limit = user[limit_field] if limit_field in user.keys() else quota_limits_for_user(user).get(query_kind, 0)
    if user["role"] == "ADMIN" and int(limit or 0) == 0:
        limit = PLAN_CONFIG["STARSHIP"]["limits"][query_kind]
    if limit is None or int(limit) < 0:
        return None
    used = user[used_field] if used_field in user.keys() else 0
    return max(0, int(limit) - int(used or 0))


def query_quota_display(user, query_kind):
    remaining = remaining_query_quota(user, query_kind)
    return "不限次数" if remaining is None else "%s 次" % remaining


def can_query_local(user, query_kind="ip"):
    if query_kind not in QUERY_QUOTA_FIELDS:
        return False, "不支持的查询类型。"
    if user["is_owner"]:
        return True, ""
    if user["role"] != "ADMIN":
        status = user["membership_status"] if "membership_status" in user.keys() else "FREE"
        plan = user["membership_plan"] if "membership_plan" in user.keys() else "FREE"
        if status != "ACTIVE" or plan not in PLAN_CONFIG:
            return False, "当前功能仅限星舰会员、旗舰 PRO、旗舰 MAX 或授权白名单使用，请升级权限。"
        expires_at = user["membership_expires_at"] if "membership_expires_at" in user.keys() else None
        if expires_at and expires_at < now():
            return False, "会员已到期，请续费后继续查询。"
    limit_field, used_field, label = QUERY_QUOTA_FIELDS[query_kind]
    limits = quota_limits_for_user(user)
    limit = user[limit_field] if limit_field in user.keys() else limits.get(query_kind, 0)
    if user["role"] == "ADMIN" and int(limit or 0) == 0:
        limit = limits.get(query_kind, 0)
    used = user[used_field] if used_field in user.keys() else 0
    if limit is not None and int(limit) >= 0 and int(used or 0) >= int(limit):
        return False, "本月%s额度已使用完，请升级或续费。" % label
    return True, ""


def consume_query_quota(conn, user, query_kind, timestamp=None):
    """Atomically reserve one quota before persisting a successful query record."""
    if user["is_owner"]:
        return True
    limit_field, used_field, _ = QUERY_QUOTA_FIELDS[query_kind]
    timestamp = timestamp or now()
    if user["role"] == "ADMIN":
        stored_limit = user[limit_field] if limit_field in user.keys() else 0
        limit = int(stored_limit or 0) or PLAN_CONFIG["STARSHIP"]["limits"][query_kind]
        if query_kind == "ip":
            result = conn.execute(
                """UPDATE users SET ip_query_limit=?,ip_query_used=ip_query_used+1,query_limit=?,query_used=query_used+1,updated_at=?
                   WHERE id=? AND ip_query_used<?""",
                (limit, limit, timestamp, user["id"], limit),
            )
        else:
            result = conn.execute(
                "UPDATE users SET %s=?,%s=%s+1,updated_at=? WHERE id=? AND %s<?" % (
                    limit_field, used_field, used_field, used_field
                ),
                (limit, timestamp, user["id"], limit),
            )
        return result.rowcount == 1
    if query_kind == "ip":
        result = conn.execute(
            """UPDATE users SET ip_query_used=ip_query_used+1,query_used=query_used+1,updated_at=?
               WHERE id=? AND (ip_query_limit<0 OR ip_query_used<ip_query_limit)""",
            (timestamp, user["id"]),
        )
    else:
        result = conn.execute(
            "UPDATE users SET %s=%s+1,updated_at=? WHERE id=? AND (%s<0 OR %s<%s)" % (
                used_field, used_field, limit_field, used_field, limit_field
            ),
            (timestamp, user["id"]),
        )
    return result.rowcount == 1


def viewer_can_export_full(user):
    return bool(user and user["is_owner"])


def check_address(value, check_type):
    address = (value or "").strip()
    if check_type == "evm":
        return EVM_ADDRESS_RE.fullmatch(address) is not None, "ethereum"
    if check_type == "solana":
        return SOLANA_ADDRESS_RE.fullmatch(address) is not None, "solana"
    if check_type == "tron":
        return TRON_ADDRESS_RE.fullmatch(address) is not None, "tron"
    if check_type == "btc":
        return BTC_ADDRESS_RE.fullmatch(address) is not None, "bitcoin"
    if check_type in ("wallet", "interaction"):
        for candidate in ("evm", "solana", "tron", "btc"):
            valid, chain = check_address(address, candidate)
            if valid:
                return True, chain
        return False, ""
    if check_type == "other":
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:_\-]{7,127}", address)), ""
    return False, ""


def icon_markup(icon_map, key):
    item = icon_map.get(key, FALLBACK_ICON)
    source = item.get("icon")
    title = "%s%s" % (item["name"], "（图标待确认）" if not item.get("iconVerified") else "")
    if source:
        return '<img class="exchange-icon" src="%s" alt="%s" title="%s">' % (esc(source), esc(item["name"]), esc(title))
    return '<span class="exchange-icon" title="%s">%s</span>' % (esc(title), esc(item.get("fallbackIcon", "?")))


def rpc_call(url, method, params):
    if not url:
        raise RuntimeError("未接入实时数据源")
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "YuanShi-JinShouZhi/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.load(response)
    if data.get("error"):
        raise RuntimeError(data["error"].get("message", "数据源返回错误"))
    return data.get("result")


def live_wallet_snapshot(address, chain):
    """Return only provider-backed public chain fields; unknown fields stay explicit."""
    started = time.time()
    base = {
        "address": address, "chain": chain or "未知链", "addressType": "未知地址", "assets": [],
        "totalValue": None, "transactionCount": None, "interactionCount": None, "lastTransactionAt": None,
        "riskScore": None, "riskLevel": "未知", "riskTags": [], "riskReasons": [], "interactions": [],
        "source": "未接入实时数据源", "updatedAt": now(), "durationMs": 0, "confidence": "低",
        "isRealtime": False, "missingFields": ["地址标签", "风险标签", "代币余额", "实时价格", "交易次数", "交互明细"],
        "status": "NOT_CONFIGURED", "message": "未配置已审核的链上节点或地址标签数据源，系统不会生成虚构余额、风险评分或交互记录。",
    }
    config = load_web3_risk_config()
    evm_rpc_url = config["evm_rpc_url"] or EVM_RPC_URL
    solana_rpc_url = config["solana_rpc_url"] or SOLANA_RPC_URL
    try:
        if chain == "ethereum":
            if not evm_rpc_url:
                return base
            balance = rpc_call(evm_rpc_url, "eth_getBalance", [address, "latest"])
            wei = int(balance, 16)
            base.update({"assets": [{"symbol": "ETH", "balance": wei / 10 ** 18, "price": None, "share": None, "icon": "ethereum"}], "source": "EVM RPC", "isRealtime": True, "confidence": "中", "status": "PARTIAL", "message": "已获得原生币余额；代币、标签、风险与交互数据仍需接入对应数据源。", "missingFields": ["地址标签", "风险标签", "代币余额", "实时价格", "交易次数", "交互明细"]})
        elif chain == "solana":
            if not solana_rpc_url:
                return base
            result = rpc_call(solana_rpc_url, "getBalance", [address])
            lamports = (result or {}).get("value")
            if lamports is None:
                raise RuntimeError("Solana 节点未返回余额")
            base.update({"assets": [{"symbol": "SOL", "balance": int(lamports) / 10 ** 9, "price": None, "share": None, "icon": "solana"}], "source": "Solana RPC", "isRealtime": True, "confidence": "中", "status": "PARTIAL", "message": "已获得原生币余额；代币、标签、风险与交互数据仍需接入对应数据源。", "missingFields": ["地址标签", "风险标签", "代币余额", "实时价格", "交易次数", "交互明细"]})
    except Exception as exc:
        base.update({"status": "SOURCE_ERROR", "message": "实时数据源异常：%s" % str(exc), "source": "数据源异常"})
    base["durationMs"] = int((time.time() - started) * 1000)
    return base


def user_display_label(user):
    if user["is_owner"]:
        return "总管理员"
    if user["role"] == "ADMIN":
        return "授权白名单"
    plan = user["membership_plan"] if "membership_plan" in user.keys() else "FREE"
    status = user["membership_status"] if "membership_status" in user.keys() else "FREE"
    if status == "ACTIVE" and plan in PLAN_CONFIG:
        return PLAN_CONFIG[plan]["name"]
    return "普通用户"


def bsc_rpc(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    request = urllib.request.Request(
        BSC_RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "YuanShi-JinShouZhi/1.0"},
    )
    with urllib.request.urlopen(request, timeout=18) as response:
        data = json.load(response)
    if data.get("error"):
        raise RuntimeError(data["error"].get("message", "链上节点返回错误"))
    return data.get("result")


def verify_bep20_payment(tx_hash, token, expected_amount, receiver):
    tx_hash = (tx_hash or "").strip()
    if not re.fullmatch(r"0x[a-fA-F0-9]{64}", tx_hash):
        return False, "Transaction Hash 格式不正确"
    token_address = TOKEN_CONTRACTS.get(token)
    if not token_address:
        return False, "暂不支持该付款币种"
    receipt = bsc_rpc("eth_getTransactionReceipt", [tx_hash])
    if not receipt:
        return False, "链上暂未查到该交易，请稍后再试"
    if str(receipt.get("status", "")).lower() != "0x1":
        return False, "链上交易状态失败"
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    receiver_norm = receiver.lower().replace("0x", "")
    token_norm = token_address.lower()
    required_raw = int(float(expected_amount) * (10 ** 18))
    for log in receipt.get("logs", []):
        topics = [str(item).lower() for item in log.get("topics", [])]
        if len(topics) < 3 or topics[0] != transfer_topic:
            continue
        if str(log.get("address", "")).lower() != token_norm:
            continue
        to_topic = topics[2][-40:]
        if to_topic != receiver_norm:
            continue
        try:
            amount_raw = int(str(log.get("data", "0x0")), 16)
        except ValueError:
            continue
        if amount_raw >= required_raw:
            confirmations = None
            try:
                latest = int(bsc_rpc("eth_blockNumber", []), 16)
                block_no = int(str(receipt.get("blockNumber", "0x0")), 16)
                confirmations = max(0, latest - block_no + 1)
            except Exception:
                confirmations = None
            detail = "链上验证通过：%s %.4f，确认数 %s" % (token, amount_raw / (10 ** 18), confirmations if confirmations is not None else "未知")
            return True, detail
    return False, "未找到转入收款地址的足额 %s BEP20 转账" % token


def membership_price(plan, months):
    return MEMBERSHIP_PERIODS[months]["prices"][plan]


def membership_monthly_equivalent(plan, months):
    return round(membership_price(plan, months) / months, 1)


def money_display(amount):
    amount = float(amount)
    return ("%.1f" % amount).rstrip("0").rstrip(".")


def activate_membership(conn, user_id, plan, months=1):
    config = PLAN_CONFIG[plan]
    months = int(months)
    if months not in MEMBERSHIP_PERIODS:
        raise ValueError("无效的会员周期")
    ts = now()
    base = datetime.now()
    current = conn.execute(
        "SELECT membership_expires_at,membership_plan FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    if current and current["membership_expires_at"]:
        try:
            previous = datetime.strptime(current["membership_expires_at"], "%Y-%m-%d %H:%M:%S")
            if previous > base:
                base = previous
        except ValueError:
            pass
    expires_at = (base + timedelta(days=config["days"] * months)).strftime("%Y-%m-%d %H:%M:%S")
    limits = config["limits"]
    conn.execute(
        """UPDATE users SET membership_plan=?,membership_status='ACTIVE',
           query_limit=?,query_used=0,ip_query_limit=?,ip_query_used=0,
           device_query_limit=?,device_query_used=0,wallet_query_limit=?,wallet_query_used=0,
           membership_expires_at=?,updated_at=? WHERE id=?""",
        (plan, limits["ip"], limits["ip"], limits["device"], limits["wallet"], expires_at, ts, user_id),
    )
    return expires_at


def exchange_label(value):
    return LEGACY_EXCHANGES.get(value, value)


def exchange_icon_text(value):
    item = exchange_catalog_by_name(value, enabled_only=False)
    if item and item["icon_text"]:
        return item["icon_text"]
    words = re.findall(r"[A-Za-z0-9]+", exchange_label(value))
    if not words:
        return "其"
    return ("".join(word[0] for word in words[:2]) if len(words) > 1 else words[0][:2]).upper()


def exchange_icon_hue(value):
    return int(hashlib.sha256(exchange_label(value).encode("utf-8")).hexdigest()[:4], 16) % 360


def load_cmc_icon_map():
    for path in (CMC_ICON_MAP_FILE, os.path.join(BRAND_DIR, "exchange_icons.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
    return {}


def exchange_icon_markup(value):
    label = exchange_label(value)
    item = exchange_catalog_by_name(label, enabled_only=False)
    filename = item["icon_file"] if item else ""
    if filename and (
        os.path.exists(os.path.join(CMC_ICON_DIR, filename))
        or os.path.exists(os.path.join(BRAND_DIR, "exchanges", filename))
    ):
        return '<img class="exchange-icon exchange-icon-img" src="/assets/exchanges/%s" alt="%s 图标">' % (filename, esc(label))
    manual_icon = MANUAL_EXCHANGE_ICONS.get(label)
    manual_path = ASSETS.get(manual_icon, ("",))[0] if manual_icon else ""
    if manual_path and os.path.exists(manual_path):
        return '<img class="exchange-icon exchange-icon-img" src="%s" alt="%s 图标">' % (manual_icon, esc(label))
    filename = load_cmc_icon_map().get(label)
    if isinstance(filename, str) and re.fullmatch(r"[0-9a-f]{32}\.png", filename) and (
        os.path.exists(os.path.join(CMC_ICON_DIR, filename))
        or os.path.exists(os.path.join(BRAND_DIR, "exchanges", filename))
    ):
        return '<img class="exchange-icon exchange-icon-img" src="/assets/exchanges/%s" alt="%s 图标">' % (filename, esc(label))
    return '<span class="exchange-icon" style="--h:%s">%s</span>' % (exchange_icon_hue(label), esc(exchange_icon_text(label)))


def exchange_display(value):
    label = exchange_label(value)
    return '<span class="exchange-name">%s%s</span>' % (exchange_icon_markup(label), esc(label))


def exchange_options(selected="", include_all=False):
    groups = ['<option value="">全部交易所</option>'] if include_all else []
    for group_label, items in exchange_groups():
        options = "".join('<option value="%s" %s>%s · %s</option>' % (
            esc(item["name"]), "selected" if selected == item["name"] else "", EXCHANGE_GROUP_META[item["group"]]["short"], esc(item["name"])
        ) for item in items)
        groups.append('<optgroup label="%s">%s</optgroup>' % (esc(group_label), options))
    return "".join(groups)


def exchange_picker(selected="", allow_all=False):
    selected = selected if selected in active_exchanges() else ""
    groups = []
    required = "" if allow_all else "required"
    if allow_all:
        groups.append(
            '<div class="exchange-group"><label class="exchange-option" data-search="全部交易所">'
            '<input type="radio" name="exchange" value="" %s><span>全部交易所</span></label></div>'
            % ("checked" if not selected else "")
        )
    for group_label, items in exchange_groups():
        items = "".join(
            '<label class="exchange-option" data-search="%s" data-name="%s"><input type="radio" name="exchange" value="%s" %s %s>%s<span>%s</span></label>' % (
                esc(" ".join([item["name"], *item["aliases"], item["group"], EXCHANGE_GROUP_META[item["group"]]["short"]]).lower()), esc(item["name"].lower()), esc(item["name"]), "checked" if item["name"] == selected else "", required, exchange_icon_markup(item["name"]), esc(item["name"])
            ) for item in items
        )
        groups.append('<div class="exchange-group"><strong>%s</strong>%s</div>' % (esc(group_label), items))
    empty_label = "全部交易所" if allow_all else "请选择交易所"
    current = exchange_display(selected) if selected else '<span class="muted">%s</span>' % empty_label
    return """<details class="exchange-picker"><summary data-placeholder="%s">%s</summary><div class="exchange-menu"><input class="exchange-search" type="search" placeholder="搜索交易所名称" autocomplete="off" aria-label="搜索交易所名称"><p class="exchange-search-status" aria-live="polite"></p><div class="exchange-list">%s</div></div></details>""" % (
        empty_label, current, "".join(groups)
    )


def normalize_exchange_name(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def cmc_json(url, api_key):
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "YuanShi-JinShouZhi/1.0",
        "X-CMC_PRO_API_KEY": api_key,
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError("CMC 返回状态 %s" % response.status)
        return json.load(response)


def cmc_objects(data):
    found = []
    def walk(value):
        if isinstance(value, dict):
            if value.get("id") is not None and value.get("name"):
                found.append(value)
            else:
                for child in value.values():
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(data.get("data", data) if isinstance(data, dict) else data)
    unique = {}
    for item in found:
        unique[(str(item.get("id")), str(item.get("name")))] = item
    return list(unique.values())


def match_cmc_objects(objects):
    exact = {}
    for item in objects:
        exact.setdefault(normalize_exchange_name(item.get("name", "")), item)
    aliases = {
        "gate": "gateio",
        "hashkey": "hashkeyexchange",
        "btcturk": "btcturkkripto",
        "biconomy": "biconomycom",
        "pancakeswap": "pancakeswapv3bsc",
        "uniswap": "uniswapv4ethereum",
        "aerodrome": "aerodromefinance",
        "meteora": "meteoradlmm",
        "curve": "curveethereum",
        "lfjtraderjoe": "lfjavalanche",
    }
    matched = {}
    for name in active_exchanges():
        if name == "其他":
            continue
        key = normalize_exchange_name(name)
        item = exact.get(key) or exact.get(aliases.get(key, ""))
        if not item and len(key) >= 5:
            candidates = [(len(candidate_key), candidate) for candidate_key, candidate in exact.items() if candidate_key.startswith(key)]
            if candidates:
                item = min(candidates, key=lambda pair: pair[0])[1]
        if item:
            matched[name] = item
    return matched


def sync_cmc_icons(api_key):
    os.makedirs(CMC_ICON_DIR, mode=0o700, exist_ok=True)
    sources = []
    errors = []
    endpoints = [
        "https://pro-api.coinmarketcap.com/v1/exchange/map?start=1&limit=5000&aux=status",
        "https://pro-api.coinmarketcap.com/v4/dex/listings/quotes?start=1&limit=500&sort=volume_24h&sort_dir=desc&type=all",
    ]
    for url in endpoints:
        try:
            sources.extend(cmc_objects(cmc_json(url, api_key)))
        except Exception as error:
            errors.append(str(error))
    matched = match_cmc_objects(sources)
    ids = sorted({str(item["id"]) for item in matched.values() if str(item.get("id", "")).isdigit()}, key=int)
    metadata = []
    for index in range(0, len(ids), 100):
        batch = ",".join(ids[index:index + 100])
        try:
            metadata.extend(cmc_objects(cmc_json("https://pro-api.coinmarketcap.com/v1/exchange/info?id=%s&aux=logo" % batch, api_key)))
        except Exception as error:
            errors.append(str(error))
    by_id = {str(item.get("id")): item for item in metadata}
    icon_map = load_cmc_icon_map()
    downloaded = 0
    for name, item in matched.items():
        info = by_id.get(str(item.get("id")), item)
        logo = info.get("logo") or item.get("logo")
        if not isinstance(logo, str):
            continue
        parsed = urllib.parse.urlparse(logo)
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith("coinmarketcap.com"):
            continue
        filename = hashlib.sha256(name.encode("utf-8")).hexdigest()[:32] + ".png"
        target = os.path.join(CMC_ICON_DIR, filename)
        try:
            request = urllib.request.Request(logo, headers={"User-Agent": "YuanShi-JinShouZhi/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read(512 * 1024 + 1)
            if len(data) > 512 * 1024 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
                continue
            temporary = target + ".tmp"
            with open(temporary, "wb") as f:
                f.write(data)
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
            icon_map[name] = filename
            downloaded += 1
        except (OSError, urllib.error.URLError, TimeoutError):
            continue
    with open(CMC_ICON_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(icon_map, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.chmod(CMC_ICON_MAP_FILE, 0o600)
    return {"matched": len(matched), "downloaded": downloaded, "cached": len(icon_map), "errors": errors[:3]}


def similarity(segments, row):
    other = [row["segment_a"], row["segment_b"], row["segment_c"], row["segment_d"]]
    matches = [segments[i] == other[i] for i in range(4)]
    return sum(matches) * 25, matches


def log_action(conn, user_id, action, target_type, target_id="", detail="", ip_address="127.0.0.1"):
    conn.execute(
        "INSERT INTO operation_logs(user_id,action,target_type,target_id,detail,ip_address,created_at) VALUES(?,?,?,?,?,?,?)",
        (user_id, action, target_type, str(target_id), detail, ip_address, now()),
    )


def active_popup_announcement(conn, user_id):
    return conn.execute(
        """SELECT a.* FROM site_announcements a
           LEFT JOIN site_announcement_receipts r
             ON r.announcement_id=a.id AND r.user_id=?
           WHERE a.status='PUBLISHED' AND a.popup_enabled=1
             AND a.published_at<=?
             AND (a.expires_at IS NULL OR a.expires_at='' OR a.expires_at>?)
             AND r.muted_at IS NULL AND r.deleted_at IS NULL
           ORDER BY a.published_at DESC, a.id DESC LIMIT 1""",
        (user_id, now(), now()),
    ).fetchone()


def save_announcement_receipt(conn, announcement_id, user_id, action):
    if action not in ("acknowledge", "mute"):
        return False
    announcement = conn.execute(
        "SELECT id FROM site_announcements WHERE id=? AND status='PUBLISHED'", (announcement_id,)
    ).fetchone()
    if not announcement:
        return False
    timestamp = now()
    if action == "mute":
        conn.execute(
            """INSERT INTO site_announcement_receipts(announcement_id,user_id,seen_at,muted_at)
               VALUES(?,?,?,?)
               ON CONFLICT(announcement_id,user_id) DO UPDATE SET
                 seen_at=COALESCE(site_announcement_receipts.seen_at,excluded.seen_at), muted_at=excluded.muted_at""",
            (announcement_id, user_id, timestamp, timestamp),
        )
    else:
        conn.execute(
            """INSERT INTO site_announcement_receipts(announcement_id,user_id,seen_at)
               VALUES(?,?,?)
               ON CONFLICT(announcement_id,user_id) DO UPDATE SET
                 seen_at=COALESCE(site_announcement_receipts.seen_at,excluded.seen_at)""",
            (announcement_id, user_id, timestamp),
        )
    return True


def unread_site_announcement_count(conn, user_id):
    return conn.execute(
        """SELECT COUNT(*) FROM site_announcements a
           LEFT JOIN site_announcement_receipts r
             ON r.announcement_id=a.id AND r.user_id=?
           WHERE a.status='PUBLISHED' AND a.published_at<=?
             AND (r.seen_at IS NULL) AND r.deleted_at IS NULL""",
        (user_id, now()),
    ).fetchone()[0]


def status_badge(score):
    names = {100: "精确重复", 75: "高度相似", 50: "中度相似", 25: "低度相似", 0: "未发现相似"}
    return '<span class="badge s%s">%s%% · %s</span>' % (score, score, names[score])


STYLE = """
:root{--bg:#f4f7fb;--card:#fff;--text:#132238;--muted:#6a778b;--line:#dfe6ef;--brand:#2457d6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}
a{color:inherit;text-decoration:none}.layout{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.side{position:sticky;top:0;height:100vh;overflow-y:auto;background:linear-gradient(180deg,#071424,#102344);color:#d9e4fa;padding:24px 18px}
.brandhead{display:flex;align-items:center;gap:12px;margin:0 6px 24px}.brandmark{width:52px;height:52px;object-fit:cover;border-radius:14px;border:1px solid #d9ad4d;box-shadow:0 6px 20px #0008}.logo{font-size:19px;font-weight:800;color:#fff;line-height:1.25}.logo small{display:block;margin-top:4px;font-size:10px;color:#c4a65b;letter-spacing:1px}
.nav a{display:block;padding:11px 14px;border-radius:9px;margin:5px 0}.nav a:hover,.nav a.on{background:#2457d6;color:white}.main{padding:28px;max-width:1400px;width:100%}
.business{margin-top:30px;padding-top:18px;border-top:1px solid rgba(218,229,249,.16)}.business-title{margin:0 5px 10px;color:#d5ad53;font-size:12px;font-weight:800;letter-spacing:1px}.business-item{display:flex;align-items:center;gap:9px;margin:7px 0;padding:9px 10px;border:1px solid rgba(188,207,236,.2);border-radius:8px;background:rgba(255,255,255,.045);color:#f1f5fc;font-size:12px;font-weight:650;box-shadow:inset 0 0 0 1px rgba(0,0,0,.12)}.business-item:hover{border-color:rgba(213,173,83,.52);background:rgba(255,255,255,.075)}.business-icon{display:inline-grid;place-items:center;flex:0 0 auto;width:24px;height:24px;border:1px solid rgba(213,173,83,.6);border-radius:7px;color:#e2bd68;font-size:13px}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}h1{font-size:25px;margin:0}h2{font-size:18px;margin:0 0 18px}.muted{color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;box-shadow:0 4px 18px rgba(32,61,103,.05);margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px}.col2{grid-column:span 2}.col3{grid-column:span 3}.col4{grid-column:span 4}.col6{grid-column:span 6}.col7{grid-column:span 7}.col8{grid-column:span 8}.col9{grid-column:span 9}.col10{grid-column:span 10}.col12{grid-column:span 12}
label{font-weight:650;display:block;margin:0 0 6px}input,select{width:100%;border:1px solid #cfd9e7;border-radius:9px;padding:10px 12px;background:#fff;font:inherit}
button,.btn{border:0;border-radius:9px;padding:10px 16px;background:var(--brand);color:#fff;font-weight:700;cursor:pointer;display:inline-block}.secondary{background:#e8eef9;color:#27466f}.danger{background:#c93434}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:11px 10px;border-bottom:1px solid #e7ecf3;white-space:nowrap}th{color:#68768a;font-size:12px}.tablewrap{overflow:auto}
.badge{display:inline-block;padding:5px 9px;border-radius:999px;font-weight:700}.s100{background:#fee2e2;color:#b42318}.s75{background:#ffedd5;color:#c2410c}.s50{background:#fef3c7;color:#a16207}.s25{background:#dbeafe;color:#1d4ed8}.s0{background:#dcfce7;color:#15803d}
.segments{display:flex;gap:9px;flex-wrap:wrap}.seg{padding:9px 12px;border-radius:8px;background:#eef2f7}.seg.yes{background:#dcfce7;color:#166534}.seg.no{background:#fee2e2;color:#991b1b}
.flash{padding:12px 15px;border-radius:9px;margin-bottom:16px;background:#eaf2ff;color:#174db6}.flash.err{background:#fee2e2;color:#a21d1d}
.login{min-height:100vh;display:grid;place-items:center;padding:20px;background:linear-gradient(90deg,rgba(2,10,22,.5),rgba(2,10,22,.84)),url('/assets/crypto-background.jpg') center/cover fixed}.loginbox{width:min(440px,92vw);color:#eef5ff;background:rgba(5,18,35,.9);padding:34px;border:1px solid #b58a38;border-radius:20px;box-shadow:0 24px 70px #0009;backdrop-filter:blur(14px)}.loginbrand{display:flex;align-items:center;gap:16px;margin-bottom:24px}.loginbrand img{width:76px;height:76px;object-fit:cover;border-radius:18px;border:1px solid #e1bd65;box-shadow:0 8px 24px #0008}.loginbox h1{margin:0 0 4px}.loginbox .muted{color:#a9bad0}.loginbox input{margin-bottom:15px;background:#fff;color:#132238}.loginbox button{width:100%;margin-top:5px;background:linear-gradient(135deg,#bb8b35,#e6c66f);color:#172036}
.contact{margin-top:24px;padding-top:16px;border-top:1px solid rgba(155,171,194,.25);color:var(--muted);font-size:13px;text-align:center}.contact a{color:#c99536;font-weight:750}.loginbox .contact{color:#a9bad0}.loginbox .contact a{color:#e6c66f}
.authlinks{display:flex;justify-content:space-between;gap:12px;margin-top:16px;font-size:13px}.authlinks a{color:#e6c66f;font-weight:700}.recovery{margin:16px 0;padding:14px;border:1px solid #d5ae55;border-radius:10px;background:#1a2a42;color:#f7df9a;word-break:break-all}.hint{font-size:12px;color:#8fa2bb;margin-top:-8px;margin-bottom:14px}
.hero{min-height:170px;display:flex;align-items:flex-end;padding:26px;border-radius:14px;margin-bottom:18px;color:#fff;background:linear-gradient(90deg,rgba(4,16,34,.94),rgba(4,16,34,.35)),url('/assets/crypto-background.jpg') center/cover;box-shadow:0 10px 30px #1023442b}.hero h2{font-size:26px;margin:0 0 6px}.hero p{margin:0;color:#cbd8e8;max-width:620px}
.exchange-name{display:inline-flex;align-items:center;gap:8px}.exchange-icon{--h:215;display:inline-grid;place-items:center;flex:0 0 auto;width:28px;height:28px;border-radius:9px;color:#fff;background:linear-gradient(135deg,hsl(var(--h) 72% 52%),hsl(var(--h) 72% 34%));font-size:10px;font-weight:850;letter-spacing:-.3px;box-shadow:inset 0 0 0 1px #fff3}
.exchange-icon-img{display:block;object-fit:cover;background:#fff;border:1px solid #e3e8f0;padding:2px}
.exchange-picker{position:relative}.exchange-picker>summary{list-style:none;display:flex;align-items:center;min-height:44px;padding:7px 38px 7px 11px;border:1px solid #cfd9e7;border-radius:9px;background:#fff;cursor:pointer;position:relative}.exchange-picker>summary::-webkit-details-marker{display:none}.exchange-picker>summary:after{content:"⌄";position:absolute;right:13px;font-size:18px;color:#66758a}.exchange-picker[open]{z-index:9999}.exchange-picker[open]>summary{border-color:#2457d6}.exchange-menu{position:absolute;z-index:9999;top:calc(100% + 8px);right:0;width:min(520px,88vw);padding:12px;border:1px solid rgba(255,255,255,.10);border-radius:16px;background:#111827;color:#f8fafc;box-shadow:0 28px 90px #000b}.exchange-search{margin-bottom:10px;color:#f8fafc;background:#1f2937;border-color:rgba(255,255,255,.12);font-weight:850}.exchange-search-status{min-height:18px;margin:0 0 8px;color:#9fb0c8;font-size:12px;font-weight:750}.exchange-list{max-height:min(520px,68vh);overflow:auto}.exchange-group>strong{display:block;position:sticky;top:0;padding:10px 11px;background:#1b2433;color:#9fb0c8;font-size:13px;font-weight:950;z-index:1}.exchange-picker.is-filtering .exchange-group>strong{display:none}.exchange-picker.is-filtering .exchange-group{padding:0}.exchange-option{display:flex;align-items:center;gap:13px;margin:1px 0;padding:10px 11px;border-radius:12px;cursor:pointer;font-weight:950;color:#f8fafc;letter-spacing:-.35px}.exchange-option[hidden],.exchange-group[hidden]{display:none!important}.exchange-option span:last-child{color:#f8fafc;font-size:16px;font-weight:950;text-shadow:0 2px 12px #0008}.exchange-option:hover{background:rgba(255,255,255,.075)}.exchange-option input{width:auto;margin:0;accent-color:#3b82f6}.exchange-option input:checked~span:last-child{color:#f6d680;font-weight:950}
.pager{display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin-top:15px}.pager a,.pager .on{display:inline-flex;align-items:center;justify-content:center;min-width:36px;padding:7px 11px;border:1px solid var(--line);border-radius:7px;background:rgba(255,255,255,.07);color:#d8e2f2}.pager a:hover{border-color:rgba(246,214,128,.46);background:rgba(246,214,128,.12);color:#fff}.pager .on{border-color:rgba(246,214,128,.52);background:rgba(246,214,128,.18);color:#f6d680;font-weight:850}.segments .seg{border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.065);color:#dbe6f6}.segments .seg.yes{border-color:rgba(74,222,128,.28);background:rgba(34,197,94,.13);color:#9af7c8}.segments .seg.no{border-color:rgba(251,113,133,.28);background:rgba(248,113,113,.13);color:#fecaca}.stat{font-size:34px;font-weight:850}.ip-intel-grid{grid-template-columns:repeat(4,minmax(0,1fr));align-items:start}.ip-intel-grid .col3{grid-column:span 1}.ip-intel-value{min-height:42px;margin-top:8px;color:#f2f6fd;font-size:16px;font-weight:800;line-height:1.55;overflow-wrap:anywhere;word-break:break-word}.ip-intel-score{font-size:24px;line-height:1.4;color:#f6d680}.actions{display:flex;gap:8px;align-items:end}.inline{display:inline}.catalog-filter{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.catalog-filter input{flex:1 1 280px}.catalog-filter select{min-width:130px}.catalog-edit-form{display:grid;grid-template-columns:repeat(2,minmax(180px,1fr));gap:9px;padding:12px;margin-top:8px;min-width:520px;border:1px solid rgba(255,255,255,.10);border-radius:12px;background:rgba(4,10,19,.68)}.catalog-edit-form label{font-size:12px;color:#9fb0c8}.catalog-edit-form input,.catalog-edit-form select{width:100%;margin-top:4px;padding:9px 10px}.catalog-edit-form button{justify-self:start}.catalog-edit-form label:nth-of-type(3){grid-column:1/-1}
.check-option{display:inline-flex;align-items:center;gap:6px;margin:0 14px 10px 0}.recipient-picker{max-height:220px;overflow:auto;padding:12px;border:1px solid var(--line);border-radius:7px;background:rgba(255,255,255,.03)}textarea{width:100%;min-height:120px;resize:vertical}
.market-terminal{padding:18px 18px 16px;background:radial-gradient(circle at 20% 0,rgba(246,214,128,.12),transparent 23rem),linear-gradient(145deg,rgba(10,22,38,.92),rgba(3,8,15,.96));border-color:rgba(246,214,128,.16)}
.market-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.market-kicker{font:900 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.24em;color:#f6d680}.market-live{display:inline-flex;align-items:center;gap:7px;color:#78f6c8;font-size:12px;font-weight:900}.market-live:before{content:"";width:8px;height:8px;border-radius:50%;background:#34d399;box-shadow:0 0 16px #34d399;animation:pulse-dot 1.5s infinite}
.market-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.market-tile{position:relative;min-height:178px;padding:18px;border:1px solid rgba(255,255,255,.10);border-radius:24px;background:linear-gradient(145deg,rgba(255,255,255,.055),rgba(255,255,255,.018));overflow:hidden;transition:.2s ease}.market-tile:before{content:"";position:absolute;inset:0;background:linear-gradient(120deg,transparent,rgba(255,255,255,.08),transparent);transform:translateX(-120%);animation:scan-sheen 3.6s infinite}.market-tile:hover{transform:translateY(-3px);border-color:rgba(246,214,128,.36);box-shadow:0 24px 70px rgba(0,0,0,.28),0 0 32px rgba(246,214,128,.08)}
.market-symbol{position:relative;z-index:1;color:#a8b6cb;font-weight:950;letter-spacing:.02em}.market-price{position:relative;z-index:1;margin-top:12px;font:900 30px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:#f6f9ff;letter-spacing:-1.7px}.market-change{position:relative;z-index:1;display:inline-flex;align-items:center;gap:6px;margin-top:10px;padding:6px 9px;border-radius:999px;font-size:12px;font-weight:950}.market-meta{position:relative;z-index:1;margin-top:8px;color:#718198;font-size:11px;font-weight:750}.spark{position:absolute;left:10px;right:10px;bottom:8px;height:46px;opacity:.95}.spark path{fill:none;stroke-width:4;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:230;animation:spark-flow 2.6s linear infinite}.market-tile.up{border-color:rgba(52,211,153,.22);box-shadow:inset 0 0 42px rgba(52,211,153,.045)}.market-tile.up .market-change{color:#9af7c8;background:rgba(16,185,129,.12);border:1px solid rgba(52,211,153,.22)}.market-tile.up .spark path{stroke:#34d399;filter:drop-shadow(0 0 10px rgba(52,211,153,.72))}.market-tile.down{border-color:rgba(248,113,113,.22);box-shadow:inset 0 0 42px rgba(248,113,113,.04)}.market-tile.down .market-change{color:#fecaca;background:rgba(248,113,113,.12);border:1px solid rgba(248,113,113,.24)}.market-tile.down .spark path{stroke:#fb7185;filter:drop-shadow(0 0 10px rgba(251,113,133,.65))}.market-tile.wait .market-change{color:#94a3b8;background:rgba(148,163,184,.10);border:1px solid rgba(148,163,184,.15)}.market-tile.wait .spark path{stroke:#64748b}.market-tile.active{border-color:rgba(246,214,128,.55);box-shadow:0 0 0 1px rgba(246,214,128,.14),0 0 34px rgba(246,214,128,.13),inset 0 0 36px rgba(246,214,128,.05)}
@keyframes spark-flow{from{stroke-dashoffset:230}to{stroke-dashoffset:0}}@keyframes scan-sheen{0%,55%{transform:translateX(-120%)}100%{transform:translateX(120%)}}@keyframes pulse-dot{0%,100%{opacity:.58;transform:scale(.8)}50%{opacity:1;transform:scale(1.1)}}
.market-terminal{padding:22px}.market-dashboard{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(320px,.65fr);gap:16px;margin-top:14px}.market-panel{position:relative;min-height:430px;border:1px solid rgba(246,214,128,.16);border-radius:28px;background:radial-gradient(circle at 18% 0,rgba(246,214,128,.12),transparent 20rem),linear-gradient(145deg,rgba(255,255,255,.055),rgba(255,255,255,.015));box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 26px 80px rgba(0,0,0,.26);overflow:hidden}.market-panel:before{content:"";position:absolute;inset:0;background:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px);background-size:100% 8px;opacity:.28;pointer-events:none}.market-panel:hover{border-color:rgba(246,214,128,.36);box-shadow:inset 0 1px 0 rgba(255,255,255,.10),0 30px 90px rgba(0,0,0,.34),0 0 34px rgba(246,214,128,.10)}
.market-chart-head{position:absolute;z-index:2;left:20px;right:20px;top:18px;display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.market-chart-title{font-size:11px;font-weight:950;letter-spacing:.22em;color:#7890ad}.market-chart-symbol{margin-top:5px;font-size:18px;font-weight:950;color:#fff}.market-chart-price{font:950 38px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:-2px;color:#f8fbff;text-align:right}.market-chart-change{display:inline-flex;margin-top:8px;padding:6px 10px;border-radius:999px;font-size:12px;font-weight:950}.timeframe-tabs{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}.tf-btn{padding:7px 10px;border-radius:999px;border:1px solid rgba(246,214,128,.18);background:rgba(255,255,255,.045);color:#aebbd0;font-size:11px;font-weight:950;letter-spacing:.04em;cursor:pointer}.tf-btn:hover,.tf-btn.active{color:#171105;background:linear-gradient(135deg,#f6d680,#c9942f);border-color:rgba(246,214,128,.55);box-shadow:0 0 22px rgba(246,214,128,.18)}.market-chart{position:absolute;inset:130px 12px 12px 12px}.ma-legend{margin-top:8px;font-size:12px;font-weight:900;color:#94a3b8}.ma-legend .ma7{color:#d6e4ff}.ma-legend .ma30{color:#f4e04d}
.signal-panel{padding:20px}.signal-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}.signal-title strong{font-size:18px;color:white;letter-spacing:.02em}.signal-title span{font:900 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:#f6d680;letter-spacing:.18em}.signal-row{display:grid;grid-template-columns:68px 1fr 44px;align-items:center;gap:12px;margin:12px 0}.signal-label{font:900 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:#edf4ff}.signal-note{display:block;margin-top:3px;font-size:10px;color:#687b96;font-weight:800}.signal-track{height:10px;border-radius:999px;background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.08);overflow:hidden}.signal-fill{height:100%;width:0;border-radius:999px;background:linear-gradient(90deg,#22d3ee,#34d399);box-shadow:0 0 16px rgba(34,211,238,.45);transition:width .6s ease}.signal-row.risk .signal-fill{background:linear-gradient(90deg,#f6d680,#fb7185)}.signal-value{font:950 13px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:#f6d680;text-align:right}
.market-grid{grid-template-columns:repeat(5,minmax(210px,1fr));margin-top:16px}.market-tile{min-height:154px;padding:16px}.market-price{font-size:27px;white-space:nowrap}.market-symbol{font-size:14px}.market-change{font-size:11px}.spark{height:36px}
.core-query-card{border-color:rgba(246,214,128,.34);background:radial-gradient(circle at 14% 0,rgba(246,214,128,.16),transparent 24rem),linear-gradient(145deg,rgba(16,28,48,.96),rgba(4,10,20,.97));box-shadow:0 34px 105px rgba(0,0,0,.36),0 0 0 1px rgba(246,214,128,.10),inset 0 1px 0 rgba(255,255,255,.10)}.core-query-card h2{font-size:30px;margin-bottom:22px}.core-label{display:inline-flex;margin-bottom:12px;padding:7px 11px;border-radius:999px;border:1px solid rgba(246,214,128,.26);background:rgba(246,214,128,.08);color:#f6d680;font:950 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.16em}.compact-market{opacity:.92;margin-top:18px}.compact-market h2{margin:6px 0 4px;font-size:22px}.compact-market .market-grid{grid-template-columns:repeat(5,minmax(160px,1fr));gap:10px}.compact-market .market-tile{min-height:124px;padding:14px;border-color:rgba(255,255,255,.08);box-shadow:none}.compact-market .market-tile:before{opacity:.35}.compact-market .market-price{font-size:24px;margin-top:10px}.compact-market .market-meta{font-size:10px}
.exchange-picker>summary{background:linear-gradient(145deg,rgba(5,12,22,.96),rgba(12,24,42,.92))!important;color:#f8fbff!important;border-color:rgba(246,214,128,.28)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 0 0 1px rgba(246,214,128,.06),0 12px 30px rgba(0,0,0,.22)}.exchange-picker>summary .exchange-name{color:#f8fbff!important;font-weight:750;text-shadow:none;letter-spacing:0}.exchange-picker>summary .selected-exchange-label{color:#dbe7f6!important;font-size:15px;font-weight:750;text-shadow:none;letter-spacing:0}.exchange-picker>summary:after{color:#f6d680!important}.exchange-menu .exchange-option,.exchange-menu .exchange-option span,.exchange-menu .exchange-option span:last-child{color:#ffffff!important;font-size:16px!important;font-weight:950!important;text-shadow:0 2px 12px rgba(0,0,0,.75)}.exchange-menu .exchange-option input:checked~span:last-child{color:#f6d680!important;text-shadow:0 0 18px rgba(246,214,128,.28),0 2px 12px rgba(0,0,0,.85)}

/* Premium dark-gold skin */
:root{--bg:#070b12;--card:rgba(13,22,36,.78);--text:#eef5ff;--muted:#8493aa;--line:rgba(255,255,255,.09);--brand:#d7a642;--gold:#f6d680;--gold2:#b98225;--blue:#2c65ff}
body{background:
radial-gradient(circle at 78% -10%,rgba(246,214,128,.14),transparent 34rem),
radial-gradient(circle at 18% 105%,rgba(42,101,255,.14),transparent 32rem),
linear-gradient(135deg,#060a11,#0a1220 48%,#04070c);color:var(--text);font-size:14px}
.layout{grid-template-columns:292px 1fr}.side{background:linear-gradient(180deg,rgba(5,14,26,.98),rgba(10,23,43,.96));border-right:1px solid rgba(246,214,128,.13);box-shadow:22px 0 70px rgba(0,0,0,.28);position:sticky}
.side:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 50% 0,rgba(246,214,128,.10),transparent 16rem);pointer-events:none}.side>*{position:relative}.main{padding:34px;max-width:1600px}
.brandhead{gap:16px;margin-bottom:30px;padding:10px;border:1px solid rgba(246,214,128,.10);border-radius:24px;background:linear-gradient(145deg,rgba(255,255,255,.055),rgba(255,255,255,.015));box-shadow:inset 0 1px 0 rgba(255,255,255,.08)}
.brandmark{width:74px;height:74px;border-radius:22px;border:1px solid rgba(246,214,128,.78);box-shadow:0 0 0 6px rgba(246,214,128,.06),0 18px 38px rgba(0,0,0,.42),0 0 34px rgba(246,214,128,.13)}
.logo{font-size:24px;letter-spacing:-.8px;text-shadow:0 3px 18px rgba(0,0,0,.45)}.logo small{font-size:11px;color:#e4b957;letter-spacing:2.2px}
.nav a{border:1px solid transparent;border-radius:16px;margin:8px 0;padding:14px 16px;color:#c9d5e8;font-size:15px;font-weight:750;transition:transform .18s ease,background .18s ease,border-color .18s ease}.nav a:hover{transform:translateX(3px);border-color:rgba(246,214,128,.18);background:rgba(255,255,255,.06)}.nav a.on{background:linear-gradient(135deg,#2d61f0,#1842bc);box-shadow:0 16px 34px rgba(45,97,240,.32);border-color:rgba(255,255,255,.14);color:white}
.business{border-top:1px solid rgba(246,214,128,.16)}.business-title{font-size:13px;color:#f0c568}.business-item{border-radius:15px;padding:12px;background:linear-gradient(145deg,rgba(255,255,255,.07),rgba(255,255,255,.025));border-color:rgba(255,255,255,.11);box-shadow:inset 0 1px 0 rgba(255,255,255,.06),0 12px 26px rgba(0,0,0,.16)}.business-icon{width:32px;height:32px;border-radius:11px;background:rgba(246,214,128,.08);box-shadow:inset 0 0 18px rgba(246,214,128,.05)}
.top{padding:6px 0 22px}.top h1{font-size:34px;letter-spacing:-1.4px}.top .muted{color:#74849c}.card{position:relative;background:linear-gradient(145deg,rgba(17,29,48,.82),rgba(7,13,23,.9));border:1px solid rgba(255,255,255,.09);border-radius:26px;box-shadow:0 22px 70px rgba(0,0,0,.30),inset 0 1px 0 rgba(255,255,255,.06);backdrop-filter:blur(18px)}.card:has(.exchange-picker[open]){z-index:9000;overflow:visible}h2{font-size:21px;color:#f8fbff}.muted{color:#8b9ab0}
input,select{background:rgba(5,12,22,.72);color:#f8fbff;border-color:rgba(255,255,255,.12);border-radius:15px;padding:13px 14px;outline:none}input:focus,select:focus{border-color:rgba(246,214,128,.65);box-shadow:0 0 0 4px rgba(246,214,128,.08)}button,.btn{border-radius:14px;background:linear-gradient(135deg,#f6d680,#b98225);color:#151006;box-shadow:0 12px 26px rgba(185,130,37,.26);transition:transform .18s ease,filter .18s ease}button:hover,.btn:hover{transform:translateY(-1px);filter:brightness(1.05)}.secondary{background:rgba(255,255,255,.08);color:#d8e2f2;border:1px solid rgba(255,255,255,.10);box-shadow:none}.danger{background:linear-gradient(135deg,#ef4444,#991b1b);color:white}
.exchange-menu .exchange-search{background:#1f2937;color:#f8fafc;border-color:rgba(255,255,255,.12)}.exchange-menu .exchange-search::placeholder{color:#9ca3af;font-weight:850}.exchange-menu .exchange-option span:last-child{color:#f8fafc!important}.exchange-menu .exchange-option input:checked~span:last-child{color:#f6d680!important}
table{color:#dbe6f6}th,td{border-bottom:1px solid rgba(255,255,255,.07)}th{color:#8291a7}.tablewrap{border-radius:18px}
.hero{border:1px solid rgba(246,214,128,.13);border-radius:30px;min-height:220px;padding:34px;background:linear-gradient(90deg,rgba(5,12,23,.96),rgba(5,12,23,.72) 45%,rgba(5,12,23,.20)),url('/assets/crypto-background.jpg') center/cover;box-shadow:0 28px 80px rgba(0,0,0,.34),inset 0 1px 0 rgba(255,255,255,.08)}.hero h2{font-size:38px;letter-spacing:-1.6px}.hero p{font-size:15px;color:#b7c4d8;max-width:760px}
.member-hero{position:relative;overflow:hidden;display:grid;grid-template-columns:1fr 220px;align-items:center;gap:24px;min-height:260px}.member-hero:after{content:"";position:absolute;inset:-1px;background:radial-gradient(circle at 83% 42%,rgba(246,214,128,.20),transparent 14rem),radial-gradient(circle at 68% 85%,rgba(44,101,255,.16),transparent 17rem);pointer-events:none}.member-hero>*{position:relative}.hero-kicker{display:inline-flex;gap:8px;align-items:center;margin-bottom:14px;padding:8px 12px;border:1px solid rgba(246,214,128,.22);border-radius:999px;background:rgba(246,214,128,.08);color:#f6d680;font-size:12px;font-weight:850;letter-spacing:.12em}.hero-logo{justify-self:end;width:160px;height:160px;clip-path:polygon(50% 0%,92% 23%,92% 75%,50% 100%,8% 75%,8% 23%);border:1px solid rgba(246,214,128,.58);object-fit:cover;box-shadow:0 0 0 10px rgba(246,214,128,.06),0 30px 90px rgba(0,0,0,.45),0 0 60px rgba(246,214,128,.18);filter:contrast(1.03) saturate(1.05)}
.plan-card{position:relative;overflow:hidden;min-height:330px;padding:28px;border-radius:30px}.plan-card:before{content:"";position:absolute;inset:0;background:linear-gradient(135deg,rgba(255,255,255,.09),transparent 38%);pointer-events:none}.plan-card h2{font-size:25px;margin-bottom:20px}.plan-card ul{margin:24px 0 0;padding-left:20px;color:#d8e3f3}.plan-card li{margin:10px 0}.plan-price{font-size:48px;font-weight:950;letter-spacing:-2px;color:#fff;text-shadow:0 8px 28px rgba(0,0,0,.28)}.plan-unit{color:#9caac0;font-weight:700}.plan-badge{display:inline-flex;margin-bottom:18px;padding:7px 11px;border-radius:999px;border:1px solid rgba(246,214,128,.22);background:rgba(246,214,128,.08);color:#f6d680;font-size:11px;font-weight:900;letter-spacing:.1em}.plan-starship{border-color:rgba(82,132,255,.36);box-shadow:0 26px 80px rgba(38,92,255,.20),inset 0 1px 0 rgba(255,255,255,.08)}.plan-starship .plan-price{color:#dfe8ff}.plan-pro{transform:translateY(-10px);border-color:rgba(246,214,128,.48);background:linear-gradient(145deg,rgba(51,35,12,.92),rgba(10,16,26,.92) 48%,rgba(17,29,48,.86));box-shadow:0 34px 110px rgba(185,130,37,.26),0 0 0 1px rgba(246,214,128,.18),inset 0 1px 0 rgba(255,255,255,.12)}.plan-pro:after{content:"旗舰首选";position:absolute;right:22px;top:22px;padding:8px 12px;border-radius:999px;background:linear-gradient(135deg,#f6d680,#b98225);color:#151006;font-size:11px;font-weight:950}.plan-pro .plan-price{background:linear-gradient(135deg,#fff7cf,#f6d680 45%,#b98225);-webkit-background-clip:text;background-clip:text;color:transparent}
.payment-panel{position:relative;overflow:hidden}.payment-panel:before{content:"";position:absolute;right:-80px;top:-100px;width:260px;height:260px;border-radius:50%;background:radial-gradient(circle,rgba(246,214,128,.14),transparent 65%)}.payment-panel>*{position:relative}.payment-panel .hint{margin-top:10px;margin-bottom:20px;line-height:1.75}.payment-panel p{line-height:1.9}.payment-rule{margin-top:14px;padding:14px 16px;border:1px solid rgba(246,214,128,.34);border-radius:16px;background:rgba(246,214,128,.10);color:#fff0bd;font-size:13px;line-height:1.8}.payment-rule strong{color:#f6d680}.pay-address input{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:750;letter-spacing:-.4px}.chain-pill{display:inline-flex;align-items:center;gap:8px;padding:11px 14px;border-radius:16px;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.05);font-weight:850}.chain-pill.good{border-color:rgba(34,197,94,.22);background:rgba(34,197,94,.10);color:#86efac}.chain-pill.gold{border-color:rgba(246,214,128,.22);background:rgba(246,214,128,.10);color:#f6d680}
body:before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.014) 1px,transparent 1px);background-size:54px 54px;mask-image:radial-gradient(circle at 50% 20%,black,transparent 75%)}::selection{background:rgba(246,214,128,.28);color:white}::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-track{background:rgba(255,255,255,.025)}::-webkit-scrollbar-thumb{background:linear-gradient(180deg,rgba(246,214,128,.48),rgba(80,92,117,.42));border:2px solid rgba(5,8,15,.95);border-radius:999px}.side{box-shadow:26px 0 92px rgba(0,0,0,.36),inset -1px 0 rgba(246,214,128,.08)}.brandhead{box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 18px 50px rgba(0,0,0,.20)}.card{overflow:hidden}.card:before{content:"";position:absolute;inset:0;background:linear-gradient(135deg,rgba(255,255,255,.07),transparent 35%),linear-gradient(180deg,rgba(255,255,255,.025),transparent 55%);pointer-events:none}.card>*{position:relative;z-index:1}table{border-collapse:separate;border-spacing:0}th{font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:850}tr{transition:background .16s ease}tbody tr:hover{background:rgba(246,214,128,.035)}.hero,.member-hero{box-shadow:0 38px 120px rgba(0,0,0,.44),inset 0 1px 0 rgba(255,255,255,.09)}.plan-card{box-shadow:0 28px 90px rgba(0,0,0,.32),inset 0 1px 0 rgba(255,255,255,.08)}.plan-card:hover{transform:translateY(-4px)}.gold-text{background:linear-gradient(135deg,#fff7d6,#f6d680 48%,#b98225);-webkit-background-clip:text;background-clip:text;color:transparent}
.terminal-font, .stat, .market-price, .risk-score, .metric-value{font-family:"JetBrains Mono","SFMono-Regular","Menlo","HarmonyOS Sans","Source Han Sans SC","PingFang SC",monospace}.logo,.market-kicker,.core-label,.hero-kicker{font-family:"Orbitron","JetBrains Mono","SFMono-Regular","HarmonyOS Sans","PingFang SC",sans-serif}.risk-disclaimer{border:1px solid rgba(246,214,128,.20);border-radius:18px;padding:14px 16px;background:linear-gradient(135deg,rgba(246,214,128,.08),rgba(255,255,255,.025));color:#d8cda9;font-size:13px;line-height:1.75}.trust-grid,.risk-dashboard{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.trust-card,.risk-panel{position:relative;border:1px solid rgba(255,255,255,.09);border-radius:22px;padding:18px;background:linear-gradient(145deg,rgba(255,255,255,.055),rgba(255,255,255,.018));box-shadow:inset 0 1px 0 rgba(255,255,255,.06);overflow:hidden}.trust-card:after,.risk-panel:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,transparent 0,rgba(255,255,255,.035) 50%,transparent 100%);background-size:100% 9px;opacity:.28;pointer-events:none}.trust-card strong{display:block;margin-top:8px;font-size:28px;color:#f8fbff}.trust-card span,.risk-panel span{color:#8b9ab0;font-size:12px;font-weight:800}.risk-panel h3{margin:0 0 14px;font-size:17px;color:#f8fbff}.risk-row{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:10px 0;color:#dce7f7}.risk-score{display:inline-flex;padding:6px 9px;border-radius:999px;font-weight:950}.risk-low{background:rgba(34,197,94,.14);color:#86efac}.risk-medium{background:rgba(246,214,128,.13);color:#f6d680}.risk-high{background:rgba(248,113,113,.14);color:#fecaca}.scan-progress{display:none;margin-top:16px;border:1px solid rgba(246,214,128,.16);border-radius:999px;background:rgba(0,0,0,.24);overflow:hidden}.scan-progress span{display:block;width:0;height:10px;background:linear-gradient(90deg,#f6d680,#34d399);box-shadow:0 0 18px rgba(246,214,128,.35);animation:scan-fill 1.35s ease forwards}@keyframes scan-fill{from{width:0}to{width:85%}}form.scanning .scan-progress{display:block}form.scanning button{pointer-events:none;opacity:.82}.market-detail{position:relative;z-index:1;display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:12px;color:#9badc4;font-size:11px;font-weight:800}.market-detail b{color:#e8f1ff}.market-mini{position:relative;z-index:1;margin-top:12px;width:100%;height:34px}.market-mini path{fill:none;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.market-tile.up .market-mini path{stroke:#34d399;filter:drop-shadow(0 0 8px rgba(52,211,153,.55))}.market-tile.down .market-mini path{stroke:#fb7185;filter:drop-shadow(0 0 8px rgba(251,113,133,.45))}
.core-query-card{padding:30px 32px}.core-query-card h2{margin-bottom:30px}.core-query-card .grid,.address-check-card .grid{row-gap:22px}.query-action-row{display:flex;align-items:flex-end;gap:16px;padding-top:4px}.query-action-row button{white-space:nowrap}.address-check-card{margin-top:18px;margin-bottom:26px;border-color:rgba(246,214,128,.18)}.address-check-card h2{margin-bottom:22px}.address-check-card input,.settings-long-input,.pay-address input{min-width:0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:0}.address-check-card #check-address{font-size:15px}.trust-grid{margin:24px 0 26px}.risk-dashboard{margin:0 0 28px}.payment-panel{margin-top:22px}.plan-order-form{margin-top:20px;display:grid;gap:12px}.plan-order-form select{max-width:180px}.order-box{margin-top:22px;padding:18px;border:1px solid rgba(246,214,128,.16);border-radius:20px;background:rgba(255,255,255,.035)}.verify-form{display:grid;grid-template-columns:1fr auto;gap:14px;align-items:end;margin-top:18px}.verify-form label{grid-column:1/-1}.verify-form input{min-width:0}
.announcement-modal{position:fixed;z-index:11000;inset:0;display:grid;place-items:center;padding:20px;background:rgba(2,6,14,.78);backdrop-filter:blur(10px)}.announcement-dialog{position:relative;width:min(560px,calc(100vw - 32px));overflow:hidden;border:1px solid rgba(246,214,128,.42);border-radius:26px;padding:30px;background:radial-gradient(circle at 86% 0,rgba(246,214,128,.17),transparent 17rem),linear-gradient(145deg,rgba(19,31,51,.98),rgba(5,11,20,.98));box-shadow:0 34px 110px rgba(0,0,0,.64),inset 0 1px 0 rgba(255,255,255,.11)}.announcement-dialog:before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(rgba(255,255,255,.024) 1px,transparent 1px);background-size:100% 7px;opacity:.42}.announcement-dialog>*{position:relative;z-index:1}.announcement-kicker{display:inline-flex;padding:7px 10px;border:1px solid rgba(246,214,128,.24);border-radius:999px;background:rgba(246,214,128,.09);color:#f6d680;font:900 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em}.announcement-dialog h2{margin:17px 0 12px;font-size:25px;line-height:1.35}.announcement-body{max-height:42vh;overflow:auto;padding-right:4px;color:#cbd8e8;font-size:14px;line-height:1.85;white-space:pre-wrap}.announcement-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:24px}.announcement-actions button{min-width:112px}.notice-bell{position:relative;display:inline-grid;place-items:center;width:42px;height:42px;margin-right:10px;border:1px solid rgba(255,255,255,.13);border-radius:14px;background:rgba(255,255,255,.06);color:#f6d680;font-size:21px;line-height:1;box-shadow:none}.notice-bell:hover{background:rgba(246,214,128,.12);transform:translateY(-1px)}.notice-bell-count{position:absolute;right:-7px;top:-7px;display:grid;place-items:center;min-width:20px;height:20px;padding:0 5px;border:2px solid #101a2b;border-radius:999px;background:#ef4444;color:#fff;font-size:10px;font-weight:900;box-shadow:0 0 16px rgba(239,68,68,.48)}.inbox-meta{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.inbox-item{border:1px solid rgba(255,255,255,.10);border-radius:20px;padding:20px;margin-bottom:13px;background:linear-gradient(145deg,rgba(255,255,255,.045),rgba(255,255,255,.018))}.inbox-item.unread{border-color:rgba(246,214,128,.38);box-shadow:inset 3px 0 0 #f6d680}.inbox-title{margin:0;color:#f4f8ff;font-size:18px}.inbox-body{margin:13px 0 0;color:#b6c4d8;line-height:1.8;white-space:pre-wrap}.notice-status{display:inline-flex;padding:5px 9px;border-radius:999px;background:rgba(246,214,128,.12);color:#f6d680;font-size:12px;font-weight:800}.notice-status.read{background:rgba(148,163,184,.12);color:#aab8cb}.inbox-actions{display:flex;justify-content:flex-end;margin-top:16px}.inbox-actions button{padding:8px 12px;font-size:12px}
@media(max-width:1180px){.market-dashboard{grid-template-columns:1fr}.market-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.market-tile{min-height:168px}}
@media(max-width:850px){.layout{display:block}.side{position:static;height:auto;overflow:visible;padding:14px}.brandhead{margin-bottom:12px}.brandmark{width:42px;height:42px}.nav{display:flex;overflow:auto}.nav a{white-space:nowrap}.business{margin-top:12px;padding-top:10px}.business-list{display:flex;gap:8px;overflow-x:auto;padding-bottom:3px}.business-item{min-width:max-content;margin:0}.main{padding:16px}.col2,.col3,.col4,.col6,.col7,.col8,.col9,.col10{grid-column:span 12}.query-action-row button{width:100%}.ip-intel-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 14px}.ip-intel-grid .col3{grid-column:span 1}.ip-intel-grid .col12{grid-column:1/-1}.ip-intel-value{min-height:0;font-size:15px}.ip-intel-score{font-size:22px}.card{padding:16px}.hero{min-height:145px;padding:20px}.hero h2{font-size:22px}.market-dashboard{grid-template-columns:1fr}.market-panel{min-height:300px}.market-grid,.trust-grid,.risk-dashboard{grid-template-columns:1fr}.market-price{font-size:34px}.market-chart-price{font-size:28px}.announcement-modal{padding:14px}.announcement-dialog{padding:23px 20px;border-radius:22px}.announcement-dialog h2{font-size:21px}.announcement-actions{display:grid;grid-template-columns:1fr}.announcement-actions button{width:100%}.inbox-meta{align-items:flex-start;flex-direction:column}}
@media(max-width:850px){.layout{grid-template-columns:1fr}.side{border-right:0}.main{padding:18px}.top h1{font-size:28px}.brandhead{border-radius:18px}.member-hero{grid-template-columns:1fr;min-height:auto}.hero-logo{justify-self:start;width:92px;height:92px}.plan-pro{transform:none}.plan-price{font-size:40px}.hero h2{font-size:30px}}

/* OriginX Web4 visual refresh: preserve existing markup and behavior, refine the visual hierarchy. */
:root{--bg:#06060a;--card:#0c0c10;--panel:#0c0c10;--elevated:#12121a;--text:#f4f7fb;--muted:#858995;--line:rgba(255,255,255,.08);--brand:#3b82f6;--blue:#2563eb;--gold:#93b4ef}
body{background:var(--bg);color:var(--text);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;font-size:14px}
body:before{background:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.012) 1px,transparent 1px);background-size:56px 56px;opacity:.42}
.layout{grid-template-columns:250px 1fr}.side{background:#09090d;border-right:1px solid var(--line);box-shadow:18px 0 50px rgba(0,0,0,.28);padding:22px 16px}.side:before{display:none}
.brandhead{margin:0 4px 26px;padding:8px;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.025);box-shadow:0 10px 28px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.05)}
.brandmark{width:54px;height:54px;border-radius:12px;border:1px solid rgba(59,130,246,.6);box-shadow:0 0 0 4px rgba(59,130,246,.08),0 12px 26px rgba(0,0,0,.42);clip-path:polygon(25% 6.7%,75% 6.7%,100% 50%,75% 93.3%,25% 93.3%,0 50%)}
.logo{font-size:20px;letter-spacing:-.4px}.logo small{color:#8fb8ff;letter-spacing:1.6px}
.nav a{border:1px solid transparent;border-radius:10px;margin:4px 0;padding:10px 12px;color:#aeb2bd;transition:background .16s ease,color .16s ease,transform .16s ease}.nav a:hover{background:rgba(59,130,246,.08);color:#dbeafe;transform:translateX(2px)}.nav a.on{background:#2563eb;color:#fff;box-shadow:0 8px 22px rgba(37,99,235,.22),inset 0 1px 0 rgba(255,255,255,.16)}
.business{border-top-color:var(--line)}.business-title{color:#7f8797}.business-item{border-color:var(--line);background:rgba(255,255,255,.025);color:#c8ccd5}.business-icon{border-color:rgba(59,130,246,.38);color:#8fb8ff}
.main{padding:30px;max-width:1500px}.top{margin-bottom:24px}.top h1{font-size:24px;letter-spacing:-.5px}.top .muted{margin-top:4px;color:#717581}.notice-bell{width:38px;height:38px;border-radius:10px;color:#a8c7ff;background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.22);font-size:18px}.notice-bell:hover{background:rgba(59,130,246,.16)}
.card,.trust-card,.risk-panel,.market-panel,.inbox-item{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 4px 24px rgba(0,0,0,.38),inset 0 1px 0 rgba(255,255,255,.045)}.card:before{background:linear-gradient(135deg,rgba(255,255,255,.035),transparent 35%)}
.hero{min-height:142px;padding:26px;background:linear-gradient(90deg,rgba(7,9,16,.96),rgba(7,9,16,.56)),url('/assets/crypto-background.jpg') center/cover;border-color:var(--line)}.hero h2{font-size:28px;letter-spacing:-.7px}.hero-kicker,.core-label{color:#8fb8ff;border-color:rgba(59,130,246,.28);background:rgba(59,130,246,.09)}
input,select,textarea,.exchange-picker>summary{color:var(--text);background:#08080c!important;border-color:var(--line)!important;border-radius:10px;box-shadow:inset 0 2px 8px rgba(0,0,0,.48),0 1px 0 rgba(255,255,255,.025)}input::placeholder,textarea::placeholder{color:#5f6470}input:focus,select:focus,textarea:focus{outline:0;border-color:rgba(59,130,246,.72)!important;box-shadow:0 0 0 3px rgba(59,130,246,.13),inset 0 2px 8px rgba(0,0,0,.48)}
button,.btn{background:linear-gradient(180deg,#3b82f6,#2563eb);border-radius:10px;box-shadow:0 8px 18px rgba(37,99,235,.2),inset 0 1px 0 rgba(255,255,255,.18);transition:transform .16s ease,box-shadow .16s ease}button:hover,.btn:hover{transform:translateY(-1px);box-shadow:0 12px 24px rgba(37,99,235,.28),inset 0 1px 0 rgba(255,255,255,.2)}button.secondary,.secondary{background:#17181f;color:#cfd4df;border:1px solid var(--line);box-shadow:none}.danger{background:#b93643}
.core-query-card{border-color:rgba(59,130,246,.28);background:linear-gradient(145deg,#10131c,#0b0c11);box-shadow:0 24px 70px rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.06)}.core-query-card h2{font-size:22px}.query-action-row{align-items:center}.scan-cta{position:relative;isolation:isolate;overflow:hidden}.scan-cta:before{content:"";position:absolute;z-index:-1;inset:-2px;border-radius:12px;background:conic-gradient(from 0deg,transparent 0 70%,#60a5fa 82%,#2563eb 92%,transparent);animation:originx-spin 2.8s linear infinite}.scan-cta:after{content:"";position:absolute;z-index:-1;inset:1px;border-radius:9px;background:#2563eb}@keyframes originx-spin{to{transform:rotate(360deg)}}
.trust-card,.risk-panel{background:linear-gradient(145deg,#111219,#0c0c10);box-shadow:0 8px 24px rgba(0,0,0,.25),inset 0 1px 0 rgba(255,255,255,.045)}.trust-card:hover,.risk-panel:hover{border-color:rgba(59,130,246,.28);transform:translateY(-2px);transition:.16s ease}.trust-card strong{color:#f8fafc}.trust-card span,.risk-panel span{color:#858995}.risk-panel h3{color:#e9edf5}.risk-low{background:rgba(74,222,128,.13);color:#86efac}.risk-medium{background:rgba(250,204,21,.13);color:#fde68a}.risk-high{background:rgba(248,113,113,.13);color:#fca5a5}.risk-score{border:1px solid rgba(255,255,255,.07)}
table{border-collapse:separate;border-spacing:0}th,td{border-bottom-color:rgba(255,255,255,.07)}th{color:#777d89}tbody tr:hover{background:rgba(59,130,246,.05)}.pager a,.pager .on{border-color:var(--line);background:#111219;color:#c9ced8}.pager a:hover,.pager .on{border-color:rgba(59,130,246,.42);background:rgba(59,130,246,.13);color:#bfdbfe}
.market-terminal,.market-panel{background:linear-gradient(145deg,#101219,#0b0c10);border-color:var(--line)}.market-kicker,.market-chart-title{color:#8fb8ff}.market-tile{border-radius:12px;background:#111219;border-color:var(--line)}.market-tile:hover{border-color:rgba(59,130,246,.36);box-shadow:0 18px 50px rgba(0,0,0,.32)}.market-tile.active{border-color:rgba(59,130,246,.55);box-shadow:0 0 0 1px rgba(59,130,246,.14),0 0 30px rgba(59,130,246,.1)}.market-source{color:#858995!important}
.announcement-dialog{border-color:rgba(59,130,246,.42);border-radius:16px;background:linear-gradient(145deg,#141722,#0b0c11)}.announcement-kicker{color:#9bc1ff;border-color:rgba(59,130,246,.3);background:rgba(59,130,246,.1)}.announcement-dialog h2{color:#f4f7fb}.notice-status{background:rgba(59,130,246,.12);color:#9bc1ff}.inbox-item{border-radius:12px}.inbox-item.unread{border-color:rgba(59,130,246,.42);box-shadow:inset 3px 0 0 #3b82f6}
.login{background:linear-gradient(120deg,rgba(4,5,10,.76),rgba(4,5,10,.9)),url('/assets/crypto-background.jpg') center/cover fixed}.loginbox{border-color:var(--line);border-radius:16px;background:rgba(12,12,16,.9);box-shadow:0 30px 80px rgba(0,0,0,.58),inset 0 1px 0 rgba(255,255,255,.06)}.loginbrand img{border-color:rgba(59,130,246,.55);border-radius:12px}.loginbox .muted,.loginbox .contact{color:#858995}.loginbox input{color:var(--text);background:#08080c}.loginbox button{background:linear-gradient(180deg,#3b82f6,#2563eb);color:#fff}.loginbox .contact a,.authlinks a,.contact a{color:#9bc1ff}
.home-market-strip{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:0 0 18px}.home-market-card{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:72px;padding:14px 16px;border:1px solid var(--line);border-radius:12px;background:#0c0c10;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}.home-market-card .market-symbol{color:#dbeafe}.home-market-card .market-price{margin:0;font-size:19px}.home-market-card .market-change{margin:0}.home-market-source{grid-column:1/-1;margin:-4px 2px 0;color:#686d78;font-size:11px}
.console-heading{position:relative;margin-bottom:18px}.console-heading .hero{margin-bottom:0}.console-crumb{margin:0 0 9px;color:#717581;font:700 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase}.system-status{position:absolute;right:20px;top:20px;display:inline-flex;align-items:center;gap:8px;padding:7px 10px;border:1px solid rgba(74,222,128,.22);border-radius:999px;background:rgba(74,222,128,.08);color:#9af7c8;font-size:12px;font-weight:800}.system-status i{width:7px;height:7px;border-radius:50%;background:#4ade80;box-shadow:0 0 12px rgba(74,222,128,.8);animation:pulse-dot 1.5s infinite}
@media(max-width:850px){.main{padding:18px}.home-market-strip{grid-template-columns:1fr}.home-market-source{grid-column:auto}.hero h2{font-size:23px}.top h1{font-size:22px}}

/* Uiverse-inspired blue terminal details: a single moving beam, tactile depth, and responsive data density. */
.hero{position:relative;overflow:hidden;border:1px solid rgba(96,165,250,.16)}.hero:after{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(110deg,transparent 18%,rgba(96,165,250,.13) 49%,transparent 68%);transform:translateX(-115%);animation:originx-hero-sweep 8s ease-in-out infinite}.hero>div{position:relative;z-index:1}@keyframes originx-hero-sweep{0%,58%{transform:translateX(-115%)}78%,100%{transform:translateX(115%)}}
.risk-disclaimer{display:flex;align-items:flex-start;gap:8px;border-color:rgba(59,130,246,.17);border-radius:12px;background:linear-gradient(100deg,rgba(37,99,235,.11),rgba(12,12,16,.8) 48%);color:#aeb8c8;box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}
.market-terminal{position:relative;isolation:isolate;overflow:hidden;padding:20px!important;border-color:rgba(59,130,246,.24)!important;background:radial-gradient(circle at 7% 0,rgba(37,99,235,.19),transparent 23rem),linear-gradient(145deg,#10131d,#090a0f 64%)!important}.market-terminal:after{content:"";position:absolute;z-index:-1;inset:-1px;border-radius:15px;padding:1px;background:linear-gradient(110deg,transparent 6%,rgba(96,165,250,.02) 30%,rgba(96,165,250,.76) 50%,rgba(37,99,235,.06) 67%,transparent 93%);background-size:240% 100%;animation:originx-border-beam 6.5s linear infinite;mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);mask-composite:exclude;pointer-events:none}@keyframes originx-border-beam{to{background-position:240% 0}}
.market-terminal .market-head{padding-bottom:15px;margin-bottom:0;border-bottom:1px solid rgba(255,255,255,.065)}.market-terminal .market-head h2{font-size:23px;letter-spacing:-.45px}.market-terminal .market-head .secondary{position:relative;min-width:105px;padding-right:34px}.market-terminal .market-head .secondary:after{content:"↻";position:absolute;right:12px;top:50%;font-size:16px;line-height:1;transform:translateY(-50%);transition:transform .5s ease}.market-terminal .market-head .secondary:hover:after{transform:translateY(-50%) rotate(360deg)}
.compact-market .market-grid{grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:12px;margin-top:16px}.compact-market .market-tile{min-height:228px;padding:16px;border:1px solid rgba(148,163,184,.15);border-radius:13px;background:linear-gradient(145deg,rgba(27,31,43,.96),rgba(12,13,19,.94));box-shadow:0 10px 28px rgba(0,0,0,.18),inset 0 1px 0 rgba(255,255,255,.045);transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease}.compact-market .market-tile:before{background:linear-gradient(112deg,transparent 26%,rgba(96,165,250,.12) 48%,transparent 70%);animation:originx-card-sweep 4.5s ease-in-out infinite}.compact-market .market-tile:hover{transform:translateY(-4px);border-color:rgba(96,165,250,.5);box-shadow:0 20px 40px rgba(0,0,0,.34),0 0 0 1px rgba(59,130,246,.1),inset 0 1px 0 rgba(255,255,255,.08)}@keyframes originx-card-sweep{0%,62%{transform:translateX(-140%)}100%{transform:translateX(140%)}}
.compact-market .market-symbol{display:flex;align-items:center;gap:8px;color:#c8d8f5;font-size:12px;letter-spacing:.08em}.compact-market .market-symbol:before{content:"";width:7px;height:7px;border-radius:999px;background:#60a5fa;box-shadow:0 0 12px rgba(96,165,250,.72)}.compact-market .market-price{font-size:25px;color:#f8fbff;text-shadow:0 4px 18px rgba(0,0,0,.38)}.compact-market .market-detail{margin-top:13px;padding-top:12px;border-top:1px solid rgba(255,255,255,.055);gap:8px;color:#7f899b}.compact-market .market-detail b{color:#dfeaff}.compact-market .market-meta{margin-top:12px;padding-top:9px;border-top:1px solid rgba(255,255,255,.05);color:#657187}.compact-market .market-tile.up{border-color:rgba(74,222,128,.24);box-shadow:inset 0 0 38px rgba(74,222,128,.035),0 10px 28px rgba(0,0,0,.18)}.compact-market .market-tile.down{border-color:rgba(248,113,113,.25);box-shadow:inset 0 0 38px rgba(248,113,113,.035),0 10px 28px rgba(0,0,0,.18)}
@media(max-width:1180px){.compact-market .market-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:850px){.market-terminal{padding:16px!important}.market-terminal .market-head{align-items:flex-start}.compact-market .market-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.compact-market .market-tile{min-height:216px}.compact-market .market-price{font-size:21px}}@media(max-width:560px){.compact-market .market-grid{grid-template-columns:1fr}.market-terminal .market-head h2{font-size:20px}.market-terminal .market-head{gap:10px}.risk-disclaimer{font-size:12px}}

/* Halo design system: quiet deep-space surfaces, indigo actions, and signal-only color. */
:root{--bg:#0a0b0f;--card:#14151c;--panel:#14151c;--elevated:#1e2029;--text:#f2f4f8;--muted:#9aa0ae;--faint:#5c6170;--line:#2a2d38;--line-strong:#3a3d4a;--brand:#5b6bff;--blue:#4a59e6;--gold:#f5d547;--cyan:#3dd7e5;--success:#2be08c;--danger:#ff3a5c}
body{background:var(--bg);color:var(--text);font:15px/1.55 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}body:before{display:none}::selection{background:rgba(91,107,255,.35);color:#fff}
.layout{grid-template-columns:248px 1fr}.side{background:#0a0b0f;border-right:1px solid var(--line);box-shadow:none;padding:24px 16px}.brandhead{margin:0 4px 28px;padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}.brandmark{width:42px;height:42px;border:1px solid var(--line-strong);border-radius:10px;clip-path:none;box-shadow:none}.logo{font-size:18px;letter-spacing:-.35px}.logo small{color:var(--faint);font-size:10px;letter-spacing:1.3px}.nav a{border-radius:8px;color:var(--muted);margin:3px 0;padding:9px 11px}.nav a:hover{background:#14151c;color:var(--text);transform:none}.nav a.on{background:rgba(91,107,255,.15);border-color:rgba(91,107,255,.42);color:#c8ceff;box-shadow:inset 0 0 0 1px rgba(91,107,255,.08)}.business{margin-top:24px;padding-top:18px;border-top-color:var(--line)}.business-title{color:var(--faint)}.business-item{border:0;background:transparent;color:#818796;box-shadow:none;padding:7px 10px}.business-item:hover{background:#14151c;border-color:transparent}.business-icon{width:20px;height:20px;border:0;border-radius:5px;background:#1e2029;color:#9ca9ff}
.main{max-width:1440px;padding:32px clamp(20px,3vw,40px)}.top{padding-bottom:20px;margin-bottom:24px;border-bottom:1px solid var(--line)}.top h1{font-size:24px;font-weight:600;letter-spacing:-.48px}.top .muted{color:var(--muted)}.contact{border-top-color:var(--line);color:var(--faint)}.contact a{color:#aeb7ff}.notice-bell{width:40px;height:40px;border:1px solid var(--line-strong);border-radius:10px;background:#14151c;color:#cbd0dc;box-shadow:none}.notice-bell:hover{background:#1e2029;border-color:#535b70}.notice-bell-count{border-color:#14151c;background:var(--danger);box-shadow:none}
h1,h2,h3{font-weight:600;letter-spacing:-.02em}.muted{color:var(--muted)}.hint{color:var(--faint)}.card,.trust-card,.risk-panel,.market-panel,.inbox-item{background:var(--card);border-color:var(--line);border-radius:16px;box-shadow:0 1px 0 rgba(255,255,255,.02) inset,0 1px 2px rgba(0,0,0,.4)}.card{padding:24px}.card:before{display:none}.card>*{z-index:auto}.flash{border:1px solid rgba(61,215,229,.24);border-radius:10px;background:rgba(61,215,229,.09);color:#b8f4fb}.flash.err{border-color:rgba(255,58,92,.32);background:rgba(255,58,92,.11);color:#ffd0d9}
label{color:#c7cad4;font-size:12px;font-weight:500;letter-spacing:.06em;text-transform:uppercase}input,select,textarea,.exchange-picker>summary{min-height:40px;padding:9px 14px;background:#14151c!important;border-color:var(--line)!important;border-radius:10px;box-shadow:none;color:var(--text)}input:focus,select:focus,textarea:focus{border-color:var(--brand)!important;box-shadow:0 0 0 3px rgba(91,107,255,.35)}input::placeholder,textarea::placeholder{color:var(--faint)}
button,.btn{min-height:40px;padding:9px 18px;border-radius:10px;background:var(--brand);box-shadow:none;font-size:13px;font-weight:600;transition:background .15s cubic-bezier(.2,.6,.2,1),transform .15s cubic-bezier(.2,.6,.2,1)}button:hover,.btn:hover{background:#7886ff;transform:none;box-shadow:none}button:active,.btn:active{background:#4a59e6;transform:translateY(1px)}button.secondary,.secondary{background:#14151c;color:var(--text);border:1px solid var(--line-strong)}button.secondary:hover,.secondary:hover{background:#1e2029;border-color:#4b4f5d}.danger{background:var(--danger)}
.hero{min-height:152px;padding:26px;border:1px solid var(--line);border-radius:16px;background:linear-gradient(100deg,rgba(91,107,255,.13),rgba(20,21,28,.88) 46%,rgba(20,21,28,.97)),url('/assets/crypto-background.jpg') center/cover;box-shadow:none}.hero:after{display:none}.hero h2{font-size:28px}.hero p{color:#b4bac7}.hero-kicker,.core-label{border:0;background:transparent;color:#aeb7ff;font:500 12px/1 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:.1em}.console-crumb{color:var(--faint)}.system-status{border-color:rgba(43,224,140,.26);background:rgba(43,224,140,.1);color:#9cf3c6;box-shadow:none}.system-status i{background:var(--success);box-shadow:0 0 10px rgba(43,224,140,.56)}
.scan-cta{overflow:visible}.scan-cta:before,.scan-cta:after{display:none}.core-query-card{background:#14151c;border-color:var(--line-strong);box-shadow:0 8px 24px rgba(0,0,0,.45),0 1px 0 rgba(255,255,255,.03) inset}.core-query-card h2{font-size:22px}.scan-progress{border-color:var(--line);background:#0a0b0f}.scan-progress span{background:var(--brand);box-shadow:none}
.trust-card,.risk-panel{border-radius:16px;background:#14151c;box-shadow:none}.trust-card:after,.risk-panel:after{display:none}.trust-card:hover,.risk-panel:hover{transform:none;border-color:var(--line-strong)}.trust-card strong{font:600 30px/1 "JetBrains Mono",ui-monospace,monospace}.trust-card span,.risk-panel span{color:var(--muted)}.risk-panel h3{color:var(--text)}.risk-row{color:#d7dbe4}.risk-score{border:0}.risk-low{background:rgba(43,224,140,.12);color:#8cf0bc}.risk-medium{background:rgba(245,213,71,.13);color:#f7df7d}.risk-high{background:rgba(255,58,92,.13);color:#ff9eb0}
.risk-disclaimer{border-color:rgba(245,213,71,.3);border-radius:10px;background:rgba(245,213,71,.065);color:#d9cf9a;box-shadow:none}.market-terminal{padding:24px!important;border-color:var(--line-strong)!important;background:#14151c!important;box-shadow:0 8px 24px rgba(0,0,0,.45),0 1px 0 rgba(255,255,255,.03) inset}.market-terminal:after{display:none}.market-terminal .market-head{border-bottom-color:var(--line)}.market-kicker,.market-chart-title{color:var(--cyan)}.compact-market .market-grid{grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.compact-market .market-tile{min-height:220px;border-color:var(--line);border-radius:12px;background:#1e2029;box-shadow:none}.compact-market .market-tile:before{display:none}.compact-market .market-tile:hover{transform:translateY(-2px);border-color:#50576a;box-shadow:0 8px 24px rgba(0,0,0,.32)}.compact-market .market-symbol{color:#cfd6e6}.compact-market .market-symbol:before{background:var(--cyan);box-shadow:0 0 10px rgba(61,215,229,.55)}.compact-market .market-price{font:600 24px/1 "JetBrains Mono",ui-monospace,monospace;letter-spacing:-.6px;text-shadow:none}.compact-market .market-detail,.compact-market .market-meta{border-color:var(--line);color:var(--muted)}.compact-market .market-detail b{color:#e7eaf1}.market-tile.up{border-color:rgba(43,224,140,.35)!important}.market-tile.down{border-color:rgba(255,58,92,.38)!important}.market-tile.up .market-change{background:rgba(43,224,140,.12);color:#83f0b6}.market-tile.down .market-change{background:rgba(255,58,92,.12);color:#ff9fb0}.market-source{color:var(--faint)!important}
table{border-collapse:separate;border-spacing:0}th,td{padding:12px 10px;border-bottom-color:var(--line)}th{color:var(--muted);font-size:11px;font-weight:500;letter-spacing:.08em}tbody tr:hover{background:rgba(91,107,255,.055)}.pager a,.pager .on{border-color:var(--line);border-radius:8px;background:#14151c;color:var(--muted)}.pager a:hover,.pager .on{border-color:rgba(91,107,255,.65);background:rgba(91,107,255,.13);color:#ccd1ff}
.plan-card{min-height:0;padding:24px;border-color:var(--line);border-radius:16px;background:#14151c;box-shadow:none}.plan-card:before{display:none}.plan-card:hover{transform:none;border-color:var(--line-strong)}.plan-card h2{font-size:22px}.plan-badge{border:0;background:rgba(91,107,255,.13);color:#b8c0ff}.plan-price{font:600 40px/1 "JetBrains Mono",ui-monospace,monospace;color:#f2f4f8;text-shadow:none}.plan-unit{color:var(--muted)}.plan-card ul{color:var(--muted)}.plan-starship{border-color:rgba(91,107,255,.44);box-shadow:0 0 0 1px rgba(91,107,255,.1) inset}.plan-pro{transform:none;border-color:rgba(61,215,229,.45);background:linear-gradient(145deg,#19212a,#14151c);box-shadow:0 0 0 1px rgba(61,215,229,.1) inset}.plan-pro:after{right:18px;top:18px;background:rgba(61,215,229,.14);color:#9af2fa;font-weight:600}.plan-pro .plan-price{background:none;color:#f2f4f8}.plan-max{border-color:rgba(168,85,247,.5);background:linear-gradient(145deg,#241b35,#14151c);box-shadow:0 0 0 1px rgba(168,85,247,.12) inset}.plan-max .plan-badge{background:rgba(168,85,247,.14);color:#e9d5ff}.plan-max .plan-price{color:#f3e8ff}.payment-panel{background:#14151c}.payment-panel:before{display:none}.payment-rule{border-color:rgba(245,213,71,.3);border-radius:10px;background:rgba(245,213,71,.065);color:#e9d98b}.payment-rule strong{color:#f5d547}.chain-pill{border-radius:999px;border-color:var(--line-strong);background:#1e2029}.chain-pill.good{border-color:rgba(43,224,140,.3);background:rgba(43,224,140,.1);color:#8cf0bc}.chain-pill.gold{border-color:rgba(245,213,71,.3);background:rgba(245,213,71,.09);color:#f7df7d}.order-box{border-color:var(--line);border-radius:12px;background:#1e2029}
.announcement-modal{background:rgba(5,6,9,.78);backdrop-filter:blur(8px)}.announcement-dialog{border-color:var(--line-strong);border-radius:16px;background:#1e2029;box-shadow:0 24px 60px rgba(0,0,0,.55)}.announcement-dialog:before{display:none}.announcement-kicker{border:0;background:rgba(91,107,255,.14);color:#bcc3ff}.notice-status{background:rgba(91,107,255,.13);color:#bec5ff}.inbox-item{border-radius:12px;background:#14151c}.inbox-item.unread{border-color:rgba(91,107,255,.55);box-shadow:inset 3px 0 0 var(--brand)}
.brandmark,.loginbrand img,.hero-logo{display:block;object-fit:contain;object-position:center;background:#1e2029;border:1px solid var(--line-strong);box-shadow:inset 0 0 0 1px rgba(255,255,255,.025),0 5px 16px rgba(0,0,0,.26)}.brandmark{padding:5px;border-radius:10px;clip-path:none}.login{background:linear-gradient(120deg,rgba(10,11,15,.88),rgba(10,11,15,.7)),url('/assets/crypto-background.jpg') center/cover fixed}.loginbox{border-color:var(--line);border-radius:16px;background:rgba(20,21,28,.94);box-shadow:0 24px 60px rgba(0,0,0,.55)}.loginbrand img{padding:8px;border-radius:14px}.hero-logo{padding:18px;border-radius:18px;clip-path:none;filter:none}.loginbox .muted,.loginbox .contact{color:var(--muted)}.loginbox button{background:var(--brand)}.loginbox .contact a,.authlinks a,.contact a{color:#b8c0ff}
@media(max-width:850px){.layout{display:block}.side{padding:14px;border-right:0;border-bottom:1px solid var(--line)}.brandhead{margin-bottom:12px}.main{padding:20px}.top{align-items:flex-start;gap:14px}.top>div:last-child{display:flex;align-items:center;flex-wrap:wrap;justify-content:flex-end}.hero{min-height:142px}.system-status{position:static;margin-top:10px}.console-heading{display:block}.compact-market .market-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.plan-pro{transform:none}}@media(max-width:560px){.compact-market .market-grid{grid-template-columns:1fr}.card,.market-terminal{padding:16px!important}.hero h2{font-size:23px}}
.brandmark[src^="/assets/site-logo"],.loginbrand img[src^="/assets/site-logo"],.hero-logo[src^="/assets/site-logo"]{object-fit:cover;padding:0;background:transparent}.brandmark[src^="/assets/site-logo"]{width:42px;height:42px;border-radius:10px}.loginbrand img[src^="/assets/site-logo"]{width:76px;height:76px;border-radius:14px}.hero-logo[src^="/assets/site-logo"]{width:128px;height:128px;border-radius:18px}
@media(max-width:850px){.brandmark[src^="/assets/site-logo"]{width:42px;height:42px}.loginbrand img[src^="/assets/site-logo"]{width:64px;height:64px}.hero-logo[src^="/assets/site-logo"]{width:92px;height:92px}}
"""


class App(BaseHTTPRequestHandler):
    server_version = "YuanShiJinShouZhiLocal/1.0"

    def log_message(self, fmt, *args):
        pass

    def send_html(self, content, status=200, headers=None):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self'; form-action 'self'; frame-ancestors 'none'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_asset(self, path):
        asset_path, content_type = ASSETS[path]
        if path == "/assets/site-logo" and not os.path.exists(asset_path):
            asset_path, content_type = ASSETS["/assets/ck-logo.jpg"]
        try:
            with open(asset_path, "rb") as asset:
                data = asset.read()
        except OSError:
            return self.send_html("Not Found", 404)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable" if path == "/assets/site-logo" else "public, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_exchange_icon(self, path):
        filename = path.rsplit("/", 1)[-1]
        if not re.fullmatch(r"[0-9a-f]{32}\.png", filename):
            return self.send_html("Not Found", 404)
        candidates = [
            os.path.join(CMC_ICON_DIR, filename),
            os.path.join(BRAND_DIR, "exchanges", filename),
        ]
        data = None
        for candidate in candidates:
            try:
                with open(candidate, "rb") as icon:
                    data = icon.read()
                break
            except OSError:
                continue
        if data is None:
            return self.send_html("Not Found", 404)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=604800")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, cookie=None):
        self.send_response(303)
        self.send_header("Location", location)
        if cookie:
            if isinstance(cookie, (list, tuple)):
                for item in cookie:
                    self.send_header("Set-Cookie", item)
            else:
                self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def form(self):
        content_type = self.headers.get("Content-Type", "")
        max_length = EXCHANGE_ICON_UPLOAD_MAX_BYTES + 128 * 1024 if content_type.startswith("multipart/form-data") else 1024 * 1024
        try:
            length = min(int(self.headers.get("Content-Length", "0")), max_length)
        except ValueError:
            length = 0
        if content_type.startswith("multipart/form-data"):
            if not length:
                return {}
            environ = {"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type, "CONTENT_LENGTH": str(length)}
            parsed = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=environ, keep_blank_values=True)
            values = {}
            fields = parsed.list or []
            for field in fields:
                if field.filename:
                    values[field.name] = {"filename": field.filename, "data": field.file.read(EXCHANGE_ICON_UPLOAD_MAX_BYTES + 1)}
                else:
                    values[field.name] = field.value
            return values
        parsed = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        return {key: values if key == "recipient_ids" else values[-1] for key, values in parsed.items()}

    def session(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        token = jar.get("ys_jsz_session")
        if not token:
            return None
        session = SESSIONS.get(token.value)
        if not session or session["expires"] < time.time():
            SESSIONS.pop(token.value, None)
            return None
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE id=? AND status='ACTIVE' AND deleted_at IS NULL", (session["user_id"],)).fetchone()
        if not user:
            return None
        return {"token": token.value, "csrf": session["csrf"], "user": user}

    def require_user(self, admin=False):
        session = self.session()
        if not session:
            self.redirect("/login")
            return None
        if admin and session["user"]["role"] != "ADMIN":
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要管理员权限</h2></div>'), 403)
            return None
        return session

    def valid_csrf(self, session, form):
        return session and hmac.compare_digest(session["csrf"], form.get("csrf", ""))

    def page(self, session, title, content, active=""):
        user = session["user"]
        brand = site_brand_config()
        with db() as conn:
            unread_announcements = unread_site_announcement_count(conn, user["id"])
        nav = [("/", "IP风险检测", "home"), ("/wallet", "钱包检测专区", "wallet"), ("/markets", "市场监控中心", "markets"), ("/membership", "权限中心", "membership"), ("/history", "查询历史", "history"), ("/inbox", "站内信", "inbox")]
        if user["is_owner"]:
            nav += [("/analytics", "会员数据", "analytics"), ("/users", "用户管理", "users"), ("/exchanges", "交易所管理", "exchanges"), ("/logs", "操作日志", "logs"), ("/settings", "系统设置", "settings")]
        links = "".join('<a class="%s" href="%s">%s</a>' % ("on" if active == key else "", url, label) for url, label, key in nav)
        business = "".join(
            '<div class="business-item"><span class="business-icon">%s</span><span>%s</span></div>' % (esc(icon), esc(label))
            for icon, label in BUSINESS_ITEMS
        )
        # 保留内部业务目录兼容旧测试与后续配置，但不再在网站侧栏展示。
        business_section = ''
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s · %s</title><style>%s</style></head>
        <body><div class="layout"><aside class="side"><div class="brandhead"><img class="brandmark" src="%s" alt="%s Logo"><div class="logo">%s<small>%s</small></div></div><nav class="nav">%s</nav>%s</aside>
        <main class="main"><div class="top"><div><h1>%s</h1><div class="muted">%s · Web3 用户增长 / 安全风控 / 女巫检测 / 钱包画像</div></div><div><a class="notice-bell" href="/inbox" aria-label="站内信%s">&#128276;%s</a>%s · %s　<form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="%s"><button class="secondary">退出</button></form></div></div>%s<div class="contact">产品由 %s 提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a></div></main></div><script src="/assets/exchange-picker.js?v=20260808-2" defer></script><script src="/assets/market-ticker.js?v=20260801-5" defer></script></body></html>""" % (
            esc(title), esc(brand["name"]), STYLE, esc(brand["logo"]), esc(brand["name"]), esc(brand["name"]), esc(brand["tagline"]), links, business_section, esc(title), esc(brand["tagline"]), "，%s 条未读" % unread_announcements if unread_announcements else "", '<span class="notice-bell-count">%s</span>' % ("99+" if unread_announcements > 99 else unread_announcements) if unread_announcements else "", esc(user["username"]), user_display_label(user), session["csrf"], content, esc(brand["name"])
        )

    def login_page(self, error=""):
        brand = site_brand_config()
        flash = '<div class="flash err">%s</div>' % esc(error) if error else ""
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>登录 · %s</title><style>%s</style></head>
        <body><div class="login"><div class="loginbox"><div class="loginbrand"><img src="%s" alt="%s Logo"><div><h1>%s</h1><p class="muted">%s</p></div></div>%s<form method="post" action="/login"><label>用户名 / 邮箱</label><div style="display:grid;grid-template-columns:1fr 145px;gap:8px"><input name="username" autocomplete="username" placeholder="用户名或邮箱账号" required><select name="email_domain"><option value="">用户名登录</option>%s</select></div><label>密码</label><input name="password" type="password" autocomplete="current-password" required><button>登录</button></form><div class="authlinks"><a href="/register">注册普通用户</a><a href="/recover">忘记密码</a></div><div class="contact">产品由 %s 提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a></div></div></div></body></html>""" % (esc(brand["name"]), STYLE, esc(brand["logo"]), esc(brand["name"]), esc(brand["name"]), esc(brand["tagline"]), flash, email_suffix_options(""), esc(brand["name"]))

    def register_page(self, error="", recovery=""):
        brand = site_brand_config()
        flash = '<div class="flash err">%s</div>' % esc(error) if error else ""
        result = ('<div class="flash">注册成功，请妥善保存下面的恢复码。</div><div class="recovery"><strong>密码恢复码：</strong><br>%s</div><p class="hint">恢复码只显示这一次。请复制保存，不要发给其他人。</p><a class="btn" href="/login">返回登录</a>' % esc(recovery)) if recovery else """%s<form method="post" action="/register" id="register-form"><label>用户名</label><input name="username" minlength="3" maxlength="40" pattern="[A-Za-z0-9_.-]+" autocomplete="username" required><p class="hint">仅支持字母、数字、点、下划线和短横线。</p><label>邮箱</label><div style="display:grid;grid-template-columns:1fr 145px;gap:8px"><input name="email_local" maxlength="180" placeholder="邮箱账号" autocomplete="email" required><select name="email_domain" required>%s</select></div><p class="hint">必须使用指定主流邮箱：Gmail、QQ邮箱、Outlook、163、iCloud、Yahoo、Proton、阿里云邮箱、Zoho Mail。</p><label>邮箱验证码</label><div style="display:grid;grid-template-columns:1fr 120px;gap:8px"><input name="email_code" maxlength="6" pattern="[0-9]{6}" placeholder="6 位验证码" required><button type="button" class="secondary" id="send-code">发送验证码</button></div><p class="hint" id="code-tip">验证码会发送到上方邮箱，10 分钟内有效。</p><label>密码</label><input name="password" type="password" minlength="10" maxlength="128" autocomplete="new-password" required><label>确认密码</label><input name="confirm_password" type="password" minlength="10" maxlength="128" autocomplete="new-password" required><label style="display:flex;gap:8px;align-items:flex-start"><input name="accepted_statement" type="checkbox" value="1" required style="width:auto;margin-top:4px"><span>我已阅读并同意 <a href="/statement" target="_blank">《原石金手指 · 用户注册声明》</a></span></label><button>注册普通用户</button></form><script>
        document.getElementById('send-code')?.addEventListener('click', async function(){
          const form = document.getElementById('register-form');
          const tip = document.getElementById('code-tip');
          const email = (form.email_local.value || '').split('@')[0].trim() + form.email_domain.value;
          try {
            const res = await fetch('/register/send-code', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email})});
            const data = await res.json();
            tip.textContent = data.message || data.error || '验证码已处理';
            tip.style.color = res.ok ? '#86efac' : '#fecaca';
          } catch(e) { tip.textContent = '发送失败，请检查邮箱配置或联系管理员'; tip.style.color = '#fecaca'; }
        });
        </script><div class="authlinks"><a href="/login">返回登录</a><a href="/recover">忘记密码</a></div>""" % (flash, email_suffix_options("@gmail.com"))
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>注册 · %s</title><style>%s</style></head><body><div class="login"><div class="loginbox"><div class="loginbrand"><img src="%s" alt="%s Logo"><div><h1>创建账号</h1><p class="muted">注册后即可进入系统，开通会员后使用查重服务</p></div></div>%s<div class="contact">产品由 %s 提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a></div></div></div></body></html>""" % (esc(brand["name"]), STYLE, esc(brand["logo"]), esc(brand["name"]), result, esc(brand["name"]))

    def recover_page(self, error="", recovery=""):
        brand = site_brand_config()
        flash = '<div class="flash err">%s</div>' % esc(error) if error else ""
        result = ('<div class="flash">密码已重置。旧恢复码已失效，请保存新的恢复码。</div><div class="recovery"><strong>新密码恢复码：</strong><br>%s</div><a class="btn" href="/login">使用新密码登录</a>' % esc(recovery)) if recovery else """%s<form method="post" action="/recover"><label>用户名</label><input name="username" autocomplete="username" required><label>密码恢复码</label><input name="recovery_code" autocomplete="off" required><label>新密码</label><input name="password" type="password" minlength="10" maxlength="128" autocomplete="new-password" required><label>确认新密码</label><input name="confirm_password" type="password" minlength="10" maxlength="128" autocomplete="new-password" required><button>重置密码</button></form><div class="authlinks"><a href="/login">返回登录</a><a href="/register">注册账号</a></div>""" % flash
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>找回密码 · %s</title><style>%s</style></head><body><div class="login"><div class="loginbox"><div class="loginbrand"><img src="%s" alt="%s Logo"><div><h1>找回密码</h1><p class="muted">使用注册时保存的恢复码</p></div></div>%s<div class="contact">恢复码丢失请联系：产品由 %s 提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a></div></div></div></body></html>""" % (esc(brand["name"]), STYLE, esc(brand["logo"]), esc(brand["name"]), result, esc(brand["name"]))

    def statement_page(self):
        brand = site_brand_config()
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>用户注册声明 · %s</title><style>%s</style></head><body><div class="login"><div class="loginbox"><h1>%s · 用户注册声明</h1><p class="muted">本系统用于 Web3 风控、IP 环境管理、女巫风险识别、钱包画像与行情辅助展示。注册即代表已阅读、已理解并同意本声明。</p><ol style="line-height:1.8;color:#cbd8e8"><li>系统仅保存完成业务所需的数据。</li><li>禁止用于欺诈、洗钱、市场操纵、非法多账号等违法违规用途。</li><li>用户应遵守相关法律法规及交易平台规则。</li><li>行情、趋势和技术指标仅供信息参考，不构成任何投资或交易建议。</li><li>发现共享账号、破解程序、恶意攻击或非法使用时，开发者有权暂停或终止服务。</li></ol><a class="btn" href="/register">返回注册</a></div></div></body></html>""" % (esc(brand["name"]), STYLE, esc(brand["name"]))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, query = parsed.path, urllib.parse.parse_qs(parsed.query)
        if path in ASSETS:
            return self.send_asset(path)
        if path.startswith("/assets/exchanges/"):
            return self.send_exchange_icon(path)
        if path == "/login":
            if self.session():
                return self.redirect("/")
            return self.send_html(self.login_page())
        if path == "/register":
            if self.session():
                return self.redirect("/")
            return self.send_html(self.register_page())
        if path == "/recover":
            if self.session():
                return self.redirect("/")
            return self.send_html(self.recover_page())
        if path == "/statement":
            return self.send_html(self.statement_page())
        if path == "/health":
            return self.send_html("OK")
        if path == "/":
            return self.home(query)
        if path == "/wallet":
            return self.wallet(query)
        if path == "/history":
            return self.history(query)
        if path == "/inbox":
            return self.inbox(query)
        if path == "/markets":
            return self.markets(query)
        if path == "/membership":
            return self.membership(query)
        if path == "/market/tickers":
            return self.market_tickers()
        if path == "/market/candles":
            return self.market_candles(query)
        if path == "/history/export":
            return self.export_csv(query)
        if path == "/users":
            return self.users(query)
        if path == "/analytics":
            return self.analytics(query)
        if path == "/logs":
            return self.logs(query)
        if path == "/settings":
            return self.settings(query)
        if path == "/exchanges":
            return self.exchanges(query)
        self.send_html("Not Found", 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/login":
            return self.login()
        if path == "/register":
            return self.register()
        if path == "/register/send-code":
            return self.send_register_code()
        if path == "/recover":
            return self.recover()
        if path == "/logout":
            return self.logout()
        if path == "/query":
            return self.query_ip()
        if path == "/wallet-check":
            return self.wallet_check()
        if path == "/membership/create-order":
            return self.create_membership_order()
        if path == "/membership/verify":
            return self.verify_membership_order()
        if path == "/history/delete":
            return self.delete_record()
        if path == "/users/create":
            return self.create_user()
        if path == "/users/toggle":
            return self.toggle_user()
        if path == "/users/delete":
            return self.delete_user()
        if path == "/users/quota":
            return self.adjust_user_quota()
        if path == "/settings/cmc-key":
            return self.save_cmc_key()
        if path == "/settings/web3-risk":
            return self.save_web3_risk()
        if path == "/settings/ip-risk":
            return self.save_ip_risk()
        if path == "/settings/payment-receiver":
            return self.save_payment_receiver()
        if path == "/settings/branding":
            return self.save_branding()
        if path == "/settings/cmc-sync":
            return self.sync_cmc()
        if path == "/settings/smtp":
            return self.save_smtp()
        if path == "/settings/smtp-test":
            return self.send_smtp_test()
        if path == "/settings/announcement":
            return self.send_announcement()
        if path == "/announcements/create":
            return self.create_site_announcement()
        if path == "/announcements/archive":
            return self.archive_site_announcement()
        if path == "/announcements/receipt":
            return self.site_announcement_receipt()
        if path == "/announcements/delete":
            return self.delete_site_announcement_for_user()
        if path == "/exchanges/create":
            return self.create_exchange()
        if path == "/exchanges/update":
            return self.update_exchange()
        if path == "/exchanges/toggle":
            return self.toggle_exchange()
        if path == "/exchanges/move":
            return self.move_exchange()
        self.send_html("Not Found", 404)

    def login(self):
        form = self.form()
        key = "login:" + self.client_address[0]
        attempts = RATE_LIMITS.setdefault(key, [])
        cutoff = time.time() - 60
        attempts[:] = [x for x in attempts if x > cutoff]
        if len(attempts) >= 5:
            return self.send_html(self.login_page("尝试次数过多，请一分钟后再试。"), 429)
        attempts.append(time.time())
        identifier = form.get("username", "").strip()
        email_domain = form.get("email_domain", "").strip()
        if email_domain:
            identifier = (identifier.split("@", 1)[0].strip() + email_domain).lower()
        with db() as conn:
            if "@" in identifier:
                user = conn.execute("SELECT * FROM users WHERE (username=? OR lower(email)=?) AND deleted_at IS NULL", (identifier, identifier.lower())).fetchone()
            else:
                user = conn.execute("SELECT * FROM users WHERE username=? AND deleted_at IS NULL", (identifier,)).fetchone()
            if not user or user["status"] != "ACTIVE" or not verify_password(form.get("password", ""), user["password_hash"]):
                return self.send_html(self.login_page("用户名或密码错误。"), 401)
            ts = now()
            conn.execute("UPDATE users SET last_login_at=?,updated_at=? WHERE id=?", (ts, ts, user["id"]))
            log_action(conn, user["id"], "LOGIN", "SESSION", detail="本地登录")
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        existing_device = jar.get("ys_device")
        device_token = existing_device.value if existing_device else secrets.token_urlsafe(24)
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = {"user_id": user["id"], "csrf": secrets.token_urlsafe(24), "expires": time.time() + 43200}
        RATE_LIMITS.pop(key, None)
        self.redirect("/", [
            "ys_jsz_session=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200" % token,
            "ys_device=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=31536000" % device_token,
        ])

    def send_register_code(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")).decode("utf-8") or "{}")
        except Exception:
            body = {}
        email = (body.get("email") or "").strip().lower()
        if not allowed_email(email):
            return self.send_json({"error": "请使用指定主流邮箱。"}, 400)
        key = "email-code:%s:%s" % (self.client_address[0], email)
        attempts = RATE_LIMITS.setdefault(key, [])
        cutoff = time.time() - 600
        attempts[:] = [x for x in attempts if x > cutoff]
        if len(attempts) >= 3:
            return self.send_json({"error": "验证码发送过于频繁，请稍后再试。"}, 429)
        attempts.append(time.time())
        code = "%06d" % secrets.randbelow(1000000)
        expires_at = datetime.fromtimestamp(time.time() + 600).strftime("%Y-%m-%d %H:%M:%S")
        try:
            send_verification_email(email, code)
            with db() as conn:
                conn.execute(
                    "INSERT INTO email_verification_codes(email,code_hash,purpose,expires_at,created_at) VALUES(?,?,?,?,?)",
                    (email, hash_password(code), "REGISTER", expires_at, now()),
                )
            return self.send_json({"message": "验证码已发送，请查看邮箱。"})
        except Exception as error:
            return self.send_json({"error": str(error)}, 500)

    def register(self):
        form = self.form()
        key = "register:" + self.client_address[0]
        attempts = RATE_LIMITS.setdefault(key, [])
        cutoff = time.time() - 3600
        attempts[:] = [x for x in attempts if x > cutoff]
        if len(attempts) >= 5:
            return self.send_html(self.register_page("注册过于频繁，请一小时后再试。"), 429)
        attempts.append(time.time())
        username = form.get("username", "").strip()
        email = (form.get("email", "").strip() or (form.get("email_local", "").strip().split("@", 1)[0] + form.get("email_domain", "").strip())).lower()
        password = form.get("password", "")
        if not USERNAME_RE.fullmatch(username):
            return self.send_html(self.register_page("用户名格式不正确。"), 400)
        if not allowed_email(email):
            return self.send_html(self.register_page("请使用指定主流邮箱注册，例如 Gmail、QQ邮箱、Outlook、163、iCloud、Yahoo、Proton、阿里云邮箱或 Zoho Mail。"), 400)
        if len(password) < 10 or len(password) > 128:
            return self.send_html(self.register_page("密码必须为 10–128 位。"), 400)
        if password != form.get("confirm_password", ""):
            return self.send_html(self.register_page("两次输入的密码不一致。"), 400)
        if form.get("accepted_statement") != "1":
            return self.send_html(self.register_page("请先阅读并同意用户注册声明。"), 400)
        email_code = form.get("email_code", "").strip()
        if not re.fullmatch(r"\d{6}", email_code):
            return self.send_html(self.register_page("请输入 6 位邮箱验证码。"), 400)
        recovery_code = secrets.token_urlsafe(18)
        try:
            with db() as conn:
                code_row = conn.execute(
                    "SELECT * FROM email_verification_codes WHERE email=? AND purpose='REGISTER' AND used_at IS NULL AND expires_at>=? ORDER BY created_at DESC LIMIT 1",
                    (email, now()),
                ).fetchone()
                if not code_row or not verify_password(email_code, code_row["code_hash"]):
                    return self.send_html(self.register_page("邮箱验证码错误或已过期。"), 400)
                ts = now()
                cur = conn.execute(
                    "INSERT INTO users(username,email,password_hash,recovery_hash,role,status,email_verified_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (username, email, hash_password(password), hash_password(recovery_code), "USER", "ACTIVE", ts, ts, ts),
                )
                conn.execute("UPDATE email_verification_codes SET used_at=? WHERE id=?", (ts, code_row["id"]))
                log_action(conn, cur.lastrowid, "REGISTER_USER", "USER", cur.lastrowid, username, self.client_address[0])
        except sqlite3.IntegrityError:
            return self.send_html(self.register_page("该用户名或邮箱已被使用。"), 409)
        return self.send_html(self.register_page(recovery=recovery_code), 201)

    def recover(self):
        form = self.form()
        key = "recover:" + self.client_address[0]
        attempts = RATE_LIMITS.setdefault(key, [])
        cutoff = time.time() - 900
        attempts[:] = [x for x in attempts if x > cutoff]
        if len(attempts) >= 5:
            return self.send_html(self.recover_page("尝试次数过多，请 15 分钟后再试。"), 429)
        attempts.append(time.time())
        username = form.get("username", "").strip()
        password = form.get("password", "")
        if len(password) < 10 or len(password) > 128:
            return self.send_html(self.recover_page("新密码必须为 10–128 位。"), 400)
        if password != form.get("confirm_password", ""):
            return self.send_html(self.recover_page("两次输入的新密码不一致。"), 400)
        with db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username=? AND status='ACTIVE' AND deleted_at IS NULL",
                (username,),
            ).fetchone()
            recovery_code = form.get("recovery_code", "")
            if not user or not user["recovery_hash"] or not verify_password(recovery_code, user["recovery_hash"]):
                return self.send_html(self.recover_page("用户名或恢复码错误。"), 401)
            new_recovery_code = secrets.token_urlsafe(18)
            conn.execute(
                "UPDATE users SET password_hash=?,recovery_hash=?,updated_at=? WHERE id=?",
                (hash_password(password), hash_password(new_recovery_code), now(), user["id"]),
            )
            log_action(conn, user["id"], "RECOVER_PASSWORD", "USER", user["id"], "用户使用恢复码重置密码", self.client_address[0])
        for token, session in list(SESSIONS.items()):
            if session["user_id"] == user["id"]:
                SESSIONS.pop(token, None)
        RATE_LIMITS.pop(key, None)
        return self.send_html(self.recover_page(recovery=new_recovery_code))

    def logout(self):
        session = self.session()
        form = self.form()
        if session and self.valid_csrf(session, form):
            SESSIONS.pop(session["token"], None)
        self.redirect("/login", "ys_jsz_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")

    def home(self, query):
        session = self.require_user()
        if not session:
            return
        message = query.get("message", [""])[0]
        flash = '<div class="flash">%s</div>' % esc(message) if message else ""
        with db() as conn:
            total_checks = conn.execute("SELECT COUNT(*) FROM ip_records").fetchone()[0] + conn.execute("SELECT COUNT(*) FROM wallet_checks").fetchone()[0]
            wallet_total = conn.execute("SELECT COUNT(*) FROM wallet_checks").fetchone()[0]
            high_risk = conn.execute("SELECT COUNT(*) FROM wallet_checks WHERE risk_score >= 70").fetchone()[0]
            today = now()[:10]
            new_today = conn.execute("SELECT COUNT(*) FROM ip_records WHERE created_at >= ?", (today,)).fetchone()[0] + conn.execute("SELECT COUNT(*) FROM wallet_checks WHERE created_at >= ?", (today,)).fetchone()[0]
            if session["user"]["is_owner"]:
                recent = conn.execute("""SELECT r.*,u.username,u.email FROM ip_records r JOIN users u ON u.id=r.user_id ORDER BY r.last_seen_at DESC LIMIT 10""").fetchall()
            else:
                recent = conn.execute("""SELECT r.*,u.username,u.email FROM ip_records r JOIN users u ON u.id=r.user_id WHERE r.user_id=? ORDER BY r.last_seen_at DESC LIMIT 10""", (session["user"]["id"],)).fetchall()
            popup_announcement = active_popup_announcement(conn, session["user"]["id"])
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(display_ip_for_viewer(r["full_ip"], session["user"])), exchange_display(r["exchange"]), status_badge(r["last_similarity"]), user_identity(r, session["user"]), r["query_count"], esc(r["last_seen_at"])
        ) for r in recent) or '<tr><td colspan="6" class="muted">暂无查询记录</td></tr>'
        content = flash + """<div class="console-heading"><div><div class="console-crumb">风险控制台 / IP 环境</div><div class="hero"><div><span class="hero-kicker">GOLD FINGER · WEB3 RISK TERMINAL</span><h2>IP 风险检测核心工作台</h2><p>从网络环境、交易所关联到女巫风险，快速建立可追溯的检测记录。</p></div></div></div><div class="system-status"><i></i> 系统在线</div></div>
        <div class="home-market-strip" aria-label="实时行情"><div id="btc-card" class="home-market-card"><div><div class="market-symbol">BTC / USDT</div><div id="btc-meta" class="muted">行情加载中...</div></div><div><strong id="btc-price" class="market-price">$--</strong><span id="btc-change" class="market-change">--</span></div></div><div id="eth-card" class="home-market-card"><div><div class="market-symbol">ETH / USDT</div><div id="eth-meta" class="muted">行情加载中...</div></div><div><strong id="eth-price" class="market-price">$--</strong><span id="eth-change" class="market-change">--</span></div></div><div id="market-source" class="home-market-source" style="display:block">数据源：实时行情连接中...</div></div>
        <div class="card core-query-card"><h2>开始 IP 风险检测</h2><form method="post" action="/query" id="risk-query-form"><input type="hidden" name="csrf" value="%s"><div class="grid">
        <div class="col8"><label>IPv4 地址</label><input name="ip" placeholder="例如：192.168.1.10" required></div><div class="col4"><label>交易所</label>%s</div>
        <div class="col12 query-action-row"><button id="risk-submit" class="scan-cta">启动扫描并自动入库</button><div class="scan-progress"><span></span></div></div></div></form></div>
        <div class="grid trust-grid"><div class="trust-card"><span>总检测次数</span><strong>%s</strong></div><div class="trust-card"><span>分析钱包</span><strong>%s</strong></div><div class="trust-card"><span>风险地址</span><strong>%s</strong></div><div class="trust-card"><span>覆盖交易所</span><strong>10 CEX / 7 DEX</strong></div></div>
        <div class="risk-dashboard"><div class="risk-panel"><h3>AI 市场雷达</h3><div class="risk-row"><span>BTC</span><b>震荡</b></div><div class="risk-row"><span>ETH</span><b>弱势</b></div><div class="risk-row"><span>SOL</span><b>强势</b></div><div class="risk-row"><span>山寨风险</span><b class="risk-score risk-medium">中等</b></div></div>
        <div class="risk-panel"><h3>风险监控中心</h3><div class="risk-row"><span>总检测</span><b>%s</b></div><div class="risk-row"><span>今日新增风险</span><b>%s</b></div><div class="risk-row"><span>高风险</span><b class="risk-score risk-high">%s</b></div><div class="risk-row"><span>安全指数</span><b class="risk-score risk-low">暂无实时基线</b></div><p class="muted">大额转账、交易所异动、项目方异动、黑名单与女巫集群需接入风控规则库后统计。</p></div>
        <div class="risk-panel"><h3>IP 女巫检测</h3><div class="risk-row"><span>授权 IP 记录</span><b>%s</b></div><div class="risk-row"><span>关联设备指纹</span><b>未采集</b></div><div class="risk-row"><span>代理 / VPN / Tor</span><b>待接入 IP 数据源</b></div><p class="muted">仅分析平台内部已授权的登录、设备与风控日志；链上钱包不能直接获取真实 IP。</p></div>
        <div class="risk-panel"><h3>钱包检测专区</h3><div class="risk-row"><span>主要活跃链</span><b>按实时查询返回</b></div><div class="risk-row"><span>资产 / 持仓变化</span><b>待接入价格源</b></div><div class="risk-row"><span>女巫 / 工作室判断</span><b class="risk-score">待规则库</b></div><p class="muted">钱包地址、交互地址、DEX/CEX、NFT、空投和合约频率请在钱包检测专区查询。</p><a class="btn secondary" href="/wallet">进入钱包检测专区</a></div></div>
        <div class="card"><h2>最近检测记录</h2><p class="muted">查询用户信息默认脱敏。仅总管理员可查看完整身份、完整钱包和完整日志；完整 CSV 导出也仅限总管理员。</p><div class="tablewrap"><table><thead><tr><th>IP</th><th>交易所</th><th>相似度</th><th>查询用户</th><th>次数</th><th>最近查询</th></tr></thead><tbody>%s</tbody></table></div></div>
        <script>document.addEventListener("DOMContentLoaded",function(){var f=document.getElementById("risk-query-form"),b=document.getElementById("risk-submit");if(f&&b)f.addEventListener("submit",function(){f.classList.add("scanning");b.textContent="正在分析网络环境...";});});</script>""" % (
            session["csrf"], exchange_picker(), total_checks, wallet_total, high_risk,
            total_checks, new_today, high_risk, total_checks, rows
        )
        if popup_announcement:
            content += """<div class="announcement-modal" id="site-announcement-modal" data-announcement-id="%s">
            <section class="announcement-dialog" role="dialog" aria-modal="true" aria-labelledby="site-announcement-title">
            <span class="announcement-kicker">SYSTEM BROADCAST</span><h2 id="site-announcement-title">%s</h2><div class="announcement-body">%s</div>
            <div class="announcement-actions"><button type="button" class="secondary" data-announcement-action="mute">不再提示</button><button type="button" data-announcement-action="acknowledge">我知道了</button></div></section></div>
            <script>document.addEventListener("DOMContentLoaded",function(){var modal=document.getElementById("site-announcement-modal");if(!modal)return;var id=modal.getAttribute("data-announcement-id"),key="ys-announcement-seen-"+id;if(sessionStorage.getItem(key)){modal.remove();return;}modal.querySelectorAll("[data-announcement-action]").forEach(function(button){button.addEventListener("click",function(){var action=button.getAttribute("data-announcement-action");button.disabled=true;fetch("/announcements/receipt",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams({csrf:%s,id:id,action:action})}).catch(function(){}).finally(function(){sessionStorage.setItem(key,"1");modal.remove();});});});});</script>""" % (
                popup_announcement["id"], esc(popup_announcement["title"]), esc(popup_announcement["body"]), json.dumps(session["csrf"])
            )
        self.send_html(self.page(session, "IP风险检测", content, "home"))

    def inbox(self, query):
        session = self.require_user()
        if not session:
            return
        message = query.get("message", [""])[0]
        flash = '<div class="flash">%s</div>' % esc(message) if message else ""
        with db() as conn:
            announcements = conn.execute(
                """SELECT a.*,r.seen_at,r.muted_at FROM site_announcements a
                   LEFT JOIN site_announcement_receipts r ON r.announcement_id=a.id AND r.user_id=?
                   WHERE a.status='PUBLISHED' AND a.published_at<=?
                     AND r.deleted_at IS NULL
                   ORDER BY a.published_at DESC,a.id DESC LIMIT 100""",
                (session["user"]["id"], now()),
            ).fetchall()
            opened_ids = set()
            for announcement in announcements:
                if not announcement["seen_at"]:
                    save_announcement_receipt(conn, announcement["id"], session["user"]["id"], "acknowledge")
                    opened_ids.add(announcement["id"])
        rows = "".join(
            '<article class="inbox-item %s"><div class="inbox-meta"><div><span class="notice-status %s">%s</span><h2 class="inbox-title">%s</h2></div><span class="muted">%s</span></div><div class="inbox-body">%s</div><div class="inbox-actions">%s</div></article>' % (
                "unread" if not item["seen_at"] and item["id"] not in opened_ids else "", "" if not item["seen_at"] and item["id"] not in opened_ids else "read", "未读" if not item["seen_at"] and item["id"] not in opened_ids else "已读",
                esc(item["title"]), esc(item["published_at"]), esc(item["body"]),
                '<form method="post" action="/announcements/delete" onsubmit="return confirm(\'删除后仅会从您的站内信隐藏，确认删除？\');"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="id" value="%s"><button type="submit" class="secondary">删除已读信件</button></form>' % (session["csrf"], item["id"]),
            ) for item in announcements
        ) or '<div class="card"><h2>暂无站内公告</h2><p class="muted">系统发布的新公告会在这里保留，重要公告也会在首页提示。</p></div>'
        content = flash + '<div class="hero"><div><span class="hero-kicker">SYSTEM MESSAGE CENTER</span><h2>站内信</h2><p>这里保留系统发布的公告。已选择“不再提示”的公告仍可在此回看。</p></div></div>' + rows
        self.send_html(self.page(session, "站内信", content, "inbox"))

    def wallet(self, query):
        session = self.require_user()
        if not session:
            return
        message = query.get("message", [""])[0]
        flash = '<div class="flash">%s</div>' % esc(message) if message else ""
        with db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM wallet_checks").fetchone()[0]
            high_risk = conn.execute("SELECT COUNT(*) FROM wallet_checks WHERE risk_score >= 70").fetchone()[0]
            recent = conn.execute("SELECT check_type,address,risk_score,created_at FROM wallet_checks WHERE user_id=? ORDER BY id DESC LIMIT 8", (session["user"]["id"],)).fetchall()
        rows = "".join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            esc(CHECK_TYPES.get(row["check_type"], CHECK_TYPES["wallet"])["label"]),
            esc(row["address"] if viewer_can_export_full(session["user"]) else mask_wallet_address(row["address"])),
            esc(str(row["risk_score"]) if row["risk_score"] is not None else "待接入"),
            esc(row["created_at"]),
        ) for row in recent) or '<tr><td colspan="4" class="muted">暂无钱包检测记录</td></tr>'
        options = "".join('<option value="%s">%s</option>' % (esc(key), esc(item["label"])) for key, item in CHECK_TYPES.items() if item["kind"] != "ip")
        content = flash + """<div class="hero"><div><span class="hero-kicker">GOLD FINGER · WALLET INTELLIGENCE</span><h2>钱包检测专区</h2><p>统一分析多链钱包、交互地址与公开链上风险数据；平台内部授权数据不会与链上公开数据混淆展示。</p></div></div>
        <div class="card address-check-card"><h2>钱包 / 交互地址检测</h2><p class="muted">支持通用钱包、钱包交互地址、EVM、Solana、TRON、BTC 和其他链地址。未配置真实数据源时会明确返回配置状态，不生成模拟检测结果。</p><form method="post" action="/wallet-check" id="address-check-form"><input type="hidden" name="csrf" value="%s"><div class="grid">
        <div class="col2"><label>检测类型</label><select name="check_type" id="check-type">%s</select></div>
        <div class="col8"><label id="address-label">钱包地址</label><input name="address" id="check-address" placeholder="请输入钱包地址" spellcheck="false" autocomplete="off" required></div>
        <div class="col2 query-action-row"><button id="address-submit">开始检测</button></div></div></form></div>
        <div class="grid trust-grid"><div class="trust-card"><span>钱包检测次数</span><strong>%s</strong></div><div class="trust-card"><span>高风险地址</span><strong>%s</strong></div><div class="trust-card"><span>支持地址类型</span><strong>7</strong></div><div class="trust-card"><span>数据模式</span><strong>实时 / 配置化</strong></div></div>
        <div class="card"><h2>最近钱包检测记录</h2><p class="muted">地址按权限脱敏显示。完整用户身份和完整查询日志仅总管理员可查看。</p><div class="tablewrap"><table><thead><tr><th>检测类型</th><th>钱包地址</th><th>风险评分</th><th>检测时间</th></tr></thead><tbody>%s</tbody></table></div></div>
        <script>document.addEventListener("DOMContentLoaded",function(){var f=document.getElementById("address-check-form"),t=document.getElementById("check-type"),a=document.getElementById("check-address"),l=document.getElementById("address-label"),b=document.getElementById("address-submit"),types=%s;function sync(){var x=types[t.value];a.placeholder=x.placeholder;l.textContent=x.label;}sync();t.addEventListener("change",sync);f.addEventListener("submit",function(){b.textContent="查询中...";b.disabled=true;});});</script>""" % (
            session["csrf"], options, total, high_risk, rows, json.dumps(CHECK_TYPES, ensure_ascii=False)
        )
        self.send_html(self.page(session, "钱包检测专区", content, "wallet"))

    def market_tickers(self):
        if not self.session():
            return self.send_json({"error": "未登录"}, 401)
        pairs = [
            ("BTC-USDT", "BTC", "BTC-USDT", "BTCUSDT"),
            ("ETH-USDT", "ETH", "ETH-USDT", "ETHUSDT"),
            ("SOL-USDT", "SOL", "SOL-USDT", "SOLUSDT"),
            ("BNB-USDT", "BNB", "BNB-USDT", "BNBUSDT"),
            ("OKB-USDT", "OKB", "OKB-USDT", None),
        ]

        def number(value):
            try:
                if value in (None, ""):
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        def now_iso():
            return datetime.utcnow().isoformat()

        items = []
        sources = []
        try:
            headers = {"User-Agent": "Yuanshi-Jinshouzhi/1.0"}
            request = urllib.request.Request("https://api.binance.com/api/v3/ticker/24hr", headers=headers)
            with urllib.request.urlopen(request, timeout=8) as response:
                spot_rows = json.loads(response.read().decode("utf-8"))

            for symbol, base, _okx_spot, binance_symbol in pairs:
                if not binance_symbol:
                    continue
                row = next((entry for entry in spot_rows if entry.get("symbol") == binance_symbol), None)
                price = number((row or {}).get("lastPrice"))
                if not row or price is None:
                    continue
                close_time = int(row.get("closeTime", 0) or 0)
                items.append({
                    "symbol": symbol,
                    "base": base,
                    "venue": "Binance",
                    "marketType": "SPOT",
                    "price": price,
                    "indexPrice": price,
                    "change24h": number(row.get("priceChangePercent")),
                    "high24h": number(row.get("highPrice")),
                    "low24h": number(row.get("lowPrice")),
                    "volume24h": number(row.get("quoteVolume")),
                    "updatedAt": datetime.fromtimestamp(close_time / 1000).isoformat() if close_time else now_iso(),
                })
            if items:
                sources.append("Binance")
        except Exception:
            pass

        missing = {symbol for symbol, *_rest in pairs} - {item["symbol"] for item in items}
        if missing:
            try:
                headers = {"User-Agent": "Yuanshi-Jinshouzhi/1.0"}
                request = urllib.request.Request("https://www.okx.com/api/v5/market/tickers?instType=SPOT", headers=headers)
                with urllib.request.urlopen(request, timeout=8) as response:
                    spot_rows = json.loads(response.read().decode("utf-8")).get("data", [])
                for symbol, base, okx_spot, _binance_symbol in pairs:
                    if symbol not in missing:
                        continue
                    row = next((entry for entry in spot_rows if entry.get("instId") == okx_spot), None)
                    price = number((row or {}).get("last"))
                    if not row or price is None:
                        continue
                    open_24h = number(row.get("open24h")) or number(row.get("sodUtc0"))
                    ts = int(row.get("ts", "0") or "0")
                    items.append({
                        "symbol": symbol,
                        "base": base,
                        "venue": "OKX",
                        "marketType": "SPOT",
                        "price": price,
                        "indexPrice": price,
                        "change24h": ((price - open_24h) / open_24h * 100) if open_24h else None,
                        "high24h": number(row.get("high24h")),
                        "low24h": number(row.get("low24h")),
                        "volume24h": number(row.get("volCcy24h")) or number(row.get("vol24h")),
                        "updatedAt": datetime.fromtimestamp(ts / 1000).isoformat() if ts else now_iso(),
                    })
                if any(item["venue"] == "OKX" for item in items):
                    sources.append("OKX")
            except Exception:
                pass

        missing = {symbol for symbol, *_rest in pairs} - {item["symbol"] for item in items}
        if missing:
            try:
                headers = {"User-Agent": "Yuanshi-Jinshouzhi/1.0"}
                request = urllib.request.Request("https://api.bybit.com/v5/market/tickers?category=spot", headers=headers)
                with urllib.request.urlopen(request, timeout=8) as response:
                    spot_rows = json.loads(response.read().decode("utf-8")).get("result", {}).get("list", [])
                bybit_symbols = {
                    "BTC-USDT": "BTCUSDT",
                    "ETH-USDT": "ETHUSDT",
                    "SOL-USDT": "SOLUSDT",
                    "BNB-USDT": "BNBUSDT",
                    "OKB-USDT": "OKBUSDT",
                }
                for symbol, base, *_rest in pairs:
                    if symbol not in missing:
                        continue
                    row = next((entry for entry in spot_rows if entry.get("symbol") == bybit_symbols.get(symbol)), None)
                    price = number((row or {}).get("lastPrice"))
                    if not row or price is None:
                        continue
                    change = number(row.get("price24hPcnt"))
                    ts = int(row.get("timestamp", "0") or "0")
                    items.append({
                        "symbol": symbol,
                        "base": base,
                        "venue": "Bybit",
                        "marketType": "SPOT",
                        "price": price,
                        "indexPrice": price,
                        "change24h": change * 100 if change is not None else None,
                        "high24h": number(row.get("highPrice24h")),
                        "low24h": number(row.get("lowPrice24h")),
                        "volume24h": number(row.get("turnover24h")),
                        "updatedAt": datetime.fromtimestamp(ts / 1000).isoformat() if ts else now_iso(),
                    })
                if any(item["venue"] == "Bybit" for item in items):
                    sources.append("Bybit")
            except Exception:
                pass

        missing = {symbol for symbol, *_rest in pairs} - {item["symbol"] for item in items}
        if missing and os.path.exists(CMC_KEY_FILE):
            try:
                with open(CMC_KEY_FILE, "r", encoding="utf-8") as f:
                    api_key = f.read().strip()
                request = urllib.request.Request(
                    "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol=BTC,ETH,SOL,BNB,OKB&convert=USD",
                    headers={"X-CMC_PRO_API_KEY": api_key, "User-Agent": "Yuanshi-Jinshouzhi/1.0"},
                )
                with urllib.request.urlopen(request, timeout=8) as response:
                    cmc_payload = json.loads(response.read().decode("utf-8")).get("data", {})
                for symbol, base, _okx_spot, _binance_symbol in pairs:
                    if symbol not in missing:
                        continue
                    quote = ((cmc_payload.get(base) or {}).get("quote") or {}).get("USD") or {}
                    price = number(quote.get("price"))
                    if price is None:
                        continue
                    items.append({
                        "symbol": symbol,
                        "base": base,
                        "venue": "CMC",
                        "marketType": "QUOTE",
                        "price": price,
                        "indexPrice": price,
                        "change24h": number(quote.get("percent_change_24h")),
                        "high24h": None,
                        "low24h": None,
                        "volume24h": number(quote.get("volume_24h")),
                        "updatedAt": quote.get("last_updated") or now_iso(),
                    })
                if any(item["venue"] == "CMC" for item in items):
                    sources.append("CMC")
            except Exception:
                pass

        order = {symbol: index for index, (symbol, *_rest) in enumerate(pairs)}
        items.sort(key=lambda item: order.get(item["symbol"], 999))
        if items:
            return self.send_json({
                "source": " + ".join(dict.fromkeys(sources)) or "实时行情",
                "generatedAt": now_iso(),
                "items": items,
            })

        try:
            request = urllib.request.Request("https://fapi.binance.com/fapi/v1/premiumIndex", headers={"User-Agent": "Yuanshi-Jinshouzhi/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))

            def fallback_item(symbol, base, _okx_spot, api_symbol):
                if not api_symbol:
                    return None
                row = next((item for item in payload if item.get("symbol") == api_symbol), None)
                price = number((row or {}).get("markPrice"))
                if not row or price is None:
                    return None
                ts = int(row.get("time", 0) or 0)
                return {
                    "symbol": symbol,
                    "base": base,
                    "venue": "Binance",
                    "marketType": "SWAP",
                    "price": price,
                    "indexPrice": number(row.get("indexPrice")),
                    "change24h": None,
                    "high24h": None,
                    "low24h": None,
                    "volume24h": None,
                    "updatedAt": datetime.fromtimestamp(ts / 1000).isoformat() if ts else now_iso(),
                }

            fallback_items = [item for item in (fallback_item(*pair) for pair in pairs) if item]
            if fallback_items:
                return self.send_json({"source": "Binance", "generatedAt": now_iso(), "items": fallback_items})
        except Exception:
            pass
        return self.send_json({"error": "实时行情暂时无法连接"}, 503)

    def market_candles(self, query):
        if not self.session():
            return self.send_json({"error": "未登录"}, 401)
        symbol = query.get("symbol", ["BTC-USDT"])[0]
        interval = query.get("interval", ["1H"])[0]
        pairs = {
            "BTC-USDT": {"binance": "BTCUSDT", "okx": "BTC-USDT"},
            "ETH-USDT": {"binance": "ETHUSDT", "okx": "ETH-USDT"},
            "SOL-USDT": {"binance": "SOLUSDT", "okx": "SOL-USDT"},
            "BNB-USDT": {"binance": "BNBUSDT", "okx": "BNB-USDT"},
            "OKB-USDT": {"binance": None, "okx": "OKB-USDT"},
        }
        okx_bars = {"5m": "5m", "15m": "15m", "1H": "1H", "4H": "4H"}
        binance_bars = {"5m": "5m", "15m": "15m", "1H": "1h", "4H": "4h"}
        if symbol not in pairs or interval not in okx_bars:
            return self.send_json({"error": "参数错误"}, 400)

        def number(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def normalize(items):
            items.sort(key=lambda item: item["time"])
            return items[-160:]

        headers = {"User-Agent": "Yuanshi-Jinshouzhi/1.0"}
        if pairs[symbol]["binance"]:
            try:
                url = "https://api.binance.com/api/v3/klines?symbol=%s&interval=%s&limit=160" % (
                    urllib.parse.quote(pairs[symbol]["binance"]),
                    urllib.parse.quote(binance_bars[interval]),
                )
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=8) as response:
                    rows = json.loads(response.read().decode("utf-8"))
                candles = []
                for row in rows:
                    candles.append({
                        "time": int(row[0]),
                        "open": number(row[1]),
                        "high": number(row[2]),
                        "low": number(row[3]),
                        "close": number(row[4]),
                        "volume": number(row[5]),
                    })
                candles = [item for item in candles if None not in (item["open"], item["high"], item["low"], item["close"])]
                if candles:
                    return self.send_json({"symbol": symbol, "interval": interval, "source": "Binance", "items": normalize(candles)})
            except Exception:
                pass

        try:
            url = "https://www.okx.com/api/v5/market/candles?instId=%s&bar=%s&limit=160" % (
                urllib.parse.quote(pairs[symbol]["okx"]),
                urllib.parse.quote(okx_bars[interval]),
            )
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=8) as response:
                rows = json.loads(response.read().decode("utf-8")).get("data", [])
            candles = []
            for row in rows:
                candles.append({
                    "time": int(row[0]),
                    "open": number(row[1]),
                    "high": number(row[2]),
                    "low": number(row[3]),
                    "close": number(row[4]),
                    "volume": number(row[5]),
                })
            candles = [item for item in candles if None not in (item["open"], item["high"], item["low"], item["close"])]
            if candles:
                return self.send_json({"symbol": symbol, "interval": interval, "source": "OKX", "items": normalize(candles)})
        except Exception:
            pass

        bybit_intervals = {"5m": "5", "15m": "15", "1H": "60", "4H": "240"}
        try:
            url = "https://api.bybit.com/v5/market/kline?category=spot&symbol=%s&interval=%s&limit=160" % (
                urllib.parse.quote(pairs[symbol]["binance"] or pairs[symbol]["okx"].replace("-", "")),
                urllib.parse.quote(bybit_intervals[interval]),
            )
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=8) as response:
                rows = json.loads(response.read().decode("utf-8")).get("result", {}).get("list", [])
            candles = []
            for row in rows:
                candles.append({
                    "time": int(row[0]) * 1000,
                    "open": number(row[1]),
                    "high": number(row[2]),
                    "low": number(row[3]),
                    "close": number(row[4]),
                    "volume": number(row[5]),
                })
            candles = [item for item in candles if None not in (item["open"], item["high"], item["low"], item["close"])]
            if candles:
                return self.send_json({"symbol": symbol, "interval": interval, "source": "Bybit", "items": normalize(candles)})
        except Exception:
            pass
        return self.send_json({"error": "K线行情暂时无法连接"}, 503)

    def query_ip(self):
        session = self.require_user()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html(self.page(session, "请求失败", '<div class="flash err">请求已失效，请刷新页面重试。</div>'), 403)
        allowed, reason = can_query_local(session["user"], "ip")
        if not allowed:
            content = """<div class="card"><h2>当前账号尚未开通权限</h2><p class="muted">%s</p><div class="actions"><a class="btn" href="/membership#payment">立即开通</a><a class="btn secondary" href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">联系客服</a></div></div>""" % esc(reason)
            return self.send_html(self.page(session, "需要权限", content, "membership"), 403)
        if not session["user"]["is_owner"]:
            jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
            device_cookie = jar.get("ys_device")
            device_token = device_cookie.value if device_cookie else ""
            if not device_token:
                return self.send_html(self.page(session, "设备校验失败", '<div class="card"><h2>设备校验失败</h2><p class="muted">请重新登录后再试。</p></div>'), 403)
            with db() as conn:
                user = conn.execute("SELECT * FROM users WHERE id=?", (session["user"]["id"],)).fetchone()
                bound = user["bound_device_token"] if user and "bound_device_token" in user.keys() else None
                if bound and not hmac.compare_digest(bound, device_token):
                    return self.send_html(self.page(session, "设备已绑定", '<div class="card"><h2>账号已绑定其它设备</h2><p class="muted">请联系客服处理设备解绑或重新绑定。</p></div>'), 403)
                if not bound:
                    conn.execute("UPDATE users SET bound_device_token=?,updated_at=? WHERE id=?", (device_token, now(), session["user"]["id"]))
        raw_ip = form.get("ip", form.get("address", "")).strip()
        exchange = form.get("exchange", "其他")
        try:
            parsed = ipaddress.ip_address(raw_ip)
            if str(parsed) != raw_ip:
                raise ValueError()
        except ValueError:
            return self.redirect("/?message=" + urllib.parse.quote("请输入合法的 IPv4 / IPv6 地址。"))
        if exchange not in active_exchanges():
            return self.redirect("/?message=" + urllib.parse.quote("请选择有效的交易所。"))
        is_ipv4 = parsed.version == 4
        seg = [int(x) for x in raw_ip.split(".")] if is_ipv4 else [0, 0, 0, 0]
        ip_risk = ip_risk_snapshot(raw_ip)
        with db() as conn:
            history = conn.execute("""SELECT r.*,u.username,u.email FROM ip_records r JOIN users u ON u.id=r.user_id""").fetchall()
            compared = []
            if is_ipv4:
                for row in history:
                    if ":" in row["full_ip"]:
                        continue
                    score, matches = similarity(seg, row)
                    compared.append((score, row["last_seen_at"], row, matches))
            compared.sort(key=lambda x: (x[0], x[1]), reverse=True)
            top = compared[:20]
            exact = [item for item in compared if item[0] == 100]
            highest = top[0][0] if top else 0
            ts = now()
            if not consume_query_quota(conn, session["user"], "ip", ts):
                return self.send_html(self.page(session, "额度已用完", '<div class="card"><h2>IP 查询额度已使用完</h2><p class="muted">请升级或续费后继续查询。</p><a class="btn" href="/membership#payment">查看套餐</a></div>', "membership"), 403)
            existing = conn.execute("SELECT id FROM ip_records WHERE full_ip=? AND exchange=?", (raw_ip, exchange)).fetchone()
            if existing:
                conn.execute("""UPDATE ip_records SET query_count=query_count+1,last_seen_at=?,last_similarity=?,country=?,region=?,city=?,isp=?,asn=?,ip_type=?,purity_score=?,is_proxy=?,is_vpn=?,is_tor=?,is_datacenter=?,ip_source=?,ip_checked_at=?,updated_at=? WHERE id=?""", (ts, highest, ip_risk["country"], ip_risk["region"], ip_risk["city"], ip_risk["isp"], ip_risk["asn"], ip_risk["ip_type"], ip_risk["purity_score"], ip_risk["is_proxy"], ip_risk["is_vpn"], ip_risk["is_tor"], ip_risk["is_datacenter"], ip_risk["source"], ip_risk["checked_at"], ts, existing["id"]))
                record_id = existing["id"]
            else:
                cur = conn.execute("""INSERT INTO ip_records(full_ip,segment_a,segment_b,segment_c,segment_d,exchange,user_id,query_count,last_similarity,first_seen_at,last_seen_at,created_at,updated_at,country,region,city,isp,asn,ip_type,purity_score,is_proxy,is_vpn,is_tor,is_datacenter,ip_source,ip_checked_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (raw_ip, *seg, exchange, session["user"]["id"], 1, highest, ts, ts, ts, ts, ip_risk["country"], ip_risk["region"], ip_risk["city"], ip_risk["isp"], ip_risk["asn"], ip_risk["ip_type"], ip_risk["purity_score"], ip_risk["is_proxy"], ip_risk["is_vpn"], ip_risk["is_tor"], ip_risk["is_datacenter"], ip_risk["source"], ip_risk["checked_at"]))
                record_id = cur.lastrowid
            log_action(conn, session["user"]["id"], "QUERY_IP", "IP_RECORD", record_id, json.dumps({"ip": raw_ip, "exchange": exchange, "similarity": highest, "ip_source": ip_risk["source"]}, ensure_ascii=False))
        best_matches = top[0][3] if top else [False] * 4
        segments_html = "".join('<span class="seg %s">%s = %s · %s</span>' % (
            "yes" if best_matches[i] else "no", "ABCD"[i], seg[i], "匹配" if best_matches[i] else "不匹配"
        ) for i in range(4)) if is_ipv4 else '<span class="seg">IPv6 当前支持格式校验与精确记录；分段相似分析仅适用于 IPv4。</span>'
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(display_ip_for_viewer(item[2]["full_ip"], session["user"])), status_badge(item[0]), exchange_display(item[2]["exchange"]),
            user_identity(item[2], session["user"]), esc(item[2]["first_seen_at"]), esc(item[2]["last_seen_at"])
        ) for item in top) or '<tr><td colspan="6" class="muted">这是第一条记录，未发现历史相似 IP。</td></tr>'
        exact_text = "是，共找到 %d 条完整 IP 记录" % len(exact) if exact else "否"
        content = """<div class="card"><div class="grid"><div class="col3"><div class="muted">当前查询 IP</div><div class="stat">%s</div></div><div class="col3"><div class="muted">交易所</div><div style="margin-top:10px">%s</div></div><div class="col3"><div class="muted">最高相似度</div><div class="stat">%s%%</div></div><div class="col3"><div class="muted">精确重复</div><div style="margin-top:10px">%s</div></div><div class="col12"><div class="segments">%s</div></div></div></div>
        <div class="card"><h2>最相似历史记录（最多 20 条）</h2><div class="tablewrap"><table><thead><tr><th>历史 IP</th><th>相似度</th><th>交易所</th><th>录入用户</th><th>首次录入</th><th>最近查询</th></tr></thead><tbody>%s</tbody></table></div></div>
        <div class="card"><h2>IP 归属地与纯净度</h2><div class="grid ip-intel-grid"><div class="col3"><div class="muted">国家 / 地区 / 城市</div><div class="ip-intel-value">%s / %s / %s</div></div><div class="col3"><div class="muted">ISP / ASN</div><div class="ip-intel-value">%s / %s</div></div><div class="col3"><div class="muted">IP 类型</div><div class="ip-intel-value">%s</div></div><div class="col3"><div class="muted">IP 纯净度</div><div class="ip-intel-value ip-intel-score">%s</div></div><div class="col12"><div class="segments"><span class="seg">代理：%s</span><span class="seg">VPN：%s</span><span class="seg">Tor：%s</span><span class="seg">数据中心：%s</span><span class="seg">来源：%s</span><span class="seg">检测时间：%s</span></div><p class="muted">%s</p></div></div></div>
        <div class="card"><h2>IP 女巫关联数据</h2><p class="muted">平台内部授权日志可用于后续关联设备指纹、浏览器指纹、关联账号、钱包和邮箱。链上公开数据不能反向取得钱包真实 IP；缺失字段不会以推测结果展示。</p></div><a class="btn secondary" href="/">返回继续查询</a>""" % (esc(display_ip_for_viewer(raw_ip, session["user"])), exchange_display(exchange), highest, esc(exact_text), segments_html, rows, esc(ip_risk["country"] or "待检测"), esc(ip_risk["region"] or "-"), esc(ip_risk["city"] or "-"), esc(ip_risk["isp"] or "待检测"), esc(ip_risk["asn"] or "-"), esc(ip_risk["ip_type"]), esc(str(ip_risk["purity_score"]) + "/100" if ip_risk["purity_score"] is not None else ("数据源未提供评分" if ip_risk["source"] not in ("未接入 IP 风控数据源", "数据源异常") else "待检测")), "是" if ip_risk["is_proxy"] else ("否" if ip_risk["is_proxy"] is not None else "待检测"), "是" if ip_risk["is_vpn"] else ("否" if ip_risk["is_vpn"] is not None else "待检测"), "是" if ip_risk["is_tor"] else ("否" if ip_risk["is_tor"] is not None else "待检测"), "是" if ip_risk["is_datacenter"] else ("否" if ip_risk["is_datacenter"] is not None else "待检测"), esc(ip_risk["source"]), esc(ip_risk["checked_at"]), esc(ip_risk["message"]))
        self.send_html(self.page(session, "查询结果", content, "home"))

    def wallet_check(self):
        session = self.require_user()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html(self.page(session, "请求失败", '<div class="flash err">请求已失效，请刷新页面重试。</div>'), 403)
        allowed, reason = can_query_local(session["user"], "wallet")
        if not allowed:
            content = """<div class="card"><h2>当前账号尚未开通权限</h2><p class="muted">%s</p><div class="actions"><a class="btn" href="/membership#payment">立即开通</a><a class="btn secondary" href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">联系客服</a></div></div>""" % esc(reason)
            return self.send_html(self.page(session, "需要权限", content, "membership"), 403)
        address = form.get("address", "").strip()
        check_type = form.get("check_type", "wallet")
        if check_type not in CHECK_TYPES or CHECK_TYPES[check_type]["kind"] == "ip":
            check_type = "wallet"
        valid, chain = check_address(address, check_type)
        if not valid:
            return self.redirect("/wallet?message=" + urllib.parse.quote(CHECK_TYPES[check_type]["placeholder"]))
        snapshot = live_wallet_snapshot(address, chain)
        ts = now()
        with db() as conn:
            if not consume_query_quota(conn, session["user"], "wallet", ts):
                return self.send_html(self.page(session, "额度已用完", '<div class="card"><h2>钱包查询额度已使用完</h2><p class="muted">请升级或续费后继续查询。</p><a class="btn" href="/membership#payment">查看套餐</a></div>', "membership"), 403)
            cur = conn.execute(
                "INSERT INTO wallet_checks(address,check_type,user_id,risk_score,result,created_at) VALUES(?,?,?,?,?,?)",
                (address, check_type, session["user"]["id"], int(snapshot["riskScore"] or 0), json.dumps(snapshot, ensure_ascii=False), ts),
            )
            log_action(conn, session["user"]["id"], "WALLET_CHECK", "WALLET", cur.lastrowid, json.dumps({"address": address, "type": check_type, "source": snapshot["source"], "status": snapshot["status"]}, ensure_ascii=False))
        assets = "".join('<tr><td>%s %s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (icon_markup(CHAIN_ICON_MAP, item.get("icon", "")), esc(item["symbol"]), esc(item["balance"]), esc(item.get("price") if item.get("price") is not None else "待接入"), esc(item.get("share") if item.get("share") is not None else "待计算")) for item in snapshot["assets"]) or '<tr><td colspan="4" class="muted">暂无可验证资产数据</td></tr>'
        missing = "、".join(snapshot["missingFields"])
        content = """<div class="card"><h2>%s</h2><div class="grid"><div class="col6"><div class="muted">钱包地址 / 所属链</div><div class="stat" style="font-size:22px;word-break:break-all">%s<br><small>%s %s</small></div></div><div class="col2"><div class="muted">地址类型</div><div class="stat">%s</div></div><div class="col2"><div class="muted">风险评分</div><div class="stat">%s</div></div><div class="col2"><div class="muted">风险等级</div><div class="stat">%s</div></div><div class="col12"><div class="segments"><span class="seg">数据来源：%s</span><span class="seg">更新时间：%s</span><span class="seg">耗时：%sms</span><span class="seg">可信度：%s</span><span class="seg">%s</span></div></div></div></div>
        <div class="card"><h2>资产与钱包画像</h2><p class="muted">总资产估值：%s；持仓价格、资产占比、交易次数、CEX/DEX/NFT/空投/合约活跃度、钱包年龄、批量注册、工作室与女巫判断，均仅在真实数据源可用时显示。</p><div class="tablewrap"><table><thead><tr><th>币种</th><th>余额</th><th>实时价格</th><th>资产占比</th></tr></thead><tbody>%s</tbody></table></div></div>
        <div class="card"><h2>钱包交互地址分析</h2><p class="muted">交互地址、链、类型、CEX/DEX、风险、项目方、次数、金额、首次/最近交互及风险标签需要链上索引或授权标签库。当前状态：%s</p><p class="muted">交互列表支持风险/链/CEX-DEX 筛选、次数/金额排序、分页与 CSV 导出；在数据源未接入前不生成虚构列表。缺失字段：%s。</p></div><a class="btn secondary" href="/wallet">返回继续检测</a>""" % (
            esc(CHECK_TYPES[check_type]["label"] + "结果"), esc(address), icon_markup(CHAIN_ICON_MAP, chain), esc((CHAIN_ICON_MAP.get(chain) or FALLBACK_ICON)["name"]), esc(snapshot["addressType"]), esc(snapshot["riskScore"] if snapshot["riskScore"] is not None else "待接入"), esc(snapshot["riskLevel"]), esc(snapshot["source"]), esc(snapshot["updatedAt"]), snapshot["durationMs"], esc(snapshot["confidence"]), "实时数据" if snapshot["isRealtime"] else "非实时 / 未配置", esc(snapshot["totalValue"] if snapshot["totalValue"] is not None else "待接入"), assets, esc(snapshot["message"]), esc(missing)
        )
        self.send_html(self.page(session, "地址检测结果", content, "wallet"))

    def create_membership_order(self):
        session = self.require_user()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html(self.page(session, "请求失败", '<div class="flash err">请求已失效，请刷新页面重试。</div>'), 403)
        plan = form.get("plan", "").strip().upper()
        try:
            months = int(form.get("months", "1"))
        except ValueError:
            months = 0
        token = form.get("token", "USDT").strip().upper()
        if plan not in PLAN_CONFIG or months not in MEMBERSHIP_PERIODS or token not in TOKEN_CONTRACTS:
            return self.redirect("/membership?message=" + urllib.parse.quote("请选择有效套餐和付款币种。"))
        ts = now()
        order_no = "YS" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + secrets.token_hex(3).upper()
        config = PLAN_CONFIG[plan]
        with db() as conn:
            conn.execute(
                "INSERT INTO membership_orders(order_no,user_id,plan,months,token,amount,receiver,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (order_no, session["user"]["id"], plan, months, token, membership_price(plan, months), current_payment_receiver(), "PENDING", ts, ts),
            )
            log_action(conn, session["user"]["id"], "CREATE_ORDER", "MEMBERSHIP_ORDER", order_no, json.dumps({"plan": plan, "months": months, "token": token, "amount": membership_price(plan, months)}, ensure_ascii=False))
        self.redirect("/membership?order=" + urllib.parse.quote(order_no) + "#payment")

    def verify_membership_order(self):
        session = self.require_user()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html(self.page(session, "请求失败", '<div class="flash err">请求已失效，请刷新页面重试。</div>'), 403)
        order_no = form.get("order_no", "").strip()
        tx_hash = form.get("tx_hash", "").strip()
        ts = now()
        with db() as conn:
            order = conn.execute("SELECT * FROM membership_orders WHERE order_no=? AND user_id=?", (order_no, session["user"]["id"])).fetchone()
            if not order:
                return self.redirect("/membership?message=" + urllib.parse.quote("订单不存在，请重新选择套餐。"))
            if order["status"] == "PAID":
                return self.redirect("/membership?message=" + urllib.parse.quote("该订单已开通成功。"))
            used = conn.execute("SELECT order_no FROM membership_orders WHERE tx_hash=? AND status='PAID'", (tx_hash,)).fetchone()
            if used:
                return self.redirect("/membership?order=%s&message=%s#payment" % (urllib.parse.quote(order_no), urllib.parse.quote("该 Transaction Hash 已被使用。")))
            try:
                ok, detail = verify_bep20_payment(tx_hash, order["token"], order["amount"], order["receiver"])
            except Exception as error:
                ok, detail = False, "自动链上验证暂时失败：%s" % error
            if not ok:
                conn.execute("UPDATE membership_orders SET tx_hash=?,status='REJECTED',verify_detail=?,updated_at=? WHERE id=?", (tx_hash, detail, ts, order["id"]))
                log_action(conn, session["user"]["id"], "VERIFY_ORDER_FAILED", "MEMBERSHIP_ORDER", order_no, detail)
                return self.redirect("/membership?order=%s&message=%s#payment" % (urllib.parse.quote(order_no), urllib.parse.quote(detail)))
            expires_at = activate_membership(conn, session["user"]["id"], order["plan"], order["months"])
            conn.execute("UPDATE membership_orders SET tx_hash=?,status='PAID',verify_detail=?,paid_at=?,updated_at=? WHERE id=?", (tx_hash, detail, ts, ts, order["id"]))
            log_action(conn, session["user"]["id"], "VERIFY_ORDER_PAID", "MEMBERSHIP_ORDER", order_no, detail)
        self.redirect("/membership?success=1")

    def membership(self, query):
        session = self.require_user()
        if not session:
            return
        brand = site_brand_config()
        message = query.get("message", [""])[0]
        if query.get("success", [""])[0] == "1":
            message = "付款验证成功，会员权益已开通并同步到当前账号。"
        order_no = query.get("order", [""])[0]
        flash = '<div class="flash">%s</div>' % esc(message) if message else ""
        order = None
        if order_no:
            with db() as conn:
                order = conn.execute("SELECT * FROM membership_orders WHERE order_no=? AND user_id=?", (order_no, session["user"]["id"])).fetchone()
        with db() as conn:
            current_user = conn.execute("""SELECT role,is_owner,membership_plan,membership_status,membership_expires_at,
                                               ip_query_limit,ip_query_used,device_query_limit,device_query_used,
                                               wallet_query_limit,wallet_query_used
                                        FROM users WHERE id=?""", (session["user"]["id"],)).fetchone()
        current_plan = user_display_label(current_user)
        current_expiry = current_user["membership_expires_at"] or "暂无到期时间"
        plans = [
            ("plan-starship", "STARSHIP", "轻度环境管理", "星舰会员", "12", "USDT / USDC / 月", ["IP 查询：10 次 / 月", "设备查询：10 次 / 月", "钱包查询：5 次 / 月", "支持全部 CEX 与 DEX", "适合个人轻度环境管理"]),
            ("plan-pro", "PRO", "高频环境管理", "旗舰 PRO", "39.9", "USDT / USDC / 月", ["IP 查询：60 次 / 月", "设备查询：60 次 / 月", "钱包查询：60 次 / 月", "市场监控中心", "支持全部 CEX 与 DEX", "适合个人高频环境管理"]),
            ("plan-max", "MAX", "机构级权限", "旗舰 MAX", "128.88", "USDT / USDC / 月", ["全部 CEX 与 DEX", "钱包检测全部功能", "市场监控中心", "无限次数 + 无限历史", "适合高频量化、机构及专业团队"]),
        ]
        plan_html = "".join(
            """<div class="card col4 plan-card %s"><span class="plan-badge">%s</span><h2>%s</h2><div><span class="plan-price">%s</span><span class="plan-unit"> %s</span></div><ul>%s</ul>%s</div>""" % (
                esc(style),
                esc(badge),
                esc(name),
                esc(price if price == "0" else "$" + price),
                esc(unit),
                "".join("<li>%s</li>" % esc(item) for item in features),
                "" if price == "0" else """<form method="post" action="/membership/create-order" class="plan-order-form"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="plan" value="%s"><label>开通周期</label><select name="months"><option value="1">1 个月 · $%s（$%s / 月）</option><option value="3">3 个月 · $%s（$%s / 月）</option><option value="6">6 个月 · $%s（$%s / 月）</option><option value="12">年会员 · $%s（$%s / 月）</option></select><label>付款币种</label><select name="token"><option value="USDT">USDT</option><option value="USDC">USDC</option></select><button style="margin-top:14px">选择套餐并付款</button></form>""" % (
                    esc(session["csrf"]), esc(plan_code),
                    money_display(membership_price(plan_code, 1)), money_display(membership_monthly_equivalent(plan_code, 1)),
                    money_display(membership_price(plan_code, 3)), money_display(membership_monthly_equivalent(plan_code, 3)),
                    money_display(membership_price(plan_code, 6)), money_display(membership_monthly_equivalent(plan_code, 6)),
                    money_display(membership_price(plan_code, 12)), money_display(membership_monthly_equivalent(plan_code, 12)),
                ),
            )
            for style, plan_code, badge, name, price, unit, features in plans
        )
        if order:
            verify_html = """<div class="order-box"><div class="grid"><div class="col3"><label>订单号</label><input readonly value="%s" onclick="this.select()"></div><div class="col3"><label>套餐</label><input readonly value="%s"></div><div class="col3"><label>币种 / 网络</label><input readonly value="%s · BEP20"></div><div class="col3"><label>金额</label><input readonly value="%s"></div></div>
            <form method="post" action="/membership/verify" class="verify-form"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="order_no" value="%s"><label>Transaction Hash</label><input name="tx_hash" placeholder="0x..." required><button>提交并自动检测付款</button></form></div>""" % (
                esc(order["order_no"]), esc("%s · %s" % (PLAN_CONFIG[order["plan"]]["name"], MEMBERSHIP_PERIODS.get(int(order["months"] or 1), MEMBERSHIP_PERIODS[1])["name"])), esc(order["token"]), esc(order["amount"]), esc(session["csrf"]), esc(order["order_no"])
            )
        else:
            verify_html = '<div class="order-box muted">请先在上方选择套餐，系统会生成订单并跳转到这里。</div>'
        quota_display = lambda kind: query_quota_display(current_user, kind)
        content = flash + """<div class="hero member-hero"><div><span class="hero-kicker">%s · ACCESS CONTROL</span><h2>权限中心</h2><p class="hint">当前会员：<strong>%s</strong>　到期时间：<strong>%s</strong></p><p class="hint">剩余查询次数：IP <strong>%s</strong>　设备 <strong>%s</strong>　钱包 <strong>%s</strong></p></div><img class="hero-logo" src="%s" alt="%s Logo"></div>
        <div class="risk-disclaimer">⚠️ 本系统提供 Web3 风控、IP 环境管理和行情辅助信息。所有行情分析、趋势判断、技术指标仅作为信息参考，不构成任何投资建议、交易建议或投资依据。</div>
        <p class="muted">查询按类别分别计入当前开通周期额度；旗舰 MAX 不限次数与历史。设备额度已预留给后续设备风控检测，不会因正常登录或设备绑定而扣减。</p>
        <div class="grid">%s</div>
        <div class="card payment-panel" id="payment"><h2>付款信息</h2><div class="payment-rule"><strong>开通条件：</strong>收款地址必须足额到账订单显示的 USDT / USDC 金额。BEP20 Gas 费由付款方自行额外承担，并由钱包以 BNB 扣除；不能从订单金额中扣除。少转或到账不足，系统无法自动开通会员。</div><div class="grid"><div class="col6"><label>支付币种</label><div class="segments"><span class="chain-pill good">USDT</span><span class="chain-pill good">USDC</span><span class="chain-pill gold">BEP20 / BSC</span></div><p class="hint">请务必使用 BNB Smart Chain（BEP20）。其它网络付款无法自动确认。</p></div>
        <div class="col6 pay-address"><label>收款地址</label><input readonly value="%s" onclick="this.select()"><p class="hint">点击输入框可全选复制。</p></div></div>
        %s
        <p>如付款遇到问题，请联系：产品由 CK原石提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a>。</p>
        <p class="muted">系统会自动核对 Token、网络、金额、收款地址和交易 Hash；验证成功后立即开通对应会员权益。</p></div>""" % (
            esc(brand["name"]), esc(current_plan), esc(current_expiry), esc(quota_display("ip")), esc(quota_display("device")), esc(quota_display("wallet")), esc(brand["logo"]), esc(brand["name"]), plan_html, current_payment_receiver(), verify_html
        )
        self.send_html(self.page(session, "权限中心", content, "membership"))

    def history_filters(self, query):
        clauses, params = [], []
        fields = [("ip", "r.full_ip = ?"), ("a", "r.segment_a = ?"), ("b", "r.segment_b = ?"), ("c", "r.segment_c = ?"), ("d", "r.segment_d = ?"), ("exchange", "r.exchange = ?"), ("user", "u.username = ?"), ("similarity", "r.last_similarity = ?")]
        for key, clause in fields:
            value = query.get(key, [""])[0].strip()
            if value:
                clauses.append(clause)
                params.append(value)
        date_from, date_to = query.get("from", [""])[0], query.get("to", [""])[0]
        if date_from:
            clauses.append("r.last_seen_at >= ?"); params.append(date_from + " 00:00:00")
        if date_to:
            clauses.append("r.last_seen_at <= ?"); params.append(date_to + " 23:59:59")
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), params

    def history(self, query):
        session = self.require_user()
        if not session:
            return
        where, params = self.history_filters(query)
        try:
            page = max(1, int(query.get("page", ["1"])[0]))
        except ValueError:
            page = 1
        if not session["user"]["is_owner"]:
            if where:
                where += " AND r.user_id = ?"
            else:
                where = " WHERE r.user_id = ?"
            params.append(session["user"]["id"])
        with db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM ip_records r JOIN users u ON u.id=r.user_id" + where, params).fetchone()[0]
            records = conn.execute("SELECT r.*,u.username,u.email FROM ip_records r JOIN users u ON u.id=r.user_id" + where + " ORDER BY r.last_seen_at DESC LIMIT 20 OFFSET ?", params + [(page - 1) * 20]).fetchall()
        delete = lambda r: ('<form class="inline" method="post" action="/history/delete"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="id" value="%s"><button class="danger">删除</button></form>' % (session["csrf"], r["id"])) if session["user"]["is_owner"] else ""
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(display_ip_for_viewer(r["full_ip"], session["user"])), exchange_display(r["exchange"]), user_identity(r, session["user"]), status_badge(r["last_similarity"]), r["query_count"], esc(r["last_seen_at"]), delete(r)
        ) for r in records) or '<tr><td colspan="7" class="muted">没有符合条件的记录</td></tr>'
        q = {k: v[-1] for k, v in query.items() if k != "page"}
        pages = max(1, (total + 19) // 20)
        pager_links = []
        if pages > 1:
            for i in range(max(1, page - 2), min(pages, page + 2) + 1):
                if i == page:
                    pager_links.append('<span class="on" aria-current="page">%s</span>' % i)
                else:
                    pager_links.append('<a href="/history?%s">%s</a>' % (urllib.parse.urlencode(dict(q, page=i)), i))
        pager = '<div class="pager">%s</div>' % "".join(pager_links) if pager_links else ""
        val = lambda k: esc(query.get(k, [""])[0])
        content = """<div class="card"><form method="get" action="/history"><div class="grid">
        <div class="col3"><label>完整 IP</label><input name="ip" value="%s"></div><div class="col3"><label>A 段</label><input name="a" value="%s"></div><div class="col3"><label>B 段</label><input name="b" value="%s"></div><div class="col3"><label>C 段</label><input name="c" value="%s"></div>
        <div class="col3"><label>D 段</label><input name="d" value="%s"></div><div class="col3"><label>交易所</label>%s</div><div class="col3"><label>查询用户</label><input name="user" value="%s"></div><div class="col3"><label>相似度</label><select name="similarity"><option value="">全部</option>%s</select></div>
        <div class="col3"><label>开始日期</label><input type="date" name="from" value="%s"></div><div class="col3"><label>结束日期</label><input type="date" name="to" value="%s"></div><div class="col6 actions"><button>筛选</button><a class="btn secondary" href="/history">清空</a>%s</div>
        </div></form></div><div class="card"><h2>共 %s 条记录</h2><div class="tablewrap"><table><thead><tr><th>IP</th><th>交易所</th><th>用户</th><th>相似度</th><th>次数</th><th>最近查询</th><th></th></tr></thead><tbody>%s</tbody></table></div>%s</div>""" % (
            val("ip"), val("a"), val("b"), val("c"), val("d"),
            exchange_picker(query.get("exchange", [""])[0], allow_all=True),
            val("user"), "".join('<option value="%s" %s>%s%%</option>' % (s, "selected" if val("similarity") == str(s) else "", s) for s in [100,75,50,25,0]),
            val("from"), val("to"), '<a class="btn secondary" href="/history/export?%s">导出完整 CSV</a>' % urllib.parse.urlencode(q) if viewer_can_export_full(session["user"]) else '<span class="muted">完整 CSV 导出仅限总管理员</span>', total, rows, pager
        )
        self.send_html(self.page(session, "查询历史", content, "history"))

    def export_csv(self, query):
        session = self.require_user()
        if not session:
            return
        if not viewer_can_export_full(session["user"]):
            return self.send_html(self.page(session, "无权导出", '<div class="card"><h2>无权导出完整隐私数据</h2><p class="muted">完整用户名、邮箱、钱包与 IP 查询日志仅限总管理员导出。</p></div>', "history"), 403)
        where, params = self.history_filters(query)
        with db() as conn:
            records = conn.execute("SELECT r.*,u.username,u.email FROM ip_records r JOIN users u ON u.id=r.user_id" + where + " ORDER BY r.last_seen_at DESC LIMIT 10000", params).fetchall()
            log_action(conn, session["user"]["id"], "EXPORT_CSV", "IP_RECORD", detail="导出 %d 条" % len(records))
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["完整IP","A","B","C","D","交易所","录入用户","邮箱","查询次数","相似度","首次录入","最近查询"])
        for r in records:
            writer.writerow([r["full_ip"],r["segment_a"],r["segment_b"],r["segment_c"],r["segment_d"],exchange_label(r["exchange"]),r["username"],r["email"] or "",r["query_count"],r["last_similarity"],r["first_seen_at"],r["last_seen_at"]])
        data = ("\ufeff" + output.getvalue()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="ip-history.csv"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def markets(self, query):
        session = self.require_user()
        if not session:
            return
        content = """<div class="hero"><div><span class="hero-kicker">MARKET WATCH</span><h2>市场监控中心</h2></div></div>
        <div class="risk-disclaimer">⚠️ 所有行情分析、趋势判断、技术指标仅作为信息参考，不构成任何投资建议、交易建议或投资依据。市场存在不确定性，用户需独立判断并自行承担投资风险。</div>
        <div class="card market-terminal compact-market"><div class="market-head"><div><div class="market-kicker">COIN PRICE WATCH</div><h2>实时价格与趋势</h2></div><button class="secondary" type="button" onclick="loadMarket()">刷新价格</button></div><div class="market-grid">
        <div class="market-tile wait" id="btc-card"><div class="market-symbol">BTC-USDT</div><div id="btc-price" class="market-price">$--</div><div id="btc-change" class="market-change">--</div><svg id="btc-mini" class="market-mini" viewBox="0 0 220 34" preserveAspectRatio="none"><path d="M0 22 L40 18 L80 20 L120 13 L160 17 L220 10"/></svg><div class="market-detail"><span>成交量 <b id="btc-volume">--</b></span><span>RSI <b id="btc-rsi">--</b></span><span>趋势 <b id="btc-trend">--</b></span><span>评分 <b id="btc-score">--</b></span><span>支持 <b id="btc-support">--</b></span><span>压力 <b id="btc-resistance">--</b></span></div><div id="btc-meta" class="market-meta">等待行情</div></div>
        <div class="market-tile wait" id="eth-card"><div class="market-symbol">ETH-USDT</div><div id="eth-price" class="market-price">$--</div><div id="eth-change" class="market-change">--</div><svg id="eth-mini" class="market-mini" viewBox="0 0 220 34" preserveAspectRatio="none"><path d="M0 22 L40 18 L80 20 L120 13 L160 17 L220 10"/></svg><div class="market-detail"><span>成交量 <b id="eth-volume">--</b></span><span>RSI <b id="eth-rsi">--</b></span><span>趋势 <b id="eth-trend">--</b></span><span>评分 <b id="eth-score">--</b></span><span>支持 <b id="eth-support">--</b></span><span>压力 <b id="eth-resistance">--</b></span></div><div id="eth-meta" class="market-meta">等待行情</div></div>
        <div class="market-tile wait" id="sol-card"><div class="market-symbol">SOL-USDT</div><div id="sol-price" class="market-price">$--</div><div id="sol-change" class="market-change">--</div><svg id="sol-mini" class="market-mini" viewBox="0 0 220 34" preserveAspectRatio="none"><path d="M0 22 L40 18 L80 20 L120 13 L160 17 L220 10"/></svg><div class="market-detail"><span>成交量 <b id="sol-volume">--</b></span><span>RSI <b id="sol-rsi">--</b></span><span>趋势 <b id="sol-trend">--</b></span><span>评分 <b id="sol-score">--</b></span><span>支持 <b id="sol-support">--</b></span><span>压力 <b id="sol-resistance">--</b></span></div><div id="sol-meta" class="market-meta">等待行情</div></div>
        <div class="market-tile wait" id="bnb-card"><div class="market-symbol">BNB-USDT</div><div id="bnb-price" class="market-price">$--</div><div id="bnb-change" class="market-change">--</div><svg id="bnb-mini" class="market-mini" viewBox="0 0 220 34" preserveAspectRatio="none"><path d="M0 22 L40 18 L80 20 L120 13 L160 17 L220 10"/></svg><div class="market-detail"><span>成交量 <b id="bnb-volume">--</b></span><span>RSI <b id="bnb-rsi">--</b></span><span>趋势 <b id="bnb-trend">--</b></span><span>评分 <b id="bnb-score">--</b></span><span>支持 <b id="bnb-support">--</b></span><span>压力 <b id="bnb-resistance">--</b></span></div><div id="bnb-meta" class="market-meta">等待行情</div></div>
        <div class="market-tile wait" id="okb-card"><div class="market-symbol">OKB-USDT</div><div id="okb-price" class="market-price">$--</div><div id="okb-change" class="market-change">--</div><svg id="okb-mini" class="market-mini" viewBox="0 0 220 34" preserveAspectRatio="none"><path d="M0 22 L40 18 L80 20 L120 13 L160 17 L220 10"/></svg><div class="market-detail"><span>成交量 <b id="okb-volume">--</b></span><span>RSI <b id="okb-rsi">--</b></span><span>趋势 <b id="okb-trend">--</b></span><span>评分 <b id="okb-score">--</b></span><span>支持 <b id="okb-support">--</b></span><span>压力 <b id="okb-resistance">--</b></span></div><div id="okb-meta" class="market-meta">等待行情</div></div>
        </div><div id="market-source" class="hint" style="display:none"></div></div>
        <div class="risk-disclaimer">⚠️ 行情页所有内容均为辅助观察信息，不承诺准确性、实时性或收益结果；不构成投资、交易、合约开仓或资产配置建议。</div>"""
        self.send_html(self.page(session, "市场监控中心", content, "markets"))

    def delete_record(self):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">授权白名单拥有与星舰会员相同的查询权限，不能删除历史记录。</p></div>'), 403)
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html("Forbidden", 403)
        try:
            record_id = int(form.get("id", "0"))
        except ValueError:
            record_id = 0
        with db() as conn:
            record = conn.execute("SELECT full_ip FROM ip_records WHERE id=?", (record_id,)).fetchone()
            if record:
                conn.execute("DELETE FROM ip_records WHERE id=?", (record_id,))
                log_action(conn, session["user"]["id"], "DELETE_IP", "IP_RECORD", record_id, record["full_ip"])
        self.redirect("/history")

    def users(self, query):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">授权白名单拥有与星舰会员相同的查询权限，不能访问用户管理。</p></div>'), 403)
            return
        recovery = query.get("recovery", [""])[0]
        created_for = query.get("created_for", [""])[0]
        error = query.get("error", [""])[0]
        recovery_notice = ('<div class="flash">账号 <strong>%s</strong> 已创建。请立即把初始恢复码交给本人：<div class="recovery">%s</div>该恢复码离开本页后不再显示。</div>' % (esc(created_for), esc(recovery))) if recovery else ""
        error_notice = '<div class="flash err">%s</div>' % esc(error) if error else ""
        with db() as conn:
            users = conn.execute("SELECT * FROM users WHERE deleted_at IS NULL ORDER BY is_owner DESC,created_at DESC").fetchall()
        def actions(u):
            if u["id"] == session["user"]["id"] or u["is_owner"]:
                return '<span class="muted">受保护</span>'
            if u["role"] == "ADMIN" and not session["user"]["is_owner"]:
                return '<span class="muted">仅总管理员可操作</span>'
            toggle = """<form class="inline" method="post" action="/users/toggle"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="id" value="%s"><button class="secondary">%s</button></form>""" % (session["csrf"], u["id"], "停用" if u["status"] == "ACTIVE" else "启用")
            can_delete = session["user"]["is_owner"] or u["role"] == "USER"
            delete = """ <form class="inline" method="post" action="/users/delete"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="id" value="%s"><button class="danger">删除</button></form>""" % (session["csrf"], u["id"]) if can_delete else ""
            return toggle + delete
        quota_summary = lambda u: "<br>".join("%s：%s" % (QUERY_QUOTA_FIELDS[kind][2], query_quota_display(u, kind)) for kind in QUERY_QUOTA_FIELDS)
        rows = "".join("""<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>""" % (
            esc(u["username"]), "总管理员" if u["is_owner"] else ("授权白名单" if u["role"] == "ADMIN" else "普通用户"), "启用" if u["status"] == "ACTIVE" else "停用", quota_summary(u), esc(u["last_login_at"] or "从未"), actions(u)
        ) for u in users)
        admin_option = '<option value="ADMIN">授权白名单</option>' if session["user"]["is_owner"] else ""
        quota_options = "".join('<option value="%s">%s（IP %s，设备 %s，钱包 %s）</option>' % (
            u["id"], esc(u["username"]), esc(query_quota_display(u, "ip")), esc(query_quota_display(u, "device")), esc(query_quota_display(u, "wallet"))
        ) for u in users if not u["is_owner"])
        quota_card = """<div class="card"><h2>增加查询次数</h2><p class="muted">增加的是当前可用次数，不会清除已使用记录；无限套餐保持不限次数，无需追加。每项可填 0 到 1,000,000 次。</p><form method="post" action="/users/quota"><input type="hidden" name="csrf" value="%s"><div class="grid"><div class="col4"><label>用户</label><select name="id" required><option value="">请选择用户</option>%s</select></div><div class="col2"><label>IP 查询</label><input type="number" name="ip_add" min="0" max="1000000" value="0" required></div><div class="col3"><label>设备查询</label><input type="number" name="device_add" min="0" max="1000000" value="0" required></div><div class="col3"><label>钱包查询</label><input type="number" name="wallet_add" min="0" max="1000000" value="0" required></div><div class="col12"><button>增加查询次数</button></div></div></form></div>""" % (session["csrf"], quota_options)
        content = """%s%s<div class="card"><h2>创建用户</h2><form method="post" action="/users/create"><input type="hidden" name="csrf" value="%s"><div class="grid"><div class="col4"><label>用户名</label><input name="username" minlength="3" maxlength="40" pattern="[A-Za-z0-9_.\\-\u4e00-\u9fff]+" placeholder="支持中文、英文和数字" required></div><div class="col4"><label>初始密码</label><input name="password" type="password" minlength="10" maxlength="128" placeholder="至少 10 位" required></div><div class="col4"><label>角色</label><select name="role"><option value="USER">普通用户</option>%s</select></div><div class="col12"><p class="hint">用户名 3–40 位；密码至少 10 位。创建成功后会显示一次性恢复码。</p><button>创建</button></div></div></form></div>
        %s<div class="card"><h2>用户列表</h2><p class="muted">公开注册只能成为普通用户；授权白名单拥有与星舰会员相同的查询额度和隐私权限；只有总管理员可以管理账号。删除采用安全软删除，历史记录和操作日志仍会保留。</p><div class="tablewrap"><table><thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>剩余查询次数</th><th>最后登录</th><th>操作</th></tr></thead><tbody>%s</tbody></table></div></div>""" % (error_notice, recovery_notice, session["csrf"], admin_option, quota_card, rows)
        self.send_html(self.page(session, "用户管理", content, "users"))

    def create_user(self):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2></div>'), 403)
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html("Forbidden", 403)
        username, password, role = form.get("username", "").strip(), form.get("password", ""), form.get("role", "USER")
        if not USERNAME_RE.fullmatch(username) or len(password) < 10 or len(password) > 128 or role not in ("ADMIN", "USER"):
            return self.redirect("/users?error=" + urllib.parse.quote("用户名需为 3–40 位中文、英文、数字或 . _ -；密码至少 10 位。"))
        if role == "ADMIN" and not session["user"]["is_owner"]:
            return self.redirect("/users?error=" + urllib.parse.quote("只有总管理员可以创建授权白名单。"))
        recovery_code = secrets.token_urlsafe(18)
        try:
            with db() as conn:
                ts = now()
                limits = PLAN_CONFIG["STARSHIP"]["limits"] if role == "ADMIN" else {kind: 0 for kind in QUERY_QUOTA_FIELDS}
                cur = conn.execute(
                    """INSERT INTO users(username,password_hash,recovery_hash,role,is_owner,status,
                                         query_limit,ip_query_limit,device_query_limit,wallet_query_limit,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (username, hash_password(password), hash_password(recovery_code), role, 0, "ACTIVE",
                     limits["ip"], limits["ip"], limits["device"], limits["wallet"], ts, ts),
                )
                log_action(conn, session["user"]["id"], "CREATE_USER", "USER", cur.lastrowid, username)
        except sqlite3.IntegrityError:
            return self.redirect("/users?error=" + urllib.parse.quote("用户名已存在，请换一个。"))
        self.redirect("/users?created_for=%s&recovery=%s" % (urllib.parse.quote(username), urllib.parse.quote(recovery_code)))

    def toggle_user(self):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2></div>'), 403)
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html("Forbidden", 403)
        try:
            user_id = int(form.get("id", "0"))
        except ValueError:
            user_id = 0
        if user_id == session["user"]["id"]:
            return self.redirect("/users")
        with db() as conn:
            target = conn.execute("SELECT status,username,role,is_owner FROM users WHERE id=? AND deleted_at IS NULL", (user_id,)).fetchone()
            if target:
                if target["is_owner"] or (target["role"] == "ADMIN" and not session["user"]["is_owner"]):
                    return self.redirect("/users")
                new_status = "DISABLED" if target["status"] == "ACTIVE" else "ACTIVE"
                conn.execute("UPDATE users SET status=?,updated_at=? WHERE id=?", (new_status, now(), user_id))
                log_action(conn, session["user"]["id"], "UPDATE_USER_STATUS", "USER", user_id, "%s -> %s" % (target["username"], new_status))
        self.redirect("/users")

    def delete_user(self):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2></div>'), 403)
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html("Forbidden", 403)
        try:
            user_id = int(form.get("id", "0"))
        except ValueError:
            user_id = 0
        if user_id == session["user"]["id"]:
            return self.redirect("/users")
        with db() as conn:
            target = conn.execute("SELECT username,role,is_owner FROM users WHERE id=? AND deleted_at IS NULL", (user_id,)).fetchone()
            allowed = target and not target["is_owner"] and (session["user"]["is_owner"] or target["role"] == "USER")
            if allowed:
                ts = now()
                conn.execute("UPDATE users SET status='DISABLED',deleted_at=?,updated_at=? WHERE id=?", (ts, ts, user_id))
                log_action(conn, session["user"]["id"], "DELETE_USER", "USER", user_id, target["username"])
        for token, active_session in list(SESSIONS.items()):
            if active_session["user_id"] == user_id:
                SESSIONS.pop(token, None)
        self.redirect("/users")

    def adjust_user_quota(self):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2></div>'), 403)
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html("Forbidden", 403)
        try:
            user_id = int(form.get("id", "0"))
            additions = {kind: int(form.get("%s_add" % kind, "0")) for kind in QUERY_QUOTA_FIELDS}
        except (TypeError, ValueError):
            return self.redirect("/users?error=" + urllib.parse.quote("增加次数必须是有效的非负整数。"))
        if user_id <= 0 or any(amount < 0 or amount > 1000000 for amount in additions.values()):
            return self.redirect("/users?error=" + urllib.parse.quote("增加次数仅支持 0 到 1,000,000。"))
        if not any(additions.values()):
            return self.redirect("/users?error=" + urllib.parse.quote("请至少填写一项需要增加的查询次数。"))
        with db() as conn:
            target = conn.execute("SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (user_id,)).fetchone()
            if not target or target["is_owner"]:
                return self.redirect("/users?error=" + urllib.parse.quote("目标用户不存在或属于受保护的总管理员账号。"))
            updates, params, effective = [], [], {}
            for kind, amount in additions.items():
                limit_field, _, _ = QUERY_QUOTA_FIELDS[kind]
                if int(target[limit_field] or 0) < 0:
                    effective[kind] = 0
                    continue
                if target["role"] == "ADMIN" and int(target[limit_field] or 0) == 0:
                    baseline = PLAN_CONFIG["STARSHIP"]["limits"][kind]
                    updates.append("%s=?" % limit_field)
                    params.append(baseline + amount)
                else:
                    updates.append("%s=%s+?" % (limit_field, limit_field))
                    params.append(amount)
                effective[kind] = amount
            if updates:
                if effective["ip"]:
                    if target["role"] == "ADMIN" and int(target["ip_query_limit"] or 0) == 0:
                        updates.append("query_limit=?")
                        params.append(PLAN_CONFIG["STARSHIP"]["limits"]["ip"] + effective["ip"])
                    else:
                        updates.append("query_limit=query_limit+?")
                        params.append(effective["ip"])
                updates.append("updated_at=?")
                params.extend([now(), user_id])
                conn.execute("UPDATE users SET %s WHERE id=?" % ",".join(updates), params)
            log_action(conn, session["user"]["id"], "ADJUST_QUERY_QUOTA", "USER", user_id, json.dumps({"username": target["username"], "added": effective, "unlimited": [kind for kind, amount in additions.items() if amount and effective[kind] == 0]}, ensure_ascii=False))
        self.redirect("/users")

    def analytics(self, query):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">会员数据包含收款和经营统计，仅总管理员可查看。</p></div>'), 403)
            return
        today = datetime.now().strftime("%Y-%m-%d")
        day_ago = datetime.fromtimestamp(time.time() - 86400).strftime("%Y-%m-%d %H:%M:%S")
        with db() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL").fetchone()[0]
            active_24h = conn.execute(
                "SELECT COUNT(*) FROM users WHERE deleted_at IS NULL AND last_login_at >= ?",
                (day_ago,),
            ).fetchone()[0]
            today_queries = conn.execute(
                "SELECT COUNT(*) FROM operation_logs WHERE action='QUERY_IP' AND created_at >= ?",
                (today + " 00:00:00",),
            ).fetchone()[0]
            total_queries = conn.execute("SELECT COUNT(*) FROM operation_logs WHERE action='QUERY_IP'").fetchone()[0]
            record_count = conn.execute("SELECT COUNT(*) FROM ip_records").fetchone()[0]
            log_count = conn.execute("SELECT COUNT(*) FROM operation_logs").fetchone()[0]
            admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='ADMIN' AND deleted_at IS NULL").fetchone()[0]
            normal_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='USER' AND deleted_at IS NULL").fetchone()[0]
            payment_summary = conn.execute(
                "SELECT COUNT(*) AS order_count,COALESCE(SUM(amount),0) AS total_amount FROM membership_orders WHERE status='PAID'"
            ).fetchone()
            active_starship = conn.execute(
                """SELECT COUNT(*) FROM users
                   WHERE deleted_at IS NULL AND membership_plan='STARSHIP'
                     AND membership_status='ACTIVE' AND membership_expires_at >= ?""",
                (now(),),
            ).fetchone()[0]
            active_pro = conn.execute(
                """SELECT COUNT(*) FROM users
                   WHERE deleted_at IS NULL AND membership_plan='PRO'
                     AND membership_status='ACTIVE' AND membership_expires_at >= ?""",
                (now(),),
            ).fetchone()[0]
            active_max = conn.execute(
                """SELECT COUNT(*) FROM users
                   WHERE deleted_at IS NULL AND membership_plan='MAX'
                     AND membership_status='ACTIVE' AND membership_expires_at >= ?""",
                (now(),),
            ).fetchone()[0]
            recent = conn.execute(
                """SELECT r.full_ip,r.exchange,r.last_similarity,r.last_seen_at,u.username
                   FROM ip_records r JOIN users u ON u.id=r.user_id
                   ORDER BY r.last_seen_at DESC LIMIT 8"""
            ).fetchall()
        cards = [
            ("累计收款", "$" + money_display(payment_summary["total_amount"]), "已确认 USDT / USDC 订单金额汇总"),
            ("收款笔数", str(payment_summary["order_count"]), "按已确认付款订单统计"),
            ("星舰会员", str(active_starship), "当前有效且未到期的星舰会员"),
            ("旗舰 PRO", str(active_pro), "当前有效且未到期的旗舰 PRO 会员"),
            ("旗舰 MAX", str(active_max), "当前有效且未到期的旗舰 MAX 会员"),
            ("今日调用查询 IP", str(today_queries), "今日成功查询次数"),
            ("累计调用查询 IP", str(total_queries), "按查询日志统计"),
            ("24 小时活跃", str(active_24h), "按最近登录时间统计"),
            ("总注册用户", str(total_users), "包含普通用户和管理员"),
        ]
        card_html = "".join(
            '<div class="card col3"><div class="muted">%s</div><div class="stat">%s</div><p class="hint">%s</p></div>' %
            (esc(title), esc(value), esc(note))
            for title, value, note in cards
        )
        rows = "".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" %
            (esc(r["full_ip"]), exchange_display(r["exchange"]), status_badge(r["last_similarity"]), esc(r["username"]), esc(r["last_seen_at"]))
            for r in recent
        ) or '<tr><td colspan="5" class="muted">暂无查询记录</td></tr>'
        content = """<div class="hero"><div><h2>会员与经营数据</h2><p>集中查看收款、会员、用户活跃和 IP 查询调用情况。该页面仅管理员可见。</p></div></div>
        <div class="grid">%s</div>
        <div class="grid"><div class="card col4"><div class="muted">管理员数</div><div class="stat">%s</div></div><div class="card col4"><div class="muted">普通用户数</div><div class="stat">%s</div></div><div class="card col4"><div class="muted">操作日志数</div><div class="stat">%s</div></div></div>
        <div class="card"><h2>最近 IP 调用</h2><div class="tablewrap"><table><thead><tr><th>IP</th><th>交易所</th><th>相似度</th><th>用户</th><th>时间</th></tr></thead><tbody>%s</tbody></table></div></div>""" % (
            card_html, admin_count, normal_count, log_count, rows
        )
        self.send_html(self.page(session, "会员数据", content, "analytics"))

    def logs(self, query):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">授权白名单拥有与星舰会员相同的查询权限，不能查看操作日志。</p></div>'), 403)
            return
        with db() as conn:
            logs = conn.execute("""SELECT l.*,u.username FROM operation_logs l LEFT JOIN users u ON u.id=l.user_id ORDER BY l.created_at DESC LIMIT 500""").fetchall()
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s #%s</td><td>%s</td></tr>" % (
            esc(l["created_at"]), esc(l["username"] or "系统"), esc(l["action"]), esc(l["target_type"]), esc(l["target_id"]), esc(l["detail"])
        ) for l in logs) or '<tr><td colspan="5">暂无日志</td></tr>'
        content = '<div class="card"><h2>最近 500 条操作</h2><div class="tablewrap"><table><thead><tr><th>时间</th><th>用户</th><th>操作</th><th>对象</th><th>详情</th></tr></thead><tbody>%s</tbody></table></div></div>' % rows
        self.send_html(self.page(session, "操作日志", content, "logs"))

    def exchange_admin_session(self):
        session = self.require_user(admin=True)
        if not session:
            return None
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">授权白名单拥有与星舰会员相同的查询权限，不能维护交易所目录。</p></div>'), 403)
            return None
        return session

    def exchange_form_values(self, form, catalog, current_id=""):
        name = form.get("name", "").strip()
        group = form.get("group", "").strip().lower()
        aliases = []
        for alias in form.get("aliases", "").replace("\n", ",").split(","):
            alias = alias.strip()
            if alias and alias.casefold() != name.casefold() and alias.casefold() not in {value.casefold() for value in aliases}:
                aliases.append(alias)
        icon_file = form.get("icon_file", "").strip().lower()
        icon_text = form.get("icon_text", "").strip()
        if not name or len(name) > 80 or group not in EXCHANGE_GROUP_META:
            raise ValueError("请填写 1-80 个字符的名称，并选择有效分组。")
        if len(aliases) > 20 or any(len(alias) > 80 for alias in aliases):
            raise ValueError("搜索别名最多 20 个，每个不超过 80 个字符。")
        if icon_file and not EXCHANGE_ICON_FILE_RE.fullmatch(icon_file):
            raise ValueError("图标缓存文件名必须是 32 位小写哈希加 .png，例如 0123...abcd.png。")
        if len(icon_text) > 6:
            raise ValueError("备用图标文字最多 6 个字符。")
        for item in catalog["items"]:
            if item["id"] != current_id and item["name"].casefold() == name.casefold():
                raise ValueError("交易所名称已存在，请使用不同名称或编辑现有项目。")
        return {"name": name, "group": group, "aliases": aliases, "icon_file": icon_file, "icon_text": icon_text}

    def exchange_icon_from_upload(self, form, values):
        upload = form.get("icon_upload")
        if not isinstance(upload, dict) or not upload.get("filename"):
            return values
        values["icon_file"] = save_uploaded_exchange_icon(upload.get("data", b""))
        return values

    def exchanges(self, query):
        session = self.exchange_admin_session()
        if not session:
            return
        message = query.get("message", [""])[0]
        keyword = query.get("q", [""])[0].strip().lower()
        group_filter = query.get("group", ["all"])[0].lower()
        status_filter = query.get("status", ["all"])[0].lower()
        if group_filter not in ("all", *EXCHANGE_GROUP_META):
            group_filter = "all"
        if status_filter not in ("all", "enabled", "disabled"):
            status_filter = "all"
        catalog = load_exchange_catalog()
        all_items = exchange_catalog_items(False)
        filtered = []
        for item in all_items:
            searchable = " ".join([item["name"], *item["aliases"], item["group"]]).lower()
            if keyword and keyword not in searchable:
                continue
            if group_filter != "all" and item["group"] != group_filter:
                continue
            if status_filter == "enabled" and not item["enabled"]:
                continue
            if status_filter == "disabled" and item["enabled"]:
                continue
            filtered.append(item)
        group_options = '<option value="all">全部分组</option>' + "".join('<option value="%s"%s>%s</option>' % (group, " selected" if group_filter == group else "", esc(meta["label"])) for group, meta in EXCHANGE_GROUP_META.items())
        status_options = "".join('<option value="%s"%s>%s</option>' % (value, " selected" if status_filter == value else "", label) for value, label in (("all", "全部状态"), ("enabled", "已启用"), ("disabled", "已停用")))
        rows = []
        for item in filtered:
            cached = bool(item["icon_file"] and (os.path.exists(os.path.join(CMC_ICON_DIR, item["icon_file"])) or os.path.exists(os.path.join(BRAND_DIR, "exchanges", item["icon_file"]))))
            icon_state = "已验证本地缓存" if cached else ("缓存文件未找到" if item["icon_file"] else "自动图标 / 备用图标")
            rows.append("""<tr><td>%s</td><td>%s</td><td><strong>%s</strong><br><span class=\"muted\">%s</span></td><td>%s</td><td>%s</td><td>%s</td><td><details><summary>编辑</summary><form method=\"post\" action=\"/exchanges/update\" enctype=\"multipart/form-data\" class=\"catalog-edit-form\"><input type=\"hidden\" name=\"csrf\" value=\"%s\"><input type=\"hidden\" name=\"id\" value=\"%s\"><label>名称<input name=\"name\" value=\"%s\" maxlength=\"80\" required></label><label>分组<select name=\"group\">%s</select></label><label>搜索别名<input name=\"aliases\" value=\"%s\" placeholder=\"英文名, 中文别名\"></label><label>上传图标<input name=\"icon_upload\" type=\"file\" accept=\"image/png,image/jpeg,image/webp\"></label><label>图标缓存文件名<input name=\"icon_file\" value=\"%s\" placeholder=\"32 位哈希.png\"></label><label>备用图标文字<input name=\"icon_text\" value=\"%s\" maxlength=\"6\"></label><button>保存修改</button></form></details></td><td><form class=\"inline\" method=\"post\" action=\"/exchanges/move\"><input type=\"hidden\" name=\"csrf\" value=\"%s\"><input type=\"hidden\" name=\"id\" value=\"%s\"><button class=\"secondary\" name=\"direction\" value=\"up\" title=\"在同组内上移\">上移</button><button class=\"secondary\" name=\"direction\" value=\"down\" title=\"在同组内下移\">下移</button></form><form class=\"inline\" method=\"post\" action=\"/exchanges/toggle\"><input type=\"hidden\" name=\"csrf\" value=\"%s\"><input type=\"hidden\" name=\"id\" value=\"%s\"><button class=\"%s\">%s</button></form></td></tr>""" % (
                item["order"], exchange_icon_markup(item["name"]), esc(item["name"]), esc("、".join(item["aliases"]) or "无别名"), esc(EXCHANGE_GROUP_META[item["group"]]["short"]), esc(icon_state), '<span class="badge s0">已启用</span>' if item["enabled"] else '<span class="badge">已停用</span>', session["csrf"], esc(item["id"]), esc(item["name"]), "".join('<option value="%s"%s>%s</option>' % (group, " selected" if item["group"] == group else "", esc(meta["label"])) for group, meta in EXCHANGE_GROUP_META.items()), esc(", ".join(item["aliases"])), esc(item["icon_file"]), esc(item["icon_text"]), session["csrf"], esc(item["id"]), session["csrf"], esc(item["id"]), "danger" if item["enabled"] else "secondary", "停用" if item["enabled"] else "恢复"
            ))
        flash = '<div class="flash">%s</div>' % esc(message) if message else ""
        rows_html = "".join(rows) or '<tr><td colspan="8" class="muted">没有匹配的交易所目录项。</td></tr>'
        content = flash + """<div class="hero"><div><h2>交易所管理</h2><p>维护 IP 风险检测中可选择的 CEX、DEX 与其他交易所。名称、别名、分组和同组排序保存后立即同步到检测下拉搜索；停用后不影响已有历史记录。</p></div></div>
        <div class="card"><h2>新增交易所 / 协议</h2><form method="post" action="/exchanges/create" enctype="multipart/form-data"><input type="hidden" name="csrf" value="%s"><div class="grid"><div class="col4"><label>名称</label><input name="name" maxlength="80" placeholder="例如 Jupiter" required></div><div class="col2"><label>分组</label><select name="group"><option value="cex">CEX</option><option value="dex">DEX</option><option value="other">其他</option></select></div><div class="col6"><label>搜索别名</label><input name="aliases" maxlength="800" placeholder="例如 币安, Binance Exchange；用英文逗号分隔"></div><div class="col6"><label>上传图标（可选）</label><input name="icon_upload" type="file" accept="image/png,image/jpeg,image/webp"><p class="hint">支持 PNG、JPG、WebP，最大 4 MB。上传后会自动校验、等比缩放并居中输出为 256 × 256 PNG。</p></div><div class="col3"><label>图标缓存文件名（可选）</label><input name="icon_file" placeholder="已同步 CMC 的 32 位哈希.png" spellcheck="false"></div><div class="col3"><label>备用图标文字</label><input name="icon_text" maxlength="6" placeholder="JUP"></div><div class="col3 query-action-row"><button>新增并启用</button></div></div></form></div>
        <div class="card"><h2>目录列表</h2><form method="get" action="/exchanges" class="catalog-filter"><input name="q" value="%s" placeholder="搜索名称、别名或分组"><select name="group">%s</select><select name="status">%s</select><button class="secondary">筛选</button></form><p class="muted">共 %s 条匹配，当前启用 %s 条。图标缓存可在“系统设置 - CoinMarketCap 官方图标”同步后填写到相应项目。</p><div class="tablewrap"><table><thead><tr><th>排序</th><th>图标</th><th>名称 / 别名</th><th>分组</th><th>图标状态</th><th>状态</th><th>编辑</th><th>操作</th></tr></thead><tbody>%s</tbody></table></div></div>""" % (session["csrf"], esc(keyword), group_options, status_options, len(filtered), len(exchange_catalog_items(True)), rows_html)
        self.send_html(self.page(session, "交易所管理", content, "exchanges"))

    def create_exchange(self):
        session = self.exchange_admin_session()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html("Forbidden", 403)
        catalog = load_exchange_catalog()
        try:
            values = self.exchange_form_values(form, catalog)
            values = self.exchange_icon_from_upload(form, values)
        except ValueError as error:
            return self.redirect("/exchanges?message=" + urllib.parse.quote(str(error)))
        order = 1 + max((item["order"] for item in catalog["items"] if item["group"] == values["group"]), default=0)
        item = {"id": "custom-" + secrets.token_hex(8), **values, "order": order, "enabled": True, "created_at": now(), "updated_at": now()}
        catalog["items"].append(item)
        save_exchange_catalog(catalog)
        with db() as conn:
            log_action(conn, session["user"]["id"], "CREATE_EXCHANGE", "EXCHANGE_CATALOG", item["id"], detail="新增 %s（%s）" % (item["name"], item["group"]))
        self.redirect("/exchanges?message=" + urllib.parse.quote("已新增并启用 %s，IP 检测搜索已同步。" % item["name"]))

    def update_exchange(self):
        session = self.exchange_admin_session()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html("Forbidden", 403)
        catalog = load_exchange_catalog()
        item = next((value for value in catalog["items"] if value["id"] == form.get("id", "")), None)
        if not item:
            return self.redirect("/exchanges?message=" + urllib.parse.quote("未找到要编辑的交易所。"))
        try:
            values = self.exchange_form_values(form, catalog, item["id"])
            values = self.exchange_icon_from_upload(form, values)
        except ValueError as error:
            return self.redirect("/exchanges?message=" + urllib.parse.quote(str(error)))
        old_name, old_group = item["name"], item["group"]
        item.update(values)
        if old_group != item["group"]:
            item["order"] = 1 + max((value["order"] for value in catalog["items"] if value["group"] == item["group"] and value["id"] != item["id"]), default=0)
        item["updated_at"] = now()
        save_exchange_catalog(catalog)
        with db() as conn:
            log_action(conn, session["user"]["id"], "UPDATE_EXCHANGE", "EXCHANGE_CATALOG", item["id"], detail="%s 更新为 %s（%s）" % (old_name, item["name"], item["group"]))
        self.redirect("/exchanges?message=" + urllib.parse.quote("交易所目录已更新，检测搜索已同步。"))

    def toggle_exchange(self):
        session = self.exchange_admin_session()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html("Forbidden", 403)
        catalog = load_exchange_catalog()
        item = next((value for value in catalog["items"] if value["id"] == form.get("id", "")), None)
        if not item:
            return self.redirect("/exchanges?message=" + urllib.parse.quote("未找到要操作的交易所。"))
        item["enabled"] = not item["enabled"]
        item["updated_at"] = now()
        save_exchange_catalog(catalog)
        with db() as conn:
            log_action(conn, session["user"]["id"], "TOGGLE_EXCHANGE", "EXCHANGE_CATALOG", item["id"], detail="%s：%s" % (item["name"], "启用" if item["enabled"] else "停用"))
        self.redirect("/exchanges?message=" + urllib.parse.quote("已%s %s；历史记录不会受影响。" % ("恢复" if item["enabled"] else "停用", item["name"])))

    def move_exchange(self):
        session = self.exchange_admin_session()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html("Forbidden", 403)
        direction = form.get("direction", "")
        catalog = load_exchange_catalog()
        item = next((value for value in catalog["items"] if value["id"] == form.get("id", "")), None)
        if not item or direction not in ("up", "down"):
            return self.redirect("/exchanges?message=" + urllib.parse.quote("排序请求不正确。"))
        siblings = sorted((value for value in catalog["items"] if value["group"] == item["group"]), key=lambda value: (value["order"], value["name"].casefold()))
        index = next(index for index, value in enumerate(siblings) if value["id"] == item["id"])
        swap_index = index - 1 if direction == "up" else index + 1
        if 0 <= swap_index < len(siblings):
            siblings[index]["order"], siblings[swap_index]["order"] = siblings[swap_index]["order"], siblings[index]["order"]
            siblings[index]["updated_at"] = siblings[swap_index]["updated_at"] = now()
            save_exchange_catalog(catalog)
            with db() as conn:
                log_action(conn, session["user"]["id"], "MOVE_EXCHANGE", "EXCHANGE_CATALOG", item["id"], detail="%s 在 %s 分组内%s" % (item["name"], item["group"], "上移" if direction == "up" else "下移"))
        self.redirect("/exchanges?message=" + urllib.parse.quote("排序已更新。"))

    def settings(self, query):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">授权白名单拥有与星舰会员相同的查询权限，不能访问系统设置。</p></div>'), 403)
            return
        message = query.get("message", [""])[0]
        flash = '<div class="flash">%s</div>' % esc(message) if message else ""
        with db() as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            record_count = conn.execute("SELECT COUNT(*) FROM ip_records").fetchone()[0]
            log_count = conn.execute("SELECT COUNT(*) FROM operation_logs").fetchone()[0]
            announcement_users = conn.execute(
                "SELECT id,username,email FROM users WHERE deleted_at IS NULL AND status='ACTIVE' AND email IS NOT NULL AND email != '' ORDER BY is_owner DESC,username COLLATE NOCASE"
            ).fetchall()
            announcements = conn.execute(
                """SELECT a.*,u.username AS sender_username FROM email_announcements a
                   LEFT JOIN users u ON u.id=a.sender_user_id ORDER BY a.created_at DESC LIMIT 8"""
            ).fetchall()
            site_announcements = conn.execute(
                """SELECT a.*,COUNT(r.user_id) AS seen_count,
                          SUM(CASE WHEN r.muted_at IS NOT NULL THEN 1 ELSE 0 END) AS muted_count
                   FROM site_announcements a LEFT JOIN site_announcement_receipts r ON r.announcement_id=a.id
                   GROUP BY a.id ORDER BY a.published_at DESC,a.id DESC LIMIT 12"""
            ).fetchall()
        icon_count = len(load_cmc_icon_map())
        key_ready = os.path.exists(CMC_KEY_FILE) and os.path.getsize(CMC_KEY_FILE) > 15
        if session["user"]["is_owner"]:
            cmc_card = """<div class="card"><h2>CoinMarketCap 官方图标</h2><p>API Key 状态：<strong>%s</strong>　已缓存官方图标：<strong>%s</strong> 个</p>
            <p class="muted">Key 只保存在服务器的 <code>local_data/cmc_api_key.txt</code>，权限为 600，不会写入网页、日志或 GitHub 压缩包。</p>
            <form method="post" action="/settings/cmc-key"><input type="hidden" name="csrf" value="%s"><label>CMC API Key</label><input name="api_key" type="password" minlength="16" maxlength="200" autocomplete="off" placeholder="在这里粘贴后保存" required><div style="margin-top:12px"><button>保存 API Key</button></div></form>
            <form method="post" action="/settings/cmc-sync" style="margin-top:14px"><input type="hidden" name="csrf" value="%s"><button class="secondary" %s>同步并缓存 CMC 官方图标</button></form></div>""" % (
                "已配置" if key_ready else "尚未配置", icon_count, session["csrf"], session["csrf"], "" if key_ready else "disabled"
            )
        else:
            cmc_card = '<div class="card"><h2>CoinMarketCap 官方图标</h2><p>已缓存官方图标：<strong>%s</strong> 个</p><p class="muted">只有总管理员可以配置 API Key 和执行同步。</p></div>' % icon_count
        smtp_cfg = load_smtp_config()
        smtp_ready = bool(smtp_cfg["host"] and smtp_cfg["user"] and smtp_cfg["password"] and smtp_cfg["from"])
        mode_options = "".join(
            '<option value="%s"%s>%s</option>' % (
                value,
                " selected" if smtp_cfg["mode"] == value else "",
                label,
            )
            for value, label in (("starttls", "STARTTLS（推荐）"), ("ssl", "SSL/TLS"), ("none", "无加密"))
        )
        smtp_card = """<div class="card"><h2>邮件服务（注册验证码）</h2>
        <p>状态：<strong>%s</strong>　当前服务器：<code>%s:%s</code></p>
        <p class="muted">配置保存在服务器的 <code>local_data/smtp.json</code>，权限为 600，不会写入 GitHub。保存后立即生效，无需重启服务。</p>
        <form method="post" action="/settings/smtp"><input type="hidden" name="csrf" value="%s"><div class="grid">
        <div class="col6"><label>SMTP 服务器</label><input name="host" value="%s" placeholder="例如 smtp.qq.com" required></div>
        <div class="col3"><label>端口</label><input name="port" type="number" min="1" max="65535" value="%s" required></div>
        <div class="col3"><label>加密方式</label><select name="mode">%s</select></div>
        <div class="col6"><label>登录账号</label><input name="user" value="%s" autocomplete="off" required></div>
        <div class="col6"><label>发件人</label><input name="from" value="%s" autocomplete="off" required></div>
        <div class="col12"><label>SMTP 密码</label><input name="password" type="password" autocomplete="new-password" placeholder="留空则保留当前密码"><p class="hint">QQ/163 等邮箱请使用“授权码”而不是登录密码。</p></div>
        <div class="col12"><button>保存邮件配置</button></div></div></form>
        <form method="post" action="/settings/smtp-test" style="margin-top:14px"><input type="hidden" name="csrf" value="%s"><label>测试收件邮箱</label><input name="test_email" type="email" placeholder="your@example.com" required><div style="margin-top:10px"><button class="secondary" %s>发送测试邮件</button></div></form></div>""" % (
            "已配置" if smtp_ready else "尚未配置",
            esc(smtp_cfg["host"] or "未设置"),
            smtp_cfg["port"],
            session["csrf"],
            esc(smtp_cfg["host"]),
            smtp_cfg["port"],
            mode_options,
            esc(smtp_cfg["user"]),
            esc(smtp_cfg["from"]),
            session["csrf"],
            "" if smtp_ready else "disabled",
        )
        recipient_options = "".join(
            '<label class="check-option"><input type="checkbox" name="recipient_ids" value="%s"> <strong>%s</strong> <span class="muted">%s</span></label>' % (
                user["id"], esc(user["username"]), esc(user["email"])
            )
            for user in announcement_users
        ) or '<p class="muted">暂无可发送公告的启用用户邮箱。</p>'
        announcement_rows = "".join(
            '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s / %s / %s</td></tr>' % (
                esc(item["created_at"]), esc(item["subject"]), esc(item["audience"]), esc(item["sender_username"] or "已删除用户"),
                item["recipient_count"], item["sent_count"], item["failed_count"],
            )
            for item in announcements
        ) or '<tr><td colspan="5" class="muted">暂无公告发送记录</td></tr>'
        announcement_card = """<div class="card"><h2>公告邮件</h2>
        <p>使用上方 SMTP 配置逐封发送公告邮件，不会向收件人暴露其他用户邮箱。仅总管理员可发送，范围仅包含状态为“启用”且邮箱有效的账户。</p>
        <form method="post" action="/settings/announcement" onsubmit="return confirm('确认发送公告邮件？发送后无法撤回。');"><input type="hidden" name="csrf" value="%s">
        <div class="grid"><div class="col12"><label>邮件主题</label><input name="subject" maxlength="160" placeholder="例如：原石金手指 · 系统公告" required></div>
        <div class="col12"><label>公告正文</label><textarea name="body" rows="8" maxlength="12000" placeholder="请输入发送给用户的公告内容" required></textarea><p class="hint">将以纯文本邮件发送。请勿在公告中包含密码、API Key 或私钥等敏感信息。</p></div>
        <div class="col12"><label>发送范围</label><div class="segments"><label><input type="radio" name="audience" value="all" checked> 全部可发送用户（%s）</label><label><input type="radio" name="audience" value="selected"> 仅发送给下方勾选用户</label></div></div>
        <div class="col12 recipient-picker">%s</div><div class="col12"><button %s>发送公告邮件</button></div></div></form>
        <div class="tablewrap" style="margin-top:18px"><table><thead><tr><th>时间</th><th>主题</th><th>范围</th><th>发送人</th><th>目标 / 成功 / 失败</th></tr></thead><tbody>%s</tbody></table></div></div>""" % (
            session["csrf"], len(announcement_users), recipient_options, "" if smtp_ready and announcement_users else "disabled", announcement_rows,
        )
        site_announcement_rows = "".join(
            '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s / %s</td><td>%s</td><td><form method="post" action="/announcements/archive" onsubmit="return confirm(\'确认归档这条站内公告？归档后不再展示，但不删除记录。\');"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="id" value="%s"><button class="secondary" %s>归档</button></form></td></tr>' % (
                esc(item["published_at"]), esc(item["title"]), "首页弹窗" if item["popup_enabled"] else "仅站内信",
                esc(item["expires_at"] or "长期有效"), item["seen_count"], item["muted_count"] or 0,
                "已发布" if item["status"] == "PUBLISHED" else "已归档", session["csrf"], item["id"], "" if item["status"] == "PUBLISHED" else "disabled",
            ) for item in site_announcements
        ) or '<tr><td colspan="7" class="muted">暂无站内公告</td></tr>'
        site_announcement_card = """<div class="card"><h2>站内公告</h2>
        <p>发布后将面向所有登录用户展示，并同步进入“站内信”。开启首页提示时，用户可选择“我知道了”或“不再提示”；后者仅关闭该条公告的首页弹窗，不会删除站内信记录。</p>
        <form method="post" action="/announcements/create"><input type="hidden" name="csrf" value="%s"><div class="grid"><div class="col12"><label>公告标题</label><input name="title" maxlength="160" placeholder="例如：原石金手指 · 系统维护通知" required></div><div class="col12"><label>公告正文</label><textarea name="body" rows="7" maxlength="8000" placeholder="请输入要向全站用户播报的内容" required></textarea><p class="hint">仅支持纯文本，会保留换行。请勿发布密码、API Key、私钥或其他敏感信息。</p></div><div class="col4"><label>首页弹窗</label><select name="popup_enabled"><option value="1">开启首页提示</option><option value="0">仅发送站内信</option></select></div><div class="col4"><label>弹窗截止时间（可选）</label><input name="expires_at" type="datetime-local"></div><div class="col4 query-action-row"><button>发布全站公告</button></div></div></form>
        <div class="tablewrap" style="margin-top:18px"><table><thead><tr><th>发布时间</th><th>标题</th><th>投递方式</th><th>截止时间</th><th>已读 / 不再提示</th><th>状态</th><th>操作</th></tr></thead><tbody>%s</tbody></table></div></div>""" % (session["csrf"], site_announcement_rows)
        web3_cfg = load_web3_risk_config()
        web3_card = """<div class="card"><h2>第三方 Web3 风控与钱包画像 API</h2>
        <p>推荐地址安全源：<strong>GoPlus Security</strong>。它适合先接入基础地址安全、恶意/钓鱼合约与代币风险信息；RPC 负责真实余额。更完整的 CEX 标签、资金追踪、制裁与 AML 风险可在下方接入商业标签库。</p>
        <p class="muted">所有接口仅由服务端调用。密钥保存到 <code>local_data/web3_risk.json</code>（权限 600），保存后不会在后台回显明文、不会写入操作日志或 GitHub。</p>
        <form method="post" action="/settings/web3-risk"><input type="hidden" name="csrf" value="%s"><div class="grid">
        <div class="col6"><label>EVM RPC URL</label><input class="settings-long-input" name="evm_rpc_url" value="%s" placeholder="https://eth-mainnet.g.alchemy.com/v2/..." spellcheck="false"><p class="hint">用于 EVM 原生币余额。推荐 Alchemy、Infura、QuickNode 或自建节点。</p></div>
        <div class="col6"><label>Solana RPC URL</label><input class="settings-long-input" name="solana_rpc_url" value="%s" placeholder="https://api.mainnet-beta.solana.com" spellcheck="false"><p class="hint">用于 SOL 原生币余额。推荐 Helius、QuickNode 或自建节点。</p></div>
        <div class="col3"><label>启用 GoPlus 地址安全</label><select name="goplus_enabled"><option value="0"%s>未启用</option><option value="1"%s>启用</option></select></div>
        <div class="col9"><label>GoPlus API Base URL</label><input class="settings-long-input" name="goplus_base_url" value="%s" placeholder="https://api.gopluslabs.io/api/v1" spellcheck="false"></div>
        <div class="col12"><label>GoPlus API Key（如套餐要求）</label><input name="goplus_api_key" type="password" autocomplete="new-password" placeholder="留空则保留当前密钥；免费接口通常无需填写"><p class="hint">建议先使用 GoPlus 的免费/低门槛地址安全能力；具体限额、链支持和授权以供应商当前文档为准。</p></div>
        <div class="col6"><label>地址标签 / AML API URL</label><input class="settings-long-input" name="label_api_url" value="%s" placeholder="例如已采购的 AML、CEX/DEX 地址标签 API 地址" spellcheck="false"></div>
        <div class="col6"><label>地址标签 / AML API Key</label><input name="label_api_key" type="password" autocomplete="new-password" placeholder="留空则保留当前密钥"></div>
        <div class="col6"><label>钱包画像 API URL</label><input class="settings-long-input" name="profile_api_url" value="%s" placeholder="交易、持仓、NFT、空投与交互索引 API 地址" spellcheck="false"></div>
        <div class="col6"><label>钱包画像 API Key</label><input name="profile_api_key" type="password" autocomplete="new-password" placeholder="留空则保留当前密钥"></div>
        <div class="col12"><button>保存 Web3 风控配置</button></div></div></form></div>""" % (
            session["csrf"], esc(web3_cfg["evm_rpc_url"]), esc(web3_cfg["solana_rpc_url"]),
            "" if web3_cfg["goplus_enabled"] else " selected", " selected" if web3_cfg["goplus_enabled"] else "",
            esc(web3_cfg["goplus_base_url"]), esc(web3_cfg["label_api_url"]), esc(web3_cfg["profile_api_url"]),
        )
        ip_cfg = load_ip_risk_config()
        ip_card = """<div class="card"><h2>IP 归属地与纯净度检测 API</h2><p>推荐 <strong>IPQualityScore</strong>：可返回国家/地区/城市、ISP、ASN、代理、VPN、Tor、数据中心与欺诈分。每次 IP 入库前会调用已启用的数据源，并保存来源和检测时间。</p><p class="muted">接口 URL 支持 <code>{ip}</code> 和 <code>{key}</code> 占位符；如果没有 <code>{key}</code>，系统会在请求参数中添加 <code>key</code>。密钥仅保存于 <code>local_data/ip_risk.json</code>（权限 600），不回显、不记录到日志。</p><p class="hint">使用 <code>ipwho.is</code> 可免费查询归属地、ISP、ASN 与 VPN/代理等基础属性，但它不提供欺诈分，因此页面会显示“数据源未提供评分”；要得到 0-100 的纯净度，请配置 IPQualityScore 或其他包含欺诈评分的数据源。</p><form method="post" action="/settings/ip-risk"><input type="hidden" name="csrf" value="%s"><div class="grid"><div class="col2"><label>启用检测</label><select name="enabled"><option value="0"%s>未启用</option><option value="1"%s>启用</option></select></div><div class="col2"><label>供应商名称</label><input name="provider" value="%s" placeholder="IPQualityScore"></div><div class="col8"><label>API URL</label><input class="settings-long-input" name="api_url" value="%s" placeholder="https://.../{key}/{ip}" spellcheck="false"></div><div class="col12"><label>API Key</label><input name="api_key" type="password" autocomplete="new-password" placeholder="留空则保留当前密钥"><p class="hint">未配置或调用失败时，系统会明确保存为“待检测/数据源异常”，不会伪造归属地或 IP 纯净度。</p></div><div class="col12"><button>保存 IP 风控配置</button></div></div></form></div>""" % (session["csrf"], "" if ip_cfg["enabled"] else " selected", " selected" if ip_cfg["enabled"] else "", esc(ip_cfg["provider"]), esc(ip_cfg["api_url"]))
        system_cfg = load_system_config()
        brand = site_brand_config()
        branding_card = """<div class="card"><h2>网站品牌设置</h2>
        <p>修改后会同步到侧栏、登录注册页、用户声明和会员页面。Logo 会自动等比适配为 256 × 256 PNG，并保存在服务器 <code>local_data</code>，不会写入 GitHub。</p>
        <form method="post" action="/settings/branding" enctype="multipart/form-data"><input type="hidden" name="csrf" value="%s"><div class="grid">
        <div class="col6"><label>网站名称</label><input name="site_name" value="%s" maxlength="80" placeholder="例如 OriginX" required></div>
        <div class="col6"><label>网站副标题</label><input name="site_tagline" value="%s" maxlength="120" placeholder="例如 WEB3 风控终端"></div>
        <div class="col8"><label>上传网站 Logo</label><input name="logo_upload" type="file" accept="image/png,image/jpeg,image/webp"><p class="hint">支持 PNG、JPG、WebP，最大 4 MB；系统会自动裁切、居中并保持清晰度。</p></div>
        <div class="col4"><label>当前 Logo</label><div style="display:flex;align-items:center;gap:12px"><img src="%s" alt="%s Logo" style="width:64px;height:64px;object-fit:contain;border-radius:14px;background:#0b1424;padding:6px"><span class="muted">留空则保留当前 Logo</span></div></div>
        <div class="col12"><button>保存品牌设置</button></div></div></form></div>""" % (session["csrf"], esc(brand["name"]), esc(brand["tagline"]), esc(brand["logo"]), esc(brand["name"]))
        payment_card = """<div class="card"><h2>会员收款地址</h2><p>新订单会使用当前配置的 BSC / BEP20 收款地址，并将地址快照写入订单；修改地址不会影响已经生成订单的自动核验。</p><form method="post" action="/settings/payment-receiver"><input type="hidden" name="csrf" value="%s"><div class="grid"><div class="col10"><label>BEP20 收款地址</label><input class="settings-long-input" name="payment_receiver" value="%s" pattern="0x[a-fA-F0-9]{40}" spellcheck="false" autocomplete="off" required><p class="hint">仅接受 0x 开头的 42 位 EVM 地址。请确认该地址可接收 BSC 上的 USDT / USDC。</p></div><div class="col2 query-action-row"><button>更新收款地址</button></div></div></form></div>""" % (session["csrf"], esc(system_cfg["payment_receiver"]))
        content = flash + """<div class="grid"><div class="card col4"><div class="muted">用户数</div><div class="stat">%s</div></div><div class="card col4"><div class="muted">IP 记录数</div><div class="stat">%s</div></div><div class="card col4"><div class="muted">操作日志数</div><div class="stat">%s</div></div></div>
        %s%s%s%s%s%s%s%s<div class="card"><h2>系统运行信息</h2><p>服务端口：<code>3000</code></p><p>数据目录：<code>local_data</code></p><p class="muted">请定期备份数据目录，避免误删或服务器故障造成数据丢失。</p></div>""" % (user_count, record_count, log_count, branding_card, payment_card, ip_card, web3_card, smtp_card, announcement_card, site_announcement_card, cmc_card)
        self.send_html(self.page(session, "系统设置", content, "settings"))

    def save_branding(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        name = form.get("site_name", "").strip()
        tagline = form.get("site_tagline", "").strip()
        if not name or len(name) > 80 or len(tagline) > 120:
            return self.redirect("/settings?message=" + urllib.parse.quote("网站名称不能为空且不超过 80 个字符，副标题不超过 120 个字符。"))
        config = {"site_name": name, "site_tagline": tagline, "site_logo": site_brand_config()["logo"]}
        upload = form.get("logo_upload")
        try:
            if upload and not isinstance(upload, dict):
                return self.redirect("/settings?message=" + urllib.parse.quote("Logo 上传字段格式不正确，请重新选择文件后保存。"))
            if upload and upload.get("data"):
                config["site_logo"] = save_uploaded_brand_logo(upload["data"])
        except ValueError as error:
            return self.redirect("/settings?message=" + urllib.parse.quote(str(error)))
        save_system_config(config)
        with db() as conn:
            log_action(conn, session["user"]["id"], "SAVE_BRANDING_CONFIG", "SYSTEM", detail="网站名称与品牌配置已更新（未记录图片内容）")
        self.redirect("/settings?message=" + urllib.parse.quote("品牌设置已保存，刷新页面后即可看到新名称和 Logo。"))

    def save_web3_risk(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        current = load_web3_risk_config()
        config = {}
        for key in ("evm_rpc_url", "solana_rpc_url", "goplus_base_url", "label_api_url", "profile_api_url"):
            value = form.get(key, "").strip()
            if value and (not value.startswith("https://") or len(value) > 500):
                return self.redirect("/settings?message=" + urllib.parse.quote("接口地址必须是有效的 HTTPS URL。"))
            config[key] = value
        config["goplus_enabled"] = form.get("goplus_enabled") == "1"
        for key in ("goplus_api_key", "label_api_key", "profile_api_key"):
            supplied = form.get(key, "").strip()
            if len(supplied) > 500:
                return self.redirect("/settings?message=" + urllib.parse.quote("API Key 长度不正确。"))
            config[key] = supplied or current.get(key, "")
        if not config["goplus_base_url"]:
            config["goplus_base_url"] = "https://api.gopluslabs.io/api/v1"
        save_web3_risk_config(config)
        with db() as conn:
            log_action(conn, session["user"]["id"], "SAVE_WEB3_RISK_CONFIG", "SYSTEM", detail="Web3 风控数据源配置已更新（未记录接口密钥）")
        self.redirect("/settings?message=" + urllib.parse.quote("Web3 风控配置已安全保存，钱包检测将使用已配置的数据源。"))

    def save_ip_risk(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        current = load_ip_risk_config()
        provider = form.get("provider", "").strip() or "IPQualityScore"
        api_url = form.get("api_url", "").strip()
        if len(provider) > 80 or (api_url and (not api_url.startswith("https://") or len(api_url) > 800)):
            return self.redirect("/settings?message=" + urllib.parse.quote("IP 风控供应商或 HTTPS 接口地址不正确。"))
        api_key = form.get("api_key", "").strip()
        if len(api_key) > 500:
            return self.redirect("/settings?message=" + urllib.parse.quote("IP 风控 API Key 长度不正确。"))
        save_ip_risk_config({"enabled": form.get("enabled") == "1", "provider": provider, "api_url": api_url, "api_key": api_key or current.get("api_key", "")})
        with db() as conn:
            log_action(conn, session["user"]["id"], "SAVE_IP_RISK_CONFIG", "SYSTEM", detail="IP 风控数据源配置已更新（未记录接口密钥）")
        self.redirect("/settings?message=" + urllib.parse.quote("IP 风控配置已安全保存，新 IP 入库时将执行检测。"))

    def save_payment_receiver(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        receiver = form.get("payment_receiver", "").strip()
        if not EVM_ADDRESS_RE.fullmatch(receiver):
            return self.redirect("/settings?message=" + urllib.parse.quote("收款地址必须是合法的 0x 开头 EVM 地址。"))
        save_system_config({"payment_receiver": receiver})
        with db() as conn:
            log_action(conn, session["user"]["id"], "UPDATE_PAYMENT_RECEIVER", "SYSTEM", detail="会员收款地址已更新为 %s" % mask_wallet_address(receiver))
        self.redirect("/settings?message=" + urllib.parse.quote("会员收款地址已更新；仅之后新建的订单会使用新地址。"))

    def save_cmc_key(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        api_key = form.get("api_key", "").strip()
        if len(api_key) < 16 or len(api_key) > 200 or any(char.isspace() for char in api_key):
            return self.redirect("/settings?message=" + urllib.parse.quote("API Key 格式不正确。"))
        with open(CMC_KEY_FILE, "w", encoding="utf-8") as f:
            f.write(api_key)
        os.chmod(CMC_KEY_FILE, 0o600)
        with db() as conn:
            log_action(conn, session["user"]["id"], "SAVE_CMC_KEY", "SYSTEM", detail="CMC API Key 已更新（未记录内容）")
        self.redirect("/settings?message=" + urllib.parse.quote("CMC API Key 已安全保存，请点击同步图标。"))

    def save_smtp(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        host = form.get("host", "").strip()
        user = form.get("user", "").strip()
        from_addr = form.get("from", "").strip()
        password = form.get("password", "")
        mode = form.get("mode", "starttls").strip().lower()
        try:
            port = int(form.get("port", "0") or "0")
        except ValueError:
            port = 0
        if mode not in ("starttls", "ssl", "none"):
            mode = "starttls"
        if port < 1 or port > 65535 or not host or not user or not from_addr:
            return self.redirect("/settings?message=" + urllib.parse.quote("请完整填写 SMTP 服务器、端口、账号和发件人。"))
        existing = load_smtp_config()
        if not password:
            password = existing.get("password", "")
        if not password:
            return self.redirect("/settings?message=" + urllib.parse.quote("SMTP 密码不能为空，或留空以保留当前密码。"))
        save_smtp_config({
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "from": from_addr,
            "mode": mode,
        })
        with db() as conn:
            log_action(conn, session["user"]["id"], "SAVE_SMTP", "SYSTEM", detail="SMTP 配置已更新（未记录密码）")
        self.redirect("/settings?message=" + urllib.parse.quote("邮件配置已保存，建议点击发送测试邮件确认可用。"))

    def send_smtp_test(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        test_email = form.get("test_email", "").strip().lower()
        if not EMAIL_RE.fullmatch(test_email):
            return self.redirect("/settings?message=" + urllib.parse.quote("测试收件邮箱格式不正确。"))
        try:
            deliver_email(test_email, "原石金手指 · 邮件服务测试", "这是一封测试邮件，说明 SMTP 邮件服务已配置成功。")
        except Exception as error:
            message = "测试邮件发送失败：%s" % str(error)
            self.redirect("/settings?message=" + urllib.parse.quote(message))
            return
        with db() as conn:
            log_action(conn, session["user"]["id"], "TEST_SMTP", "SYSTEM", detail="测试邮件已发送至 %s" % test_email)
        self.redirect("/settings?message=" + urllib.parse.quote("测试邮件已发送，请查收 %s。" % test_email))

    def send_announcement(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        subject = form.get("subject", "").strip()
        body = form.get("body", "").strip()
        audience = form.get("audience", "")
        selected_ids = form.get("recipient_ids", [])
        if not isinstance(selected_ids, list):
            selected_ids = [selected_ids]
        try:
            selected_ids = sorted({int(value) for value in selected_ids if int(value) > 0})
        except (TypeError, ValueError):
            return self.redirect("/settings?message=" + urllib.parse.quote("所选用户格式不正确。"))
        if not subject or len(subject) > 160 or not body or len(body) > 12000:
            return self.redirect("/settings?message=" + urllib.parse.quote("请填写 1–160 字主题和 1–12000 字公告正文。"))
        if audience not in ("all", "selected"):
            return self.redirect("/settings?message=" + urllib.parse.quote("请选择公告发送范围。"))
        smtp_cfg = load_smtp_config()
        if not (smtp_cfg["host"] and smtp_cfg["user"] and smtp_cfg["password"] and smtp_cfg["from"]):
            return self.redirect("/settings?message=" + urllib.parse.quote("请先配置可用的 SMTP 邮件服务。"))
        with db() as conn:
            if audience == "all":
                recipients = conn.execute(
                    "SELECT id,email FROM users WHERE deleted_at IS NULL AND status='ACTIVE' AND email IS NOT NULL AND email != ''"
                ).fetchall()
                audience_label = "全部可发送用户"
            elif selected_ids:
                placeholders = ",".join("?" for _ in selected_ids)
                recipients = conn.execute(
                    "SELECT id,email FROM users WHERE deleted_at IS NULL AND status='ACTIVE' AND email IS NOT NULL AND email != '' AND id IN (%s)" % placeholders,
                    selected_ids,
                ).fetchall()
                audience_label = "选中用户"
            else:
                recipients = []
                audience_label = "选中用户"
        recipients = [recipient for recipient in recipients if EMAIL_RE.fullmatch(recipient["email"] or "")]
        if not recipients:
            return self.redirect("/settings?message=" + urllib.parse.quote("该范围内没有可发送公告的启用用户邮箱。"))
        rate_key = "announcement:%s" % session["user"]["id"]
        attempts = RATE_LIMITS.setdefault(rate_key, [])
        cutoff = time.time() - 60
        attempts[:] = [timestamp for timestamp in attempts if timestamp > cutoff]
        if attempts:
            return self.redirect("/settings?message=" + urllib.parse.quote("公告发送操作过于频繁，请一分钟后再试。"))
        attempts.append(time.time())
        sent_count = 0
        failed_count = 0
        for recipient in recipients:
            try:
                deliver_email(recipient["email"], subject, body)
                sent_count += 1
            except Exception:
                failed_count += 1
        with db() as conn:
            announcement_id = conn.execute(
                """INSERT INTO email_announcements(sender_user_id,subject,audience,recipient_count,sent_count,failed_count,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (session["user"]["id"], subject, audience_label, len(recipients), sent_count, failed_count, now()),
            ).lastrowid
            log_action(
                conn,
                session["user"]["id"],
                "SEND_ANNOUNCEMENT_EMAIL",
                "EMAIL_ANNOUNCEMENT",
                announcement_id,
                "范围=%s，目标=%s，成功=%s，失败=%s；正文未记录" % (audience_label, len(recipients), sent_count, failed_count),
            )
        self.redirect("/settings?message=" + urllib.parse.quote("公告发送完成：目标 %s 位，成功 %s 位，失败 %s 位。" % (len(recipients), sent_count, failed_count)))

    def create_site_announcement(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        title = form.get("title", "").strip()
        body = form.get("body", "").strip()
        popup_enabled = form.get("popup_enabled") == "1"
        expires_raw = form.get("expires_at", "").strip()
        if not title or len(title) > 160 or not body or len(body) > 8000:
            return self.redirect("/settings?message=" + urllib.parse.quote("请填写 1–160 字标题和 1–8000 字公告正文。"))
        expires_at = None
        if expires_raw:
            try:
                expires_at = datetime.strptime(expires_raw, "%Y-%m-%dT%H:%M").strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return self.redirect("/settings?message=" + urllib.parse.quote("公告截止时间格式不正确。"))
            if expires_at <= now():
                return self.redirect("/settings?message=" + urllib.parse.quote("公告截止时间必须晚于当前时间。"))
        timestamp = now()
        with db() as conn:
            announcement_id = conn.execute(
                """INSERT INTO site_announcements(sender_user_id,title,body,popup_enabled,status,published_at,expires_at,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (session["user"]["id"], title, body, 1 if popup_enabled else 0, "PUBLISHED", timestamp, expires_at, timestamp, timestamp),
            ).lastrowid
            log_action(conn, session["user"]["id"], "PUBLISH_SITE_ANNOUNCEMENT", "SITE_ANNOUNCEMENT", announcement_id, detail="标题：%s；首页弹窗：%s" % (title, "开启" if popup_enabled else "关闭"))
        self.redirect("/settings?message=" + urllib.parse.quote("站内公告已发布，所有登录用户均可在站内信查看。"))

    def archive_site_announcement(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        try:
            announcement_id = int(form.get("id", "0"))
        except ValueError:
            announcement_id = 0
        with db() as conn:
            announcement = conn.execute("SELECT title,status FROM site_announcements WHERE id=?", (announcement_id,)).fetchone()
            if not announcement or announcement["status"] != "PUBLISHED":
                return self.redirect("/settings?message=" + urllib.parse.quote("公告不存在或已归档。"))
            conn.execute("UPDATE site_announcements SET status='ARCHIVED',updated_at=? WHERE id=?", (now(), announcement_id))
            log_action(conn, session["user"]["id"], "ARCHIVE_SITE_ANNOUNCEMENT", "SITE_ANNOUNCEMENT", announcement_id, detail="标题：%s" % announcement["title"])
        self.redirect("/settings?message=" + urllib.parse.quote("站内公告已归档，不会再向用户展示。"))

    def site_announcement_receipt(self):
        session = self.require_user()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_json({"error": "请求已失效，请刷新页面重试。"}, 403)
        try:
            announcement_id = int(form.get("id", "0"))
        except ValueError:
            announcement_id = 0
        with db() as conn:
            saved = save_announcement_receipt(conn, announcement_id, session["user"]["id"], form.get("action", ""))
        if not saved:
            return self.send_json({"error": "公告不存在或操作无效。"}, 404)
        self.send_json({"ok": True})

    def delete_site_announcement_for_user(self):
        session = self.require_user()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html(self.page(session, "请求失败", '<div class="flash err">请求已失效，请刷新页面重试。</div>'), 403)
        try:
            announcement_id = int(form.get("id", "0"))
        except ValueError:
            announcement_id = 0
        with db() as conn:
            announcement = conn.execute(
                """SELECT a.id,r.seen_at,r.deleted_at FROM site_announcements a
                   LEFT JOIN site_announcement_receipts r ON r.announcement_id=a.id AND r.user_id=?
                   WHERE a.id=? AND a.status='PUBLISHED'""",
                (session["user"]["id"], announcement_id),
            ).fetchone()
            if not announcement or announcement["deleted_at"] or not announcement["seen_at"]:
                return self.redirect("/inbox?message=" + urllib.parse.quote("只能删除已经阅读的站内信。"))
            conn.execute(
                "UPDATE site_announcement_receipts SET deleted_at=? WHERE announcement_id=? AND user_id=?",
                (now(), announcement_id, session["user"]["id"]),
            )
        self.redirect("/inbox?message=" + urllib.parse.quote("站内信已从您的收件箱删除。"))

    def sync_cmc(self):
        session = self.require_user(admin=True)
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form) or not session["user"]["is_owner"]:
            return self.send_html("Forbidden", 403)
        key = "cmc-sync:%s" % session["user"]["id"]
        attempts = RATE_LIMITS.setdefault(key, [])
        cutoff = time.time() - 60
        attempts[:] = [timestamp for timestamp in attempts if timestamp > cutoff]
        if attempts:
            return self.redirect("/settings?message=" + urllib.parse.quote("同步操作过于频繁，请一分钟后再试。"))
        attempts.append(time.time())
        try:
            with open(CMC_KEY_FILE, "r", encoding="utf-8") as f:
                api_key = f.read().strip()
        except OSError:
            return self.redirect("/settings?message=" + urllib.parse.quote("请先保存 CMC API Key。"))
        result = sync_cmc_icons(api_key)
        if result["downloaded"] or result["cached"]:
            message = "CMC 同步完成：匹配 %s 家，本次下载 %s 个，当前缓存 %s 个官方图标。" % (
                result["matched"], result["downloaded"], result["cached"]
            )
        else:
            message = "未能同步图标，请检查 API Key、网络或 CMC 额度。"
        with db() as conn:
            log_action(conn, session["user"]["id"], "SYNC_CMC_ICONS", "SYSTEM", detail=json.dumps({
                "matched": result["matched"], "downloaded": result["downloaded"], "cached": result["cached"]
            }, ensure_ascii=False))
        self.redirect("/settings?message=" + urllib.parse.quote(message))


if __name__ == "__main__":
    init_db()
    print("原石金手指本地版运行于 http://%s:%s" % (HOST, PORT), flush=True)
    ThreadingHTTPServer((HOST, PORT), App).serve_forever()
