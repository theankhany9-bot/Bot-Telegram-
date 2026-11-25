import hashlib
from typing import Optional
from database import Database
from config import PAYMENT_GROUP_ID, CURRENCY, logger
from utils.helpers import parse_order_id_from_text, parse_amount_from_text


def evaluate_group_payment_notification(
    db: Database,
    chat_id: int,
    message_text: str,
    sender_id: Optional[int] = None,
) -> dict:
    result = {
        "authorized_source": False,
        "duplicate": False,
        "order_id": None,
        "auto_verified": False,
        "reason": "",
    }

    if PAYMENT_GROUP_ID is None or chat_id != PAYMENT_GROUP_ID:
        result["reason"] = "ប្រភពសារមិនមែនជាក្រុមជូនដំណឹងទូទាត់ដែលបានកំណត់ (PAYMENT_GROUP_ID) ទេ។"
        return result

    result["authorized_source"] = True
    clean_text = (message_text or "").strip()
    if not clean_text:
        result["reason"] = "ខ្លឹមសារសារទទេ។"
        return result

    notif_hash = hashlib.sha256(f"{chat_id}:{clean_text}".encode("utf-8")).hexdigest()
    order_id = parse_order_id_from_text(clean_text)

    if db.is_notification_processed(notif_hash):
        result["duplicate"] = True
        result["order_id"] = order_id
        result["reason"] = "សារជូនដំណឹងប្រតិបត្តិការនេះត្រូវបានដំណើរការរួចហើយ (ស្ទួន)។"
        return result

    db.mark_notification_processed(notif_hash, order_id, chat_id)
    result["order_id"] = order_id

    if not order_id:
        result["reason"] = "រកមិនឃើញលេខកូដវិក្កយបត្រ (Order ID) ក្នុងសារជូនដំណឹងទេ។"
        return result

    order = db.get_order(order_id)
    if not order:
        result["reason"] = f"រកមិនឃើញការបញ្ជាទិញ {order_id} ក្នុងប្រព័ន្ធទេ។"
        return result

    if order["order_status"] in ("Completed", "Cancelled", "Expired"):
        result["reason"] = f"ការបញ្ជាទិញ {order_id} ស្ថិតក្នុងស្ថានភាព {order['order_status']} រួចហើយ។"
        return result

    parsed_amount = parse_amount_from_text(clean_text)
    expected_amount = float(order["price_usd"])
    if parsed_amount is None or abs(parsed_amount - expected_amount) > 0.009:
        db.add_payment_record(
            order_id=order_id,
            user_id=int(order["user_id"]),
            amount_usd=parsed_amount if parsed_amount is not None else 0.0,
            currency=CURRENCY,
            source_type="payment_group",
            source_ref=f"chat:{chat_id}:sender:{sender_id}",
            verification_status="Uncertain Amount",
            raw_note=clean_text[:500],
        )
        amt_txt = f"{parsed_amount:.2f}" if parsed_amount is not None else "មិនច្បាស់"
        result["reason"] = (
            f"ទឹកប្រាក់មិនត្រូវគ្នា (រំពឹងទុក ${expected_amount:.2f} {CURRENCY}, "
            f"ឃើញ {amt_txt})។ ទុកជារង់ចាំ Admin ពិនិត្យ។"
        )
        return result

    db.add_payment_record(
        order_id=order_id,
        user_id=int(order["user_id"]),
        amount_usd=parsed_amount,
        currency=CURRENCY,
        source_type="payment_group",
        source_ref=f"chat:{chat_id}:sender:{sender_id}",
        verification_status="Group Notified (Needs Admin Confirm)",
        raw_note=clean_text[:500],
    )
    db.update_order_status(order_id, "Awaiting Verification", payment_status="Group Notified")
    result["auto_verified"] = False
    result["reason"] = (
        f"បានកត់ត្រាការជូនដំណឹងទូទាត់សម្រាប់ {order_id} (${parsed_amount:.2f} {CURRENCY}) "
        f"និងដាក់ជា Awaiting Verification រង់ចាំ Admin បញ្ជាក់។"
    )
    logger.info("Recorded payment group notification for order %s", order_id)
    return result
