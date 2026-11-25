import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from config import QR_DIR, PHOTOS_DIR, STOCK_UPLOADS_DIR, logger
from utils.helpers import format_usd, sanitize_contact_username


def _not_admin_text() -> str:
    return "⛔ អ្នកមិនមានសិទ្ធិចូលប្រើមុខងារ Admin ទេ។"


async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> None:
    user = update.effective_user
    if not user or not db.is_admin(user.id):
        if update.callback_query:
            await update.callback_query.answer(_not_admin_text(), show_alert=True)
        return

    context.user_data.pop("admin_state", None)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Manage Products", callback_data="adm_products"),
            InlineKeyboardButton("📁 Manage Categories", callback_data="adm_categories"),
        ],
        [
            InlineKeyboardButton("💰 Manage Prices", callback_data="adm_prices"),
            InlineKeyboardButton("📊 Manage Stock", callback_data="adm_stock"),
        ],
        [
            InlineKeyboardButton("🧾 Manage Orders", callback_data="adm_orders"),
            InlineKeyboardButton("💳 Payment Settings", callback_data="adm_payment"),
        ],
        [
            InlineKeyboardButton("🖼️ Upload Product Photos", callback_data="adm_photos"),
            InlineKeyboardButton("✏️ Edit Welcome Message", callback_data="adm_welcome"),
        ],
        [
            InlineKeyboardButton("☎️ Contact Settings", callback_data="adm_contact"),
            InlineKeyboardButton("👥 Admin Management", callback_data="adm_admins"),
        ],
        [
            InlineKeyboardButton("📈 Statistics", callback_data="adm_stats"),
            InlineKeyboardButton("🔙 Back", callback_data="main_menu"),
        ],
    ])

    text = "<b>⚙️ ផ្ទាំងគ្រប់គ្រង Admin (BEDA STORE Admin Panel)</b>\nជ្រើសរើសមុខងារដែលចង់គ្រប់គ្រង៖"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=kb, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=kb, parse_mode="HTML")


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> bool:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return False
    data = query.data or ""
    if not data.startswith("adm_"):
        return False

    if not db.is_admin(user.id):
        await query.answer(_not_admin_text(), show_alert=True)
        return True

    if data == "adm_menu":
        await show_admin_menu(update, context, db)
        return True

    # --- Categories ---
    if data == "adm_categories":
        await query.answer()
        cats = db.get_categories(include_inactive=True)
        lines = ["<b>📁 គ្រប់គ្រងប្រភេទទំនិញ (Manage Categories)</b>"]
        rows = []
        for idx, c in enumerate(cats):
            status = "Active" if c["is_active"] else "Disabled"
            lines.append(f"• #{c['id']} <b>{c['name']}</b> [{status}] (order={c['sort_order']})")
            btn_row = [
                InlineKeyboardButton(f"✏️ {c['name']}", callback_data=f"adm_cat_edit_{c['id']}"),
                InlineKeyboardButton("🔄 Toggle", callback_data=f"adm_cat_tog_{c['id']}"),
                InlineKeyboardButton("🗑️ Del", callback_data=f"adm_cat_del_{c['id']}"),
            ]
            if idx > 0:
                btn_row.append(InlineKeyboardButton("⬆️", callback_data=f"adm_cat_up_{c['id']}_{cats[idx-1]['id']}"))
            rows.append(btn_row)
        rows.append([InlineKeyboardButton("➕ បង្កើតប្រភេទថ្មី (Create Category)", callback_data="adm_cat_new")])
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="adm_menu")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return True

    if data == "adm_cat_new":
        await query.answer()
        context.user_data["admin_state"] = {"action": "create_category"}
        await query.edit_message_text(
            "ផ្ញើឈ្មោះប្រភេទថ្មី និងការពិពណ៌នា (ឧទាហរណ៍៖ <code>VPN PROXY.VIP | សេវា VPN ល្បឿនលឿន</code>)៖",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_categories")]]),
            parse_mode="HTML",
        )
        return True

    if data.startswith("adm_cat_tog_"):
        cid = int(data.split("_")[-1])
        cat = db.get_category(cid)
        if cat:
            db.update_category(cid, is_active=0 if cat["is_active"] else 1)
        await query.answer("បានប្ដូរស្ថានភាពប្រភេទ។")
        query.data = "adm_categories"
        return await handle_admin_callback(update, context, db)

    if data.startswith("adm_cat_del_"):
        cid = int(data.split("_")[-1])
        db.delete_category(cid)
        await query.answer("បានលុបប្រភេទ។")
        query.data = "adm_categories"
        return await handle_admin_callback(update, context, db)

    if data.startswith("adm_cat_up_"):
        parts = data.split("_")
        db.swap_category_order(int(parts[3]), int(parts[4]))
        await query.answer("បានប្ដូរលំដាប់។")
        query.data = "adm_categories"
        return await handle_admin_callback(update, context, db)

    if data.startswith("adm_cat_edit_"):
        cid = int(data.split("_")[-1])
        await query.answer()
        context.user_data["admin_state"] = {"action": "edit_category", "category_id": cid}
        await query.edit_message_text(
            f"កែសម្រួលប្រភេទ #{cid}៖ ផ្ញើ <code>ឈ្មោះថ្មី | ការពិពណ៌នាថ្មី</code> ឬផ្ញើ <b>រូបភាព</b> ដើម្បីកំណត់រូបភាពប្រភេទ។",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_categories")]]),
            parse_mode="HTML",
        )
        return True

    # --- Products & Packages ---
    if data == "adm_products":
        await query.answer()
        prods = db.get_all_products()
        lines = ["<b>📦 គ្រប់គ្រងផលិតផល និងកញ្ចប់ (Manage Products & Packages)</b>"]
        rows = []
        for p in prods:
            st = db.get_stock_count(p["id"])
            status = "Active" if p["is_active"] else "Disabled"
            lines.append(f"• #{p['id']} <b>{p['name']}</b> — {format_usd(float(p['price_usd']))} | Stock: {st} [{status}]")
            rows.append([
                InlineKeyboardButton(f"✏️ {p['name']}", callback_data=f"adm_prod_cfg_{p['id']}"),
                InlineKeyboardButton("🔄 Toggle", callback_data=f"adm_prod_tog_{p['id']}"),
                InlineKeyboardButton("🗑️ Del", callback_data=f"adm_prod_del_{p['id']}"),
            ])
        rows.append([InlineKeyboardButton("➕ បន្ថែមផលិតផលថ្មី (Add Product)", callback_data="adm_prod_new")])
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="adm_menu")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return True

    if data == "adm_prod_new":
        await query.answer()
        cats = db.get_categories(include_inactive=True)
        if not cats:
            await query.answer("សូមបង្កើតប្រភេទទំនិញជាមុនសិន។", show_alert=True)
            return True
        rows = [[InlineKeyboardButton(f"📁 {c['name']}", callback_data=f"adm_prod_newcat_{c['id']}")] for c in cats]
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="adm_products")])
        await query.edit_message_text("ជ្រើសរើសប្រភេទសម្រាប់ផលិតផលថ្មី៖", reply_markup=InlineKeyboardMarkup(rows))
        return True

    if data.startswith("adm_prod_newcat_"):
        cid = int(data.split("_")[-1])
        await query.answer()
        context.user_data["admin_state"] = {"action": "create_product", "category_id": cid}
        await query.edit_message_text(
            "ផ្ញើព័ត៌មានផលិតផលថ្មី៖\n<code>ឈ្មោះ | តម្លៃUSD | ការពិពណ៌នា</code>\nឧទាហរណ៍៖ <code>E-SIGN Certificate | 5.00 | សេវាវិញ្ញាបនបត្រ iOS</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_products")]]),
            parse_mode="HTML",
        )
        return True

    if data.startswith("adm_prod_tog_"):
        pid = int(data.split("_")[-1])
        p = db.get_product(pid)
        if p:
            db.update_product(pid, is_active=0 if p["is_active"] else 1)
        await query.answer("បានប្ដូរស្ថានភាពផលិតផល។")
        query.data = "adm_products"
        return await handle_admin_callback(update, context, db)

    if data.startswith("adm_prod_del_"):
        pid = int(data.split("_")[-1])
        db.delete_product(pid)
        await query.answer("បានលុបផលិតផល។")
        query.data = "adm_products"
        return await handle_admin_callback(update, context, db)

    if data.startswith("adm_prod_cfg_"):
        pid = int(data.split("_")[-1])
        await query.answer()
        p = db.get_product(pid)
        if not p:
            return True
        pkgs = db.get_packages_by_product(pid, include_inactive=True)
        lines = [
            f"<b>ផលិតផល #{p['id']}: {p['name']}</b>",
            f"តម្លៃមូលដ្ឋាន៖ {format_usd(float(p['price_usd']))}",
            f"ការពិពណ៌នា៖ {p['description'] or '-'}",
            "<b>កញ្ចប់ (Packages)៖</b>",
        ]
        for pkg in pkgs:
            dur = f" ({pkg['duration_label']})" if pkg["duration_label"] else ""
            lines.append(f"• #{pkg['id']} {pkg['name']}{dur} — {format_usd(float(pkg['price_usd']))} [{'Active' if pkg['is_active'] else 'Off'}]")

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ បន្ថែមកញ្ចប់ (Add Package)", callback_data=f"adm_pkg_add_{pid}")],
            [InlineKeyboardButton("✏️ កែឈ្មោះ/តម្លៃ/ពិពណ៌នា", callback_data=f"adm_prod_edit_{pid}")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_products")],
        ])
        await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        return True

    if data.startswith("adm_prod_edit_"):
        pid = int(data.split("_")[-1])
        await query.answer()
        context.user_data["admin_state"] = {"action": "edit_product", "product_id": pid}
        await query.edit_message_text(
            "ផ្ញើ៖ <code>ឈ្មោះថ្មី | តម្លៃUSDថ្មី | ការពិពណ៌នាថ្មី</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"adm_prod_cfg_{pid}")]]),
            parse_mode="HTML",
        )
        return True

    if data.startswith("adm_pkg_add_"):
        pid = int(data.split("_")[-1])
        await query.answer()
        context.user_data["admin_state"] = {"action": "add_package", "product_id": pid}
        await query.edit_message_text(
            "ផ្ញើកញ្ចប់ថ្មី៖\n<code>ឈ្មោះកញ្ចប់ | រយៈពេល | តម្លៃUSD</code>\nឧទាហរណ៍៖ <code>1 Hour | 1 Hour | 0.25</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"adm_prod_cfg_{pid}")]]),
            parse_mode="HTML",
        )
        return True

    # --- Prices ---
    if data == "adm_prices":
        await query.answer()
        prods = db.get_all_products()
        rows = [[InlineKeyboardButton(f"💰 {p['name']} ({format_usd(float(p['price_usd']))})", callback_data=f"adm_pr_prod_{p['id']}")] for p in prods]
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="adm_menu")])
        await query.edit_message_text("<b>💰 គ្រប់គ្រងតម្លៃ (Manage Prices)</b>\nជ្រើសរើសផលិតផល៖", reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return True

    if data.startswith("adm_pr_prod_"):
        pid = int(data.split("_")[-1])
        await query.answer()
        p = db.get_product(pid)
        pkgs = db.get_packages_by_product(pid, include_inactive=True)
        rows = [[InlineKeyboardButton(f"Base Price: {format_usd(float(p['price_usd']))}", callback_data=f"adm_set_pprice_{pid}")]]
        for pkg in pkgs:
            rows.append([InlineKeyboardButton(f"Pkg {pkg['name']}: {format_usd(float(pkg['price_usd']))}", callback_data=f"adm_set_kprice_{pkg['id']}_{pid}")])
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="adm_prices")])
        await query.edit_message_text(f"ជ្រើសរើសដើម្បីប្ដូរតម្លៃសម្រាប់ <b>{p['name']}</b>៖", reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return True

    if data.startswith("adm_set_pprice_"):
        pid = int(data.split("_")[-1])
        await query.answer()
        context.user_data["admin_state"] = {"action": "set_product_price", "product_id": pid}
        await query.edit_message_text("ផ្ញើតម្លៃថ្មីជា USD (ឧទាហរណ៍៖ <code>2.50</code>):", parse_mode="HTML")
        return True

    if data.startswith("adm_set_kprice_"):
        parts = data.split("_")
        pkg_id, pid = int(parts[3]), int(parts[4])
        await query.answer()
        context.user_data["admin_state"] = {"action": "set_package_price", "package_id": pkg_id, "product_id": pid}
        await query.edit_message_text("ផ្ញើតម្លៃកញ្ចប់ថ្មីជា USD (ឧទាហរណ៍៖ <code>1.20</code>):", parse_mode="HTML")
        return True

    # --- Stock ---
    if data == "adm_stock":
        await query.answer()
        prods = db.get_all_products()
        rows = []
        for p in prods:
            cnt = db.get_stock_count(p["id"])
            rows.append([InlineKeyboardButton(f"📊 {p['name']} (Available: {cnt})", callback_data=f"adm_st_prod_{p['id']}")])
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="adm_menu")])
        await query.edit_message_text("<b>📊 គ្រប់គ្រងស្តុក (Manage Stock)</b>\nជ្រើសរើសផលិតផល៖", reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return True

    if data.startswith("adm_st_prod_"):
        pid = int(data.split("_")[-1])
        await query.answer()
        p = db.get_product(pid)
        items = db.list_stock_items(pid, include_used=False)
        avail = sum(1 for i in items if i["is_available"])
        lines = [
            f"<b>📊 ស្តុកផលិតផល៖ {p['name']}</b>",
            f"• ស្តុកមិនទាន់ប្រើសរុប៖ {len(items)} (Available: {avail})",
        ]
        for it in items[:10]:
            st_flag = "ON" if it["is_available"] else "OFF"
            lines.append(f"  - #{it['id']} [{st_flag}]: <code>{it['content'][:35]}</code>")

        rows = [
            [InlineKeyboardButton("➕ Add Stock (Multiple/Single)", callback_data=f"adm_st_add_{pid}")],
            [InlineKeyboardButton("📄 Upload Stock .TXT File", callback_data=f"adm_st_file_{pid}")],
            [InlineKeyboardButton("🗑️ Clear Unused Stock", callback_data=f"adm_st_clr_{pid}")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_stock")],
        ]
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return True

    if data.startswith("adm_st_add_"):
        pid = int(data.split("_")[-1])
        await query.answer()
        context.user_data["admin_state"] = {"action": "add_stock_text", "product_id": pid}
        await query.edit_message_text(
            "ផ្ញើទិន្នន័យស្តុក (១ ជួរ = ១ ស្តុក ឬច្រើនជួរក្នុងពេលតែមួយ)៖",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"adm_st_prod_{pid}")]]),
        )
        return True

    if data.startswith("adm_st_file_"):
        pid = int(data.split("_")[-1])
        await query.answer()
        context.user_data["admin_state"] = {"action": "upload_stock_file", "product_id": pid}
        await query.edit_message_text(
            "សូមផ្ញើឯកសារ <b>.txt</b> ដែលមានស្តុក (១ ជួរ = ១ entry)៖",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"adm_st_prod_{pid}")]]),
            parse_mode="HTML",
        )
        return True

    if data.startswith("adm_st_clr_"):
        pid = int(data.split("_")[-1])
        removed = db.clear_unused_stock(pid)
        await query.answer(f"បានលុបស្តុកមិនទាន់ប្រើចំនួន {removed}។", show_alert=True)
        query.data = f"adm_st_prod_{pid}"
        return await handle_admin_callback(update, context, db)

    # --- Orders ---
    if data == "adm_orders" or data.startswith("adm_ord_list_"):
        await query.answer()
        status_filter = "ALL"
        if data.startswith("adm_ord_list_"):
            status_filter = data.replace("adm_ord_list_", "")
        orders = db.list_orders(status_filter=status_filter, limit=15)
        lines = [f"<b>🧾 គ្រប់គ្រងការបញ្ជាទិញ (Filter: {status_filter})</b>"]
        rows = []
        for o in orders:
            lines.append(f"• <code>{o['order_id']}</code> | {format_usd(float(o['price_usd']))} | <b>{o['order_status']}</b>")
            rows.append([InlineKeyboardButton(f"🔍 {o['order_id']} ({o['order_status']})", callback_data=f"adm_ord_v_{o['order_id']}")])

        rows.append([
            InlineKeyboardButton("All", callback_data="adm_ord_list_ALL"),
            InlineKeyboardButton("Pending", callback_data="adm_ord_list_Pending Payment"),
            InlineKeyboardButton("Awaiting", callback_data="adm_ord_list_Awaiting Verification"),
        ])
        rows.append([
            InlineKeyboardButton("Completed", callback_data="adm_ord_list_Completed"),
            InlineKeyboardButton("Cancelled", callback_data="adm_ord_list_Cancelled"),
        ])
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="adm_menu")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return True

    if data.startswith("adm_ord_v_"):
        oid = data.replace("adm_ord_v_", "")
        await query.answer()
        o = db.get_order(oid)
        if not o:
            return True
        pay_recs = db.get_payment_records_for_order(oid)
        text = (
            f"<b>🧾 វិក្កយបត្រ <code>{o['order_id']}</code></b>\n"
            f"• User ID: <code>{o['user_id']}</code> (@{o['username'] or 'none'})\n"
            f"• ផលិតផល៖ {o['product_name']} — {o['package_name']}\n"
            f"• តម្លៃ៖ {format_usd(float(o['price_usd']))} {o['currency']}\n"
            f"• ស្ថានភាពទូទាត់៖ {o['payment_status']}\n"
            f"• ស្ថានភាពបញ្ជាទិញ៖ <b>{o['order_status']}</b>\n"
            f"• កំណត់ត្រាទូទាត់៖ {len(pay_recs)} ប្រតិបត្តិការ"
        )
        rows = []
        if o["order_status"] not in ("Completed", "Cancelled"):
            rows.append([InlineKeyboardButton("✅ Confirm & Deliver Stock", callback_data=f"adm_ord_ok_{oid}")])
            rows.append([InlineKeyboardButton("❌ Cancel Order", callback_data=f"adm_ord_no_{oid}")])
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="adm_orders")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return True

    if data.startswith("adm_ord_ok_"):
        oid = data.replace("adm_ord_ok_", "")
        o = db.get_order(oid)
        if not o:
            return True
        if o["order_status"] == "Completed":
            await query.answer("វិក្កយបត្រនេះបានបញ្ចប់ និងប្រគល់រួចហើយ។", show_alert=True)
            return True

        db.update_order_status(oid, "Confirmed", payment_status="Verified", admin_id=user.id)
        db.add_payment_record(
            order_id=oid,
            user_id=int(o["user_id"]),
            amount_usd=float(o["price_usd"]),
            currency=o["currency"],
            source_type="admin_verified",
            source_ref=f"admin:{user.id}",
            verification_status="Verified by Admin",
            verified_by=user.id,
        )

        delivered = db.claim_stock_for_order(oid, int(o["product_id"]), o["package_id"])
        if delivered:
            await query.answer("បានផ្ទៀងផ្ទាត់ និងប្រគល់ស្តុកជោគជ័យ!", show_alert=True)
            try:
                await context.bot.send_message(
                    chat_id=int(o["user_id"]),
                    text=(
                        f"✅ <b>ការបញ្ជាទិញរបស់អ្នកត្រូវបានអនុម័ត និងប្រគល់រួចរាល់!</b>\n"
                        f"• <b>Order ID:</b> <code>{oid}</code>\n"
                        f"• <b>ផលិតផល៖</b> {o['product_name']} ({o['package_name']})\n"
                        f"• <b>ទិន្នន័យ/លេខកូដ៖</b>\n<code>{delivered}</code>"
                    ),
                    parse_mode="HTML",
                )
            except Exception as exc:
                logger.warning("Failed notifying customer %s for order %s: %s", o["user_id"], oid, exc)
        else:
            err_msg = "គ្មានស្តុកសម្រាប់ប្រគល់ (Out of Stock) ពេលបញ្ជាក់ការទូទាត់។"
            db.update_order_status(oid, "Confirmed", payment_status="Verified", admin_id=user.id, delivery_error=err_msg)
            await query.answer("⚠️ ទូទាត់ត្រូវបានបញ្ជាក់ ប៉ុន្តែស្តុកអស់ (Out of Stock)!", show_alert=True)
            try:
                await context.bot.send_message(
                    chat_id=int(o["user_id"]),
                    text=f"⚠️ ការទូទាត់ <code>{oid}</code> ត្រូវបានបញ្ជាក់ ប៉ុន្តែស្តុកអស់បណ្ដោះអាសន្ន។ Admin នឹងប្រគល់ជូនឆាប់ៗ។",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        query.data = f"adm_ord_v_{oid}"
        return await handle_admin_callback(update, context, db)

    if data.startswith("adm_ord_no_"):
        oid = data.replace("adm_ord_no_", "")
        db.update_order_status(oid, "Cancelled", payment_status="Cancelled", admin_id=user.id)
        await query.answer("បានលុបចោលវិក្កយបត្រ។")
        query.data = f"adm_ord_v_{oid}"
        return await handle_admin_callback(update, context, db)

    # --- Payment Settings & QR ---
    if data == "adm_payment":
        await query.answer()
        enabled = db.get_setting("payment_enabled", "1") == "1"
        qr_path = db.get_setting("default_qr_path", "")
        inst = db.get_setting("payment_instructions", "")
        text = (
            f"<b>💳 ការកំណត់ការទូទាត់ (Payment Settings)</b>\n"
            f"• ស្ថានភាព៖ {'✅ Enabled' if enabled else '❌ Disabled'}\n"
            f"• រូបភាព QR៖ {qr_path if qr_path else 'មិនទាន់កំណត់'}\n"
            f"• ការណែនាំទូទាត់៖ {inst}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼️ Upload / Replace QR Image", callback_data="adm_pay_qr")],
            [InlineKeyboardButton("✏️ Edit Payment Instructions", callback_data="adm_pay_inst")],
            [InlineKeyboardButton("🔄 Enable / Disable Payment", callback_data="adm_pay_tog")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_menu")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return True

    if data == "adm_pay_qr":
        await query.answer()
        context.user_data["admin_state"] = {"action": "upload_qr"}
        await query.edit_message_text("សូមផ្ញើ <b>រូបភាព QR</b> ដើម្បីកំណត់ ឬជំនួស QR ទូទាត់៖", parse_mode="HTML")
        return True

    if data == "adm_pay_inst":
        await query.answer()
        context.user_data["admin_state"] = {"action": "edit_payment_instructions"}
        await query.edit_message_text("ផ្ញើសារណែនាំការទូទាត់ថ្មី៖")
        return True

    if data == "adm_pay_tog":
        cur_val = db.get_setting("payment_enabled", "1")
        db.set_setting("payment_enabled", "0" if cur_val == "1" else "1")
        await query.answer("បានប្ដូរស្ថានភាពការទូទាត់។")
        query.data = "adm_payment"
        return await handle_admin_callback(update, context, db)

    # --- Product Photos ---
    if data == "adm_photos":
        await query.answer()
        prods = db.get_all_products()
        rows = [[InlineKeyboardButton(f"🖼️ {p['name']}", callback_data=f"adm_pphoto_{p['id']}")] for p in prods]
        rows.append([InlineKeyboardButton("🔙 Back", callback_data="adm_menu")])
        await query.edit_message_text("<b>🖼️ Upload Product Photos</b>\nជ្រើសរើសផលិតផលដើម្បីផ្ញើរូបភាព៖", reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return True

    if data.startswith("adm_pphoto_"):
        pid = int(data.split("_")[-1])
        await query.answer()
        context.user_data["admin_state"] = {"action": "upload_product_photo", "product_id": pid}
        await query.edit_message_text("សូមផ្ញើរូបភាពសម្រាប់ផលិតផលនេះ៖")
        return True

    # --- Welcome & Description ---
    if data == "adm_welcome":
        await query.answer()
        context.user_data["admin_state"] = {"action": "edit_welcome"}
        await query.edit_message_text(
            "ផ្ញើសារស្វាគមន៍ និងការពិពណ៌នាហាងថ្មី៖\n<code>សារស្វាគមន៍ | ការពិពណ៌នាហាង</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_menu")]]),
            parse_mode="HTML",
        )
        return True

    # --- Contact Settings ---
    if data == "adm_contact":
        await query.answer()
        cur_c = db.get_setting("contact_admin", "@Beda_modz")
        context.user_data["admin_state"] = {"action": "edit_contact"}
        await query.edit_message_text(
            f"Contact Admin បច្ចុប្បន្ន៖ <b>{cur_c}</b>\nផ្ញើ username ថ្មី (ឧទាហរណ៍៖ <code>@Beda_modz</code>)៖",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_menu")]]),
            parse_mode="HTML",
        )
        return True

    # --- Admin Management ---
    if data == "adm_admins":
        await query.answer()
        admins = db.list_admins()
        context.user_data["admin_state"] = {"action": "add_admin"}
        lines = ["<b>👥 Admin Management</b>", "បញ្ជី Admin IDs៖"] + [f"• <code>{aid}</code>" for aid in admins]
        lines.append("\nផ្ញើ Telegram User ID ថ្មីដើម្បីបន្ថែមជា Admin៖")
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_menu")]]),
            parse_mode="HTML",
        )
        return True

    # --- Statistics ---
    if data == "adm_stats":
        await query.answer()
        st = db.get_statistics()
        text = (
            "<b>📈 ស្ថិតិហាង BEDA STORE (Statistics)</b>\n"
            f"• អ្នកប្រើប្រាស់សរុប (Total Users): <b>{st['total_users']}</b>\n"
            f"• ការបញ្ជាទិញសរុប (Total Orders): <b>{st['total_orders']}</b>\n"
            f"• កំពុងរង់ចាំ (Pending Orders): <b>{st['pending_orders']}</b>\n"
            f"• បានបញ្ចប់ (Completed Orders): <b>{st['completed_orders']}</b>\n"
            f"• បានលុបចោល/ផុតកំណត់ (Cancelled): <b>{st['cancelled_orders']}</b>\n"
            f"• ស្តុកមានស្រាប់ (Available Stock): <b>{st['available_stock']}</b>\n"
            f"• ប្រាក់លក់សរុប (Sales): <b>{format_usd(st['total_sales_usd'])}</b>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_menu")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return True

    return False


