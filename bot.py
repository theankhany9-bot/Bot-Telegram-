import json
import math
import os
import re
import sys
import telebot
from telebot import types

# ================= ការកំណត់សំខាន់ៗ =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
FILES_DIR = os.path.join(DATA_DIR, "files")
DATA_FILE = os.path.join(DATA_DIR, "data.json")
os.makedirs(FILES_DIR, exist_ok=True)


def _load_dotenv_if_present() -> None:
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


_load_dotenv_if_present()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "6214336913"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "PUVIN009").lstrip("@").strip()
ABA_GROUP_ID = int(os.getenv("ABA_GROUP_ID", "-1003803639749"))
# =================================================

if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    print("❌ ERROR: មិនទាន់បានកំណត់ BOT_TOKEN ទេ!")
    print("👉 សូមកំណត់ BOT_TOKEN ក្នុង environment variable ឬឯកសារ .env (ឧ. BOT_TOKEN=123456:ABC...)")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
admin_states = {}
user_states = {}
pending_purchases = {}


def make_btn(text, callback_data=None, url=None, style=None, custom_emoji_id=None):
    """បង្កើត InlineKeyboardButton ដែលគាំទ្រ style (បៃតង/ខៀវ) និង custom_emoji_id"""
    kwargs = {"text": text}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url

    extra = {}
    if style is not None:
        extra["style"] = style
    if custom_emoji_id:
        extra["icon_custom_emoji_id"] = str(custom_emoji_id).strip()

    try:
        return types.InlineKeyboardButton(**kwargs, **extra)
    except TypeError:
        pass

    btn = types.InlineKeyboardButton(**kwargs)
    for k, v in extra.items():
        try:
            setattr(btn, k, v)
        except Exception:
            pass
    return btn


DEFAULT_DATA = {
    "admins": [],
    "balances": {},
    "orders": {},
    "qr_photo_id": None,
    "item_qrs": {},
    "aba_txns": {},
    "pending_claims": {},
    "home_buttons": {
        "shop": {"label": "🛒 Buy Now / ទិញឥឡូវនេះ", "emoji_id": None, "style": "success"},
        "orders": {"label": "📝 My Order / ការបញ្ជាទិញរបស់ខ្ញុំ", "emoji_id": None, "style": "primary"},
        "contact": {"label": "💬 Contact Admin / ទាក់ទងអ្នកគ្រប់គ្រង", "emoji_id": None, "style": "success"},
    },
    "categories": {
        "esign": {
            "name": "😉𝙀-𝙎𝙄𝙂𝙉-𝘾𝙚𝙧𝙩𝙞𝙛𝙞𝙘𝙖𝙩𝙚 (𝙞𝙋𝘼)",
            "emoji_id": None,
            "products": [
                {"id": "es_1y", "name": "ESing 1Y ធានា 2ខែ", "price": 3.50, "stock": 0, "emoji_id": None, "items": []}
            ],
        },
        "vpn": {
            "name": "😊𝗩𝗣𝗡 𝗣𝗥𝗢𝗫𝗬.𝗩𝗜𝗣 (មានខ្សែរ)",
            "emoji_id": None,
            "products": [
                {"id": "vpn_1h", "name": "1ម៉ោង", "price": 0.18, "stock": 0, "emoji_id": None, "items": []},
                {"id": "vpn_2h", "name": "2ម៉ោង", "price": 0.25, "stock": 0, "emoji_id": None, "items": []},
                {"id": "vpn_1d", "name": "1ថ្ងៃ", "price": 0.90, "stock": 0, "emoji_id": None, "items": []},
            ],
        },
        "fileza": {
            "name": "FILEZA MOD (ប្រើe-sign)",
            "emoji_id": None,
            "products": [
                {"id": "fz_1h", "name": "1ម៉ោង", "price": 0.25, "stock": 0, "emoji_id": None, "items": []}
            ],
        },
        "airlift": {
            "name": "AIRLIFT MOD IPA (ប្រើ e-sign)",
            "emoji_id": None,
            "products": [
                {"id": "al_1h", "name": "1ម៉ោង", "price": 0.25, "stock": 0, "emoji_id": None, "items": []},
                {"id": "al_6h", "name": "6ម៉ោង", "price": 0.70, "stock": 0, "emoji_id": None, "items": []},
                {"id": "al_12h", "name": "12ម៉ោង", "price": 0.90, "stock": 0, "emoji_id": None, "items": []},
            ],
        },
        "innova": {
            "name": "INNOVA CHEAT (មិនប្រើ e-sign)",
            "emoji_id": None,
            "products": [
                {"id": "in_1h", "name": "1ម៉ោង", "price": 0.20, "stock": 0, "emoji_id": None, "items": []},
                {"id": "in_3h", "name": "3ម៉ោង", "price": 0.30, "stock": 0, "emoji_id": None, "items": []},
                {"id": "in_6h", "name": "6ម៉ោង", "price": 0.40, "stock": 0, "emoji_id": None, "items": []},
            ],
        },
        "proxythis": {
            "name": "PROXY THIS.VIP (មិនប្រើ e-sign)",
            "emoji_id": None,
            "products": [
                {"id": "pt_2h", "name": "2ម៉ោង", "price": 0.40, "stock": 0, "emoji_id": None, "items": []},
                {"id": "pt_6h", "name": "6ម៉ោង", "price": 0.70, "stock": 0, "emoji_id": None, "items": []},
                {"id": "pt_12h", "name": "12ម៉ោង", "price": 1.20, "stock": 0, "emoji_id": None, "items": []},
                {"id": "pt_24h", "name": "24ម៉ោង", "price": 1.50, "stock": 0, "emoji_id": None, "items": []},
            ],
        },
        "rezz": {
            "name": "REZZ PANEL (ios & android)",
            "emoji_id": None,
            "products": [
                {"id": "rz_1h", "name": "1ម៉ោង", "price": 0.25, "stock": 0, "emoji_id": None, "items": []},
                {"id": "rz_3h", "name": "3ម៉ោង", "price": 0.69, "stock": 0, "emoji_id": None, "items": []},
            ],
        },
        "drip": {
            "name": "DRIP WIRE (ios & android)",
            "emoji_id": None,
            "products": [
                {"id": "dw_1h", "name": "1ម៉ោង", "price": 0.25, "stock": 0, "emoji_id": None, "items": []},
                {"id": "dw_3h", "name": "3ម៉ោង", "price": 0.69, "stock": 0, "emoji_id": None, "items": []},
            ],
        },
        "phantom": {
            "name": "PHANTOM (ios & android)",
            "emoji_id": None,
            "products": [
                {"id": "ph_1h", "name": "1ម៉ោង", "price": 0.25, "stock": 0, "emoji_id": None, "items": []},
                {"id": "ph_3h", "name": "3ម៉ោង", "price": 0.69, "stock": 0, "emoji_id": None, "items": []},
            ],
        },
        "primeko": {
            "name": "PRIMEKO (ios & android)",
            "emoji_id": None,
            "products": [
                {"id": "pr_1h", "name": "1ម៉ោង", "price": 0.25, "stock": 0, "emoji_id": None, "items": []},
                {"id": "pr_3h", "name": "3ម៉ោង", "price": 0.69, "stock": 0, "emoji_id": None, "items": []},
            ],
        },
    },
}


