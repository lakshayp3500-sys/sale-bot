"""handlers/orders.py — My Orders section."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from utils.db_helpers import get_user_orders, get_order, get_order_codes
from utils.messages import order_detail_msg, DIVIDER
from keyboards.reply import main_menu
from keyboards.inline import orders_keyboard, order_detail_keyboard

router = Router()


@router.message(F.text == "📦 My Orders")
async def my_orders(message: Message):
    orders = get_user_orders(message.from_user.id)
    if not orders:
        await message.answer(
            f"┌────────────────────┐\n"
            f"│   📦  MY ORDERS    │\n"
            f"└────────────────────┘\n\n"
            f"No orders yet 😊\n\n"
            f"Tap <b>🛍 Buy Vouchers</b> to place your first order!",
            parse_mode="HTML"
        )
        return

    approved = sum(1 for o in orders if o["status"] == "approved")
    pending  = sum(1 for o in orders if o["status"] == "pending")

    await message.answer(
        f"╔════════════════════╗\n"
        f"     📦  MY ORDERS    \n"
        f"╚════════════════════╝\n\n"
        f"✅  Delivered  :  {approved}\n"
        f"⏳  Pending    :  {pending}\n"
        f"📊  Total      :  {len(orders)}\n\n"
        f"{DIVIDER}\n"
        f"Tap any order to view details 👇",
        reply_markup=orders_keyboard(orders),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("view_o:"))
async def view_order(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]
    order    = get_order(order_id)

    if not order or int(order["user_id"]) != int(callback.from_user.id):
        await callback.answer("Order not found!", show_alert=True)
        return

    codes = get_order_codes(order_id) if order["status"] == "approved" else []
    text  = order_detail_msg(order, codes)

    await callback.message.edit_text(
        text,
        reply_markup=order_detail_keyboard(order_id, order["status"]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "back_orders")
async def back_orders(callback: CallbackQuery):
    orders = get_user_orders(callback.from_user.id)
    if not orders:
        await callback.message.edit_text(
            f"📦 <b>MY ORDERS</b>\n\nNo orders yet 😊",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    approved = sum(1 for o in orders if o["status"] == "approved")
    pending  = sum(1 for o in orders if o["status"] == "pending")

    await callback.message.edit_text(
        f"╔════════════════════╗\n"
        f"     📦  MY ORDERS    \n"
        f"╚════════════════════╝\n\n"
        f"✅  Delivered  :  {approved}\n"
        f"⏳  Pending    :  {pending}\n"
        f"📊  Total      :  {len(orders)}\n\n"
        f"{DIVIDER}\n"
        f"Tap any order to view details 👇",
        reply_markup=orders_keyboard(orders),
        parse_mode="HTML"
    )
    await callback.answer()