async def handle_admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> bool:
    user = update.effective_user
    msg = update.message
    if not user or not msg or not msg.text:
        return False
    if not db.is_admin(user.id):
        return False

    state = context.user_data.get("admin_state")
    if not state:
        return False

    action = state.get("action")
    text = msg.text.strip()
    context.user_data.pop("admin_state", None)

    try:
        if action == "create_category":
            parts = [p.strip() for p in text.split("|", 1)]
            name = parts[0]
            desc = parts[1] if len(parts) > 1 else ""
            cid = db.create_category(name=name, description=desc)
            await msg.reply_text(f"✅ បានបង្កើតប្រភេទ #{cid}: <b>{name}</b>", parse_mode="HTML")
            return True

        if action == "edit_category":
            cid = int(state["category_id"])
            parts = [p.strip() for p in text.split("|", 1)]
            updates = {"name": parts[0]}
            if len(parts) > 1:
                updates["description"] = parts[1]
            db.update_category(cid, **updates)
            await msg.reply_text(f"✅ បានកែសម្រួលប្រភេទ #{cid}។")
            return True

        if action == "create_product":
            cid = int(state["category_id"])
            parts = [p.strip() for p in text.split("|", 2)]
            name = parts[0]
            price = float(parts[1]) if len(parts) > 1 else 0.0
            desc = parts[2] if len(parts) > 2 else ""
            pid = db.create_product(category_id=cid, name=name, description=desc, price_usd=price)
            await msg.reply_text(f"✅ បានបន្ថែមផលិតផល #{pid}: <b>{name}</b> ({format_usd(price)})", parse_mode="HTML")
            return True

        if action == "edit_product":
            pid = int(state["product_id"])
            parts = [p.strip() for p in text.split("|", 2)]
            updates = {"name": parts[0]}
            if len(parts) > 1:
                updates["price_usd"] = float(parts[1])
            if len(parts) > 2:
                updates["description"] = parts[2]
            db.update_product(pid, **updates)
            await msg.reply_text(f"✅ បានកែសម្រួលផលិតផល #{pid}។")
            return True

        if action == "add_package":
            pid = int(state["product_id"])
            parts = [p.strip() for p in text.split("|", 2)]
            pkg_name = parts[0]
            dur = parts[1] if len(parts) > 1 else ""
            price = float(parts[2]) if len(parts) > 2 else 0.0
            kid = db.create_package(product_id=pid, name=pkg_name, duration_label=dur, price_usd=price)
            await msg.reply_text(f"✅ បានបន្ថែមកញ្ចប់ #{kid}: <b>{pkg_name}</b> — {format_usd(price)}", parse_mode="HTML")
            return True

        if action == "set_product_price":
            pid = int(state["product_id"])
            price = float(text)
            db.update_product(pid, price_usd=price)
            await msg.reply_text(f"✅ បានប្ដូរតម្លៃផលិតផល #{pid} ទៅ {format_usd(price)}។")
            return True

        if action == "set_package_price":
            pkg_id = int(state["package_id"])
            price = float(text)
            db.update_package(pkg_id, price_usd=price)
            await msg.reply_text(f"✅ បានប្ដូរតម្លៃកញ្ចប់ #{pkg_id} ទៅ {format_usd(price)}។")
            return True

        if action == "add_stock_text":
            pid = int(state["product_id"])
            entries = [line.strip() for line in text.splitlines() if line.strip()]
            added = db.add_stock_entries(pid, entries)
            await msg.reply_text(f"✅ បានបញ្ចូលស្តុកចំនួន <b>{added}</b> entries។", parse_mode="HTML")
            return True

        if action == "edit_payment_instructions":
            db.set_setting("payment_instructions", text)
            await msg.reply_text("✅ បានកែសម្រួលការណែនាំទូទាត់។")
            return True

        if action == "edit_welcome":
            parts = [p.strip() for p in text.split("|", 1)]
            db.set_setting("welcome_message", parts[0])
            if len(parts) > 1:
                db.set_setting("store_description", parts[1])
            await msg.reply_text("✅ បានកែសម្រួលសារស្វាគមន៍។")
            return True

        if action == "edit_contact":
            handle = sanitize_contact_username(text)
            db.set_setting("contact_admin", handle)
            await msg.reply_text(f"✅ បានប្ដូរ Contact Admin ទៅ <b>{handle}</b>។", parse_mode="HTML")
            return True

        if action == "add_admin":
            if not text.isdigit():
                await msg.reply_text("❌ សូមផ្ញើ User ID ជាលេខ។")
                return True
            db.add_admin(int(text), user.id)
            await msg.reply_text(f"✅ បានបន្ថែម Admin ID <code>{text}</code>។", parse_mode="HTML")
            return True

    except Exception as exc:
        logger.warning("Admin input error (%s): %s", action, exc)
        await msg.reply_text("❌ ទម្រង់ទិន្នន័យមិនត្រឹមត្រូវ។ សូមព្យាយាមម្ដងទៀត។")
        return True

    return False