def validate_price(raw_val, allow_zero: bool = False):
    try:
        val = float(str(raw_val).strip().replace("$", ""))
    except (TypeError, ValueError):
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    if allow_zero:
        if val < 0:
            return None
    else:
        if val <= 0:
            return None
    return round(val, 2)


def sync_product_stock(prod: dict) -> int:
    items = prod.get("items")
    if not isinstance(items, list):
        items = []
        prod["items"] = items
    prod["stock"] = len(items)
    return prod["stock"]


def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    for cat in data.get("categories", {}).values():
        for p in cat.get("products", []):
            sync_product_stock(p)
    tmp_path = f"{DATA_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, DATA_FILE)


def load_data():
    if not os.path.exists(DATA_FILE):
        fresh = json.loads(json.dumps(DEFAULT_DATA))
        save_data(fresh)
        return json.loads(json.dumps(fresh))
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("admins", [])
    d.setdefault("balances", {})
    d.setdefault("orders", {})
    d.setdefault("qr_photo_id", None)
    d.setdefault("item_qrs", {})
    d.setdefault("aba_txns", {})
    d.setdefault("pending_claims", {})
    d.setdefault("home_buttons", json.loads(json.dumps(DEFAULT_DATA["home_buttons"])))
    for k, v in DEFAULT_DATA["home_buttons"].items():
        d["home_buttons"].setdefault(k, json.loads(json.dumps(v)))
    for cat in d.get("categories", {}).values():
        cat.setdefault("emoji_id", None)
        for p in cat.get("products", []):
            p.setdefault("items", [])
            p.setdefault("emoji_id", None)
            sync_product_stock(p)
    return d


def is_admin(user_id):
    if int(user_id) == int(ADMIN_ID):
        return True
    data = load_data()
    return int(user_id) in [int(x) for x in data.get("admins", [])]


def parse_aba_notification(text):
    if not text:
        return None, None
    amt_match = re.search(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)", text)
    trx_match = re.search(
        r"(?:Trx\.?\s*ID|លេខប្រតិបត្តិការ)\s*[:：]?\s*([A-Za-z0-9\-]+)",
        text,
        re.IGNORECASE,
    )
    amount = float(amt_match.group(1)) if amt_match else None
    trx_id = trx_match.group(1).strip() if trx_match else None
    return amount, trx_id


def get_item_qr(data: dict, cat_key: str, prod: dict):
    qrs = data.get("item_qrs") or {}
    prod_key = f"{cat_key}:{prod['id']}"
    return qrs.get(prod_key) or qrs.get(cat_key) or data.get("qr_photo_id")


def set_item_qr(data: dict, cat_key: str, prod_id: str, file_id: str):
    qrs = data.setdefault("item_qrs", {})
    qrs[f"{cat_key}:{prod_id}"] = file_id


def deliver_stock_item(chat_id: int, uid_str: str, cat_name: str, prod: dict, data: dict):
    items = prod.get("items") or []
    if not items:
        prod["stock"] = 0
        return False, None

    payload = items.pop(0)
    prod["stock"] = len(items)
    order_text = f"{cat_name} - {prod['name']} (${float(prod['price']):.2f})"
    data.setdefault("orders", {}).setdefault(uid_str, []).append(order_text)

    if isinstance(payload, dict) and payload.get("type") == "file" and payload.get("path") and os.path.exists(payload["path"]):
        with open(payload["path"], "rb") as f_doc:
            bot.send_document(
                chat_id,
                f_doc,
                caption=f"✅ <b>ទូទាត់ជោគជ័យ! (AUTO DELIVERY)</b>\n📦 ហ្វាល់សម្រាប់ <b>{order_text}</b>",
                parse_mode="HTML",
            )
        return True, order_text

    key_val = payload.get("value") if isinstance(payload, dict) else str(payload)
    bot.send_message(
        chat_id,
        f"✅ <b>ទូទាត់ជោគជ័យ! (AUTO DELIVERY)</b>\n"
        f"📦 ទំនិញ៖ <b>{order_text}</b>\n"
        f"🔑 <b>KEY របស់អ្នក៖</b>\n<code>{key_val}</code>",
        parse_mode="HTML",
    )
    return True, order_text


def fulfill_pending_purchase(uid_str: str, data: dict, trx_id: str | None = None):
    claim = pending_purchases.get(uid_str)
    if not claim or claim.get("fulfilled"):
        return False, None

    cat_key = claim["cat_key"]
    prod_id = claim["prod_id"]
    cat_info = data.get("categories", {}).get(cat_key)
    if not cat_info:
        return False, None
    prod = next((p for p in cat_info.get("products", []) if p["id"] == prod_id), None)
    if not prod:
        return False, None

    ok, order_text = deliver_stock_item(int(uid_str), uid_str, cat_info["name"], prod, data)
    if not ok:
        return False, None

    claim["fulfilled"] = True
    if trx_id:
        claim["trx_id"] = trx_id
    pending_purchases.pop(uid_str, None)
    save_data(data)
    return True, order_text


def main_inline_keyboard():
    data = load_data()
    hb = data["home_buttons"]
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        make_btn(
            hb["shop"]["label"],
            callback_data="menu:shop",
            style="success",
            custom_emoji_id=hb["shop"].get("emoji_id"),
        ),
        make_btn(
            hb["orders"]["label"],
            callback_data="menu:orders",
            style="primary",
            custom_emoji_id=hb["orders"].get("emoji_id"),
        ),
        make_btn(
            hb["contact"]["label"],
            url=f"https://t.me/{ADMIN_USERNAME}",
            style="success",
            custom_emoji_id=hb["contact"].get("emoji_id"),
        ),
    )
    return kb


def categories_keyboard():
    data = load_data()
    kb = types.InlineKeyboardMarkup(row_width=1)
    for idx, (cat_key, cat_info) in enumerate(data["categories"].items()):
        btn_style = "success" if idx % 2 == 0 else "primary"
        kb.add(
            make_btn(
                cat_info["name"],
                callback_data=f"cat:{cat_key}",
                style=btn_style,
                custom_emoji_id=cat_info.get("emoji_id"),
            )
        )
    kb.add(make_btn("⬅️ Back", callback_data="menu:home", style="primary"))
    return kb


