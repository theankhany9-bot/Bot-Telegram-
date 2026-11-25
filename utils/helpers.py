import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def format_usd(amount: float) -> str:
    return f"${amount:.2f}"


def sanitize_contact_username(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return "@Beda_modz"
    if not raw.startswith("@"):
        raw = "@" + raw
    return raw


def contact_url(contact_handle: str) -> str:
    clean = sanitize_contact_username(contact_handle).lstrip("@")
    return f"https://t.me/{clean}"


def build_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🛍️ Shop / Choose a category", callback_data="shop_cats")],
        [InlineKeyboardButton("📦 My Order", callback_data="my_orders")],
        [InlineKeyboardButton("☎️ Contact Admin", callback_data="contact_admin")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("⚙️ Admin", callback_data="admin_menu")])
    return InlineKeyboardMarkup(rows)


def parse_order_id_from_text(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"\b(BD-\d{8}-[A-F0-9]{6})\b", text.upper())
    return m.group(1) if m else None


def parse_amount_from_text(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", text)
    if m:
        return float(m.group(1))
    m2 = re.search(r"\b(\d+(?:\.\d{1,2})?)\s*(?:USD|\$)", text.upper())
    if m2:
        return float(m2.group(1))
    return None
