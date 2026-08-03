"""utils/messages.py — All message text templates."""

DIVIDER = "━━━━━━━━━━━━━━━━━━━━"

CATEGORY_NAMES = {
    "payment": "💸 Payment Issue",
    "code":    "🎫 Code Not Working",
    "order":   "📦 Order Problem",
    "other":   "❓ Other Query",
}


def welcome_msg(first_name: str, bot_name: str, support: str) -> str:
    return (
        f"👋 Hey <b>{first_name}</b>!\n\n"
        f"Welcome to <b>{bot_name}</b> — your one-stop shop for "
        f"digital vouchers &amp; coupons.\n\n"
        f"{DIVIDER}\n"
        f"Choose an option below 👇"
    )


def new_user_alert(username: str, user_id: int, full_name: str) -> str:
    uname = f"@{username}" if username else "N/A"
    return (
        f"🆕 <b>NEW USER JOINED</b>\n{DIVIDER}\n\n"
        f"📛 Name: {full_name}\n"
        f"🔖 Username: {uname}\n"
        f"🆔 User ID: <code>{user_id}</code>\n"
    )


def payment_waiting_msg(voucher_name: str, qty: int, total: float, order_id: str) -> str:
    return (
        f"┌──────────────────────┐\n"
        f"│   💳  PAYMENT DETAILS │\n"
        f"└──────────────────────┘\n\n"
        f"🛍  <b>{voucher_name}</b> × {qty}\n"
        f"💰  Total: <b>₹{total:.0f}</b>\n"
        f"🆔  Order: <code>#{order_id}</code>\n\n"
        f"{DIVIDER}\n"
        f"⏳ Pay within <b>10 minutes</b>\n"
        f"Scan the QR with any UPI app 👆"
    )


def success_delivery_msg(voucher_name: str, codes: list, amount: float,
                         order_id: str, support: str) -> str:
    codes_text = "\n".join([f"🔑 <code>{c}</code>" for c in codes])
    return (
        f"🎉 <b>Payment Approved!</b>\n{DIVIDER}\n\n"
        f"🛍  {voucher_name} × {len(codes)}\n"
        f"💰  Amount: ₹{amount:.0f}\n"
        f"🆔  Order: <code>#{order_id}</code>\n\n"
        f"<b>Your Codes:</b>\n{codes_text}\n\n"
        f"{DIVIDER}\n"
        f"Thank you for shopping! 🙏\n"
        f"Need help? {support}"
    )


def rejection_msg(order_id: str, support: str) -> str:
    return (
        f"❌ <b>Payment Rejected</b>\n{DIVIDER}\n\n"
        f"🆔 Order: <code>#{order_id}</code>\n\n"
        f"Your UTR could not be verified.\n"
        f"Please contact support: {support}"
    )


def order_detail_msg(order: dict, codes: list) -> str:
    status_map = {
        "pending":   "⏳ Pending",
        "approved":  "✅ Delivered",
        "rejected":  "❌ Rejected",
        "cancelled": "🚫 Cancelled",
        "expired":   "⌛ Expired",
    }
    text = (
        f"📦 <b>ORDER DETAIL</b>\n{DIVIDER}\n\n"
        f"🆔 Order: <code>#{order['id']}</code>\n"
        f"🛍  {order['voucher_name']} × {order['quantity']}\n"
        f"💰 Amount: ₹{order['total_price']:.0f}\n"
        f"📊 Status: {status_map.get(order['status'], order['status'])}\n"
        f"📅 Date: {str(order['created_at'])[:16]}\n"
    )
    if order.get("utr"):
        text += f"🧾 UTR: <code>{order['utr']}</code>\n"
    if codes:
        codes_block = "\n".join([f"🔑 <code>{c}</code>" for c in codes])
        text += f"\n<b>Codes:</b>\n{codes_block}\n"
    text += f"\n{DIVIDER}"
    return text


def admin_pending_msg(order: dict, full_name: str, username: str) -> str:
    uname = f"@{username}" if username else "N/A"
    return (
        f"🔔 <b>PAYMENT REQUEST</b>\n{DIVIDER}\n\n"
        f"👤 {full_name} ({uname})\n"
        f"🆔 User ID: <code>{order['user_id']}</code>\n"
        f"🛍  {order['voucher_name']} × {order['quantity']}\n"
        f"💰 Amount: ₹{order['total_price']:.0f}\n"
        f"🆔 Order: <code>#{order['id']}</code>\n"
        f"🧾 UTR: <code>{order['utr']}</code>\n"
        f"⏰ {str(order['created_at'])[:16]}\n"
        f"{DIVIDER}"
    )


