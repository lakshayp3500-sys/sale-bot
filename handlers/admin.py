"""handlers/admin.py — Complete admin panel with every button working."""

import asyncio

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from states.states import AdminStates
from utils.db_helpers import (
    get_all_vouchers_with_stock, get_voucher, get_voucher_stock,
    add_voucher, delete_voucher, update_price,
    set_voucher_disclaimer, add_codes_bulk,
    get_all_users, get_pending_orders, get_all_live_orders,
    get_order, get_order_codes, reject_order,
    deliver_codes, mark_utr_used,
    get_setting, set_setting,
    get_all_channels, add_channel, remove_channel,
    get_stats, get_user, get_user_orders,
)
from utils.messages import (
    DIVIDER, more_commands_msg,
    admin_order_detail_msg, admin_user_info_msg,
    success_delivery_msg, rejection_msg,
)
from keyboards.reply import admin_menu, main_menu, cancel_keyboard
from keyboards.inline import (
    admin_approve_keyboard, voucher_manage_keyboard,
    voucher_action_keyboard, voucher_select_keyboard,
    channel_manage_keyboard,
)

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ══════════════════════════════════════════════════════════════════════════════
# /admin — PANEL ENTRY
# ══════════════════════════════════════════════════════════════════════════════

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access Denied.")
        return
    s = get_stats()
    await message.answer(
        f"╔════════════════════╗\n"
        f"   🔐  ADMIN PANEL   \n"
        f"╚════════════════════╝\n\n"
        f"  📅 Today\n"
        f"  💰 Revenue    :  ₹{s['today_earnings']:.0f}\n"
        f"  🛒 Orders     :  {s['today_orders']}\n\n"
        f"  📈 All Time\n"
        f"  👥 Users      :  {s['total_users']}\n"
        f"  ✅ Completed  :  {s['total_orders']}\n"
        f"  ⏳ Pending    :  {s['pending_orders']}\n\n"
        f"{DIVIDER}",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 📦 STOCK MANAGER
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📦 Stock Manager")
async def stock_manager(message: Message):
    if not is_admin(message.from_user.id):
        return
    vouchers = get_all_vouchers_with_stock()
    if not vouchers:
        await message.answer(
            f"📦 <b>Stock Manager</b>\n{DIVIDER}\n\n"
            f"No vouchers yet. Use ➕ Add Voucher to create one.",
            parse_mode="HTML"
        )
        return
    text = f"📦 <b>STOCK OVERVIEW</b>\n{DIVIDER}\n\n"
    for v in vouchers:
        icon = "🟢" if v["stock"] > 0 else "🔴"
        disc = "✅" if v.get("disclaimer") else "❌"
        text += (
            f"{icon} <b>{v['name']}</b>\n"
            f"   💰 ₹{v['price']:.0f}  |  📦 {v['stock']} codes  |  📋 T&amp;C: {disc}\n"
            f"   🆔 ID: <code>{v['id']}</code>\n   ─────────────\n"
        )
    await message.answer(text, reply_markup=voucher_manage_keyboard(vouchers), parse_mode="HTML")


@router.callback_query(F.data.startswith("vstk:"))
async def voucher_stock_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    voucher_id = int(callback.data.split(":")[1])
    v = get_voucher(voucher_id)
    if not v:
        await callback.answer("Voucher not found!", show_alert=True)
        return
    await callback.message.edit_text(
        f"📦 <b>{v['name']}</b>\n{DIVIDER}\n\n"
        f"🆔 ID: <code>{v['id']}</code>\n"
        f"💰 Price: ₹{v['price']:.0f}\n"
        f"🔢 Stock: {v['stock']} codes\n"
        f"📋 Disclaimer: {'✅ Set' if v.get('disclaimer') else '❌ Not set'}\n\n"
        f"Choose an action 👇",
        reply_markup=voucher_action_keyboard(voucher_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vdel:"))
async def delete_voucher_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    voucher_id = int(callback.data.split(":")[1])
    v = get_voucher(voucher_id)
    if not v:
        await callback.answer("Not found!", show_alert=True)
        return
    delete_voucher(voucher_id)
    await callback.message.edit_text(
        f"✅ Voucher <b>{v['name']}</b> deleted.\n"
        f"Past orders and delivered codes are preserved in history.",
        parse_mode="HTML"
    )
    await callback.answer("Deleted!")


@router.callback_query(F.data.startswith("vdisc:"))
async def set_disclaimer_inline(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    voucher_id = int(callback.data.split(":")[1])
    await state.update_data(target_voucher_id=voucher_id)
    await state.set_state(AdminStates.set_disclaimer_input)
    await callback.message.answer(
        f"📝 <b>Set Disclaimer</b>\n\nType the T&amp;C text for this voucher:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.set_disclaimer_input, F.text)
async def save_disclaimer(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    set_voucher_disclaimer(data["target_voucher_id"], message.text)
    await message.answer("✅ Disclaimer updated!", reply_markup=admin_menu())
    await state.clear()


@router.callback_query(F.data == "vstk_back")
async def back_to_stock(callback: CallbackQuery):
    vouchers = get_all_vouchers_with_stock()
    await callback.message.edit_text(
        f"📦 <b>Stock Manager</b>\n{DIVIDER}\n\nSelect a voucher to manage:",
        reply_markup=voucher_manage_keyboard(vouchers),
        parse_mode="HTML"
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# ➕ ADD VOUCHER
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "➕ Add Voucher")
@router.message(Command("add"))
async def add_voucher_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.add_voucher_name)
    await message.answer(
        f"➕ <b>Add New Voucher</b>\n{DIVIDER}\n\n"
        f"Enter voucher name:\n"
        f"Example: <code>Shein ₹800 Off</code>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AdminStates.add_voucher_name, F.text)
async def save_voucher_name(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    await state.update_data(new_voucher_name=message.text.strip())
    await state.set_state(AdminStates.add_voucher_price)
    await message.answer(
        f"💰 Enter price per code (₹):\nExample: <code>150</code>",
        parse_mode="HTML"
    )


@router.message(AdminStates.add_voucher_price, F.text)
async def save_voucher_price(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Enter a valid price (e.g. 150):")
        return
    data = await state.get_data()
    name = data.get("new_voucher_name", "")
    ok = add_voucher(name, price)
    if ok:
        vouchers = get_all_vouchers_with_stock()
        new_v = next((v for v in vouchers if v["name"] == name), None)
        v_id_text = f"\n🆔 Voucher ID: <code>{new_v['id']}</code>" if new_v else ""
        await message.answer(
            f"✅ <b>Voucher Added!</b>\n\n"
            f"📦 Name: <b>{name}</b>\n"
            f"💰 Price: ₹{price:.0f}"
            f"{v_id_text}\n\n"
            f"Now use <b>🔑 Add Codes</b> to add stock.",
            reply_markup=admin_menu(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ Voucher '<b>{name}</b>' already exists!",
            reply_markup=admin_menu(),
            parse_mode="HTML"
        )
    await state.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 🔑 ADD CODES
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "🔑 Add Codes")
async def add_codes_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    vouchers = get_all_vouchers_with_stock()
    if not vouchers:
        await message.answer("❌ No vouchers yet. Add a voucher first.")
        return
    await state.set_state(AdminStates.add_codes_voucher)
    await message.answer(
        f"🔑 <b>Add Codes</b>\n{DIVIDER}\n\nSelect voucher:",
        reply_markup=voucher_select_keyboard(vouchers, "addcode"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("addcode:"))
async def add_codes_voucher_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    voucher_id = int(callback.data.split(":")[1])
    v = get_voucher(voucher_id)
    if not v:
        await callback.answer("Not found!", show_alert=True)
        return
    await state.update_data(target_voucher_id=voucher_id, target_voucher_name=v["name"])
    await state.set_state(AdminStates.add_codes_input)
    await callback.message.edit_text(
        f"🔑 <b>Add Codes to: {v['name']}</b>\n{DIVIDER}\n\n"
        f"Send codes — one per line or comma-separated:\n\n"
        f"<code>CODE1\nCODE2\nCODE3</code>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.add_codes_input, F.text)
async def save_codes(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    data         = await state.get_data()
    voucher_id   = data.get("target_voucher_id")
    voucher_name = data.get("target_voucher_name", "")
    count        = add_codes_bulk(voucher_id, message.text)
    if count == 0:
        await message.answer("❌ No valid codes found. Check format.", reply_markup=admin_menu())
    else:
        total = get_voucher_stock(voucher_id)
        await message.answer(
            f"✅ <b>{count} codes added</b> to <b>{voucher_name}</b>!\n"
            f"📦 Total stock now: <b>{total}</b>",
            reply_markup=admin_menu(),
            parse_mode="HTML"
        )
    await state.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 💰 SET PRICE
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "💰 Set Price")
async def set_price_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    vouchers = get_all_vouchers_with_stock()
    if not vouchers:
        await message.answer("❌ No vouchers yet.")
        return
    await state.set_state(AdminStates.set_price_voucher)
    await message.answer(
        f"💰 <b>Set Price</b>\n{DIVIDER}\n\nSelect voucher:",
        reply_markup=voucher_select_keyboard(vouchers, "setprice"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("setprice:"))
async def set_price_voucher_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    voucher_id = int(callback.data.split(":")[1])
    v = get_voucher(voucher_id)
    if not v:
        await callback.answer("Not found!", show_alert=True)
        return
    await state.update_data(target_voucher_id=voucher_id,
                            old_price=v["price"], target_voucher_name=v["name"])
    await state.set_state(AdminStates.set_price_input)
    await callback.message.edit_text(
        f"💰 <b>{v['name']}</b>\nCurrent: ₹{v['price']:.0f}\n\nEnter new price (₹):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.set_price_input, F.text)
async def save_price(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Enter a valid price (e.g. 150):")
        return
    data = await state.get_data()
    update_price(data["target_voucher_id"], price)
    await message.answer(
        f"✅ Price updated!\n\n"
        f"📦 {data['target_voucher_name']}\n"
        f"📉 Old: ₹{data['old_price']:.0f}  →  📈 New: ₹{price:.0f}",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )
    await state.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 📋 PENDING REQUESTS  (NEW BUTTON)
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📋 Pending Requests")
@router.message(Command("pending"))
async def pending_requests(message: Message):
    if not is_admin(message.from_user.id):
        return
    orders = get_pending_orders()
    if not orders:
        await message.answer(
            f"📋 <b>Pending Requests</b>\n{DIVIDER}\n\n"
            f"✅ No pending payment requests right now.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"📋 <b>Pending Requests</b> ({len(orders)})\n{DIVIDER}\n\n"
        f"Showing orders with UTR submitted — tap Approve or Reject 👇",
        parse_mode="HTML"
    )
    for order in orders:
        full_name = order.get("full_name") or "Unknown"
        username  = order.get("username")  or ""
        uname     = f"@{username}" if username else "N/A"
        text = (
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
        await message.answer(
            text,
            reply_markup=admin_approve_keyboard(order["id"]),
            parse_mode="HTML"
        )
        await asyncio.sleep(0.05)


# ══════════════════════════════════════════════════════════════════════════════
# ✅ APPROVE / ❌ REJECT
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("approve:"))
async def approve_order(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return

    order_id = callback.data.split(":")[1]
    order    = get_order(order_id)

    if not order:
        await callback.answer("❌ Order not found!", show_alert=True)
        return
    if order["status"] != "pending":
        await callback.answer(f"Order already {order['status']}!", show_alert=True)
        return

    codes = deliver_codes(order_id, order["voucher_id"], order["quantity"])

    if codes is None:
        await callback.answer("❌ Not enough stock!", show_alert=True)
        try:
            await callback.message.edit_text(
                (callback.message.text or "") + "\n\n🔴 <b>FAILED — Out of stock!</b>",
                reply_markup=None,
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    if order.get("utr"):
        mark_utr_used(order["utr"], order_id)

    support  = get_setting("support_username") or "@admin"
    user_msg = success_delivery_msg(
        voucher_name=order["voucher_name"],
        codes=codes,
        amount=order["total_price"],
        order_id=order_id,
        support=support,
    )
    try:
        await bot.send_message(order["user_id"], user_msg, parse_mode="HTML")
    except Exception:
        pass

    remaining  = get_voucher_stock(order["voucher_id"])
    stock_note = ""
    if remaining == 0:
        stock_note = "\n\n🚨 <b>STOCK EMPTY! Add more codes.</b>"
    elif remaining <= 5:
        stock_note = f"\n\n⚠️ Only <b>{remaining}</b> codes left!"

    try:
        await callback.message.edit_text(
            (callback.message.text or "") + f"\n\n🟢 <b>APPROVED &amp; DELIVERED</b>{stock_note}",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.answer("✅ Approved and delivered!")


@router.callback_query(F.data.startswith("reject:"))
async def reject_order_cb(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return

    order_id = callback.data.split(":")[1]
    order    = get_order(order_id)

    if not order:
        await callback.answer("❌ Order not found!", show_alert=True)
        return
    if order["status"] != "pending":
        await callback.answer(f"Order already {order['status']}!", show_alert=True)
        return

    reject_order(order_id)

    support = get_setting("support_username") or "@admin"
    try:
        await bot.send_message(
            order["user_id"],
            rejection_msg(order_id, support),
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            (callback.message.text or "") + "\n\n🔴 <b>REJECTED</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.answer("❌ Rejected.")


# ══════════════════════════════════════════════════════════════════════════════
# 📊 STATS
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📊 Stats")
@router.message(Command("stats"))
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    s = get_stats()
    await message.answer(
        f"╔════════════════════╗\n"
        f"   📊  STATISTICS    \n"
        f"╚════════════════════╝\n\n"
        f"📅 <b>Today</b>\n"
        f"💰 Revenue     :  ₹{s['today_earnings']:.0f}\n"
        f"🛒 Orders      :  {s['today_orders']}\n"
        f"👤 New Users   :  {s['today_new_users']}\n\n"
        f"📈 <b>All Time</b>\n"
        f"👥 Total Users :  {s['total_users']}\n"
        f"✅ Delivered   :  {s['total_orders']}\n"
        f"❌ Rejected    :  {s['rejected_orders']}\n"
        f"⌛ Expired     :  {s['expired_orders']}\n"
        f"💰 Total Rev   :  ₹{s['total_revenue']:.0f}\n\n"
        f"📦 <b>Stock</b>\n"
        f"🟢 In Stock    :  {s['in_stock']} products\n"
        f"🔴 Out of Stock:  {s['out_of_stock']} products\n\n"
        f"{DIVIDER}",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


# ══════════════════════════════════════════════════════════════════════════════
# 📢 BROADCAST
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📢 Broadcast")
@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.broadcast_message)
    await message.answer(
        f"📢 <b>Broadcast</b>\n{DIVIDER}\n\n"
        f"Send the message to broadcast to all users.\n"
        f"Supports text, photo, video, etc.\n\n"
        f"Tap ❌ Cancel to abort.",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AdminStates.broadcast_message)
async def process_broadcast(message: Message, state: FSMContext):
    if message.text and message.text == "❌ Cancel":
        await state.clear()
        await message.answer("❌ Broadcast cancelled.", reply_markup=admin_menu())
        return

    users = get_all_users()
    if not users:
        await state.clear()
        await message.answer("❌ No users in database.", reply_markup=admin_menu())
        return

    await message.answer(f"⏳ Sending to {len(users)} users...")
    success = fail = 0
    for user in users:
        try:
            await message.copy_to(chat_id=user["telegram_id"])
            success += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)

    await message.answer(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"🟢 Sent   : {success}\n"
        f"🔴 Failed : {fail}",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )
    await state.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 📺 CHANNELS
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📺 Channels")
async def channels_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    channels = get_all_channels()
    if not channels:
        text = f"📺 <b>Channels</b>\n{DIVIDER}\n\nNo channels added yet."
    else:
        lines = "\n".join([f"🔗 {ch['name']} — {ch['link']}" for ch in channels])
        text  = f"📺 <b>Channels ({len(channels)})</b>\n{DIVIDER}\n\n{lines}"
    await message.answer(
        text,
        reply_markup=channel_manage_keyboard(channels),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "addch")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.add_channel_name)
    await callback.message.answer("➕ Enter channel name:", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(AdminStates.add_channel_name, F.text)
async def save_channel_name(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    await state.update_data(new_ch_name=message.text.strip())
    await state.set_state(AdminStates.add_channel_link)
    await message.answer("Enter channel link (e.g. https://t.me/mychannel):")


@router.message(AdminStates.add_channel_link, F.text)
async def save_channel_link(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    add_channel(data["new_ch_name"], message.text.strip())
    await message.answer(
        f"✅ Channel <b>{data['new_ch_name']}</b> added!",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("rmch:"))
async def remove_channel_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    ch_id = int(callback.data.split(":")[1])
    remove_channel(ch_id)
    channels = get_all_channels()
    try:
        await callback.message.edit_reply_markup(reply_markup=channel_manage_keyboard(channels))
    except Exception:
        pass
    await callback.answer("✅ Channel removed!")


# ══════════════════════════════════════════════════════════════════════════════
# 📝 LIVE ORDERS
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📝 Live Orders")
async def live_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    orders = get_all_live_orders()
    if not orders:
        await message.answer(
            f"📝 <b>Live Orders</b>\n{DIVIDER}\n\n✅ No active orders right now.",
            parse_mode="HTML"
        )
        return
    await message.answer(f"📝 <b>Live Orders</b> ({len(orders)})\n{DIVIDER}", parse_mode="HTML")
    for order in orders:
        full_name = order.get("full_name") or "Unknown"
        utr_text  = f"\n🧾 UTR: <code>{order['utr']}</code>" if order.get("utr") else "\n🧾 UTR: Not submitted"
        text = (
            f"🆔 <code>#{order['id']}</code>\n"
            f"👤 {full_name} (<code>{order['user_id']}</code>)\n"
            f"🛍  {order['voucher_name']} × {order['quantity']}\n"
            f"💰 ₹{order['total_price']:.0f}"
            f"{utr_text}\n"
            f"⏰ {str(order['created_at'])[:16]}"
        )
        markup = admin_approve_keyboard(order["id"]) if order.get("utr") else None
        await message.answer(text, reply_markup=markup, parse_mode="HTML")
        await asyncio.sleep(0.05)


# ══════════════════════════════════════════════════════════════════════════════
# 📖 MORE COMMANDS  (NEW BUTTON)
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📖 More Commands")
async def more_commands(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(more_commands_msg(), parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@router.message(Command("order"))
async def cmd_order(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args:
        await message.answer(
            "Usage: <code>/order ORDER_ID</code>\nExample: <code>/order A1B2C3D4E5F6</code>",
            parse_mode="HTML"
        )
        return
    order_id = command.args.strip().upper().lstrip("#")
    order    = get_order(order_id)
    if not order:
        await message.answer(f"❌ Order <code>#{order_id}</code> not found.", parse_mode="HTML")
        return
    user        = get_user(order["user_id"])
    buyer_name  = user.get("full_name", "Unknown") if user else "Unknown"
    buyer_uname = user.get("username", "")          if user else ""
    codes       = get_order_codes(order_id)
    text        = admin_order_detail_msg(order, buyer_name, buyer_uname, codes)
    markup      = admin_approve_keyboard(order_id) if order["status"] == "pending" else None
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.message(Command("info"))
async def cmd_info(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer(
            "Usage: <code>/info USER_ID</code>\nExample: <code>/info 123456789</code>",
            parse_mode="HTML"
        )
        return
    user_id = int(command.args.strip())
    user    = get_user(user_id)
    if not user:
        await message.answer(f"❌ User <code>{user_id}</code> not found.", parse_mode="HTML")
        return
    orders      = get_user_orders(user_id)
    total_spent = sum(o["total_price"] for o in orders if o["status"] == "approved")
    await message.answer(admin_user_info_msg(user, orders, total_spent), parse_mode="HTML")


@router.message(Command("setprice"))
async def cmd_setprice(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args:
        await message.answer("Usage: <code>/setprice VOUCHER_ID PRICE</code>", parse_mode="HTML")
        return
    parts = command.args.strip().split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/setprice VOUCHER_ID PRICE</code>", parse_mode="HTML")
        return
    try:
        vid   = int(parts[0])
        price = float(parts[1])
    except ValueError:
        await message.answer("❌ Invalid ID or price.", parse_mode="HTML")
        return
    v = get_voucher(vid)
    if not v:
        await message.answer(f"❌ Voucher ID {vid} not found.", parse_mode="HTML")
        return
    update_price(vid, price)
    await message.answer(
        f"✅ Price updated!\n📦 {v['name']}\n₹{v['price']:.0f} → ₹{price:.0f}",
        parse_mode="HTML"
    )


@router.message(Command("del"))
async def cmd_del(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Usage: <code>/del VOUCHER_ID</code>", parse_mode="HTML")
        return
    vid = int(command.args.strip())
    v   = get_voucher(vid)
    if not v:
        await message.answer(f"❌ Voucher ID {vid} not found.", parse_mode="HTML")
        return
    delete_voucher(vid)
    await message.answer(f"✅ Voucher <b>{v['name']}</b> deleted.", parse_mode="HTML")


@router.message(Command("setdisclaimer"))
async def cmd_setdisclaimer(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if not command.args:
        await message.answer(
            "Usage: <code>/setdisclaimer VOUCHER_ID T&C text</code>",
            parse_mode="HTML"
        )
        return
    parts = command.args.strip().split(" ", 1)
    if len(parts) < 2 or not parts[0].isdigit():
        await message.answer(
            "Usage: <code>/setdisclaimer VOUCHER_ID T&C text</code>",
            parse_mode="HTML"
        )
        return
    vid  = int(parts[0])
    text = parts[1].strip()
    v    = get_voucher(vid)
    if not v:
        await message.answer(f"❌ Voucher ID {vid} not found.", parse_mode="HTML")
        return
    set_voucher_disclaimer(vid, text)
    await message.answer(f"✅ Disclaimer set for <b>{v['name']}</b>!", parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
# 🏠 NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════

@router.message(F.text == "🏠 Main Menu")
async def go_main_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Main Menu", reply_markup=main_menu())


@router.callback_query(F.data == "admin_back")
async def admin_back_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("🔙 Admin Panel", reply_markup=admin_menu())
    await callback.answer()
