"""keyboards/inline.py — Inline keyboard builders."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def vouchers_keyboard(vouchers: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for v in vouchers:
        stock = v["stock"]
        if stock > 0:
            label = f"🔥 {v['name']}  —  ₹{v['price']:.0f}  |  {stock} pcs"
        else:
            label = f"😴 {v['name']}  —  Out of Stock"
        builder.button(text=label, callback_data=f"buy_v:{v['id']}")
    builder.button(text="🔙 Back", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def quantity_keyboard(voucher_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1",          callback_data=f"qty:{voucher_id}:1")
    builder.button(text="5",          callback_data=f"qty:{voucher_id}:5")
    builder.button(text="10",         callback_data=f"qty:{voucher_id}:10")
    builder.button(text="20",         callback_data=f"qty:{voucher_id}:20")
    builder.button(text="✏️ Custom",  callback_data=f"qty:{voucher_id}:custom")
    builder.button(text="🔙 Back",    callback_data="back_vouchers")
    builder.adjust(4, 1, 1)
    return builder.as_markup()


def disclaimer_keyboard(voucher_id: int, qty: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Accept & Continue",
                   callback_data=f"disc_ok:{voucher_id}:{qty}")
    builder.button(text="❌ Cancel",
                   callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def payment_keyboard(order_id: str, upi_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📲 Open UPI App to Pay", url=upi_link)
    builder.button(text="✅ I Have Paid",          callback_data=f"ipaid:{order_id}")
    builder.button(text="❌ Cancel Order",         callback_data=f"cancel_o:{order_id}")
    builder.adjust(1)
    return builder.as_markup()


def admin_approve_keyboard(order_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve & Deliver", callback_data=f"approve:{order_id}")
    builder.button(text="❌ Reject",            callback_data=f"reject:{order_id}")
    builder.adjust(2)
    return builder.as_markup()


def orders_keyboard(orders: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status_emoji = {
        "pending":   "⏳",
        "approved":  "✅",
        "rejected":  "❌",
        "cancelled": "🚫",
        "expired":   "⌛",
    }
    for o in orders:
        emoji = status_emoji.get(o["status"], "❓")
        builder.button(
            text=f"{emoji} {o['voucher_name']}  •  #{o['id'][:8]}",
            callback_data=f"view_o:{o['id']}"
        )
    builder.button(text="🔙 Back", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def order_detail_keyboard(order_id: str, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "pending":
        builder.button(text="✅ I Have Paid",  callback_data=f"ipaid:{order_id}")
        builder.button(text="❌ Cancel Order", callback_data=f"cancel_o:{order_id}")
    builder.button(text="🔙 My Orders", callback_data="back_orders")
    builder.adjust(1)
    return builder.as_markup()


def voucher_manage_keyboard(vouchers: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for v in vouchers:
        stock = v["stock"]
        builder.button(
            text=f"{'🟢' if stock > 0 else '🔴'} {v['name']} ({stock})",
            callback_data=f"vstk:{v['id']}"
        )
    builder.button(text="🔙 Back", callback_data="admin_back")
    builder.adjust(1)
    return builder.as_markup()


def voucher_action_keyboard(voucher_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Delete Voucher", callback_data=f"vdel:{voucher_id}")
    builder.button(text="📝 Set Disclaimer", callback_data=f"vdisc:{voucher_id}")
    builder.button(text="🔙 Back",           callback_data="vstk_back")
    builder.adjust(2, 1)
    return builder.as_markup()


def voucher_select_keyboard(vouchers: list, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for v in vouchers:
        builder.button(
            text=f"{v['name']} (₹{v['price']:.0f})",
            callback_data=f"{prefix}:{v['id']}"
        )
    builder.button(text="❌ Cancel", callback_data="admin_back")
    builder.adjust(1)
    return builder.as_markup()


def channel_manage_keyboard(channels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.button(
            text=f"🗑 Remove: {ch['name']}",
            callback_data=f"rmch:{ch['id']}"
        )
    builder.button(text="➕ Add Channel", callback_data="addch")
    builder.button(text="🔙 Back",        callback_data="admin_back")
    builder.adjust(1)
    return builder.as_markup()


def support_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Payment Issue",    callback_data="sup_cat:payment")
    builder.button(text="🎫 Code Not Working", callback_data="sup_cat:code")
    builder.button(text="📦 Order Problem",    callback_data="sup_cat:order")
    builder.button(text="❓ Other Query",       callback_data="sup_cat:other")
    builder.button(text="📋 My Tickets",       callback_data="my_tickets")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def ticket_action_keyboard(msg_id: int, category: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Open a Ticket", callback_data=f"open_tkt:{category}")
    builder.button(text="🔙 Back",          callback_data="sup_back")
    builder.adjust(1)
    return builder.as_markup()


def my_tickets_keyboard(tickets: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in tickets:
        icon = "🟢" if t["status"] == "open" else "🔴"
        builder.button(
            text=f"{icon} {t['id']}",
            callback_data=f"vtkt:{t['id']}"
        )
    builder.button(text="🔙 Back", callback_data="sup_back")
    builder.adjust(1)
    return builder.as_markup()


def ticket_admin_keyboard(ticket_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Reply",        callback_data=f"rtkt:{ticket_id}")
    builder.button(text="✅ Close Ticket", callback_data=f"ctkt:{ticket_id}")
    builder.adjust(2)
    return builder.as_markup()