def products_keyboard(cat_key):
    data = load_data()
    cat_info = data["categories"][cat_key]
    kb = types.InlineKeyboardMarkup(row_width=1)
    for idx, prod in enumerate(cat_info["products"]):
        stock_cnt = sync_product_stock(prod)
        label = f"{prod['name']} - ${prod['price']:.2f} [ស្ដុក {stock_cnt}]"
        btn_style = "success" if idx % 2 == 0 else "primary"
        kb.add(
            make_btn(
                label,
                callback_data=f"buy:{cat_key}:{prod['id']}",
                style=btn_style,
                custom_emoji_id=prod.get("emoji_id"),
            )
        )
    kb.add(make_btn("⬅️ Back", callback_data="menu:shop", style="primary"))
    return kb


def admin_main_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        make_btn("📦 ដាក់ស្ដុក / KEY / ហ្វាល់ (ទាំង 10)", callback_data="adm:stock_cats", style="success"),
        make_btn("🖼️ កំណត់ QR បង់ប្រាក់ (តាមម៉ូត/កញ្ចប់)", callback_data="adm:qr_cats", style="primary"),
        make_btn("🗑️ លុបស្ដុកទាំងអស់ (ទាំង 10 → 0)", callback_data="adm:clear_cats", style="success"),
        make_btn("✨ ដាក់ Premium Emoji (custom_emoji_id)", callback_data="adm:emoji_menu", style="primary"),
        make_btn("✏️ កែឈ្មោះប៊ូតុង All", callback_data="adm:rename_menu", style="success"),
        make_btn("❎ លុបប៊ូតុងផ្សេងៗ (ទាំង 10)", callback_data="adm:del_btn_cats", style="primary"),
        make_btn("👑 Add /Admin តាម ID", callback_data="adm:add_admin", style="success"),
        make_btn("💲 កែតម្លៃ / បន្ថែមកញ្ចប់ម៉ោង-Esing", callback_data="adm:price_cats", style="primary"),
    )
    return kb


def admin_cats_keyboard(mode):
    data = load_data()
    kb = types.InlineKeyboardMarkup(row_width=1)
    for idx, (cat_key, cat_info) in enumerate(data["categories"].items()):
        total_stock = sum(sync_product_stock(p) for p in cat_info["products"])
        suffix = f" [សរុប: {total_stock}]" if mode == "clear" else ""
        btn_style = "success" if idx % 2 == 0 else "primary"
        kb.add(
            make_btn(
                f"{cat_info['name']}{suffix}",
                callback_data=f"adm_cat:{mode}:{cat_key}",
                style=btn_style,
                custom_emoji_id=cat_info.get("emoji_id"),
            )
        )
    kb.add(make_btn("⬅️ Back", callback_data="adm:home", style="success"))
    return kb


def admin_prods_keyboard(mode, cat_key):
    data = load_data()
    cat_info = data["categories"][cat_key]
    qrs = data.get("item_qrs") or {}
    kb = types.InlineKeyboardMarkup(row_width=1)

    if mode == "clear":
        kb.add(
            make_btn("🗑️ លុបស្ដុកទាំងអស់ (ចុចម្ដងសល់ 0 ស្ដុក)", callback_data=f"adm_clear_all:{cat_key}", style="success")
        )

    for idx, prod in enumerate(cat_info["products"]):
        stock_cnt = sync_product_stock(prod)
        has_qr = " [QR✅]" if qrs.get(f"{cat_key}:{prod['id']}") else ""
        label = f"{prod['name']} - ${prod['price']:.2f} [ស្ដុក {stock_cnt}]{has_qr}"
        btn_style = "success" if idx % 2 == 0 else "primary"
        if mode == "clear":
            kb.add(make_btn(f"➖ លុបស្ដុកមួយ (-1): {label}", callback_data=f"adm_del_one:{cat_key}:{prod['id']}", style=btn_style))
        elif mode == "del_btn":
            kb.add(make_btn(f"❎ {label}", callback_data=f"adm_confirm_del_btn:{cat_key}:{prod['id']}", style=btn_style))
        else:
            kb.add(
                make_btn(
                    label,
                    callback_data=f"adm_prod:{mode}:{cat_key}:{prod['id']}",
                    style=btn_style,
                    custom_emoji_id=prod.get("emoji_id"),
                )
            )

    if mode in ("stock", "price", "qr"):
        kb.add(make_btn("➕ បន្ថែមកញ្ចប់ម៉ោង / Esing ថ្មី", callback_data=f"adm_addprod:{cat_key}", style="success"))

    back_cb = "adm:del_btn_cats" if mode == "del_btn" else f"adm:{mode}_cats"
    kb.add(make_btn("⬅️ Back", callback_data=back_cb, style="primary"))
    return kb


def send_home(chat_id, message_id=None, prefer_edit=True):
    text = (
        "✨ <b>BEDA STORE សូមស្វាគមន៍!</b>\n"
        "💎 <i>សេវាកម្មរហ័ស ទំនុកចិត្ត ស្ដុកពិត</i>\n"
        "Please select: / សូមជ្រើសរើស៖"
    )
    if message_id and prefer_edit:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=main_inline_keyboard())
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=main_inline_keyboard())


