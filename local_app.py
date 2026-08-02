#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
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
PAYMENT_RECEIVER = "0x04bCA584834489C26d6474701400c88D954B7782"
BSC_RPC_URL = os.environ.get("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
TOKEN_CONTRACTS = {
    "USDT": "0x55d398326f99059ff775485246999027b3197955",
    "USDC": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
}
PLAN_CONFIG = {
    "STARSHIP": {"name": "星舰会员", "price": 12.0, "limit": 10, "days": 30},
    "PRO": {"name": "旗舰 PRO", "price": 39.9, "limit": -1, "days": 30},
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
            ("membership_expires_at", "ALTER TABLE users ADD COLUMN membership_expires_at TEXT"),
            ("bound_device_token", "ALTER TABLE users ADD COLUMN bound_device_token TEXT"),
            ("email_verified_at", "ALTER TABLE users ADD COLUMN email_verified_at TEXT"),
        ]:
            if column not in columns:
                conn.execute(ddl)
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


def user_identity(row):
    email = row["email"] if "email" in row.keys() and row["email"] else "未绑定邮箱"
    return '<div><strong>%s</strong><br><small class="muted">%s</small></div>' % (esc(row["username"]), esc(email))


def can_query_local(user):
    if user["role"] == "ADMIN":
        return True, ""
    status = user["membership_status"] if "membership_status" in user.keys() else "FREE"
    plan = user["membership_plan"] if "membership_plan" in user.keys() else "FREE"
    if status != "ACTIVE" or plan == "FREE":
        return False, "当前账号尚未开通权限，请先进入权限中心开通。"
    expires_at = user["membership_expires_at"] if "membership_expires_at" in user.keys() else None
    if expires_at and expires_at < now():
        return False, "会员已到期，请续费后继续查询。"
    query_limit = user["query_limit"] if "query_limit" in user.keys() else 0
    query_used = user["query_used"] if "query_used" in user.keys() else 0
    if query_limit is not None and int(query_limit) >= 0 and int(query_used) >= int(query_limit):
        return False, "本月额度已使用完，请升级或续费。"
    return True, ""


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


def activate_membership(conn, user_id, plan):
    config = PLAN_CONFIG[plan]
    ts = now()
    expires_at = (datetime.utcnow() + timedelta(days=config["days"])).isoformat(timespec="seconds")
    conn.execute(
        "UPDATE users SET membership_plan=?,membership_status='ACTIVE',query_limit=?,query_used=0,membership_expires_at=?,updated_at=? WHERE id=?",
        (plan, config["limit"], expires_at, ts, user_id),
    )
    return expires_at


def exchange_label(value):
    return LEGACY_EXCHANGES.get(value, value)


def exchange_icon_text(value):
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
    for group_label, names in EXCHANGE_GROUPS:
        options = "".join('<option value="%s" %s>%s · %s</option>' % (
            esc(name), "selected" if selected == name else "", "CEX" if group_label.startswith("CEX") else ("DEX" if group_label.startswith("DEX") else "其他"), esc(name)
        ) for name in names)
        groups.append('<optgroup label="%s">%s</optgroup>' % (esc(group_label), options))
    return "".join(groups)


def exchange_picker(selected="", allow_all=False):
    selected = selected if selected in EXCHANGES else ""
    groups = []
    required = "" if allow_all else "required"
    if allow_all:
        groups.append(
            '<div class="exchange-group"><label class="exchange-option" data-search="全部交易所">'
            '<input type="radio" name="exchange" value="" %s><span>全部交易所</span></label></div>'
            % ("checked" if not selected else "")
        )
    for group_label, names in EXCHANGE_GROUPS:
        items = "".join(
            '<label class="exchange-option" data-search="%s"><input type="radio" name="exchange" value="%s" %s %s>%s<span>%s</span></label>' % (
                esc(name.lower()), esc(name), "checked" if name == selected else "", required, exchange_icon_markup(name), esc(name)
            ) for name in names
        )
        groups.append('<div class="exchange-group"><strong>%s</strong>%s</div>' % (esc(group_label), items))
    empty_label = "全部交易所" if allow_all else "请选择交易所"
    current = exchange_display(selected) if selected else '<span class="muted">%s</span>' % empty_label
    return """<details class="exchange-picker"><summary data-placeholder="%s">%s</summary><div class="exchange-menu"><input class="exchange-search" type="search" placeholder="搜索交易所名称"><div class="exchange-list">%s</div></div></details>""" % (
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
    for name in EXCHANGES:
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
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px}.col3{grid-column:span 3}.col4{grid-column:span 4}.col6{grid-column:span 6}.col8{grid-column:span 8}.col12{grid-column:span 12}
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
.exchange-picker{position:relative}.exchange-picker>summary{list-style:none;display:flex;align-items:center;min-height:44px;padding:7px 38px 7px 11px;border:1px solid #cfd9e7;border-radius:9px;background:#fff;cursor:pointer;position:relative}.exchange-picker>summary::-webkit-details-marker{display:none}.exchange-picker>summary:after{content:"⌄";position:absolute;right:13px;font-size:18px;color:#66758a}.exchange-picker[open]{z-index:9999}.exchange-picker[open]>summary{border-color:#2457d6}.exchange-menu{position:absolute;z-index:9999;top:calc(100% + 8px);right:0;width:min(520px,88vw);padding:12px;border:1px solid rgba(255,255,255,.10);border-radius:16px;background:#111827;color:#f8fafc;box-shadow:0 28px 90px #000b}.exchange-search{margin-bottom:10px;color:#f8fafc;background:#1f2937;border-color:rgba(255,255,255,.12);font-weight:850}.exchange-list{max-height:min(520px,68vh);overflow:auto}.exchange-group>strong{display:block;position:sticky;top:0;padding:10px 11px;background:#1b2433;color:#9fb0c8;font-size:13px;font-weight:950;z-index:1}.exchange-option{display:flex;align-items:center;gap:13px;margin:1px 0;padding:10px 11px;border-radius:12px;cursor:pointer;font-weight:950;color:#f8fafc;letter-spacing:-.35px}.exchange-option span:last-child{color:#f8fafc;font-size:16px;font-weight:950;text-shadow:0 2px 12px #0008}.exchange-option:hover{background:rgba(255,255,255,.075)}.exchange-option input{width:auto;margin:0;accent-color:#3b82f6}.exchange-option input:checked~span:last-child{color:#f6d680;font-weight:950}
.pager{display:flex;gap:7px;margin-top:15px}.pager a{padding:7px 11px;border:1px solid var(--line);border-radius:7px;background:#fff}.stat{font-size:34px;font-weight:850}.actions{display:flex;gap:8px;align-items:end}.inline{display:inline}
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
.payment-panel{position:relative;overflow:hidden}.payment-panel:before{content:"";position:absolute;right:-80px;top:-100px;width:260px;height:260px;border-radius:50%;background:radial-gradient(circle,rgba(246,214,128,.14),transparent 65%)}.payment-panel>*{position:relative}.payment-panel .hint{margin-top:10px;margin-bottom:20px;line-height:1.75}.payment-panel p{line-height:1.9}.pay-address input{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:750;letter-spacing:-.4px}.chain-pill{display:inline-flex;align-items:center;gap:8px;padding:11px 14px;border-radius:16px;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.05);font-weight:850}.chain-pill.good{border-color:rgba(34,197,94,.22);background:rgba(34,197,94,.10);color:#86efac}.chain-pill.gold{border-color:rgba(246,214,128,.22);background:rgba(246,214,128,.10);color:#f6d680}
body:before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.014) 1px,transparent 1px);background-size:54px 54px;mask-image:radial-gradient(circle at 50% 20%,black,transparent 75%)}::selection{background:rgba(246,214,128,.28);color:white}::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-track{background:rgba(255,255,255,.025)}::-webkit-scrollbar-thumb{background:linear-gradient(180deg,rgba(246,214,128,.48),rgba(80,92,117,.42));border:2px solid rgba(5,8,15,.95);border-radius:999px}.side{box-shadow:26px 0 92px rgba(0,0,0,.36),inset -1px 0 rgba(246,214,128,.08)}.brandhead{box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 18px 50px rgba(0,0,0,.20)}.card{overflow:hidden}.card:before{content:"";position:absolute;inset:0;background:linear-gradient(135deg,rgba(255,255,255,.07),transparent 35%),linear-gradient(180deg,rgba(255,255,255,.025),transparent 55%);pointer-events:none}.card>*{position:relative;z-index:1}table{border-collapse:separate;border-spacing:0}th{font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:850}tr{transition:background .16s ease}tbody tr:hover{background:rgba(246,214,128,.035)}.hero,.member-hero{box-shadow:0 38px 120px rgba(0,0,0,.44),inset 0 1px 0 rgba(255,255,255,.09)}.plan-card{box-shadow:0 28px 90px rgba(0,0,0,.32),inset 0 1px 0 rgba(255,255,255,.08)}.plan-card:hover{transform:translateY(-4px)}.gold-text{background:linear-gradient(135deg,#fff7d6,#f6d680 48%,#b98225);-webkit-background-clip:text;background-clip:text;color:transparent}
.terminal-font, .stat, .market-price, .risk-score, .metric-value{font-family:"JetBrains Mono","SFMono-Regular","Menlo","HarmonyOS Sans","Source Han Sans SC","PingFang SC",monospace}.logo,.market-kicker,.core-label,.hero-kicker{font-family:"Orbitron","JetBrains Mono","SFMono-Regular","HarmonyOS Sans","PingFang SC",sans-serif}.risk-disclaimer{border:1px solid rgba(246,214,128,.20);border-radius:18px;padding:14px 16px;background:linear-gradient(135deg,rgba(246,214,128,.08),rgba(255,255,255,.025));color:#d8cda9;font-size:13px;line-height:1.75}.trust-grid,.risk-dashboard{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.trust-card,.risk-panel{position:relative;border:1px solid rgba(255,255,255,.09);border-radius:22px;padding:18px;background:linear-gradient(145deg,rgba(255,255,255,.055),rgba(255,255,255,.018));box-shadow:inset 0 1px 0 rgba(255,255,255,.06);overflow:hidden}.trust-card:after,.risk-panel:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,transparent 0,rgba(255,255,255,.035) 50%,transparent 100%);background-size:100% 9px;opacity:.28;pointer-events:none}.trust-card strong{display:block;margin-top:8px;font-size:28px;color:#f8fbff}.trust-card span,.risk-panel span{color:#8b9ab0;font-size:12px;font-weight:800}.risk-panel h3{margin:0 0 14px;font-size:17px;color:#f8fbff}.risk-row{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:10px 0;color:#dce7f7}.risk-score{display:inline-flex;padding:6px 9px;border-radius:999px;font-weight:950}.risk-low{background:rgba(34,197,94,.14);color:#86efac}.risk-medium{background:rgba(246,214,128,.13);color:#f6d680}.risk-high{background:rgba(248,113,113,.14);color:#fecaca}.scan-progress{display:none;margin-top:16px;border:1px solid rgba(246,214,128,.16);border-radius:999px;background:rgba(0,0,0,.24);overflow:hidden}.scan-progress span{display:block;width:0;height:10px;background:linear-gradient(90deg,#f6d680,#34d399);box-shadow:0 0 18px rgba(246,214,128,.35);animation:scan-fill 1.35s ease forwards}@keyframes scan-fill{from{width:0}to{width:85%}}form.scanning .scan-progress{display:block}form.scanning button{pointer-events:none;opacity:.82}.market-detail{position:relative;z-index:1;display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:12px;color:#9badc4;font-size:11px;font-weight:800}.market-detail b{color:#e8f1ff}.market-mini{position:relative;z-index:1;margin-top:12px;width:100%;height:34px}.market-mini path{fill:none;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.market-tile.up .market-mini path{stroke:#34d399;filter:drop-shadow(0 0 8px rgba(52,211,153,.55))}.market-tile.down .market-mini path{stroke:#fb7185;filter:drop-shadow(0 0 8px rgba(251,113,133,.45))}
.core-query-card{padding:30px 32px}.core-query-card h2{margin-bottom:30px}.core-query-card .grid,.address-check-card .grid{row-gap:22px}.query-action-row{display:flex;align-items:flex-end;gap:16px;padding-top:4px}.address-check-card{margin-top:18px;margin-bottom:26px;border-color:rgba(246,214,128,.18)}.address-check-card h2{margin-bottom:22px}.trust-grid{margin:24px 0 26px}.risk-dashboard{margin:0 0 28px}.payment-panel{margin-top:22px}.plan-order-form{margin-top:20px;display:grid;gap:12px}.plan-order-form select{max-width:180px}.order-box{margin-top:22px;padding:18px;border:1px solid rgba(246,214,128,.16);border-radius:20px;background:rgba(255,255,255,.035)}.verify-form{display:grid;grid-template-columns:1fr auto;gap:14px;align-items:end;margin-top:18px}.verify-form label{grid-column:1/-1}.verify-form input{min-width:0}
@media(max-width:1180px){.market-dashboard{grid-template-columns:1fr}.market-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.market-tile{min-height:168px}}
@media(max-width:850px){.layout{display:block}.side{position:static;height:auto;overflow:visible;padding:14px}.brandhead{margin-bottom:12px}.brandmark{width:42px;height:42px}.nav{display:flex;overflow:auto}.nav a{white-space:nowrap}.business{margin-top:12px;padding-top:10px}.business-list{display:flex;gap:8px;overflow-x:auto;padding-bottom:3px}.business-item{min-width:max-content;margin:0}.main{padding:16px}.col3,.col4,.col6,.col8{grid-column:span 12}.top{align-items:flex-start;gap:12px}.card{padding:16px}.hero{min-height:145px;padding:20px}.hero h2{font-size:22px}.market-dashboard{grid-template-columns:1fr}.market-panel{min-height:300px}.market-grid,.trust-grid,.risk-dashboard{grid-template-columns:1fr}.market-price{font-size:34px}.market-chart-price{font-size:28px}}
@media(max-width:850px){.layout{grid-template-columns:1fr}.side{border-right:0}.main{padding:18px}.top h1{font-size:28px}.brandhead{border-radius:18px}.member-hero{grid-template-columns:1fr;min-height:auto}.hero-logo{justify-self:start;width:92px;height:92px}.plan-pro{transform:none}.plan-price{font-size:40px}.hero h2{font-size:30px}}
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
        try:
            with open(asset_path, "rb") as asset:
                data = asset.read()
        except OSError:
            return self.send_html("Not Found", 404)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
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
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 1024 * 1024)
        except ValueError:
            length = 0
        return {k: v[-1] for k, v in urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True).items()}

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
        nav = [("/", "IP风险检测", "home"), ("/markets", "市场监控中心", "markets"), ("/membership", "权限中心", "membership"), ("/history", "查询历史", "history")]
        if user["is_owner"]:
            nav += [("/analytics", "会员数据", "analytics"), ("/users", "用户管理", "users"), ("/logs", "操作日志", "logs"), ("/settings", "系统设置", "settings")]
        links = "".join('<a class="%s" href="%s">%s</a>' % ("on" if active == key else "", url, label) for url, label, key in nav)
        business = "".join(
            '<div class="business-item"><span class="business-icon">%s</span><span>%s</span></div>' % (esc(icon), esc(label))
            for icon, label in BUSINESS_ITEMS
        )
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s · 原石金手指</title><style>%s</style></head>
        <body><div class="layout"><aside class="side"><div class="brandhead"><img class="brandmark" src="/assets/ck-logo.jpg" alt="CK原石图标"><div class="logo">原石金手指<small>WEB3 风控终端</small></div></div><nav class="nav">%s</nav><section class="business"><div class="business-title">核心业务矩阵</div><div class="business-list">%s</div></section></aside>
        <main class="main"><div class="top"><div><h1>%s</h1><div class="muted">Gold Finger · Web3 用户增长 / 安全风控 / 女巫检测 / 钱包画像</div></div><div>%s · %s　<form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="%s"><button class="secondary">退出</button></form></div></div>%s<div class="contact">产品由 CK原石提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a>　·　<a href="https://t.me/B132609" target="_blank" rel="noopener noreferrer">技术业务交流群</a></div></main></div><script src="/assets/exchange-picker.js?v=20260801-5" defer></script><script src="/assets/market-ticker.js?v=20260801-5" defer></script></body></html>""" % (
            esc(title), STYLE, links, business, esc(title), esc(user["username"]), "总管理员" if user["is_owner"] else ("备用管理员" if user["role"] == "ADMIN" else "普通用户"), session["csrf"], content
        )

    def login_page(self, error=""):
        flash = '<div class="flash err">%s</div>' % esc(error) if error else ""
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>登录 · 原石金手指</title><style>%s</style></head>
        <body><div class="login"><div class="loginbox"><div class="loginbrand"><img src="/assets/ck-logo.jpg" alt="CK原石图标"><div><h1>欢迎使用 原石金手指</h1><p class="muted">Gold Finger · Web3 风控终端</p></div></div>%s<form method="post" action="/login"><label>用户名 / 邮箱</label><div style="display:grid;grid-template-columns:1fr 145px;gap:8px"><input name="username" autocomplete="username" placeholder="用户名或邮箱账号" required><select name="email_domain"><option value="">用户名登录</option>%s</select></div><label>密码</label><input name="password" type="password" autocomplete="current-password" required><button>登录</button></form><div class="authlinks"><a href="/register">注册普通用户</a><a href="/recover">忘记密码</a></div><div class="contact">产品由 CK原石提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a>　·　<a href="https://t.me/B132609" target="_blank" rel="noopener noreferrer">技术业务交流群</a></div></div></div></body></html>""" % (STYLE, flash, email_suffix_options(""))

    def register_page(self, error="", recovery=""):
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
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>注册 · 原石金手指</title><style>%s</style></head><body><div class="login"><div class="loginbox"><div class="loginbrand"><img src="/assets/ck-logo.jpg" alt="CK原石图标"><div><h1>创建账号</h1><p class="muted">注册后即可进入系统，开通会员后使用查重服务</p></div></div>%s<div class="contact">产品由 CK原石提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a>　·　<a href="https://t.me/B132609" target="_blank" rel="noopener noreferrer">技术业务交流群</a></div></div></div></body></html>""" % (STYLE, result)

    def recover_page(self, error="", recovery=""):
        flash = '<div class="flash err">%s</div>' % esc(error) if error else ""
        result = ('<div class="flash">密码已重置。旧恢复码已失效，请保存新的恢复码。</div><div class="recovery"><strong>新密码恢复码：</strong><br>%s</div><a class="btn" href="/login">使用新密码登录</a>' % esc(recovery)) if recovery else """%s<form method="post" action="/recover"><label>用户名</label><input name="username" autocomplete="username" required><label>密码恢复码</label><input name="recovery_code" autocomplete="off" required><label>新密码</label><input name="password" type="password" minlength="10" maxlength="128" autocomplete="new-password" required><label>确认新密码</label><input name="confirm_password" type="password" minlength="10" maxlength="128" autocomplete="new-password" required><button>重置密码</button></form><div class="authlinks"><a href="/login">返回登录</a><a href="/register">注册账号</a></div>""" % flash
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>找回密码 · 原石金手指</title><style>%s</style></head><body><div class="login"><div class="loginbox"><div class="loginbrand"><img src="/assets/ck-logo.jpg" alt="CK原石图标"><div><h1>找回密码</h1><p class="muted">使用注册时保存的恢复码</p></div></div>%s<div class="contact">恢复码丢失请联系：产品由 CK原石提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a>　·　<a href="https://t.me/B132609" target="_blank" rel="noopener noreferrer">技术业务交流群</a></div></div></div></body></html>""" % (STYLE, result)

    def statement_page(self):
        return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>用户注册声明 · 原石金手指</title><style>%s</style></head><body><div class="login"><div class="loginbox"><h1>原石金手指 · 用户注册声明</h1><p class="muted">本系统用于 Web3 风控、IP 环境管理、女巫风险识别、钱包画像与行情辅助展示。注册即代表已阅读、已理解并同意本声明。</p><ol style="line-height:1.8;color:#cbd8e8"><li>系统仅保存完成业务所需的数据。</li><li>禁止用于欺诈、洗钱、市场操纵、非法多账号等违法违规用途。</li><li>用户应遵守相关法律法规及交易平台规则。</li><li>行情、趋势和技术指标仅供信息参考，不构成任何投资或交易建议。</li><li>发现共享账号、破解程序、恶意攻击或非法使用时，开发者有权暂停或终止服务。</li></ol><a class="btn" href="/register">返回注册</a></div></div></body></html>""" % STYLE

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
        if path == "/history":
            return self.history(query)
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
        if path == "/settings/cmc-key":
            return self.save_cmc_key()
        if path == "/settings/cmc-sync":
            return self.sync_cmc()
        if path == "/settings/smtp":
            return self.save_smtp()
        if path == "/settings/smtp-test":
            return self.send_smtp_test()
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
            if session["user"]["is_owner"]:
                recent = conn.execute("""SELECT r.*,u.username,u.email FROM ip_records r JOIN users u ON u.id=r.user_id ORDER BY r.last_seen_at DESC LIMIT 10""").fetchall()
            else:
                recent = conn.execute("""SELECT r.*,u.username,u.email FROM ip_records r JOIN users u ON u.id=r.user_id WHERE r.user_id=? ORDER BY r.last_seen_at DESC LIMIT 10""", (session["user"]["id"],)).fetchall()
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(r["full_ip"]), exchange_display(r["exchange"]), status_badge(r["last_similarity"]), user_identity(r), r["query_count"], esc(r["last_seen_at"])
        ) for r in recent) or '<tr><td colspan="6" class="muted">暂无查询记录</td></tr>'
        content = flash + """<div class="hero"><div><span class="hero-kicker">GOLD FINGER · WEB3 RISK TERMINAL</span><h2>IP 风险检测核心工作台</h2></div></div>
        <div class="card core-query-card"><h2>开始 IP 风险检测</h2><form method="post" action="/query" id="risk-query-form"><input type="hidden" name="csrf" value="%s"><div class="grid">
        <div class="col8"><label>IPv4 地址</label><input name="ip" placeholder="例如：192.168.1.10" required></div><div class="col4"><label>交易所</label>%s</div>
        <div class="col12 query-action-row"><button id="risk-submit">启动扫描并自动入库</button><div class="scan-progress"><span></span></div></div></div></form></div>
        <div class="card address-check-card"><h2>钱包 / 交互地址检测</h2><form method="post" action="/wallet-check"><input type="hidden" name="csrf" value="%s"><div class="grid">
        <div class="col3"><label>检测类型</label><select name="check_type"><option value="wallet">钱包地址</option><option value="interaction">交互地址</option></select></div>
        <div class="col7"><label>EVM 地址</label><input name="address" placeholder="例如：0x82a1...9A"></div>
        <div class="col2 query-action-row"><button>开始检测</button></div></div></form></div>
        <div class="grid trust-grid"><div class="trust-card"><span>检测 IP</span><strong>2,548,920+</strong></div><div class="trust-card"><span>分析钱包</span><strong>856,320+</strong></div><div class="trust-card"><span>风险地址</span><strong>42,891+</strong></div><div class="trust-card"><span>覆盖交易所</span><strong>50+</strong></div></div>
        <div class="risk-dashboard"><div class="risk-panel"><h3>AI 市场雷达</h3><div class="risk-row"><span>BTC</span><b>震荡</b></div><div class="risk-row"><span>ETH</span><b>弱势</b></div><div class="risk-row"><span>SOL</span><b>强势</b></div><div class="risk-row"><span>山寨风险</span><b class="risk-score risk-medium">中等</b></div></div>
        <div class="risk-panel"><h3>风险监控中心</h3><div class="risk-row"><span>总检测</span><b>1,284</b></div><div class="risk-row"><span>异常</span><b>37</b></div><div class="risk-row"><span>高风险</span><b class="risk-score risk-high">6</b></div><div class="risk-row"><span>安全指数</span><b class="risk-score risk-low">94%%</b></div></div>
        <div class="risk-panel"><h3>IP 女巫检测</h3><div class="risk-row"><span>192.xxx.xxx</span><b>China</b></div><div class="risk-row"><span>设备指纹</span><b>MacOS Chrome</b></div><div class="risk-row"><span>风险评分</span><b class="risk-score risk-high">Risk 82</b></div></div>
        <div class="risk-panel"><h3>钱包画像</h3><div class="risk-row"><span>0x82...9A</span><b>124,000 USDT</b></div><div class="risk-row"><span>交互</span><b>DEX 35</b></div><div class="risk-row"><span>风险</span><b class="risk-score risk-low">低</b></div></div></div>
        <div class="card"><h2>最近检测记录</h2><p class="muted">结果页已支持精确重复、相似度排序、历史用户、风险颜色标记；查询历史页支持筛选、分页和 CSV 导出。</p><div class="tablewrap"><table><thead><tr><th>IP</th><th>交易所</th><th>相似度</th><th>查询用户</th><th>次数</th><th>最近查询</th></tr></thead><tbody>%s</tbody></table></div></div>
        <script>document.addEventListener("DOMContentLoaded",function(){var f=document.getElementById("risk-query-form");var b=document.getElementById("risk-submit");if(f&&b){f.addEventListener("submit",function(){f.classList.add("scanning");b.textContent="正在分析网络环境...";});}});</script>""" % (
            session["csrf"], exchange_picker(), session["csrf"], rows
        )
        self.send_html(self.page(session, "IP风险检测", content, "home"))

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
        allowed, reason = can_query_local(session["user"])
        if not allowed:
            content = """<div class="card"><h2>当前账号尚未开通权限</h2><p class="muted">%s</p><div class="actions"><a class="btn" href="/membership#payment">立即开通</a><a class="btn secondary" href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">联系客服</a></div></div>""" % esc(reason)
            return self.send_html(self.page(session, "需要权限", content, "membership"), 403)
        if session["user"]["role"] != "ADMIN":
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
        raw_ip = form.get("ip", "").strip()
        exchange = form.get("exchange", "")
        try:
            parsed = ipaddress.ip_address(raw_ip)
            if parsed.version != 4 or str(parsed) != raw_ip:
                raise ValueError()
        except ValueError:
            return self.redirect("/?message=" + urllib.parse.quote("请输入合法的 IPv4 地址。"))
        if exchange not in EXCHANGES:
            return self.redirect("/?message=" + urllib.parse.quote("请选择有效的交易所。"))
        seg = [int(x) for x in raw_ip.split(".")]
        with db() as conn:
            history = conn.execute("""SELECT r.*,u.username,u.email FROM ip_records r JOIN users u ON u.id=r.user_id""").fetchall()
            compared = []
            for row in history:
                score, matches = similarity(seg, row)
                compared.append((score, row["last_seen_at"], row, matches))
            compared.sort(key=lambda x: (x[0], x[1]), reverse=True)
            top = compared[:20]
            exact = [item for item in compared if item[0] == 100]
            highest = top[0][0] if top else 0
            existing = conn.execute("SELECT id FROM ip_records WHERE full_ip=? AND exchange=?", (raw_ip, exchange)).fetchone()
            ts = now()
            if existing:
                conn.execute("UPDATE ip_records SET query_count=query_count+1,last_seen_at=?,last_similarity=?,updated_at=? WHERE id=?", (ts, highest, ts, existing["id"]))
                record_id = existing["id"]
            else:
                cur = conn.execute("""INSERT INTO ip_records(full_ip,segment_a,segment_b,segment_c,segment_d,exchange,user_id,query_count,last_similarity,first_seen_at,last_seen_at,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (raw_ip, *seg, exchange, session["user"]["id"], 1, highest, ts, ts, ts, ts))
                record_id = cur.lastrowid
            if session["user"]["role"] != "ADMIN":
                limit_value = session["user"]["query_limit"] if "query_limit" in session["user"].keys() else 0
                if int(limit_value or 0) >= 0:
                    conn.execute("UPDATE users SET query_used=query_used+1,updated_at=? WHERE id=?", (ts, session["user"]["id"]))
            log_action(conn, session["user"]["id"], "QUERY_IP", "IP_RECORD", record_id, json.dumps({"ip": raw_ip, "exchange": exchange, "similarity": highest}, ensure_ascii=False))
        best_matches = top[0][3] if top else [False] * 4
        segments_html = "".join('<span class="seg %s">%s = %s · %s</span>' % (
            "yes" if best_matches[i] else "no", "ABCD"[i], seg[i], "匹配" if best_matches[i] else "不匹配"
        ) for i in range(4))
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(item[2]["full_ip"]), status_badge(item[0]), exchange_display(item[2]["exchange"]),
            user_identity(item[2]), esc(item[2]["first_seen_at"]), esc(item[2]["last_seen_at"])
        ) for item in top) or '<tr><td colspan="6" class="muted">这是第一条记录，未发现历史相似 IP。</td></tr>'
        exact_text = "是，共找到 %d 条完整 IP 记录" % len(exact) if exact else "否"
        content = """<div class="card"><div class="grid"><div class="col3"><div class="muted">当前查询 IP</div><div class="stat">%s</div></div><div class="col3"><div class="muted">交易所</div><div style="margin-top:10px">%s</div></div><div class="col3"><div class="muted">最高相似度</div><div class="stat">%s%%</div></div><div class="col3"><div class="muted">精确重复</div><div style="margin-top:10px">%s</div></div><div class="col12"><div class="segments">%s</div></div></div></div>
        <div class="card"><h2>最相似历史记录（最多 20 条）</h2><div class="tablewrap"><table><thead><tr><th>历史 IP</th><th>相似度</th><th>交易所</th><th>录入用户</th><th>首次录入</th><th>最近查询</th></tr></thead><tbody>%s</tbody></table></div></div>
        <a class="btn secondary" href="/">返回继续查询</a>""" % (esc(raw_ip), exchange_display(exchange), highest, esc(exact_text), segments_html, rows)
        self.send_html(self.page(session, "查询结果", content, "home"))

    def wallet_check(self):
        session = self.require_user()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html(self.page(session, "请求失败", '<div class="flash err">请求已失效，请刷新页面重试。</div>'), 403)
        allowed, reason = can_query_local(session["user"])
        if not allowed:
            content = """<div class="card"><h2>当前账号尚未开通权限</h2><p class="muted">%s</p><div class="actions"><a class="btn" href="/membership#payment">立即开通</a><a class="btn secondary" href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">联系客服</a></div></div>""" % esc(reason)
            return self.send_html(self.page(session, "需要权限", content, "membership"), 403)
        address = form.get("address", "").strip()
        check_type = form.get("check_type", "wallet")
        if check_type not in ("wallet", "interaction"):
            check_type = "wallet"
        if not re.fullmatch(r"0x[a-fA-F0-9]{40}", address):
            return self.redirect("/?message=" + urllib.parse.quote("请输入合法的钱包地址或交互地址。"))
        lowered = address.lower()
        entropy = int(hashlib.sha256(lowered.encode("utf-8")).hexdigest()[:4], 16)
        risk_score = 18 + (entropy % 73)
        risk_label = "低" if risk_score < 45 else ("中" if risk_score < 72 else "高")
        interactions = 12 + (entropy % 120)
        protocols = ["DEX", "CEX", "Bridge", "NFT", "Lending"]
        result = {
            "risk": risk_label,
            "interactions": interactions,
            "protocol": protocols[entropy % len(protocols)],
            "note": "本地轻量画像：用于业务辅助筛查，不替代链上审计。",
        }
        ts = now()
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO wallet_checks(address,check_type,user_id,risk_score,result,created_at) VALUES(?,?,?,?,?,?)",
                (address, check_type, session["user"]["id"], risk_score, json.dumps(result, ensure_ascii=False), ts),
            )
            log_action(conn, session["user"]["id"], "WALLET_CHECK", "WALLET", cur.lastrowid, json.dumps({"address": address, "type": check_type, "risk": risk_score}, ensure_ascii=False))
        content = """<div class="card"><h2>%s检测结果</h2><div class="grid">
        <div class="col6"><div class="muted">检测地址</div><div class="stat" style="font-size:24px;word-break:break-all">%s</div></div>
        <div class="col2"><div class="muted">风险评分</div><div class="stat">%s</div></div>
        <div class="col2"><div class="muted">风险等级</div><div style="margin-top:10px"><span class="risk-score %s">%s</span></div></div>
        <div class="col2"><div class="muted">交互次数</div><div class="stat">%s</div></div>
        <div class="col12"><div class="segments"><span class="seg yes">主要协议：%s</span><span class="seg">画像来源：本地风控模型</span><span class="seg no">仅供风控参考</span></div></div>
        </div></div><a class="btn secondary" href="/">返回继续检测</a>""" % (
            "钱包地址" if check_type == "wallet" else "交互地址",
            esc(address),
            risk_score,
            "risk-low" if risk_score < 45 else ("risk-medium" if risk_score < 72 else "risk-high"),
            risk_label,
            interactions,
            esc(result["protocol"]),
        )
        self.send_html(self.page(session, "地址检测结果", content, "home"))

    def create_membership_order(self):
        session = self.require_user()
        if not session:
            return
        form = self.form()
        if not self.valid_csrf(session, form):
            return self.send_html(self.page(session, "请求失败", '<div class="flash err">请求已失效，请刷新页面重试。</div>'), 403)
        plan = form.get("plan", "").strip().upper()
        token = form.get("token", "USDT").strip().upper()
        if plan not in PLAN_CONFIG or token not in TOKEN_CONTRACTS:
            return self.redirect("/membership?message=" + urllib.parse.quote("请选择有效套餐和付款币种。"))
        ts = now()
        order_no = "YS" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + secrets.token_hex(3).upper()
        config = PLAN_CONFIG[plan]
        with db() as conn:
            conn.execute(
                "INSERT INTO membership_orders(order_no,user_id,plan,token,amount,receiver,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (order_no, session["user"]["id"], plan, token, config["price"], PAYMENT_RECEIVER, "PENDING", ts, ts),
            )
            log_action(conn, session["user"]["id"], "CREATE_ORDER", "MEMBERSHIP_ORDER", order_no, json.dumps({"plan": plan, "token": token, "amount": config["price"]}, ensure_ascii=False))
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
            expires_at = activate_membership(conn, session["user"]["id"], order["plan"])
            conn.execute("UPDATE membership_orders SET tx_hash=?,status='PAID',verify_detail=?,paid_at=?,updated_at=? WHERE id=?", (tx_hash, detail, ts, ts, order["id"]))
            log_action(conn, session["user"]["id"], "VERIFY_ORDER_PAID", "MEMBERSHIP_ORDER", order_no, detail)
        self.redirect("/membership?message=" + urllib.parse.quote("付款验证成功，会员已自动开通，到期时间：" + expires_at))

    def membership(self, query):
        session = self.require_user()
        if not session:
            return
        message = query.get("message", [""])[0]
        order_no = query.get("order", [""])[0]
        flash = '<div class="flash">%s</div>' % esc(message) if message else ""
        order = None
        if order_no:
            with db() as conn:
                order = conn.execute("SELECT * FROM membership_orders WHERE order_no=? AND user_id=?", (order_no, session["user"]["id"])).fetchone()
        plans = [
            ("plan-free", "", "基础入口", "普通用户", "0", "默认账户", ["可以注册、登录和浏览页面", "不能执行 IP 查询", "需要开通会员后使用查重功能"]),
            ("plan-starship", "STARSHIP", "热门开通", "星舰会员", "12", "USDT / USDC", ["全部 CEX 与 DEX", "会员周期内总查询 10 次", "开通日起一个自然月", "适合小团队环境管理"]),
            ("plan-pro", "PRO", "旗舰首选", "旗舰 PRO", "39.9", "USDT / USDC / 月", ["全部交易所", "无限查询与无限历史", "每月续费使用全部功能", "优先客服", "适合高频业务团队"]),
        ]
        plan_html = "".join(
            """<div class="card col4 plan-card %s"><span class="plan-badge">%s</span><h2>%s</h2><div><span class="plan-price">%s</span><span class="plan-unit"> %s</span></div><ul>%s</ul>%s</div>""" % (
                esc(style),
                esc(badge),
                esc(name),
                esc(price if price == "0" else "$" + price),
                esc(unit),
                "".join("<li>%s</li>" % esc(item) for item in features),
                "" if price == "0" else """<form method="post" action="/membership/create-order" class="plan-order-form"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="plan" value="%s"><select name="token"><option value="USDT">USDT</option><option value="USDC">USDC</option></select><button style="margin-top:14px">选择套餐并付款</button></form>""" % (esc(session["csrf"]), esc(plan_code)),
            )
            for style, plan_code, badge, name, price, unit, features in plans
        )
        if order:
            verify_html = """<div class="order-box"><div class="grid"><div class="col3"><label>订单号</label><input readonly value="%s" onclick="this.select()"></div><div class="col3"><label>套餐</label><input readonly value="%s"></div><div class="col3"><label>币种 / 网络</label><input readonly value="%s · BEP20"></div><div class="col3"><label>金额</label><input readonly value="%s"></div></div>
            <form method="post" action="/membership/verify" class="verify-form"><input type="hidden" name="csrf" value="%s"><input type="hidden" name="order_no" value="%s"><label>Transaction Hash</label><input name="tx_hash" placeholder="0x..." required><button>提交并自动检测付款</button></form></div>""" % (
                esc(order["order_no"]), esc(PLAN_CONFIG[order["plan"]]["name"]), esc(order["token"]), esc(order["amount"]), esc(session["csrf"]), esc(order["order_no"])
            )
        else:
            verify_html = '<div class="order-box muted">请先在上方选择套餐，系统会生成订单并跳转到这里。</div>'
        content = flash + """<div class="hero member-hero"><div><span class="hero-kicker">YS GOLD FINGER · ACCESS CONTROL</span><h2>权限中心</h2></div><img class="hero-logo" src="/assets/ck-logo.jpg" alt="原石金手指 LOGO"></div>
        <div class="risk-disclaimer">⚠️ 本系统提供 Web3 风控、IP 环境管理和行情辅助信息。所有行情分析、趋势判断、技术指标仅作为信息参考，不构成任何投资建议、交易建议或投资依据。</div>
        <div class="grid">%s</div>
        <div class="card payment-panel" id="payment"><h2>付款信息</h2><div class="grid"><div class="col6"><label>支付币种</label><div class="segments"><span class="chain-pill good">USDT</span><span class="chain-pill good">USDC</span><span class="chain-pill gold">BEP20 / BSC</span></div><p class="hint">请务必使用 BNB Smart Chain（BEP20）。其它网络付款无法自动确认。</p></div>
        <div class="col6 pay-address"><label>收款地址</label><input readonly value="%s" onclick="this.select()"><p class="hint">点击输入框可全选复制。</p></div></div>
        %s
        <p>如付款遇到问题，请联系：产品由 CK原石提供技术支持 ➡️TG <a href="https://t.me/mommo10338" target="_blank" rel="noopener noreferrer">@mommo10338</a>。</p>
        <p class="muted">系统会自动核对 Token、网络、金额、收款地址和交易 Hash；验证成功后立即开通对应会员权益。</p></div>""" % (
            plan_html, PAYMENT_RECEIVER, verify_html
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
            esc(r["full_ip"]), exchange_display(r["exchange"]), user_identity(r), status_badge(r["last_similarity"]), r["query_count"], esc(r["last_seen_at"]), delete(r)
        ) for r in records) or '<tr><td colspan="7" class="muted">没有符合条件的记录</td></tr>'
        q = {k: v[-1] for k, v in query.items() if k != "page"}
        pages = max(1, (total + 19) // 20)
        pager = "".join('<a href="/history?%s">%s</a>' % (urllib.parse.urlencode(dict(q, page=i)), i) for i in range(max(1, page - 2), min(pages, page + 2) + 1))
        val = lambda k: esc(query.get(k, [""])[0])
        content = """<div class="card"><form method="get" action="/history"><div class="grid">
        <div class="col3"><label>完整 IP</label><input name="ip" value="%s"></div><div class="col3"><label>A 段</label><input name="a" value="%s"></div><div class="col3"><label>B 段</label><input name="b" value="%s"></div><div class="col3"><label>C 段</label><input name="c" value="%s"></div>
        <div class="col3"><label>D 段</label><input name="d" value="%s"></div><div class="col3"><label>交易所</label>%s</div><div class="col3"><label>查询用户</label><input name="user" value="%s"></div><div class="col3"><label>相似度</label><select name="similarity"><option value="">全部</option>%s</select></div>
        <div class="col3"><label>开始日期</label><input type="date" name="from" value="%s"></div><div class="col3"><label>结束日期</label><input type="date" name="to" value="%s"></div><div class="col6 actions"><button>筛选</button><a class="btn secondary" href="/history">清空</a><a class="btn secondary" href="/history/export?%s">导出 CSV</a></div>
        </div></form></div><div class="card"><h2>共 %s 条记录</h2><div class="tablewrap"><table><thead><tr><th>IP</th><th>交易所</th><th>用户</th><th>相似度</th><th>次数</th><th>最近查询</th><th></th></tr></thead><tbody>%s</tbody></table></div><div class="pager">%s</div></div>""" % (
            val("ip"), val("a"), val("b"), val("c"), val("d"),
            exchange_picker(query.get("exchange", [""])[0], allow_all=True),
            val("user"), "".join('<option value="%s" %s>%s%%</option>' % (s, "selected" if val("similarity") == str(s) else "", s) for s in [100,75,50,25,0]),
            val("from"), val("to"), urllib.parse.urlencode(q), total, rows, pager
        )
        self.send_html(self.page(session, "查询历史", content, "history"))

    def export_csv(self, query):
        session = self.require_user()
        if not session:
            return
        where, params = self.history_filters(query)
        if not session["user"]["is_owner"]:
            if where:
                where += " AND r.user_id = ?"
            else:
                where = " WHERE r.user_id = ?"
            params.append(session["user"]["id"])
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
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">备用管理员仅拥有查询使用权，不能删除历史记录。</p></div>'), 403)
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
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">备用管理员仅拥有查询使用权，不能访问用户管理。</p></div>'), 403)
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
        rows = "".join("""<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>""" % (
            esc(u["username"]), "总管理员" if u["is_owner"] else ("备用管理员" if u["role"] == "ADMIN" else "普通用户"), "启用" if u["status"] == "ACTIVE" else "停用", esc(u["last_login_at"] or "从未"), actions(u)
        ) for u in users)
        admin_option = '<option value="ADMIN">备用管理员</option>' if session["user"]["is_owner"] else ""
        content = """%s%s<div class="card"><h2>创建用户</h2><form method="post" action="/users/create"><input type="hidden" name="csrf" value="%s"><div class="grid"><div class="col4"><label>用户名</label><input name="username" minlength="3" maxlength="40" pattern="[A-Za-z0-9_.\\-\u4e00-\u9fff]+" placeholder="支持中文、英文和数字" required></div><div class="col4"><label>初始密码</label><input name="password" type="password" minlength="10" maxlength="128" placeholder="至少 10 位" required></div><div class="col4"><label>角色</label><select name="role"><option value="USER">普通用户</option>%s</select></div><div class="col12"><p class="hint">用户名 3–40 位；密码至少 10 位。创建成功后会显示一次性恢复码。</p><button>创建</button></div></div></form></div>
        <div class="card"><h2>用户列表</h2><p class="muted">公开注册只能成为普通用户；备用管理员仅拥有查询使用权；只有总管理员可以管理账号。删除采用安全软删除，历史记录和操作日志仍会保留。</p><div class="tablewrap"><table><thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>最后登录</th><th>操作</th></tr></thead><tbody>%s</tbody></table></div></div>""" % (error_notice, recovery_notice, session["csrf"], admin_option, rows)
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
            return self.redirect("/users?error=" + urllib.parse.quote("只有总管理员可以创建备用管理员。"))
        recovery_code = secrets.token_urlsafe(18)
        try:
            with db() as conn:
                ts = now()
                cur = conn.execute("INSERT INTO users(username,password_hash,recovery_hash,role,is_owner,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (username, hash_password(password), hash_password(recovery_code), role, 0, "ACTIVE", ts, ts))
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
            recent = conn.execute(
                """SELECT r.full_ip,r.exchange,r.last_similarity,r.last_seen_at,u.username
                   FROM ip_records r JOIN users u ON u.id=r.user_id
                   ORDER BY r.last_seen_at DESC LIMIT 8"""
            ).fetchall()
        cards = [
            ("累计收款", "$0", "按已确认订单统计"),
            ("收款笔数", "0", "按已确认付款笔数统计"),
            ("星舰会员", "0", "当前有效星舰会员"),
            ("旗舰 PRO", "0", "当前有效旗舰 PRO 会员"),
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
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">备用管理员仅拥有查询使用权，不能查看操作日志。</p></div>'), 403)
            return
        with db() as conn:
            logs = conn.execute("""SELECT l.*,u.username FROM operation_logs l LEFT JOIN users u ON u.id=l.user_id ORDER BY l.created_at DESC LIMIT 500""").fetchall()
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s #%s</td><td>%s</td></tr>" % (
            esc(l["created_at"]), esc(l["username"] or "系统"), esc(l["action"]), esc(l["target_type"]), esc(l["target_id"]), esc(l["detail"])
        ) for l in logs) or '<tr><td colspan="5">暂无日志</td></tr>'
        content = '<div class="card"><h2>最近 500 条操作</h2><div class="tablewrap"><table><thead><tr><th>时间</th><th>用户</th><th>操作</th><th>对象</th><th>详情</th></tr></thead><tbody>%s</tbody></table></div></div>' % rows
        self.send_html(self.page(session, "操作日志", content, "logs"))

    def settings(self, query):
        session = self.require_user(admin=True)
        if not session:
            return
        if not session["user"]["is_owner"]:
            self.send_html(self.page(session, "无权访问", '<div class="card"><h2>需要总管理员权限</h2><p class="muted">备用管理员仅拥有查询使用权，不能访问系统设置。</p></div>'), 403)
            return
        message = query.get("message", [""])[0]
        flash = '<div class="flash">%s</div>' % esc(message) if message else ""
        with db() as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            record_count = conn.execute("SELECT COUNT(*) FROM ip_records").fetchone()[0]
            log_count = conn.execute("SELECT COUNT(*) FROM operation_logs").fetchone()[0]
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
        content = flash + """<div class="grid"><div class="card col4"><div class="muted">用户数</div><div class="stat">%s</div></div><div class="card col4"><div class="muted">IP 记录数</div><div class="stat">%s</div></div><div class="card col4"><div class="muted">操作日志数</div><div class="stat">%s</div></div></div>
        %s%s<div class="card"><h2>系统运行信息</h2><p>服务端口：<code>3000</code></p><p>数据目录：<code>local_data</code></p><p class="muted">请定期备份数据目录，避免误删或服务器故障造成数据丢失。</p></div>""" % (user_count, record_count, log_count, smtp_card, cmc_card)
        self.send_html(self.page(session, "系统设置", content, "settings"))

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
