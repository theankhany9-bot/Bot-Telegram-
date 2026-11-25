from telegram import Update
from telegram.ext import ContextTypes
from database import Database
from payment.verifier import evaluate_group_payment_notification
from customer.handlers import (
    show_main_menu,
    handle_shop_categories,
    handle_category_detail,
    handle_product_detail,
    handle_create_order,
    handle_paid_claim,
    handle_my_orders,
    handle_view_order,
    handle_contact_admin,
)
from admin.handlers import (
    show_admin_menu,
    handle_admin_callback,
    handle_admin_text_input,
    handle_admin_media_input,
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> None:
    context.user_data.pop("admin_state", None)
    await show_main_menu(update, context, db, edit=False)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> None:
    user = update.effective_user
    if not user or not db.is_admin(user.id):
        if update.message:
            await update.message.reply_text("⛔ អ្នកមិនមានសិទ្ធិចូលប្រើ /Admin ទេ។")
        return
    await show_admin_menu(update, context, db)


async def on_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""

    if data.startswith("adm_"):
        handled = await handle_admin_callback(update, context, db)
        if handled:
            return

    if data == "main_menu":
        await query.answer()
        await show_main_menu(update, context, db, edit=True)
        return

    if data == "shop_cats":
        await handle_shop_categories(update, context, db)
        return

    if data.startswith("cat_"):
        cat_id = int(data.replace("cat_", ""))
        await handle_category_detail(update, context, db, cat_id)
        return

    if data.startswith("prod_"):
        prod_id = int(data.replace("prod_", ""))
        await handle_product_detail(update, context, db, prod_id)
        return

    if data.startswith("buy_"):
        parts = data.split("_")
        prod_id = int(parts[1])
        pkg_id = int(parts[2])
        await handle_create_order(update, context, db, prod_id, pkg_id)
        return

    if data.startswith("paid_"):
        order_id = data.replace("paid_", "", 1)
        await handle_paid_claim(update, context, db, order_id)
        return

    if data == "my_orders":
        await handle_my_orders(update, context, db)
        return

    if data.startswith("view_ord_"):
        order_id = data.replace("view_ord_", "", 1)
        await handle_view_order(update, context, db, order_id)
        return

    if data == "contact_admin":
        await handle_contact_admin(update, context, db)
        return

    await query.answer()


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> None:
    msg = update.message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not chat:
        return

    if user:
        db.upsert_user(user.id, user.username, user.first_name, user.last_name)

    if chat.type in ("group", "supergroup"):
        text_content = msg.text or msg.caption or ""
        evaluate_group_payment_notification(
            db=db,
            chat_id=chat.id,
            message_text=text_content,
            sender_id=user.id if user else None,
        )
        return

    if msg.photo or msg.document:
        if await handle_admin_media_input(update, context, db):
            return

    if msg.text:
        if await handle_admin_text_input(update, context, db):
            return
        if msg.text.strip() in ("/menu", "Menu", "Start"):
            await show_main_menu(update, context, db, edit=False)