@bot.message_handler(func=lambda m: m.chat.type in ("group", "supergroup"), content_types=["text"])
def handle_aba_group_message(message):
    if ABA_GROUP_ID != 0 and message.chat.id != ABA_GROUP_ID:
        return
    amount, trx_id = parse_aba_notification(message.text)
    if amount is None or not trx_id:
        return

    data = load_data()
    txn_record = data["aba_txns"].get(trx_id)
    if txn_record and txn_record.get("claimed_by"):
        return

    if trx_id not in data["aba_txns"]:
        data["aba_txns"][trx_id] = {
            "amount": round(amount, 2),
            "claimed_by": None,
            "raw": message.text,
        }
        save_data(data)

    matched_uid = None
    for uid_str, claim in list(pending_purchases.items()):
        if claim.get("fulfilled"):
            continue
        expected_amt = round(float(claim.get("price", 0.0)), 2)
        if abs(round(amount, 2) - expected_amt) <= 0.009:
            matched_uid = uid_str
            break

    if matched_uid:
        ok, order_text = fulfill_pending_purchase(matched_uid, data, trx_id=trx_id)
        if ok:
            data = load_data()
            data["aba_txns"][trx_id]["claimed_by"] = matched_uid
            save_data(data)
            try:
                bot.send_message(
                    int(matched_uid),
                    f"⚡ <b>ផ្ទៀងផ្ទាត់ ABA អូតូជោគជ័យ!</b>\n"
                    f"លេខប្រតិបត្តិការ (Trx. ID)៖ <code>{trx_id}</code>\n"
                    f"ទឹកប្រាក់៖ <b>${amount:.2f}</b>\n"
                    f"បានប្រគល់ទំនិញ៖ <b>{order_text}</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass


@bot.message_handler(commands=["start"])
def cmd_start(message):
    data = load_data()
    uid = str(message.from_user.id)
    data["orders"].setdefault(uid, [])
    save_data(data)
    send_home(message.chat.id, prefer_edit=False)


@bot.message_handler(commands=["my_order"])
def cmd_my_order(message):
    data = load_data()
    uid = str(message.from_user.id)
    orders = data["orders"].get(uid, [])
    txt = "📝 <b>My Order / ការបញ្ជាទិញរបស់ខ្ញុំ</b>\n\n" + (
        "\n".join(f"• {o}" for o in orders) if orders else "អ្នកមិនទាន់មានប្រវត្តិបញ្ជាទិញនៅឡើយទេ។"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(make_btn("⬅️ Back", callback_data="menu:home", style="primary"))
    bot.send_message(message.chat.id, txt, parse_mode="HTML", reply_markup=kb)


@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ អ្នកមិនមានសិទ្ធិប្រើមុខងារ Admin ទេ។")
        return
    admin_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        "⚡ <b>ADMIN CONTROL CENTER - BEDA STORE</b>\n"
        "✨ <i>គ្រប់គ្រងស្ដុក QR តាមម៉ូត/កញ្ចប់ Emoji ឈ្មោះប៊ូតុង និង Admin</i>",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard(),
    )


@bot.message_handler(commands=["addadmin"])
def cmd_addadmin(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "ប្រើទម្រង់៖ <code>/addadmin USER_ID</code>", parse_mode="HTML")
        return
    try:
        new_aid = int(parts[1])
    except ValueError:
        bot.reply_to(message, "❌ USER_ID ត្រូវតែជាលេខ។")
        return
    data = load_data()
    if new_aid not in data["admins"]:
        data["admins"].append(new_aid)
        save_data(data)
    bot.reply_to(message, f"👑 បានបន្ថែម Admin ថ្មី៖ <code>{new_aid}</code> រួចរាល់!", parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    data = load_data()
    uid = str(call.from_user.id)
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    cb = call.data

    if cb == "menu:home":
        user_states.pop(call.from_user.id, None)
        send_home(chat_id, msg_id, prefer_edit=True)

    elif cb == "menu:shop":
        try:
            bot.edit_message_text("🛒 <b>Choose a category:</b>", chat_id, msg_id, parse_mode="HTML", reply_markup=categories_keyboard())
        except Exception:
            bot.send_message(chat_id, "🛒 <b>Choose a category:</b>", parse_mode="HTML", reply_markup=categories_keyboard())

    elif cb == "menu:orders":
        orders = data["orders"].get(uid, [])
        txt = "📝 <b>My Order / ការបញ្ជាទិញរបស់ខ្ញុំ</b>\n\n" + (
            "\n".join(f"• {o}" for o in orders) if orders else "អ្នកមិនទាន់មានប្រវត្តិបញ្ជាទិញនៅឡើយទេ។"
        )
        kb = types.InlineKeyboardMarkup()
        kb.add(make_btn("⬅️ Back", callback_data="menu:home", style="primary"))
        try:
            bot.edit_message_text(txt, chat_id, msg_id, parse_mode="HTML", reply_markup=kb)
        except Exception:
            bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=kb)

    elif cb.startswith("cat:"):
        cat_key = cb.split(":")[1]
        cat_info = data["categories"][cat_key]
        txt = f"📦 <b>{cat_info['name']}</b>\n\nSelect a package / ជ្រើសរើសកញ្ចប់៖"
        try:
            bot.edit_message_text(txt, chat_id, msg_id, parse_mode="HTML", reply_markup=products_keyboard(cat_key))
        except Exception:
            bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=products_keyboard(cat_key))

    elif cb.startswith("buy:"):
        _, cat_key, prod_id = cb.split(":")
        cat_info = data["categories"][cat_key]
        prod = next((p for p in cat_info["products"] if p["id"] == prod_id), None)
        if not prod:
            return
        stock_cnt = sync_product_stock(prod)
        if stock_cnt <= 0:
            bot.answer_callback_query(call.id, "❌ អស់ស្ដុកហើយ! (ស្ដុក 0)", show_alert=True)
            return

        price_val = round(float(prod["price"]), 2)
        pending_purchases[uid] = {
            "cat_key": cat_key,
            "prod_id": prod_id,
            "price": price_val,
            "fulfilled": False,
        }

        qr_file_id = get_item_qr(data, cat_key, prod)
        caption = (
            f"💳 <b>បង់ប្រាក់តាមកញ្ចប់ផ្ទាល់ (DIRECT PACKAGE PAY)</b>\n\n"
            f"🔹 ម៉ូត៖ <b>{cat_info['name']}</b>\n"
            f"🔹 កញ្ចប់៖ <b>{prod['name']}</b>\n"
            f"💵 តម្លៃត្រូវបង់៖ <b>${price_val:.2f}</b>\n"
            f"📦 ស្ដុកមានស្រាប់៖ <b>{stock_cnt}</b>\n\n"
            f"1️⃣ ស្កេន QR ABA Merchant ខាងលើ/ក្រោមឱ្យត្រឹមត្រូវតាមតម្លៃ <b>${price_val:.2f}</b>\n"
            f"2️⃣ បន្ទាប់ពីបង់ប្រាក់រួច សូមចុចប៊ូតុង <b>«✅ បានបង់ប្រាក់រួចរាល់»</b> ដើម្បីទទួល KEY ឬ ហ្វាល់ អូតូ!"
        )

        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            make_btn("✅ បានបង់ប្រាក់រួចរាល់", callback_data=f"paid:{cat_key}:{prod_id}", style="success"),
            make_btn("💬 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}", style="primary"),
            make_btn("⬅️ Back", callback_data=f"cat:{cat_key}", style="primary"),
        )

        if qr_file_id:
            bot.send_photo(chat_id, qr_file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
        else:
            bot.send_message(
                chat_id,
                caption + "\n\n⚠️ <i>(Admin មិនទាន់បានកំណត់រូប QR សម្រាប់កញ្ចប់នេះនៅឡើយទេ)</i>",
                parse_mode="HTML",
                reply_markup=kb,
            )

    elif cb.startswith("paid:"):
        _, cat_key, prod_id = cb.split(":")
        cat_info = data["categories"].get(cat_key)
        if not cat_info:
            return
        prod = next((p for p in cat_info.get("products", []) if p["id"] == prod_id), None)
        if not prod:
            return

        expected_price = round(float(prod["price"]), 2)
        matched_trx = None
        for trx_id, txn in data.get("aba_txns", {}).items():
            if not txn.get("claimed_by") and abs(round(float(txn.get("amount", 0.0)), 2) - expected_price) <= 0.009:
                matched_trx = trx_id
                break

        if matched_trx:
            ok, order_text = fulfill_pending_purchase(uid, data, trx_id=matched_trx)
            if ok:
                data = load_data()
                data["aba_txns"][matched_trx]["claimed_by"] = uid
                save_data(data)
                bot.answer_callback_query(call.id, "✅ បានផ្ទៀងផ្ទាត់ និងប្រគល់ KEY/ហ្វាល់ អូតូរួចរាល់!", show_alert=True)
                try:
                    bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=products_keyboard(cat_key))
                except Exception:
                    pass
                return
            else:
                bot.answer_callback_query(call.id, "❌ អស់ស្ដុកសម្រាប់កញ្ចប់នេះហើយ!", show_alert=True)
                return

        pending_purchases[uid] = {
            "cat_key": cat_key,
            "prod_id": prod_id,
            "price": expected_price,
            "fulfilled": False,
        }
        bot.answer_callback_query(
            call.id,
            "⏳ កំពុងរង់ចាំសារផ្ទៀងផ្ទាត់ ABA អូតូ! ប្រព័ន្ធនឹងផ្ញើ KEY/ហ្វាល់ ឱ្យអ្នកភ្លាមពេលសារចូល។",
            show_alert=True,
        )

    # ================= ADMIN CALLBACKS =================
    elif is_admin(call.from_user.id):
        if cb == "adm:home":
            admin_states.pop(call.from_user.id, None)
            try:
                bot.edit_message_text(
                    "⚡ <b>ADMIN CONTROL CENTER - BEDA STORE</b>\n"
                    "✨ <i>គ្រប់គ្រងស្ដុក QR តាមម៉ូត/កញ្ចប់ Emoji ឈ្មោះប៊ូតុង និង Admin</i>",
                    chat_id,
                    msg_id,
                    parse_mode="HTML",
                    reply_markup=admin_main_keyboard(),
                )
            except Exception:
                bot.send_message(
                    chat_id,
                    "⚡ <b>ADMIN CONTROL CENTER - BEDA STORE</b>",
                    parse_mode="HTML",
                    reply_markup=admin_main_keyboard(),
                )

        elif cb == "adm:qr_cats":
            txt = "🖼️ <b>ជ្រើសរើសម៉ូត (ទាំង 10) ដើម្បីកំណត់ QR បង់ប្រាក់តាមកញ្ចប់/តម្លៃ៖</b>"
            try:
                bot.edit_message_text(txt, chat_id, msg_id, parse_mode="HTML", reply_markup=admin_cats_keyboard("qr"))
            except Exception:
                bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=admin_cats_keyboard("qr"))

        elif cb == "adm:add_admin":
            admin_states[call.from_user.id] = {"step": "wait_add_admin"}
            current_admins = ", ".join(str(x) for x in ([ADMIN_ID] + data.get("admins", [])))
            bot.send_message(
                chat_id,
                f"👑 <b>ADD ADMIN តាម ID</b>\n\n"
                f"បញ្ជី Admin បច្ចុប្បន្ន៖ <code>{current_admins}</code>\n"
                f"👉 សូមវាយ <b>User ID (ជាលេខ)</b> របស់ Admin ថ្មីដែលអ្នកចង់បន្ថែម៖",
                parse_mode="HTML",
            )

        elif cb == "adm:emoji_menu":
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                make_btn("🏠 ដាក់ Premium Emoji លើប៊ូតុងមុខដើម", callback_data="adm_emo_home", style="success"),
                make_btn("📦 ដាក់ Premium Emoji លើមុខងារទាំង 10", callback_data="adm_emo_cats", style="primary"),
                make_btn("⬅️ Back", callback_data="adm:home", style="success"),
            )
            bot.edit_message_text(
                "✨ <b>ដាក់ PREMIUM EMOJI (custom_emoji_id)</b>\n"
                "ជ្រើសរើសប្រភេទប៊ូតុងដែលអ្នកចង់ដាក់៖",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=kb,
            )

        elif cb == "adm_emo_home":
            kb = types.InlineKeyboardMarkup(row_width=1)
            for idx, (h_key, h_info) in enumerate(data["home_buttons"].items()):
                btn_style = "success" if idx % 2 == 0 else "primary"
                kb.add(make_btn(h_info["label"], callback_data=f"adm_set_emo_home:{h_key}", style=btn_style))
            kb.add(make_btn("⬅️ Back", callback_data="adm:emoji_menu", style="primary"))
            bot.edit_message_text("🏠 <b>ជ្រើសរើសប៊ូតុងមុខដើម៖</b>", chat_id, msg_id, parse_mode="HTML", reply_markup=kb)

        elif cb.startswith("adm_set_emo_home:"):
            h_key = cb.split(":")[1]
            admin_states[call.from_user.id] = {"step": "wait_emo_home", "h_key": h_key}
            bot.send_message(
                chat_id,
                "✨ <b>ដាក់ Premium Emoji លើប៊ូតុងមុខដើម</b>\n\n"
                "សូមវាយតាមទម្រង់៖\n<code>ឈ្មោះប៊ូតុង | custom_emoji_id</code>\n"
                "ឧទាហរណ៍៖ <code>🛒 ទិញឥឡូវនេះ | 5368324170671202286</code>",
                parse_mode="HTML",
            )

        elif cb == "adm_emo_cats":
            kb = types.InlineKeyboardMarkup(row_width=1)
            for idx, (cat_key, cat_info) in enumerate(data["categories"].items()):
                btn_style = "success" if idx % 2 == 0 else "primary"
                kb.add(make_btn(cat_info["name"], callback_data=f"adm_set_emo_cat:{cat_key}", style=btn_style))
            kb.add(make_btn("⬅️ Back", callback_data="adm:emoji_menu", style="primary"))
            bot.edit_message_text("📦 <b>ជ្រើសរើសមុខងារ (ទាំង 10) ដើម្បីដាក់ Premium Emoji៖</b>", chat_id, msg_id, parse_mode="HTML", reply_markup=kb)

        elif cb.startswith("adm_set_emo_cat:"):
            cat_key = cb.split(":")[1]
            admin_states[call.from_user.id] = {"step": "wait_emo_cat", "cat_key": cat_key}
            bot.send_message(
                chat_id,
                "✨ <b>ដាក់ Premium Emoji លើមុខងារ</b>\n\n"
                "សូមវាយតាមទម្រង់៖\n<code>ឈ្មោះមុខងារ | custom_emoji_id</code>\n"
                "ឧទាហរណ៍៖ <code>PHANTOM (ios & android) | 5368324170671202286</code>",
                parse_mode="HTML",
            )

        elif cb == "adm:rename_menu":
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                make_btn("🏠 កែឈ្មោះប៊ូតុងមុខដើម All", callback_data="adm_ren_home_list", style="success"),
                make_btn("📦 កែឈ្មោះមុខងារទាំង 10 All", callback_data="adm_ren_cat_list", style="primary"),
                make_btn("⬅️ Back", callback_data="adm:home", style="success"),
            )
            bot.edit_message_text("✏️ <b>កែឈ្មោះប៊ូតុង ALL</b>\nជ្រើសរើសប្រភេទប៊ូតុង៖", chat_id, msg_id, parse_mode="HTML", reply_markup=kb)

        elif cb == "adm_ren_home_list":
            kb = types.InlineKeyboardMarkup(row_width=1)
            for idx, (h_key, h_info) in enumerate(data["home_buttons"].items()):
                btn_style = "success" if idx % 2 == 0 else "primary"
                kb.add(make_btn(h_info["label"], callback_data=f"adm_ren_home:{h_key}", style=btn_style))
            kb.add(make_btn("⬅️ Back", callback_data="adm:rename_menu", style="primary"))
            bot.edit_message_text("🏠 <b>ចុចលើប៊ូតុងមុខដើមដើម្បីកែឈ្មោះ៖</b>", chat_id, msg_id, parse_mode="HTML", reply_markup=kb)

        elif cb.startswith("adm_ren_home:"):
            h_key = cb.split(":")[1]
            admin_states[call.from_user.id] = {"step": "wait_ren_home", "h_key": h_key}
            bot.send_message(chat_id, "✏️ <b>សូមវាយឈ្មោះថ្មីសម្រាប់ប៊ូតុងនេះ៖</b>", parse_mode="HTML")

        elif cb == "adm_ren_cat_list":
            kb = types.InlineKeyboardMarkup(row_width=1)
            for idx, (cat_key, cat_info) in enumerate(data["categories"].items()):
                btn_style = "success" if idx % 2 == 0 else "primary"
                kb.add(make_btn(cat_info["name"], callback_data=f"adm_ren_cat:{cat_key}", style=btn_style))
            kb.add(make_btn("⬅️ Back", callback_data="adm:rename_menu", style="primary"))
            bot.edit_message_text("📦 <b>ចុចលើមុខងារ (ទាំង 10) ដើម្បីកែឈ្មោះ៖</b>", chat_id, msg_id, parse_mode="HTML", reply_markup=kb)

        elif cb.startswith("adm_ren_cat:"):
            cat_key = cb.split(":")[1]
            admin_states[call.from_user.id] = {"step": "wait_ren_cat", "cat_key": cat_key}
            bot.send_message(chat_id, "✏️ <b>សូមវាយឈ្មោះថ្មីសម្រាប់មុខងារនេះ៖</b>", parse_mode="HTML")

        elif cb == "adm:del_btn_cats":
            bot.edit_message_text(
                "❎ <b>លុបប៊ូតុងផ្សេងៗ (ទាំង 10)</b>\n"
                "👇 <i>សូមចុចលើមុខងារមួយក្នុងចំណោមទាំង 10៖</i>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=admin_cats_keyboard("del_btn"),
            )

        elif cb.startswith("adm_confirm_del_btn:"):
            _, cat_key, prod_id = cb.split(":")
            cat_info = data["categories"][cat_key]
            prod = next((p for p in cat_info["products"] if p["id"] == prod_id), None)
            if not prod:
                return
            stock_cnt = sync_product_stock(prod)
            stock_status = "អស់ស្ដុក" if stock_cnt <= 0 else f"ស្ដុក {stock_cnt}"
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                make_btn("🗑️ យល់ព្រមលុបប៊ូតុងនេះចេញ", callback_data=f"adm_do_del_btn:{cat_key}:{prod_id}", style="success"),
                make_btn("⬅️ ត្រឡប់ក្រោយ / មិនលុប", callback_data=f"adm_cat:del_btn:{cat_key}", style="primary"),
            )
            bot.edit_message_text(
                f"📌 <b>{cat_info['name']}</b>\n"
                f"🔹 ប៊ូតុង៖ <b>{prod['name']} - ${prod['price']:.2f} [{stock_status}]</b>\n\n"
                f"⚠️ <b>បញ្ជាក់៖ តើអ្នកពិតជាចង់លុបប៊ូតុងនេះចេញមែនទេ?</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=kb,
            )

        elif cb.startswith("adm_do_del_btn:"):
            _, cat_key, prod_id = cb.split(":")
            cat_info = data["categories"][cat_key]
            prod = next((p for p in cat_info["products"] if p["id"] == prod_id), None)
            removed_label = f"{prod['name']} - ${prod['price']:.2f}" if prod else prod_id
            cat_info["products"] = [p for p in cat_info["products"] if p["id"] != prod_id]
            save_data(data)
            bot.answer_callback_query(call.id, "✅ បានលុបប៊ូតុងចេញរួចរាល់!", show_alert=True)
            bot.edit_message_text(
                f"✅ <b>បានលុបប៊ូតុង «{removed_label}» ចេញរួចរាល់ហើយ!</b>\n"
                f"📌 <b>{cat_info['name']}</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=admin_prods_keyboard("del_btn", cat_key),
            )

        elif cb == "adm:stock_cats":
            bot.edit_message_text(
                "📦 <b>ជ្រើសរើសមុខងារ (ទាំង 10) ដើម្បីដាក់ស្ដុក / KEY ឬ ហ្វាល់៖</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=admin_cats_keyboard("stock"),
            )
        elif cb == "adm:clear_cats":
            bot.edit_message_text(
                "🗑️ <b>ជ្រើសរើសមុខងារ (ទាំង 10) ដើម្បីលុបស្ដុកទាំងអស់ (0 ស្ដុក) ឬ លុបស្ដុកមួយ (-1)៖</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=admin_cats_keyboard("clear"),
            )
        elif cb == "adm:price_cats":
            bot.edit_message_text(
                "💲 <b>ជ្រើសរើសមុខងារ (ទាំង 10) ដើម្បីកែតម្លៃ / បន្ថែមម៉ោង-Esing៖</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=admin_cats_keyboard("price"),
            )
        elif cb.startswith("adm_cat:"):
            _, mode, cat_key = cb.split(":")
            cat_info = data["categories"][cat_key]
            if mode == "qr":
                prompt_txt = f"🖼️ <b>{cat_info['name']}</b>\n🔻 <i>ជ្រើសរើសកញ្ចប់/តម្លៃ ដើម្បីកំណត់ QR ABA Merchant ផ្ទាល់៖</i>"
            elif mode == "del_btn":
                prompt_txt = f"❎ <b>{cat_info['name']}</b>\n🔻 <i>ចុចលើប៊ូតុងខាងក្រោមដើម្បីមើល និងបញ្ជាក់លុប៖</i>"
            else:
                prompt_txt = f"📌 <b>{cat_info['name']}</b>\nជ្រើសរើសកញ្ចប់៖"
            bot.edit_message_text(
                prompt_txt,
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=admin_prods_keyboard(mode, cat_key),
            )
        elif cb.startswith("adm_clear_all:"):
            cat_key = cb.split(":")[1]
            cat_info = data["categories"][cat_key]
            for prod in cat_info["products"]:
                prod["items"] = []
                prod["stock"] = 0
            save_data(data)
            bot.answer_callback_query(call.id, "✅ បានលុបស្ដុកទាំងអស់សល់ 0 ស្ដុកហើយ!", show_alert=True)
            bot.edit_message_text(
                f"🗑️ <b>{cat_info['name']}</b>\n✅ ស្ដុកទាំងអស់ត្រូវបានលុបសល់ <b>0 ស្ដុក</b> រួចរាល់!",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=admin_prods_keyboard("clear", cat_key),
            )
        elif cb.startswith("adm_del_one:"):
            _, cat_key, prod_id = cb.split(":")
            cat_info = data["categories"][cat_key]
            prod = next((p for p in cat_info["products"] if p["id"] == prod_id), None)
            if not prod:
                return
            items = prod.get("items") or []
            if items:
                items.pop()
                prod["stock"] = len(items)
                save_data(data)
                bot.answer_callback_query(call.id, f"➖ បានលុបស្ដុកមួយ! នៅសល់ {prod['stock']} ស្ដុក", show_alert=False)
            else:
                prod["stock"] = 0
                save_data(data)
                bot.answer_callback_query(call.id, "⚠️ ស្ដុកមាន 0 រួចហើយ!", show_alert=False)
            try:
                bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=admin_prods_keyboard("clear", cat_key))
            except Exception:
                pass
        elif cb.startswith("adm_prod:"):
            _, mode, cat_key, prod_id = cb.split(":")
            cat_info = data["categories"][cat_key]
            prod = next((p for p in cat_info["products"] if p["id"] == prod_id), None)
            if not prod:
                return
            stock_cnt = sync_product_stock(prod)
            if mode == "qr":
                admin_states[call.from_user.id] = {
                    "step": "wait_item_qr",
                    "cat_key": cat_key,
                    "prod_id": prod_id,
                }
                bot.send_message(
                    chat_id,
                    f"🖼️ <b>កំណត់ QR បង់ប្រាក់</b>\n"
                    f"ម៉ូត៖ <b>{cat_info['name']}</b>\n"
                    f"កញ្ចប់៖ <b>{prod['name']} (${prod['price']:.2f})</b>\n\n"
                    f"👉 សូមផ្ញើ <b>រូបភាព QR ABA Merchant</b> សម្រាប់តម្លៃ <b>${prod['price']:.2f}</b> មកកាន់ Bot ឥឡូវនេះ៖",
                    parse_mode="HTML",
                )
            elif mode == "stock":
                admin_states[call.from_user.id] = {
                    "step": "wait_payload",
                    "cat_key": cat_key,
                    "prod_id": prod_id,
                }
                bot.send_message(
                    chat_id,
                    f"🔑/📁 <b>ដាក់ស្ដុកសម្រាប់ {cat_info['name']} → {prod['name']} (${prod['price']:.2f})</b>\n"
                    f"ស្ដុកបច្ចុប្បន្ន៖ <b>{stock_cnt} ស្ដុក</b>\n\n"
                    f"👉 សូមផ្ញើ <b>KEY (អត្ថបទ — 1 បន្ទាត់ 1 KEY)</b> ឬ <b>ផ្ញើហ្វាល់ (Document/IPA/ZIP/TXT)</b> មកកាន់ Bot ឥឡូវនេះ៖",
                    parse_mode="HTML",
                )
            elif mode == "price":
                admin_states[call.from_user.id] = {
                    "step": "wait_price",
                    "cat_key": cat_key,
                    "prod_id": prod_id,
                }
                bot.send_message(
                    chat_id,
                    f"💲 <b>កែតម្លៃសម្រាប់ {prod['name']}</b> (បច្ចុប្បន្ន៖ ${prod['price']:.2f})\n"
                    f"👉 សូមវាយតម្លៃថ្មី (ឧទាហរណ៍៖ <code>0.25</code> ឬ <code>0.69</code>)៖",
                    parse_mode="HTML",
                )
        elif cb.startswith("adm_addprod:"):
            cat_key = cb.split(":")[1]
            admin_states[call.from_user.id] = {
                "step": "wait_new_prod",
                "cat_key": cat_key,
            }
            bot.send_message(
                chat_id,
                "➕ <b>បន្ថែមកញ្ចប់ម៉ោង / Esing ថ្មី</b>\n\n"
                "សូមវាយតាមទម្រង់៖ <code>ឈ្មោះកញ្ចប់ | តម្លៃ</code>\n"
                "ឧទាហរណ៍៖ <code>1ម៉ោង | 0.25</code> ឬ <code>3ម៉ោង | 0.69</code>",
                parse_mode="HTML",
            )