async def handle_admin_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database) -> bool:
    user = update.effective_user
    msg = update.message
    if not user or not msg or not db.is_admin(user.id):
        return False

    state = context.user_data.get("admin_state")
    if not state:
        return False

    action = state.get("action")

    if action == "upload_stock_file" and msg.document:
        pid = int(state["product_id"])
        os.makedirs(STOCK_UPLOADS_DIR, exist_ok=True)
        local_path = os.path.join(STOCK_UPLOADS_DIR, f"stock_{pid}_{msg.document.file_unique_id}.txt")
        tg_file = await msg.document.get_file()
        await tg_file.download_to_drive(custom_path=local_path)
        with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        added = db.add_stock_entries(pid, lines)
        context.user_data.pop("admin_state", None)
        await msg.reply_text(f"✅ បាននាំចូលស្តុកពីឯកសារចំនួន <b>{added}</b> entries។", parse_mode="HTML")
        return True

    if action in ("upload_qr", "upload_product_photo", "edit_category") and msg.photo:
        photo_obj = msg.photo[-1]
        tg_file = await photo_obj.get_file()

        if action == "upload_qr":
            os.makedirs(QR_DIR, exist_ok=True)
            dest = os.path.join(QR_DIR, f"payment_qr_{photo_obj.file_unique_id}.jpg")
            await tg_file.download_to_drive(custom_path=dest)
            db.set_setting("default_qr_path", dest)
            context.user_data.pop("admin_state", None)
            await msg.reply_text("✅ បានរក្សារូបភាព QR ទូទាត់រួចរាល់។")
            return True

        if action == "upload_product_photo":
            pid = int(state["product_id"])
            os.makedirs(PHOTOS_DIR, exist_ok=True)
            dest = os.path.join(PHOTOS_DIR, f"prod_{pid}_{photo_obj.file_unique_id}.jpg")
            await tg_file.download_to_drive(custom_path=dest)
            db.update_product(pid, photo_path=dest)
            context.user_data.pop("admin_state", None)
            await msg.reply_text(f"✅ បានកំណត់រូបភាពសម្រាប់ផលិតផល #{pid}។")
            return True

        if action == "edit_category":
            cid = int(state["category_id"])
            os.makedirs(PHOTOS_DIR, exist_ok=True)
            dest = os.path.join(PHOTOS_DIR, f"cat_{cid}_{photo_obj.file_unique_id}.jpg")
            await tg_file.download_to_drive(custom_path=dest)
            db.update_category(cid, photo_path=dest)
            context.user_data.pop("admin_state", None)
            await msg.reply_text(f"✅ បានកំណត់រូបភាពសម្រាប់ប្រភេទ #{cid}។")
            return True

    return False
