"""handlers/buy.py — Full purchase flow: browse → QR → UTR → admin verify."""

import asyncio
from urllib.parse import quote

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from config import UPI_ID, SHOP_NAME, ADMIN_IDS, ORDER_EXPIRY_MINUTES
from states.states import BuyStates
from utils.db_helpers import (
    get_all_vouchers_with_stock, get_voucher, get_voucher_stock,
    get_user_active_order, get_order, cancel_order,
    is_utr_used, save_utr, get_user, get_setting,
)
from utils.messages import payment_waiting_msg, admin_pending_msg, DIVIDER
from order_manager import create_order
from qr_generator import generate_qr_with_label
from keyboards.inline import (
    vouchers_keyboard, quantity_keyboard, disclaimer_keyboard,
    payment_keyboard, admin_approve_keyboard,
)
from keyboards.reply import main_menu, cancel_keyboard

router = Router()


# ── BROWSE VOUCHERS ───────────────────────────────────────────────────────────

@router.message(F.text == "🛍 Buy Vouchers")
async def buy_vouchers(message: Message, state: FSMContext):
    await state.clear()

    active = get_user_active_order(message.from_user.id)
    if active:
        await message.answer(
            f"┌────────────────────┐\n"
            f"│  ⚠️  ACTIVE ORDER  │\n"
            f"└────────────────────┘\n\n"
            f"You already have a pending order!\n\n"
            f"🛍  <b>{active['voucher_name']}</b> × {active['quantity']}\n"
            f"💰  Pay: <b>₹{active['total_price']:.0f}</b>\n\n"
            f"Complete or cancel it first.\n"
            f"Go to <b>📦 My Orders</b> to view it.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
        return

    vouchers = get_all_vouchers_with_stock()
    if not vouchers:
        await message.answer(
            f"┌────────────────────┐\n"
            f"│   😴  SHOP CLOSED  │\n"
            f"└────────────────────┘\n\n"
            f"No products available right now.\n"
            f"We're restocking soon — check back later!",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"⚡ <b>LIVE STORE</b>\n{DIVIDER}\n\n"
        f"🔥 Fresh stock available!\n"
        f"Select a voucher below 👇",
        reply_markup=vouchers_keyboard(vouchers),
        parse_mode="HTML"
    )
    await state.set_state(BuyStates.select_voucher)


# ── SELECT VOUCHER ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("buy_v:"))
async def select_voucher(callback: CallbackQuery, state: FSMContext):
    voucher_id = int(callback.data.split(":")[1])
    voucher    = get_voucher(voucher_id)

    if not voucher:
        await callback.answer("❌ Product not found!", show_alert=True)
        return
    if voucher["stock"] == 0:
        await callback.answer("😴 Out of Stock! Check other options.", show_alert=True)
        return

    await state.update_data(
        voucher_id=voucher_id,
        voucher_name=voucher["name"],
        price=voucher["price"],
    )

    await callback.message.edit_text(
        f"🔥 <b>{voucher['name']}</b>\n{DIVIDER}\n\n"
        f"💰  ₹{voucher['price']:.0f} per code\n"
        f"📦  {voucher['stock']} codes available\n"
        f"⚡  Instant delivery after approval\n\n"
        f"{DIVIDER}\n"
        f"Select quantity 👇",
        reply_markup=quantity_keyboard(voucher_id),
        parse_mode="HTML"
    )
    await state.set_state(BuyStates.select_quantity)
    await callback.answer()


# ── SELECT QUANTITY ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("qty:"))
async def select_quantity(callback: CallbackQuery, state: FSMContext):
    parts      = callback.data.split(":")
    voucher_id = int(parts[1])
    qty_str    = parts[2]

    if qty_str == "custom":
        await state.update_data(voucher_id=voucher_id)
        await callback.message.edit_text(
            f"✏️ <b>Custom Quantity</b>\n{DIVIDER}\n\n"
            f"Enter the number of codes you want to buy:",
            parse_mode="HTML"
        )
        await state.set_state(BuyStates.custom_quantity)
        await callback.answer()
        return

    qty = int(qty_str)
    await _show_disclaimer(callback.message, state, voucher_id, qty, edit=True)
    await callback.answer()


@router.message(BuyStates.custom_quantity)
async def process_custom_qty(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Please enter a valid number (e.g. 3):")
        return

    qty = int(message.text.strip())
    if qty < 1:
        await message.answer("❌ Quantity must be at least 1:")
        return
    if qty > 50:
        await message.answer("❌ Maximum 50 codes per order:")
        return

    data       = await state.get_data()
    voucher_id = data.get("voucher_id")
    voucher    = get_voucher(voucher_id)

    if not voucher or voucher["stock"] < qty:
        await message.answer(
            f"❌ Not enough stock! Only {voucher['stock'] if voucher else 0} available.",
            reply_markup=main_menu()
        )
        await state.clear()
        return

    await _show_disclaimer(message, state, voucher_id, qty, edit=False)


async def _show_disclaimer(target, state: FSMContext, voucher_id: int,
                           qty: int, edit: bool):
    voucher = get_voucher(voucher_id)
    if not voucher or voucher["stock"] < qty:
        stock = voucher["stock"] if voucher else 0
        txt   = f"❌ Not enough stock! Only {stock} codes available."
        if edit:
            await target.edit_text(txt)
        else:
            await target.answer(txt, reply_markup=main_menu())
        await state.clear()
        return

    disclaimer_text = voucher.get("disclaimer") or (
        "✔ Valid for 1 account only.\n"
        "✔ One-time use only.\n"
        "✔ Must be used before expiry.\n"
        "❌ No refund / replacement after delivery."
    )

    total = voucher["price"] * qty
    text  = (
        f"📋 <b>Terms &amp; Conditions</b>\n{DIVIDER}\n\n"
        f"<b>{voucher['name']}</b>\n\n"
        f"{disclaimer_text}\n\n"
        f"{DIVIDER}\n"
        f"🛍  {qty} code(s)  ×  ₹{voucher['price']:.0f} = <b>₹{total:.0f}</b>\n\n"
        f"Tap <b>Accept &amp; Continue</b> to proceed 👇"
    )
    markup = disclaimer_keyboard(voucher_id, qty)

    if edit:
        await target.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML")

    await state.set_state(BuyStates.disclaimer_confirm)


# ── DISCLAIMER ACCEPT ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("disc_ok:"))
async def disclaimer_accept(callback: CallbackQuery, state: FSMContext):
    _, voucher_id_str, qty_str = callback.data.split(":")
    voucher_id = int(voucher_id_str)
    qty        = int(qty_str)

    voucher = get_voucher(voucher_id)
    if not voucher or voucher["stock"] < qty:
        await callback.answer("❌ Out of stock now!", show_alert=True)
        await state.clear()
        return

    total    = voucher["price"] * qty
    order_id = create_order(
        user_id=callback.from_user.id,
        voucher_id=voucher_id,
        voucher_name=voucher["name"],
        quantity=qty,
        total_price=total,
        expiry_minutes=ORDER_EXPIRY_MINUTES,
    )

    upi_link = (
        f"upi://pay?pa={quote(UPI_ID)}&pn={quote(SHOP_NAME)}"
        f"&am={total:.0f}&cu=INR"
    )
    qr_buf = generate_qr_with_label(upi_link, float(total), SHOP_NAME)
    photo  = BufferedInputFile(qr_buf.read(), filename="payment_qr.png")

    caption = payment_waiting_msg(voucher["name"], qty, total, order_id)
    markup  = payment_keyboard(order_id, upi_link)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=markup,
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


# ── I HAVE PAID ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ipaid:"))
async def i_paid(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.split(":")[1]
    order    = get_order(order_id)

    if not order:
        await callback.answer("❌ Order not found!", show_alert=True)
        return
    if order["status"] != "pending":
        await callback.answer(f"This order is already {order['status']}.", show_alert=True)
        return

    await state.update_data(order_id=order_id)
    await state.set_state(BuyStates.waiting_utr)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        f"📝 <b>Enter UTR Number</b>\n{DIVIDER}\n\n"
        f"🆔 Order: <code>#{order_id}</code>\n\n"
        f"Please enter your <b>12-digit UTR / Reference Number</b>\n"
        f"(Found in your UPI app payment confirmation)\n\n"
        f"Example: <code>123456789012</code>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


# ── PROCESS UTR ───────────────────────────────────────────────────────────────

@router.message(BuyStates.waiting_utr, F.text)
async def process_utr(message: Message, state: FSMContext, bot: Bot):
    text = message.text.strip()

    if text == "❌ Cancel":
        await state.clear()
        await message.answer("❌ Payment cancelled.", reply_markup=main_menu())
        return

    if not text.isdigit() or len(text) != 12:
        await message.answer(
            "❌ <b>Invalid UTR!</b>\n\n"
            "Enter exactly <b>12 numeric digits</b>.\n"
            "Example: <code>123456789012</code>",
            parse_mode="HTML"
        )
        return  # Stay in state

    utr      = text
    data     = await state.get_data()
    order_id = data.get("order_id")

    if not order_id:
        await message.answer("❌ Session expired. Please start over.", reply_markup=main_menu())
        await state.clear()
        return

    order = get_order(order_id)
    if not order or order["status"] != "pending":
        await message.answer("❌ Order no longer active.", reply_markup=main_menu())
        await state.clear()
        return

    # ── DUPLICATE UTR CHECK ───────────────────────────────────────────────────
    if is_utr_used(utr):
        await message.answer(
            f"⚠️ <b>Payment Verification with Another Order</b>\n{DIVIDER}\n\n"
            f"UTR <code>{utr}</code> has already been verified for a previous order.\n\n"
            f"If you think this is an error, please contact support.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
        await state.clear()
        return

    save_utr(order_id, utr)

    await message.answer(
        f"✅ <b>UTR Submitted!</b>\n{DIVIDER}\n\n"
        f"🆔 Order: <code>#{order_id}</code>\n"
        f"🧾 UTR: <code>{utr}</code>\n\n"
        f"⏳ Payment sent for verification.\n"
        f"Please wait up to <b>5 minutes</b>.\n"
        f"You'll receive your codes here once approved.",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

    # Notify all admins
    full_name     = message.from_user.full_name or "User"
    username      = message.from_user.username  or ""
    updated_order = get_order(order_id)

    if updated_order:
        admin_text = admin_pending_msg(updated_order, full_name, username)
        markup     = admin_approve_keyboard(order_id)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, reply_markup=markup, parse_mode="HTML")
            except Exception:
                pass

    await state.clear()


# ── CANCEL ORDER ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cancel_o:"))
async def cancel_order_cb(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.split(":")[1]
    cancel_order(order_id)
    await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        f"┌────────────────────┐\n"
        f"│ ❌  ORDER CANCELLED │\n"
        f"└────────────────────┘\n\n"
        f"🆔  #{order_id}\n\n"
        f"No charge was made. Place a new order anytime 👇",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await callback.answer("Order cancelled.")


# ── NAVIGATION ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_vouchers")
async def back_to_vouchers(callback: CallbackQuery, state: FSMContext):
    vouchers = get_all_vouchers_with_stock()
    await callback.message.edit_text(
        f"⚡ <b>LIVE STORE</b>\n{DIVIDER}\n\n"
        f"🔥 Fresh stock available!\n"
        f"Select a voucher below 👇",
        reply_markup=vouchers_keyboard(vouchers),
        parse_mode="HTML"
    )
    await state.set_state(BuyStates.select_voucher)
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("🏠 Main Menu", reply_markup=main_menu())
    await callback.answer()