def admin_order_detail_msg(order: dict, buyer_name: str, buyer_uname: str,
                           codes: list) -> str:
    status_map = {
        "pending":   "⏳ Pending",
        "approved":  "✅ Delivered",
        "rejected":  "❌ Rejected",
        "cancelled": "🚫 Cancelled",
        "expired":   "⌛ Expired",
    }
    uname = f"@{buyer_uname}" if buyer_uname else "N/A"
    text = (
        f"🔍 <b>ORDER LOOKUP</b>\n{DIVIDER}\n\n"
        f"🆔 Order: <code>#{order['id']}</code>\n"
        f"👤 Buyer: {buyer_name} ({uname})\n"
        f"🆔 User ID: <code>{order['user_id']}</code>\n"
        f"🛍  {order['voucher_name']} × {order['quantity']}\n"
        f"💰 Amount: ₹{order['total_price']:.0f}\n"
        f"📊 Status: {status_map.get(order['status'], order['status'])}\n"
        f"📅 Created: {str(order['created_at'])[:16]}\n"
    )
    if order.get("utr"):
        text += f"🧾 UTR: <code>{order['utr']}</code>\n"
    if order.get("approved_at"):
        text += f"✅ Approved: {str(order['approved_at'])[:16]}\n"
    if codes:
        codes_block = "\n".join([f"🔑 <code>{c}</code>" for c in codes])
        text += f"\n<b>Delivered Codes:</b>\n{codes_block}\n"
    text += f"\n{DIVIDER}"
    return text


def admin_user_info_msg(user: dict, orders: list, total_spent: float) -> str:
    uname = f"@{user.get('username')}" if user.get("username") else "N/A"
    approved = sum(1 for o in orders if o["status"] == "approved")
    pending  = sum(1 for o in orders if o["status"] == "pending")
    rejected = sum(1 for o in orders if o["status"] == "rejected")

    text = (
        f"👤 <b>USER INFO</b>\n{DIVIDER}\n\n"
        f"📛 Name: {user.get('full_name', 'N/A')}\n"
        f"🔖 Username: {uname}\n"
        f"🆔 Telegram ID: <code>{user['telegram_id']}</code>\n"
        f"📅 Joined: {str(user.get('joined_at', ''))[:16]}\n\n"
        f"📊 <b>Order Stats</b>\n"
        f"✅ Completed : {approved}\n"
        f"⏳ Pending   : {pending}\n"
        f"❌ Rejected  : {rejected}\n"
        f"💰 Total Spent: ₹{total_spent:.0f}\n\n"
    )
    if orders:
        text += "<b>Order History (last 10):</b>\n"
        for o in orders[-10:]:
            status_e = {"approved": "✅", "pending": "⏳",
                        "rejected": "❌", "expired": "⌛", "cancelled": "🚫"}.get(o["status"], "❓")
            text += (f"{status_e} <code>#{o['id']}</code> — "
                     f"{o['voucher_name']} × {o['quantity']} — ₹{o['total_price']:.0f}\n")
    text += f"\n{DIVIDER}"
    return text


def more_commands_msg() -> str:
    return (
        f"📖 <b>ALL ADMIN COMMANDS</b>\n{DIVIDER}\n\n"
        f"🔍 <b>Lookup</b>\n"
        f"<code>/order ORDER_ID</code>\n"
        f"  └ Who bought, what, when, UTR, codes, status\n\n"
        f"<code>/info USER_ID</code>\n"
        f"  └ User profile, order history, total spent\n\n"
        f"📦 <b>Stock</b>\n"
        f"<code>/add</code> — Add new voucher (guided)\n"
        f"<code>/addcode VOUCHER_ID</code> — Add codes (guided)\n"
        f"<code>/del VOUCHER_ID</code> — Delete voucher\n"
        f"<code>/setprice VOUCHER_ID PRICE</code> — Update price\n"
        f"<code>/setdisclaimer VOUCHER_ID TEXT</code> — Set T&amp;C\n\n"
        f"📢 <b>Other</b>\n"
        f"<code>/broadcast</code> — Message all users\n"
        f"<code>/pending</code> — View pending payment requests\n"
        f"<code>/stats</code> — Quick stats\n"
        f"<code>/admin</code> — Open admin panel\n\n"
        f"{DIVIDER}"
    )


def ticket_user_msg(ticket_id: str, category: str) -> str:
    cat = CATEGORY_NAMES.get(category, category)
    return (
        f"🎫 <b>Ticket Created!</b>\n{DIVIDER}\n\n"
        f"🆔 Ticket: <code>{ticket_id}</code>\n"
        f"📂 Category: {cat}\n\n"
        f"Our team will respond shortly.\n"
        f"You'll receive a reply here in this chat."
    )


def ticket_admin_notify(ticket_id: str, user_id: int, username: str,
                        full_name: str, category: str, message: str) -> str:
    uname = f"@{username}" if username else "N/A"
    cat = CATEGORY_NAMES.get(category, category)
    return (
        f"📩 <b>NEW SUPPORT TICKET</b>\n{DIVIDER}\n\n"
        f"🎫 Ticket: <code>{ticket_id}</code>\n"
        f"📂 Category: {cat}\n"
        f"👤 {full_name} ({uname})\n"
        f"🆔 User ID: <code>{user_id}</code>\n\n"
        f"{DIVIDER}\n"
        f"<b>Message:</b>\n{message}\n{DIVIDER}"
    )
