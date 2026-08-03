"""handlers/support.py — Support ticket system."""

import asyncio

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from states.states import SupportStates, AdminStates
from utils.db_helpers import (
    create_ticket, get_ticket, get_user_tickets,
    get_all_open_tickets, close_ticket,
    add_ticket_reply, get_ticket_replies,
)
from utils.messages import (
    ticket_user_msg, ticket_admin_notify, DIVIDER, CATEGORY_NAMES,
)
from keyboards.inline import (
    support_menu_keyboard, ticket_action_keyboard,
    my_tickets_keyboard, ticket_admin_keyboard,
)
from keyboards.reply import admin_menu, main_menu, cancel_keyboard

router = Router()

FAQ = {
    "payment": (
        "💸 <b>Payment Issues — FAQ</b>\n\n"
        "• UPI payment failed? Try again after 2 mins.\n"
        "• Wrong amount paid? Contact support with your Order ID.\n"
        "• Payment deducted but not verified? Submit your 12-digit UTR number.\n"
    ),
    "code": (
        "🎫 <b>Code Not Working — FAQ</b>\n\n"
        "• Make sure you're entering the code exactly as shown.\n"
        "• Check if the code has already been used.\n"
        "• Ensure you're applying it on the correct platform.\n"
    ),
    "order": (
        "📦 <b>Order Problem — FAQ</b>\n\n"
        "• Order ID can be found in My Orders section.\n"
        "• Pending orders expire after 10 minutes if unpaid.\n"
        "• Delivered codes are visible in My Orders history.\n"
    ),
    "other": (
        "❓ <b>Other Queries — FAQ</b>\n\n"
        "• For general questions, use the ticket system below.\n"
        "• Response time: within 1 hour.\n"
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# USER — SUPPORT MENU
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "🆘 Support")
async def support_main(message: Message):
    await message.answer(
        f"┌────────────────────┐\n"
        f"│    🆘  SUPPORT     │\n"
        f"└────────────────────┘\n\n"
        f"Select your issue category 👇",
        reply_markup=support_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("sup_cat:"))
async def support_category(callback: CallbackQuery):
    category = callback.data.split(":")[1]
    faq_text = FAQ.get(category, "")
    await callback.message.edit_text(
        f"{faq_text}\n{DIVIDER}\n"
        f"Still need help? Open a ticket below 👇",
        reply_markup=ticket_action_keyboard(callback.message.message_id, category),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("open_tkt:"))
async def open_ticket(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    await state.update_data(ticket_category=category)
    await state.set_state(SupportStates.write_message)
    await callback.message.edit_text(
        f"📝 <b>Open a Ticket</b>\n{DIVIDER}\n\n"
        f"Describe your issue in detail.\n"
        f"Include your Order ID if relevant:\n\n"
        f"<i>Type your message below 👇</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(SupportStates.write_message, F.text)
async def submit_ticket(message: Message, state: FSMContext, bot: Bot):
    data     = await state.get_data()
    category = data.get("ticket_category", "other")
    user     = message.from_user

    ticket_id = create_ticket(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name or "User",
        category=category,
        message=message.text,
    )

    await message.answer(
        ticket_user_msg(ticket_id, category),
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await state.clear()

    admin_text = ticket_admin_notify(
        ticket_id=ticket_id,
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name or "User",
        category=category,
        message=message.text,
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, admin_text,
                reply_markup=ticket_admin_keyboard(ticket_id),
                parse_mode="HTML"
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# USER — MY TICKETS
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "my_tickets")
async def my_tickets(callback: CallbackQuery):
    tickets = get_user_tickets(callback.from_user.id)
    if not tickets:
        await callback.message.edit_text(
            f"📋 <b>My Tickets</b>\n{DIVIDER}\n\nYou have no tickets yet.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        f"📋 <b>My Tickets</b>\n{DIVIDER}\n\nTap a ticket to view conversation 👇",
        reply_markup=my_tickets_keyboard(tickets),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vtkt:"))
async def view_ticket(callback: CallbackQuery):
    ticket_id = callback.data.split(":")[1]
    ticket    = get_ticket(ticket_id)
    if not ticket or int(ticket["user_id"]) != int(callback.from_user.id):
        await callback.answer("Ticket not found!", show_alert=True)
        return

    replies     = get_ticket_replies(ticket_id)
    cat_name    = CATEGORY_NAMES.get(ticket["category"], ticket["category"])
    status_icon = "🟢 Open" if ticket["status"] == "open" else "🔴 Closed"

    text = (
        f"🎫 <b>Ticket {ticket['id']}</b>\n{DIVIDER}\n\n"
        f"📂 Category: {cat_name}\n"
        f"📌 Status: {status_icon}\n"
        f"📅 {str(ticket['created_at'])[:16]}\n\n"
        f"{DIVIDER}\n"
        f"<b>Your Message:</b>\n{ticket['message']}\n"
    )
    if replies:
        text += f"\n{DIVIDER}\n<b>Conversation:</b>\n"
        for r in replies:
            sender = "🔧 <b>Support</b>" if r["from_admin"] else "👤 <b>You</b>"
            text  += f"\n{sender} — {str(r['created_at'])[:16]}\n{r['message']}\n"

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "sup_back")
async def sup_back(callback: CallbackQuery):
    await callback.message.edit_text(
        f"🆘 <b>Support</b>\n{DIVIDER}\n\nSelect your issue category 👇",
        reply_markup=support_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — TICKETS  (🎫 Tickets button)
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "🎫 Tickets")
async def admin_tickets(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    tickets = get_all_open_tickets()
    if not tickets:
        await message.answer(
            f"🎫 <b>Support Tickets</b>\n{DIVIDER}\n\n"
            f"✅ No open tickets right now.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"🎫 <b>Open Tickets</b> ({len(tickets)})\n{DIVIDER}",
        parse_mode="HTML"
    )
    for t in tickets:
        cat = CATEGORY_NAMES.get(t["category"], t["category"])
        await message.answer(
            f"🎫 <code>{t['id']}</code>\n"
            f"📂 {cat}\n"
            f"👤 User ID: <code>{t['user_id']}</code>\n"
            f"📅 {str(t['created_at'])[:16]}\n\n"
            f"<b>Message:</b>\n{t['message']}",
            reply_markup=ticket_admin_keyboard(t["id"]),
            parse_mode="HTML"
        )
        await asyncio.sleep(0.05)


@router.callback_query(F.data.startswith("rtkt:"))
async def admin_reply_ticket_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied!", show_alert=True)
        return
    ticket_id = callback.data.split(":")[1]
    await state.update_data(reply_ticket_id=ticket_id)
    await state.set_state(AdminStates.reply_ticket)
    await callback.message.answer(
        f"✏️ <b>Replying to Ticket {ticket_id}</b>\n\nType your reply:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.reply_ticket, F.text)
async def admin_send_reply(message: Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return

    data      = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    ticket    = get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Ticket not found.", reply_markup=admin_menu())
        await state.clear()
        return

    add_ticket_reply(ticket_id, message.text, from_admin=True)

    try:
        await bot.send_message(
            ticket["user_id"],
            f"📩 <b>Support Reply</b>\n{DIVIDER}\n\n"
            f"🎫 Ticket: <code>{ticket_id}</code>\n\n"
            f"<b>Admin:</b>\n{message.text}",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Reply sent for ticket <code>{ticket_id}</code>",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("ctkt:"))
async def close_ticket_cb(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied!", show_alert=True)
        return
    ticket_id = callback.data.split(":")[1]
    ticket    = get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Ticket not found!", show_alert=True)
        return

    close_ticket(ticket_id)

    try:
        await bot.send_message(
            ticket["user_id"],
            f"✅ <b>Ticket Resolved</b>\n{DIVIDER}\n\n"
            f"🎫 <code>{ticket_id}</code> has been closed by support.\n"
            f"If your issue persists, open a new ticket via 🆘 Support.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            (callback.message.text or "") + f"\n\n✅ <b>TICKET CLOSED</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.answer("✅ Closed & user notified!", show_alert=True)
