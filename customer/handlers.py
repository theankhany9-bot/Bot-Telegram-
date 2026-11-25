import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from utils.helpers import format_usd, contact_url, build_main_menu_keyboard


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, edit: bool = False) -> None:
    user = update.effective_user
    if user:
        db.upsert_user(user.id, user.username, user.first_name, user.last_name)
    is_admin = db.is_admin(user.id) if user else False

    welcome_msg = db.get_setting("welcome_message", "សូមស្វាគមន៍មកកាន់ BEDA STORE!")
    store_desc = db.get_setting("store_description", "")
    text = f"<b>{welcome_msg}</b>"
    if store_desc:
        text += f"\n\n{store_desc}"

    kb = build_main_menu_keyboard(is_admin=is_admin)
    if edit and update.callback_query:
        try:
            await update.callback_query.edit_message_text(text=text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    if update.message:
        await update.message.reply_text(text=text, reply_markup=kb, parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.message.reply_text(text=text, reply_markup=kb, parse_mode="HTML")


async def handle_shop_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> None:
    query = update.callback_query
    await query.answer()
    categories = db.get_categories(include_inactive=False)
    if not categories:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        await query.edit_message_text("បច្ចុប្បន្នមិនទាន់មានប្រភេទទំនិញនៅឡើយទេ។", reply_markup=kb)
        return

    rows = []
    for cat in categories:
        rows.append([InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"cat_{cat['id']}")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    await query.edit_message_text(
        "<b>🛍️ ជ្រើសរើសប្រភេទទំនិញ (Choose a Category):</b>",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="HTML",
    )


async def handle_category_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, cat_id: int) -> None:
    query = update.callback_query
    await query.answer()
    cat = db.get_category(cat_id)
    if not cat or not cat["is_active"]:
        await query.answer("មិនមានប្រភេទនេះទេ។", show_alert=True)
        return

    products = db.get_products_by_category(cat_id, include_inactive=False)
    lines = [f"<b>📁 {cat['name']}</b>"]
    if cat["description"]:
        lines.append(cat["description"])
    lines.append("\n<b>បញ្ជីទំនិញ៖</b>")

    rows = []
    for prod in products:
        stock_cnt = db.get_stock_count(prod["id"])
        pkgs = db.get_packages_by_product(prod["id"], include_inactive=False)
        if pkgs:
            min_price = min(float(p["price_usd"]) for p in pkgs)
            price_label = f"ចាប់ពី {format_usd(min_price)}"
        else:
            price_label = format_usd(float(prod["price_usd"]))
        stock_label = f"ស្តុក: {stock_cnt}" if stock_cnt > 0 else "❌ Out of Stock"
        lines.append(f"• <b>{prod['name']}</b> — {price_label} | {stock_label}")
        rows.append([InlineKeyboardButton(f"🛒 {prod['name']} ({price_label})", callback_data=f"prod_{prod['id']}")])

    if not products:
        lines.append("<i>មិនទាន់មានផលិតផលក្នុងប្រភេទនេះទេ។</i>")

    rows.append([InlineKeyboardButton("🔙 Back", callback_data="shop_cats")])
    text = "\n".join(lines)

    if cat["photo_path"] and os.path.exists(cat["photo_path"]):
        try:
            with open(cat["photo_path"], "rb") as photo:
                await query.message.reply_photo(photo=photo, caption=text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
            return
        except Exception:
            pass
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


async def handle_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, prod_id: int) -> None:
    query = update.callback_query
    await query.answer()
    prod = db.get_product(prod_id)
    if not prod or not prod["is_active"]:
        await query.answer("ផលិតផលមិនមាន ឬត្រូវបានបិទ។", show_alert=True)
        return

    pkgs = db.get_packages_by_product(prod_id, include_inactive=False)
    stock_cnt = db.get_stock_count(prod_id)

    lines = [f"<b>📦 {prod['name']}</b>"]
    if prod["description"]:
        lines.append(prod["description"])
    lines.append(f"<b>ស្ថានភាពស្តុក៖</b> {'មានស្តុក (' + str(stock_cnt) + ')' if stock_cnt > 0 else '❌ Out of Stock'}")

    rows = []
    if stock_cnt <= 0:
        lines.append("\n⚠️ <b>Out of Stock</b> — ស្តុកអស់ហើយ សូមរង់ចាំការបំពេញបន្ថែមពី Admin។")
    else:
        if pkgs:
            lines.append("\n<b>ជ្រើសរើសកញ្ចប់ (Packages):</b>")
            for pkg in pkgs:
                pkg_stock = db.get_stock_count(prod_id, pkg["id"])
                dur = f" ({pkg['duration_label']})" if pkg["duration_label"] else ""
                label = f"🛍️ Buy: {pkg['name']}{dur} — {format_usd(float(pkg['price_usd']))}"
                if pkg_stock <= 0:
                    label += " [Out of Stock]"
                rows.append([InlineKeyboardButton(label, callback_data=f"buy_{prod_id}_{pkg['id']}")])
        else:
            price_val = float(prod["price_usd"])
            lines.append(f"<b>តម្លៃ៖</b> {format_usd(price_val)}")
            rows.append([InlineKeyboardButton(f"🛍️ Buy — {format_usd(price_val)}", callback_data=f"buy_{prod_id}_0")])

    rows.append([InlineKeyboardButton("🔙 Back", callback_data=f"cat_{prod['category_id']}")])
    text = "\n".join(lines)

    if prod["photo_path"] and os.path.exists(prod["photo_path"]):
        try:
            with open(prod["photo_path"], "rb") as photo:
                await query.message.reply_photo(photo=photo, caption=text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
            return
        except Exception:
            pass
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


async def handle_create_order(
    update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, prod_id: int, pkg_id: int
) -> None:
    query = update.callback_query
    user = update.effective_user
    if not user:
        return
    db.upsert_user(user.id, user.username, user.first_name, user.last_name)

    if db.get_setting("payment_enabled", "1") != "1":
        await query.answer("ការទូទាត់ត្រូវបានផ្អាកបណ្ដោះអាសន្ន។", show_alert=True)
        return

    prod = db.get_product(prod_id)
    if not prod or not prod["is_active"]:
        await query.answer("ផលិតផលមិនអាចបញ្ជាទិញបានទេ។", show_alert=True)
        return

    pkg = db.get_package(pkg_id) if pkg_id > 0 else None
    if pkg_id > 0 and (not pkg or not pkg["is_active"]):
        await query.answer("កញ្ចប់នេះមិនមានទេ។", show_alert=True)
        return

    stock_cnt = db.get_stock_count(prod_id, pkg["id"] if pkg else None)
    if stock_cnt <= 0:
        await query.answer("Out of Stock! ស្តុកអស់ហើយ។", show_alert=True)
        return

    pkg_name = pkg["name"] if pkg else "Standard"
    price_usd = float(pkg["price_usd"]) if pkg else float(prod["price_usd"])

    order = db.create_order(
        user_id=user.id,
        username=user.username,
        category_id=prod["category_id"],
        product_id=prod["id"],
        package_id=pkg["id"] if pkg else None,
        product_name=prod["name"],
        package_name=pkg_name,
        price_usd=price_usd,
    )
    if not order:
        await query.answer("មិនអាចបង្កើតវិក្កយបត្របានទេ។", show_alert=True)
        return

    await query.answer("បានបង្កើតការបញ្ជាទិញ។")

    pay_instructions = db.get_setting("payment_instructions", "")
    qr_path = (pkg["qr_path"] if pkg and pkg["qr_path"] else None) or db.get_setting("default_qr_path", "")
    if pkg and pkg["payment_note"]:
        pay_instructions = f"{pay_instructions}\n\n<b>កំណត់សម្គាល់កញ្ចប់៖</b> {pkg['payment_note']}"

    text = (
        f"<b>🧾 វិក្កយបត្របញ្ជាទិញ (Order Summary)</b>\n"
        f"• <b>Order ID:</b> <code>{order['order_id']}</code>\n"
        f"• <b>ផលិតផល៖</b> {order['product_name']}\n"
        f"• <b>កញ្ចប់៖</b> {order['package_name']}\n"
        f"• <b>តម្លៃ៖</b> {format_usd(float(order['price_usd']))} ({order['currency']})\n"
        f"• <b>ស្ថានភាពទូទាត់៖</b> {order['payment_status']}\n"
        f"• <b>ស្ថានភាពបញ្ជាទិញ៖</b> {order['order_status']}\n\n"
        f"<b>💳 វិធីទូទាត់៖</b>\n{pay_instructions}\n\n"
        f"<i>បន្ទាប់ពីផ្ទេរប្រាក់រួច សូមចុចប៊ូតុងខាងក្រោមដើម្បីស្នើផ្ទៀងផ្ទាត់ (Admin នឹងផ្ទៀងផ្ទាត់ប្រតិបត្តិការមុនពេលប្រគល់ទំនិញ)។</i>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I have completed payment", callback_data=f"paid_{order['order_id']}")],
        [InlineKeyboardButton("📦 My Order", callback_data="my_orders")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"prod_{prod_id}")],
    ])

    if qr_path and os.path.exists(qr_path):
        try:
            with open(qr_path, "rb") as qr_img:
                await query.message.reply_photo(photo=qr_img, caption=text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await query.edit_message_text(text=text, reply_markup=kb, parse_mode="HTML")


async def handle_paid_claim(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, order_id: str) -> None:
    query = update.callback_query
    user = update.effective_user
    if not user:
        return

    updated = db.mark_awaiting_verification(order_id, user.id)
    if not updated:
        await query.answer("រកមិនឃើញវិក្កយបត្ររបស់អ្នកទេ។", show_alert=True)
        return

    db.add_payment_record(
        order_id=order_id,
        user_id=user.id,
        amount_usd=float(updated["price_usd"]),
        currency=updated["currency"],
        source_type="customer_claim",
        source_ref=f"user:{user.id}",
        verification_status="Awaiting Admin Verification",
        raw_note="Customer clicked 'I have completed payment'",
    )

    await query.answer("បានផ្ញើសំណើរង់ចាំការផ្ទៀងផ្ទាត់ពី Admin!", show_alert=True)

    for admin_id in db.list_admins():
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔔 <b>សំណើផ្ទៀងផ្ទាត់ការទូទាត់ថ្មី</b>\n"
                    f"• <b>Order ID:</b> <code>{updated['order_id']}</code>\n"
                    f"• <b>User ID:</b> <code>{user.id}</code> (@{user.username or 'none'})\n"
                    f"• <b>ទំនិញ៖</b> {updated['product_name']} — {updated['package_name']}\n"
                    f"• <b>ទឹកប្រាក់៖</b> {format_usd(float(updated['price_usd']))} {updated['currency']}\n"
                    f"<i>សូមផ្ទៀងផ្ទាត់ប្រតិបត្តិការជាមួយប្រព័ន្ធ/ក្រុមជូនដំណឹងមុនពេលបញ្ជាក់។</i>"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 My Order", callback_data="my_orders")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ])
    await query.edit_message_text(
        text=(
            f"⏳ <b>កំពុងរង់ចាំការផ្ទៀងផ្ទាត់ (Awaiting Verification)</b>\n"
            f"• <b>Order ID:</b> <code>{updated['order_id']}</code>\n"
            f"• <b>ស្ថានភាព៖</b> {updated['order_status']}\n\n"
            f"សូមរង់ចាំ Admin ពិនិត្យ និងផ្ទៀងផ្ទាត់ការទូទាត់របស់អ្នក។"
        ),
        reply_markup=kb,
        parse_mode="HTML",
    )


async def handle_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> None:
    query = update.callback_query
    user = update.effective_user
    if not user:
        return
    await query.answer()
    orders = db.get_user_orders(user.id)
    if not orders:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        await query.edit_message_text("អ្នកមិនទាន់មានប្រវត្តិបញ្ជាទិញនៅឡើយទេ។", reply_markup=kb)
        return

    lines = ["<b>📦 ការបញ្ជាទិញរបស់ខ្ញុំ (My Orders)៖</b>\n"]
    rows = []
    for o in orders[:15]:
        lines.append(
            f"• <code>{o['order_id']}</code> | {o['product_name']} ({o['package_name']})\n"
            f"  តម្លៃ: {format_usd(float(o['price_usd']))} | ទូទាត់: {o['payment_status']} | ស្ថានភាព: <b>{o['order_status']}</b> | {o['created_at']}"
        )
        rows.append([InlineKeyboardButton(f"🔍 View Order: {o['order_id']}", callback_data=f"view_ord_{o['order_id']}")])

    rows.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


async def handle_view_order(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, order_id: str) -> None:
    query = update.callback_query
    user = update.effective_user
    if not user:
        return
    await query.answer()

    order = db.get_order(order_id)
    if not order:
        await query.answer("រកមិនឃើញវិក្កយបត្រទេ។", show_alert=True)
        return

    if int(order["user_id"]) != user.id and not db.is_admin(user.id):
        await query.answer("អ្នកមិនមានសិទ្ធិមើលវិក្កយបត្ររបស់អ្នកដទៃទេ។", show_alert=True)
        return

    lines = [
        "<b>🧾 ព័ត៌មានលម្អិតវិក្កយបត្រ</b>",
        f"• <b>Order ID:</b> <code>{order['order_id']}</code>",
        f"• <b>ផលិតផល៖</b> {order['product_name']}",
        f"• <b>កញ្ចប់៖</b> {order['package_name']}",
        f"• <b>តម្លៃ៖</b> {format_usd(float(order['price_usd']))} {order['currency']}",
        f"• <b>កាលបរិច្ឆេទ៖</b> {order['created_at']}",
        f"• <b>ស្ថានភាពទូទាត់៖</b> {order['payment_status']}",
        f"• <b>ស្ថានភាពបញ្ជាទិញ៖</b> <b>{order['order_status']}</b>",
    ]
    if order["order_status"] == "Completed" and order["delivered_content"]:
        lines.append(f"\n<b>🎁 ទិន្នន័យ/លេខកូដដែលបានប្រគល់៖</b>\n<code>{order['delivered_content']}</code>")
    elif order["delivery_error"]:
        lines.append(f"\n⚠️ <b>កំណត់សម្គាល់ការប្រគល់៖</b> {order['delivery_error']}")

    rows = []
    if order["order_status"] == "Pending Payment":
        rows.append([InlineKeyboardButton("✅ I have completed payment", callback_data=f"paid_{order['order_id']}")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="my_orders")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


async def handle_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> None:
    query = update.callback_query
    await query.answer()
    contact_handle = db.get_setting("contact_admin", "@Beda_modz")
    url = contact_url(contact_handle)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"☎️ Contact Admin ({contact_handle})", url=url)],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ])
    await query.edit_message_text(
        f"<b>☎️ ទំនាក់ទំនង Admin (Customer Support)</b>\nសូមទាក់ទងទៅកាន់ <b>{contact_handle}</b> ប្រសិនបើមានបញ្ហា ឬសំណួរបន្ថែម។",
        reply_markup=kb,
        parse_mode="HTML",
    )
