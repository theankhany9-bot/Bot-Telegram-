import os
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("BedaStoreBot")


def _parse_admin_ids(raw_ids: str) -> set[int]:
    admins: set[int] = set()
    for part in (raw_ids or "").split(","):
        part = part.strip()
        if part.isdigit():
            admins.add(int(part))
    return admins


def _parse_group_id(raw_id: str) -> int | None:
    raw_id = (raw_id or "").strip()
    if not raw_id:
        return None
    try:
        return int(raw_id)
    except ValueError:
        return None


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
ENV_ADMIN_IDS: set[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
PAYMENT_GROUP_ID: int | None = _parse_group_id(os.getenv("PAYMENT_GROUP_ID", ""))
DEFAULT_CONTACT_ADMIN: str = os.getenv("CONTACT_ADMIN", "@Beda_modz").strip() or "@Beda_modz"
CURRENCY: str = (os.getenv("CURRENCY", "USD").strip() or "USD").upper()
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/beda_store.db").strip()

QR_DIR = "data/qr"
PHOTOS_DIR = "data/photos"
STOCK_UPLOADS_DIR = "data/stock_uploads"

ORDER_STATUSES = [
    "Pending Payment",
    "Awaiting Verification",
    "Confirmed",
    "Completed",
    "Cancelled",
    "Expired",
]

DEFAULT_SETTINGS = {
    "welcome_message": (
        "សូមស្វាគមន៍មកកាន់ BEDA STORE!\n"
        "ជ្រើសរើសប្រភេទទំនិញ ឬកញ្ចប់សេវាកម្មខាងក្រោមដើម្បីបញ្ជាទិញ។"
    ),
    "store_description": "ហាងលក់ផលិតផល និងសេវាកម្មឌីជីថល BEDA STORE។",
    "payment_instructions": (
        "សូមផ្ទេរប្រាក់តាម QR ឬព័ត៌មានទូទាត់ដែលបានកំណត់ បន្ទាប់មកចុចប៊ូតុង "
        "'✅ I have completed payment' ដើម្បីរង់ចាំការផ្ទៀងផ្ទាត់។"
    ),
    "payment_enabled": "1",
    "contact_admin": DEFAULT_CONTACT_ADMIN,
}