@bot.message_handler(func=lambda m: m.chat.type == "private", content_types=["text", "document", "photo"])
def handle_private_inputs(message):
    sender_id = message.from_user.id

    if is_admin(sender_id) and sender_id in admin_states:
        state = admin_states[sender_id]
        data = load_data()
        step = state.get("step")

        if step == "wait_add_admin" and message.content_type == "text":
            try:
                new_aid = int(message.text.strip())
            except ValueError:
                bot.reply_to(message, "❌ សូមវាយ User ID ជាលេខសុទ្ធ (ឧ. <code>6214336913</code>)", parse_mode="HTML")
                return
            if new_aid not in data["admins"] and new_aid != ADMIN_ID:
                data["admins"].append(new_aid)
                save_data(data)
            admin_states.pop(sender_id, None)
            bot.reply_to(message, f"👑 <b>បានបន្ថែម Admin ថ្មី៖</b> <code>{new_aid}</code> រួចរាល់!", parse_mode="HTML")
            return

        if step == "wait_emo_home" and message.content_type == "text":
            raw = message.text.strip()
            h_key = state["h_key"]
            if "|" in raw:
                lbl, eid = [x.strip() for x in raw.split("|", 1)]
            else:
                lbl = data["home_buttons"][h_key]["label"]
                eid = raw
            data["home_buttons"][h_key]["label"] = lbl
            data["home_buttons"][h_key]["emoji_id"] = eid
            save_data(data)
            admin_states.pop(sender_id, None)
            bot.reply_to(message, f"✨ <b>បានកំណត់ Premium Emoji រួចរាល់!</b>\nឈ្មោះ៖ <b>{lbl}</b>\nEmoji ID៖ <code>{eid}</code>", parse_mode="HTML")
            return

        if step == "wait_emo_cat" and message.content_type == "text":
            raw = message.text.strip()
            cat_key = state["cat_key"]
            if "|" in raw:
                cname, eid = [x.strip() for x in raw.split("|", 1)]
            else:
                cname = data["categories"][cat_key]["name"]
                eid = raw
            data["categories"][cat_key]["name"] = cname
            data["categories"][cat_key]["emoji_id"] = eid
            save_data(data)
            admin_states.pop(sender_id, None)
            bot.reply_to(message, f"✨ <b>បានកំណត់ Premium Emoji រួចរាល់!</b>\nមុខងារ៖ <b>{cname}</b>\nEmoji ID៖ <code>{eid}</code>", parse_mode="HTML")
            return

        if step == "wait_ren_home" and message.content_type == "text":
            new_lbl = message.text.strip()
            h_key = state["h_key"]
            data["home_buttons"][h_key]["label"] = new_lbl
            save_data(data)
            admin_states.pop(sender_id, None)
            bot.reply_to(message, f"✏️ <b>បានកែឈ្មោះប៊ូតុងទៅជា៖</b> <b>{new_lbl}</b>", parse_mode="HTML")
            return

        if step == "wait_ren_cat" and message.content_type == "text":
            new_cname = message.text.strip()
            cat_key = state["cat_key"]
            data["categories"][cat_key]["name"] = new_cname
            save_data(data)
            admin_states.pop(sender_id, None)
            bot.reply_to(message, f"✏️ <b>បានកែឈ្មោះមុខងារទៅជា៖</b> <b>{new_cname}</b>", parse_mode="HTML")
            return

        if step == "wait_item_qr" and message.content_type == "photo":
            file_id = message.photo[-1].file_id
            cat_key = state["cat_key"]
            prod_id = state["prod_id"]
            set_item_qr(data, cat_key, prod_id, file_id)
            save_data(data)
            cat_info = data["categories"][cat_key]
            prod = next((p for p in cat_info["products"] if p["id"] == prod_id), None)
            admin_states.pop(sender_id, None)
            bot.send_photo(
                message.chat.id,
                file_id,
                caption=(
                    f"✅ <b>បានកំណត់ QR បង់ប្រាក់រួចរាល់!</b>\n"
                    f"ម៉ូត៖ <b>{cat_info['name']}</b>\n"
                    f"កញ្ចប់៖ <b>{prod['name'] if prod else prod_id} (${prod['price']:.2f}</b>)"
                ),
                parse_mode="HTML",
            )
            return

        if step == "wait_payload":
            payloads = []
            if message.content_type == "document":
                doc = message.document
                file_info = bot.get_file(doc.file_id)
                downloaded = bot.download_file(file_info.file_path)
                safe_name = f"{doc.file_unique_id}_{doc.file_name or 'file.bin'}"
                save_path = os.path.join(FILES_DIR, safe_name)
                with open(save_path, "wb") as f:
                    f.write(downloaded)
                payloads.append({"type": "file", "path": save_path, "name": doc.file_name or safe_name})
            elif message.content_type == "text" and message.text.strip():
                lines = [ln.strip() for ln in message.text.strip().splitlines() if ln.strip()]
                for ln in lines:
                    payloads.append({"type": "key", "value": ln})
            else:
                bot.reply_to(message, "❌ សូមផ្ញើ KEY (អត្ថបទ) ឬ ហ្វាល់។")
                return

            cat_key = state["cat_key"]
            prod_id = state["prod_id"]
            cat_info = data["categories"][cat_key]
            prod = next((p for p in cat_info["products"] if p["id"] == prod_id), None)
            if prod:
                prod.setdefault("items", []).extend(payloads)
                total_stock = sync_product_stock(prod)
                save_data(data)
                bot.reply_to(
                    message,
                    f"✅ <b>បានបន្ថែមស្ដុក {len(payloads)} រួចរាល់!</b>\n"
                    f"ម៉ូត៖ <b>{cat_info['name']}</b>\n"
                    f"កញ្ចប់៖ <b>{prod['name']} - ${prod['price']:.2f}</b>\n"
                    f"ស្ដុកសរុបបច្ចុប្បន្ន៖ <b>{total_stock} ស្ដុក</b>",
                    parse_mode="HTML",
                )
            admin_states.pop(sender_id, None)
            return

        elif step == "wait_price" and message.content_type == "text":
            new_price = validate_price(message.text, allow_zero=False)
            if new_price is None:
                bot.reply_to(message, "❌ សូមវាយតម្លៃជាលេខវិជ្ជមាន ឧទាហរណ៍៖ <code>0.25</code> ឬ <code>0.69</code>", parse_mode="HTML")
                return

            cat_key = state["cat_key"]
            prod_id = state["prod_id"]
            cat_info = data["categories"][cat_key]
            prod = next((p for p in cat_info["products"] if p["id"] == prod_id), None)
            if prod:
                prod["price"] = new_price
                save_data(data)
                bot.reply_to(
                    message,
                    f"✅ បានកែតម្លៃ <b>{prod['name']}</b> ទៅជា <b>${prod['price']:.2f}</b>",
                    parse_mode="HTML",
                )
            admin_states.pop(sender_id, None)
            return

        elif step == "wait_new_prod" and message.content_type == "text":
            raw = message.text.strip()
            if "|" not in raw:
                bot.reply_to(message, "❌ វាយតាមទម្រង់៖ <code>ឈ្មោះកញ្ចប់ | តម្លៃ</code> (ឧ. <code>3ម៉ោង | 0.69</code>)", parse_mode="HTML")
                return
            pname, pprice_str = [x.strip() for x in raw.split("|", 1)]
            pprice = validate_price(pprice_str, allow_zero=False)
            if pprice is None:
                bot.reply_to(message, "❌ តម្លៃមិនត្រឹមត្រូវទេ (ត្រូវតែជាលេខធំជាង 0)។")
                return
            cat_key = state["cat_key"]
            cat_info = data["categories"][cat_key]
            new_id = f"{cat_key}_{len(cat_info['products']) + 1}"
            cat_info["products"].append({
                "id": new_id,
                "name": pname,
                "price": pprice,
                "stock": 0,
                "emoji_id": None,
                "items": [],
            })
            save_data(data)
            bot.reply_to(
                message,
                f"✅ បានបន្ថែមកញ្ចប់ថ្មី <b>{pname} - ${pprice:.2f} [ស្ដុក 0]</b> ក្នុង <b>{cat_info['name']}</b>!",
                parse_mode="HTML",
            )
            admin_states.pop(sender_id, None)
            return


try:
    me = bot.get_me()
    bot.set_my_commands([
        types.BotCommand("start", "ចាប់ផ្តើម / ម៉ឺនុយដើម"),
        types.BotCommand("my_order", "ការបញ្ជាទិញរបស់ខ្ញុំ"),
        types.BotCommand("admin", "ផ្ទាំងគ្រប់គ្រង Admin"),
    ])
    print(f"✅ Connected as @{me.username}")
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
except Exception as e:
    print(f"❌ Bot failed to start: {e}")
