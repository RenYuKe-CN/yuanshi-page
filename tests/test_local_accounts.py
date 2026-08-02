import importlib.util
import os
import re
import tempfile
import types
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = importlib.util.spec_from_file_location("ys_local_app", os.path.join(ROOT, "local_app.py"))
APP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APP)


class LocalAccountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        APP.DATA_DIR = self.temp.name
        APP.DB_PATH = os.path.join(self.temp.name, "test.db")
        APP.ADMIN_FILE = os.path.join(self.temp.name, "admin.txt")
        APP.CMC_KEY_FILE = os.path.join(self.temp.name, "cmc_api_key.txt")
        APP.CMC_ICON_DIR = os.path.join(self.temp.name, "exchange_icons")
        APP.CMC_ICON_MAP_FILE = os.path.join(self.temp.name, "exchange_icons.json")
        APP.SESSIONS.clear()
        APP.RATE_LIMITS.clear()
        APP.init_db()

    def tearDown(self):
        self.temp.cleanup()

    def handler(self, form):
        result = {}
        handler = object.__new__(APP.App)
        handler.client_address = ("127.0.0.1", 10000)
        handler.form = types.MethodType(lambda self: form, handler)
        handler.send_html = types.MethodType(
            lambda self, content, status=200, headers=None: result.update(content=content, status=status),
            handler,
        )
        return handler, result

    def test_registration_is_always_regular_user_and_recovery_rotates(self):
        with APP.db() as conn:
            conn.execute(
                "INSERT INTO email_verification_codes(email,code_hash,purpose,expires_at,created_at) VALUES(?,?,?,?,?)",
                ("operator01@gmail.com", APP.hash_password("123456"), "REGISTER", "2099-01-01 00:00:00", APP.now()),
            )
        handler, result = self.handler(
            {
                "username": "operator01",
                "email_local": "operator01",
                "email_domain": "@gmail.com",
                "email_code": "123456",
                "password": "StrongPass!123",
                "confirm_password": "StrongPass!123",
                "accepted_statement": "1",
            }
        )
        handler.register()
        self.assertEqual(result["status"], 201)
        recovery_code = re.search(r"<strong>密码恢复码：</strong><br>([^<]+)", result["content"]).group(1)
        with APP.db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username='operator01'").fetchone()
        self.assertEqual(user["role"], "USER")
        self.assertEqual(user["is_owner"], 0)
        self.assertEqual(user["email"], "operator01@gmail.com")

        handler, result = self.handler(
            {
                "username": "operator01",
                "recovery_code": recovery_code,
                "password": "NewStrong!456",
                "confirm_password": "NewStrong!456",
            }
        )
        handler.recover()
        self.assertIn("新密码恢复码", result["content"])
        with APP.db() as conn:
            changed = conn.execute("SELECT * FROM users WHERE username='operator01'").fetchone()
        self.assertFalse(APP.verify_password("StrongPass!123", changed["password_hash"]))
        self.assertTrue(APP.verify_password("NewStrong!456", changed["password_hash"]))

    def test_registration_requires_allowed_email_and_statement(self):
        handler, result = self.handler(
            {
                "username": "operator02",
                "email": "operator02@example.com",
                "password": "StrongPass!123",
                "confirm_password": "StrongPass!123",
                "accepted_statement": "1",
            }
        )
        handler.register()
        self.assertEqual(result["status"], 400)
        self.assertIn("指定主流邮箱", result["content"])

        handler, result = self.handler(
            {
                "username": "operator03",
                "email": "operator03@qq.com",
                "password": "StrongPass!123",
                "confirm_password": "StrongPass!123",
            }
        )
        handler.register()
        self.assertEqual(result["status"], 400)
        self.assertIn("用户注册声明", result["content"])

    def test_owner_can_create_chinese_named_backup_admin_and_errors_are_visible(self):
        with APP.db() as conn:
            owner = conn.execute("SELECT * FROM users WHERE is_owner=1").fetchone()
        handler, result = self.handler(
            {"csrf": "token", "username": "备用管理员", "password": "StrongPass!123", "role": "ADMIN"}
        )
        handler.require_user = types.MethodType(
            lambda self, admin=False: {"token": "session", "csrf": "token", "user": owner},
            handler,
        )
        handler.valid_csrf = types.MethodType(lambda self, session, form: True, handler)
        handler.redirect = types.MethodType(lambda self, location: result.update(location=location), handler)
        handler.create_user()
        self.assertIn("created_for=", result["location"])
        with APP.db() as conn:
            created = conn.execute("SELECT * FROM users WHERE username='备用管理员'").fetchone()
        self.assertEqual(created["role"], "ADMIN")

        handler, result = self.handler(
            {"csrf": "token", "username": "短", "password": "123", "role": "ADMIN"}
        )
        handler.require_user = types.MethodType(
            lambda self, admin=False: {"token": "session", "csrf": "token", "user": owner},
            handler,
        )
        handler.valid_csrf = types.MethodType(lambda self, session, form: True, handler)
        handler.redirect = types.MethodType(lambda self, location: result.update(location=location), handler)
        handler.create_user()
        self.assertIn("error=", result["location"])

    def test_permission_matrix_for_deleting_users(self):
        with APP.db() as conn:
            owner = conn.execute("SELECT * FROM users WHERE is_owner=1").fetchone()
            timestamp = APP.now()
            backup_id = conn.execute(
                "INSERT INTO users(username,password_hash,role,is_owner,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                ("backup", APP.hash_password("BackupPass!123"), "ADMIN", 0, "ACTIVE", timestamp, timestamp),
            ).lastrowid
            backup2_id = conn.execute(
                "INSERT INTO users(username,password_hash,role,is_owner,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                ("backup2", APP.hash_password("BackupPass!456"), "ADMIN", 0, "ACTIVE", timestamp, timestamp),
            ).lastrowid
            user_id = conn.execute(
                "INSERT INTO users(username,password_hash,role,is_owner,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                ("normal", APP.hash_password("NormalPass!123"), "USER", 0, "ACTIVE", timestamp, timestamp),
            ).lastrowid
            backup = conn.execute("SELECT * FROM users WHERE id=?", (backup_id,)).fetchone()

        self.delete_as(backup, user_id)
        with APP.db() as conn:
            self.assertIsNone(conn.execute("SELECT deleted_at FROM users WHERE id=?", (user_id,)).fetchone()["deleted_at"])

        self.delete_as(backup, backup2_id)
        with APP.db() as conn:
            self.assertIsNone(conn.execute("SELECT deleted_at FROM users WHERE id=?", (backup2_id,)).fetchone()["deleted_at"])

        self.delete_as(owner, user_id)
        with APP.db() as conn:
            self.assertIsNotNone(conn.execute("SELECT deleted_at FROM users WHERE id=?", (user_id,)).fetchone()["deleted_at"])

        self.delete_as(owner, backup2_id)
        with APP.db() as conn:
            self.assertIsNotNone(conn.execute("SELECT deleted_at FROM users WHERE id=?", (backup2_id,)).fetchone()["deleted_at"])
            self.assertIsNone(conn.execute("SELECT deleted_at FROM users WHERE id=?", (owner["id"],)).fetchone()["deleted_at"])

    def test_backup_admin_cannot_view_owner_only_pages(self):
        with APP.db() as conn:
            timestamp = APP.now()
            backup_id = conn.execute(
                "INSERT INTO users(username,password_hash,role,is_owner,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                ("backup", APP.hash_password("BackupPass!123"), "ADMIN", 0, "ACTIVE", timestamp, timestamp),
            ).lastrowid
            backup = conn.execute("SELECT * FROM users WHERE id=?", (backup_id,)).fetchone()

        session = {"token": "session", "csrf": "token", "user": backup}
        html = object.__new__(APP.App).page(session, "IP 查重", "", "home")
        self.assertNotIn("会员数据", html)
        self.assertNotIn("用户管理", html)
        self.assertNotIn("操作日志", html)
        self.assertNotIn("系统设置", html)

        for method_name in ("analytics", "users", "logs", "settings"):
            handler, result = self.handler({})
            handler.require_user = types.MethodType(lambda self, admin=False: session, handler)
            getattr(handler, method_name)({})
            self.assertEqual(result["status"], 403)
            self.assertIn("需要总管理员权限", result["content"])

    def test_exchange_catalog_is_complete_and_grouped(self):
        self.assertEqual(len(APP.CEX_EXCHANGES), 98)
        self.assertEqual(len(APP.DEX_EXCHANGES), 67)
        self.assertEqual(len(APP.EXCHANGES), 166)
        self.assertEqual(len(set(APP.EXCHANGES)), 166)
        self.assertIn("Binance", APP.CEX_EXCHANGES)
        self.assertIn("Bitrue", APP.CEX_EXCHANGES)
        self.assertIn("Uniswap", APP.DEX_EXCHANGES)
        self.assertIn("FX100", APP.DEX_EXCHANGES)
        self.assertIn("其他", APP.EXCHANGES)
        picker = APP.exchange_picker("Bitrue")
        self.assertIn("CEX 中心化交易所", picker)
        self.assertIn("DEX 去中心化交易所", picker)
        self.assertEqual(picker.count('class="exchange-option"'), 166)
        self.assertEqual(len(re.findall(r'class="exchange-icon(?:\s|")', picker)), 167)
        self.assertIn('/assets/exchange-fx-protocol.png', picker)
        self.assertIn('/assets/exchange-fx100.png', picker)
        empty_picker = APP.exchange_picker()
        self.assertIn("请选择交易所", empty_picker)
        self.assertNotIn(" checked ", empty_picker)
        history_picker = APP.exchange_picker("", allow_all=True)
        self.assertIn("全部交易所", history_picker)
        self.assertIn('value="" checked', history_picker)
        self.assertEqual(len(APP.BUSINESS_ITEMS), 9)
        self.assertIn(("⌕", "交易所流动性提供"), APP.BUSINESS_ITEMS)

    def test_same_ip_can_be_saved_for_cex_dex_and_other(self):
        with APP.db() as conn:
            owner = conn.execute("SELECT * FROM users WHERE is_owner=1").fetchone()
        for exchange in ("Binance", "Uniswap", "其他"):
            handler, result = self.handler({"csrf": "token", "ip": "192.168.10.20", "exchange": exchange})
            handler.require_user = types.MethodType(
                lambda self, admin=False: {"token": "session", "csrf": "token", "user": owner},
                handler,
            )
            handler.valid_csrf = types.MethodType(lambda self, session, form: True, handler)
            handler.redirect = types.MethodType(lambda self, location, cookie=None: result.update(redirect=location), handler)
            handler.query_ip()
            self.assertEqual(result["status"], 200)
        with APP.db() as conn:
            rows = conn.execute(
                "SELECT exchange FROM ip_records WHERE full_ip=? ORDER BY exchange",
                ("192.168.10.20",),
            ).fetchall()
        self.assertEqual({row["exchange"] for row in rows}, {"Binance", "Uniswap", "其他"})

    def test_cmc_matching_and_local_icon_fallback(self):
        objects = [
            {"id": 270, "name": "Binance"},
            {"id": 302, "name": "Gate.io"},
            {"id": 11955, "name": "Uniswap v4 (Ethereum)"},
        ]
        matched = APP.match_cmc_objects(objects)
        self.assertEqual(matched["Binance"]["id"], 270)
        self.assertEqual(matched["Gate"]["id"], 302)
        self.assertEqual(matched["Uniswap"]["id"], 11955)
        self.assertIn("<img", APP.exchange_icon_markup("Binance"))
        self.assertIn("/assets/exchanges/", APP.exchange_icon_markup("Binance"))
        filename = "a" * 32 + ".png"
        with open(APP.CMC_ICON_MAP_FILE, "w", encoding="utf-8") as file:
            file.write('{"Binance":"%s"}' % filename)
        markup = APP.exchange_icon_markup("Binance")
        self.assertNotIn(filename, markup)
        self.assertIn('<span class="exchange-icon"', markup)
        os.remove(APP.CMC_ICON_MAP_FILE)

    def test_only_owner_can_save_cmc_key_and_key_is_not_logged(self):
        with APP.db() as conn:
            owner = conn.execute("SELECT * FROM users WHERE is_owner=1").fetchone()
        key = "private-cmc-key-123456789"
        handler, result = self.handler({"csrf": "token", "api_key": key})
        handler.require_user = types.MethodType(
            lambda self, admin=False: {"token": "session", "csrf": "token", "user": owner},
            handler,
        )
        handler.valid_csrf = types.MethodType(lambda self, session, form: True, handler)
        handler.redirect = types.MethodType(lambda self, location, cookie=None: result.update(redirect=location), handler)
        handler.save_cmc_key()
        with open(APP.CMC_KEY_FILE, "r", encoding="utf-8") as file:
            self.assertEqual(file.read(), key)
        self.assertEqual(os.stat(APP.CMC_KEY_FILE).st_mode & 0o777, 0o600)
        with APP.db() as conn:
            detail = conn.execute("SELECT detail FROM operation_logs WHERE action='SAVE_CMC_KEY'").fetchone()["detail"]
        self.assertNotIn(key, detail)

    def delete_as(self, actor, target_id):
        handler, result = self.handler({"csrf": "token", "id": str(target_id)})
        handler.require_user = types.MethodType(
            lambda self, admin=False: {"token": "session", "csrf": "token", "user": actor},
            handler,
        )
        handler.valid_csrf = types.MethodType(lambda self, session, form: True, handler)
        handler.redirect = types.MethodType(lambda self, location, cookie=None: result.update(redirect=location), handler)
        handler.delete_user()


if __name__ == "__main__":
    unittest.main()
