import sqlite3
import os
import uuid
from datetime import datetime
from typing import Optional
from config import DATABASE_PATH, DEFAULT_SETTINGS, ENV_ADMIN_IDS, CURRENCY, logger


def _now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    photo_path TEXT,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    photo_path TEXT,
                    price_usd REAL NOT NULL DEFAULT 0.0,
                    qr_path TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    duration_label TEXT NOT NULL DEFAULT '',
                    price_usd REAL NOT NULL,
                    qr_path TEXT,
                    payment_note TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS stock_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    package_id INTEGER,
                    content_type TEXT NOT NULL DEFAULT 'key',
                    content TEXT NOT NULL,
                    file_path TEXT,
                    is_used INTEGER NOT NULL DEFAULT 0,
                    is_available INTEGER NOT NULL DEFAULT 1,
                    used_by_order_id TEXT,
                    created_at TEXT NOT NULL,
                    used_at TEXT,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                    FOREIGN KEY (package_id) REFERENCES packages(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    category_id INTEGER,
                    product_id INTEGER NOT NULL,
                    package_id INTEGER,
                    product_name TEXT NOT NULL,
                    package_name TEXT NOT NULL,
                    price_usd REAL NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    payment_status TEXT NOT NULL DEFAULT 'Unpaid',
                    order_status TEXT NOT NULL DEFAULT 'Pending Payment',
                    delivered_type TEXT,
                    delivered_content TEXT,
                    delivered_file_path TEXT,
                    delivery_error TEXT,
                    action_by_admin INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (product_id) REFERENCES products(id),
                    FOREIGN KEY (package_id) REFERENCES packages(id)
                );

                CREATE TABLE IF NOT EXISTS payment_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    amount_usd REAL NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    source_type TEXT NOT NULL,
                    source_ref TEXT,
                    verification_status TEXT NOT NULL DEFAULT 'Pending',
                    verified_by INTEGER,
                    raw_note TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                );

                CREATE TABLE IF NOT EXISTS processed_notifications (
                    notification_hash TEXT PRIMARY KEY,
                    order_id TEXT,
                    source_chat_id INTEGER,
                    created_at TEXT NOT NULL
                );
                """
            )
            now = _now_str()
            for key, val in DEFAULT_SETTINGS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, val, now),
                )
            for admin_id in ENV_ADMIN_IDS:
                conn.execute(
                    "INSERT OR IGNORE INTO admins (user_id, added_by, created_at) VALUES (?, ?, ?)",
                    (admin_id, admin_id, now),
                )
            self._seed_default_mods_if_empty(conn, now)

    def _seed_default_mods_if_empty(self, conn: sqlite3.Connection, now: str) -> None:
        cat_row = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()
        if int(cat_row["c"]) > 0:
            return

        cur_cat = conn.execute(
            "INSERT INTO categories (name, description, photo_path, sort_order, is_active, created_at) VALUES (?, ?, NULL, 1, 1, ?)",
            ("MODS & CERTIFICATES", "ជ្រើសរើសម៉ូត និងកញ្ចប់ដែលអ្នកត្រូវការ", now),
        )
        cat_id = int(cur_cat.lastrowid)

        mods_10 = [
            "PHANTOM (ios & android)",
            "E-SIGN-Certificate (iPA)",
            "VPN PROXY.VIP",
            "AIRLIFT MOD IPA",
            "PROXY THIS.VIP",
            "INNOVA CHEAT",
            "REZZ PANEL",
            "DRIP WIRE",
            "PRIMEKO",
            "VIP MOD STORE",
        ]
        default_packages = [
            ("1ម៉ោង", "1ម៉ោង", 0.25),
            ("3ម៉ោង", "3ម៉ោង", 0.69),
            ("6ម៉ោង", "6ម៉ោង", 1.20),
            ("12ម៉ោង", "12ម៉ោង", 2.00),
        ]

        for idx, mod_name in enumerate(mods_10, start=1):
            cur_p = conn.execute(
                """
                INSERT INTO products (category_id, name, description, photo_path, price_usd, qr_path, is_active, sort_order, created_at)
                VALUES (?, ?, ?, NULL, 0.25, NULL, 1, ?, ?)
                """,
                (cat_id, mod_name, f"កញ្ចប់សម្រាប់ {mod_name} — ទទួល KEY / ហ្វាល់ អូតូ", idx, now),
            )
            prod_id = int(cur_p.lastrowid)
            for pkg_name, dur_label, price_val in default_packages:
                conn.execute(
                    """
                    INSERT INTO packages (product_id, name, duration_label, price_usd, qr_path, payment_note, is_active, created_at)
                    VALUES (?, ?, ?, ?, NULL, NULL, 1, ?)
                    """,
                    (prod_id, pkg_name, dur_label, price_val, now),
                )

    def upsert_user(self, user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]) -> None:
        now = _now_str()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name, created_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_seen = excluded.last_seen
                """,
                (user_id, username, first_name, last_name, now, now),
            )

    def is_admin(self, user_id: int) -> bool:
        if user_id in ENV_ADMIN_IDS:
            return True
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone()
            return row is not None

    def list_admins(self) -> list[int]:
        ids = set(ENV_ADMIN_IDS)
        with self._connect() as conn:
            for r in conn.execute("SELECT user_id FROM admins").fetchall():
                ids.add(int(r["user_id"]))
        return sorted(ids)

    def add_admin(self, target_user_id: int, added_by: int) -> bool:
        now = _now_str()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO admins (user_id, added_by, created_at) VALUES (?, ?, ?)",
                (target_user_id, added_by, now),
            )
        return True

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        now = _now_str()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def get_categories(self, include_inactive: bool = False) -> list[sqlite3.Row]:
        with self._connect() as conn:
            if include_inactive:
                return conn.execute("SELECT * FROM categories ORDER BY sort_order ASC, id ASC").fetchall()
            return conn.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY sort_order ASC, id ASC").fetchall()

    def get_category(self, category_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()

    def create_category(self, name: str, description: str = "", photo_path: Optional[str] = None) -> int:
        now = _now_str()
        with self._connect() as conn:
            max_row = conn.execute("SELECT COALESCE(MAX(sort_order), 0) AS m FROM categories").fetchone()
            next_order = int(max_row["m"]) + 1
            cur = conn.execute(
                "INSERT INTO categories (name, description, photo_path, sort_order, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                (name.strip(), description.strip(), photo_path, next_order, now),
            )
            return int(cur.lastrowid)

    def update_category(self, category_id: int, **kwargs) -> bool:
        allowed = {"name", "description", "photo_path", "sort_order", "is_active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE categories SET {set_clause} WHERE id = ?", list(updates.values()) + [category_id])
            return cur.rowcount > 0

    def delete_category(self, category_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            return cur.rowcount > 0

    def swap_category_order(self, cat_a_id: int, cat_b_id: int) -> bool:
        with self._connect() as conn:
            a = conn.execute("SELECT id, sort_order FROM categories WHERE id = ?", (cat_a_id,)).fetchone()
            b = conn.execute("SELECT id, sort_order FROM categories WHERE id = ?", (cat_b_id,)).fetchone()
            if not a or not b:
                return False
            conn.execute("UPDATE categories SET sort_order = ? WHERE id = ?", (b["sort_order"], a["id"]))
            conn.execute("UPDATE categories SET sort_order = ? WHERE id = ?", (a["sort_order"], b["id"]))
            return True

    def get_products_by_category(self, category_id: int, include_inactive: bool = False) -> list[sqlite3.Row]:
        with self._connect() as conn:
            if include_inactive:
                return conn.execute("SELECT * FROM products WHERE category_id = ? ORDER BY sort_order ASC, id ASC", (category_id,)).fetchall()
            return conn.execute("SELECT * FROM products WHERE category_id = ? AND is_active = 1 ORDER BY sort_order ASC, id ASC", (category_id,)).fetchall()

    def get_all_products(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM products ORDER BY sort_order ASC, id ASC").fetchall()

    def get_product(self, product_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    def create_product(
        self,
        category_id: int,
        name: str,
        description: str = "",
        price_usd: float = 0.0,
        photo_path: Optional[str] = None,
        qr_path: Optional[str] = None,
    ) -> int:
        now = _now_str()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO products (category_id, name, description, photo_path, price_usd, qr_path, is_active, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?)
                """,
                (category_id, name.strip(), description.strip(), photo_path, float(price_usd), qr_path, now),
            )
            return int(cur.lastrowid)

    def update_product(self, product_id: int, **kwargs) -> bool:
        allowed = {"name", "description", "photo_path", "price_usd", "qr_path", "is_active", "category_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE products SET {set_clause} WHERE id = ?", list(updates.values()) + [product_id])
            return cur.rowcount > 0

    def delete_product(self, product_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            return cur.rowcount > 0

    def get_packages_by_product(self, product_id: int, include_inactive: bool = False) -> list[sqlite3.Row]:
        with self._connect() as conn:
            if include_inactive:
                return conn.execute("SELECT * FROM packages WHERE product_id = ? ORDER BY price_usd ASC, id ASC", (product_id,)).fetchall()
            return conn.execute("SELECT * FROM packages WHERE product_id = ? AND is_active = 1 ORDER BY price_usd ASC, id ASC", (product_id,)).fetchall()

    def get_package(self, package_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()

    def create_package(
        self,
        product_id: int,
        name: str,
        price_usd: float,
        duration_label: str = "",
        qr_path: Optional[str] = None,
        payment_note: Optional[str] = None,
    ) -> int:
        now = _now_str()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO packages (product_id, name, duration_label, price_usd, qr_path, payment_note, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (product_id, name.strip(), duration_label.strip(), float(price_usd), qr_path, payment_note, now),
            )
            return int(cur.lastrowid)

    def update_package(self, package_id: int, **kwargs) -> bool:
        allowed = {"name", "duration_label", "price_usd", "qr_path", "payment_note", "is_active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE packages SET {set_clause} WHERE id = ?", list(updates.values()) + [package_id])
            return cur.rowcount > 0

    def get_stock_count(self, product_id: int, package_id: Optional[int] = None) -> int:
        with self._connect() as conn:
            if package_id is not None and package_id > 0:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM stock_items WHERE product_id = ? AND package_id = ? AND is_used = 0 AND is_available = 1",
                    (product_id, package_id),
                ).fetchone()
                cnt = int(row["cnt"]) if row else 0
                if cnt > 0:
                    return cnt
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM stock_items WHERE product_id = ? AND is_used = 0 AND is_available = 1",
                (product_id,),
            ).fetchone()
            return int(row["cnt"]) if row else 0

    def list_stock_items(self, product_id: int, include_used: bool = False) -> list[sqlite3.Row]:
        with self._connect() as conn:
            if include_used:
                return conn.execute("SELECT * FROM stock_items WHERE product_id = ? ORDER BY id ASC", (product_id,)).fetchall()
            return conn.execute("SELECT * FROM stock_items WHERE product_id = ? AND is_used = 0 ORDER BY id ASC", (product_id,)).fetchall()

    def add_stock_entries(
        self,
        product_id: int,
        entries: list[str],
        package_id: Optional[int] = None,
        content_type: str = "key",
        file_path: Optional[str] = None,
    ) -> int:
        now = _now_str()
        clean_entries = [e.strip() for e in entries if e and e.strip()]
        if not clean_entries:
            return 0
        pkg_val = package_id if (package_id and package_id > 0) else None
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO stock_items (product_id, package_id, content_type, content, file_path, is_used, is_available, created_at)
                VALUES (?, ?, ?, ?, ?, 0, 1, ?)
                """,
                [(product_id, pkg_val, content_type, item, file_path, now) for item in clean_entries],
            )
        return len(clean_entries)

    def clear_unused_stock(self, product_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM stock_items WHERE product_id = ? AND is_used = 0", (product_id,))
            return cur.rowcount

    def claim_stock_for_order(self, order_id: str, product_id: int, package_id: Optional[int]) -> Optional[dict]:
        now = _now_str()
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            order_row = conn.execute(
                "SELECT order_status, delivered_type, delivered_content, delivered_file_path FROM orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
            if not order_row:
                conn.execute("ROLLBACK")
                return None
            if order_row["delivered_content"] or order_row["delivered_file_path"]:
                conn.execute("ROLLBACK")
                return {
                    "content_type": order_row["delivered_type"] or "key",
                    "content": order_row["delivered_content"] or "",
                    "file_path": order_row["delivered_file_path"],
                }

            stock_row = None
            if package_id is not None and package_id > 0:
                stock_row = conn.execute(
                    """
                    SELECT id, content_type, content, file_path FROM stock_items
                    WHERE product_id = ? AND package_id = ? AND is_used = 0 AND is_available = 1
                    ORDER BY id ASC LIMIT 1
                    """,
                    (product_id, package_id),
                ).fetchone()
            if not stock_row:
                stock_row = conn.execute(
                    """
                    SELECT id, content_type, content, file_path FROM stock_items
                    WHERE product_id = ? AND is_used = 0 AND is_available = 1
                    ORDER BY id ASC LIMIT 1
                    """,
                    (product_id,),
                ).fetchone()

            if not stock_row:
                conn.execute("ROLLBACK")
                return None

            c_type = str(stock_row["content_type"] or "key")
            content = str(stock_row["content"] or "")
            f_path = stock_row["file_path"]

            conn.execute(
                "UPDATE stock_items SET is_used = 1, is_available = 0, used_by_order_id = ?, used_at = ? WHERE id = ? AND is_used = 0",
                (order_id, now, stock_row["id"]),
            )
            conn.execute(
                """
                UPDATE orders
                SET delivered_type = ?, delivered_content = ?, delivered_file_path = ?, delivery_error = NULL,
                    order_status = 'Completed', payment_status = 'Verified', updated_at = ?
                WHERE order_id = ?
                """,
                (c_type, content, f_path, now, order_id),
            )
            conn.execute("COMMIT")
            return {"content_type": c_type, "content": content, "file_path": f_path}
        except Exception as exc:
            logger.error("Failed claiming stock for order %s: %s", order_id, exc)
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            return None
        finally:
            conn.close()

    def create_order(
        self,
        user_id: int,
        username: Optional[str],
        category_id: Optional[int],
        product_id: int,
        package_id: Optional[int],
        product_name: str,
        package_name: str,
        price_usd: float,
    ) -> Optional[dict]:
        now = _now_str()
        order_id = f"BD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name, created_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET last_seen = excluded.last_seen
                """,
                (user_id, username, None, None, now, now),
            )
            existing = conn.execute(
                """
                SELECT * FROM orders
                WHERE user_id = ? AND product_id = ? AND COALESCE(package_id, 0) = COALESCE(?, 0)
                  AND order_status IN ('Pending Payment', 'Awaiting Verification')
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, product_id, package_id),
            ).fetchone()
            if existing:
                return dict(existing)

            conn.execute(
                """
                INSERT INTO orders (
                    order_id, user_id, username, category_id, product_id, package_id,
                    product_name, package_name, price_usd, currency,
                    payment_status, order_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Unpaid', 'Pending Payment', ?, ?)
                """,
                (
                    order_id, user_id, username, category_id, product_id, package_id,
                    product_name, package_name, float(price_usd), CURRENCY, now, now,
                ),
            )
            row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            return dict(row) if row else None

    def get_order(self, order_id: str) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id.strip(),)).fetchone()

    def get_user_orders(self, user_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()

    def list_orders(self, status_filter: Optional[str] = None, limit: int = 30) -> list[sqlite3.Row]:
        with self._connect() as conn:
            if status_filter and status_filter != "ALL":
                return conn.execute("SELECT * FROM orders WHERE order_status = ? ORDER BY created_at DESC LIMIT ?", (status_filter, limit)).fetchall()
            return conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()

    def mark_awaiting_verification(self, order_id: str, user_id: int) -> Optional[sqlite3.Row]:
        now = _now_str()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orders WHERE order_id = ? AND user_id = ?", (order_id, user_id)).fetchone()
            if not row:
                return None
            if row["order_status"] in ("Completed", "Cancelled", "Expired"):
                return row
            conn.execute(
                "UPDATE orders SET order_status = 'Awaiting Verification', payment_status = 'Customer Claimed', updated_at = ? WHERE order_id = ? AND user_id = ?",
                (now, order_id, user_id),
            )
            return conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()

    def update_order_status(
        self,
        order_id: str,
        new_status: str,
        payment_status: Optional[str] = None,
        admin_id: Optional[int] = None,
        delivery_error: Optional[str] = None,
    ) -> bool:
        now = _now_str()
        with self._connect() as conn:
            row = conn.execute("SELECT order_status FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if not row:
                return False
            if row["order_status"] == "Completed" and new_status != "Completed":
                return False
            p_status = payment_status
            if p_status is None:
                if new_status in ("Confirmed", "Completed"):
                    p_status = "Verified"
                elif new_status == "Cancelled":
                    p_status = "Cancelled"
                elif new_status == "Expired":
                    p_status = "Expired"
            if p_status is not None:
                conn.execute(
                    """
                    UPDATE orders
                    SET order_status = ?, payment_status = ?, action_by_admin = COALESCE(?, action_by_admin),
                        delivery_error = COALESCE(?, delivery_error), updated_at = ?
                    WHERE order_id = ?
                    """,
                    (new_status, p_status, admin_id, delivery_error, now, order_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE orders
                    SET order_status = ?, action_by_admin = COALESCE(?, action_by_admin),
                        delivery_error = COALESCE(?, delivery_error), updated_at = ?
                    WHERE order_id = ?
                    """,
                    (new_status, admin_id, delivery_error, now, order_id),
                )
            return True

    def add_payment_record(
        self,
        order_id: str,
        user_id: int,
        amount_usd: float,
        currency: str,
        source_type: str,
        source_ref: Optional[str] = None,
        verification_status: str = "Pending",
        verified_by: Optional[int] = None,
        raw_note: Optional[str] = None,
    ) -> int:
        now = _now_str()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO payment_records (
                    order_id, user_id, amount_usd, currency, source_type, source_ref,
                    verification_status, verified_by, raw_note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id, user_id, float(amount_usd), currency, source_type,
                    source_ref, verification_status, verified_by, raw_note, now,
                ),
            )
            return int(cur.lastrowid)

    def get_payment_records_for_order(self, order_id: str) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM payment_records WHERE order_id = ? ORDER BY id DESC", (order_id,)).fetchall()

    def is_notification_processed(self, notif_hash: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM processed_notifications WHERE notification_hash = ?", (notif_hash,)).fetchone()
            return row is not None

    def mark_notification_processed(self, notif_hash: str, order_id: Optional[str], source_chat_id: Optional[int]) -> None:
        now = _now_str()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_notifications (notification_hash, order_id, source_chat_id, created_at) VALUES (?, ?, ?, ?)",
                (notif_hash, order_id, source_chat_id, now),
            )

    def get_statistics(self) -> dict:
        with self._connect() as conn:
            total_users = int(conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"])
            total_orders = int(conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"])
            pending_orders = int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM orders WHERE order_status IN ('Pending Payment', 'Awaiting Verification', 'Confirmed')"
                ).fetchone()["c"]
            )
            completed_orders = int(conn.execute("SELECT COUNT(*) AS c FROM orders WHERE order_status = 'Completed'").fetchone()["c"])
            cancelled_orders = int(conn.execute("SELECT COUNT(*) AS c FROM orders WHERE order_status IN ('Cancelled', 'Expired')").fetchone()["c"])
            sales_row = conn.execute("SELECT COALESCE(SUM(price_usd), 0.0) AS s FROM orders WHERE order_status IN ('Confirmed', 'Completed')").fetchone()
            total_sales = float(sales_row["s"]) if sales_row else 0.0
            stock_row = conn.execute("SELECT COUNT(*) AS c FROM stock_items WHERE is_used = 0 AND is_available = 1").fetchone()
            available_stock = int(stock_row["c"]) if stock_row else 0

        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "completed_orders": completed_orders,
            "cancelled_orders": cancelled_orders,
            "available_stock": available_stock,
            "total_sales_usd": total_sales,
        }
