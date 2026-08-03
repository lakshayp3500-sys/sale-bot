"""keyboards/reply.py — Reply keyboard builders."""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Buy Vouchers"), KeyboardButton(text="📦 My Orders")],
            [KeyboardButton(text="📢 Our Channels"), KeyboardButton(text="🆘 Support")],
            [KeyboardButton(text="📜 Disclaimer")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose an option..."
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Stock Manager"), KeyboardButton(text="➕ Add Voucher")],
            [KeyboardButton(text="🔑 Add Codes"),     KeyboardButton(text="💰 Set Price")],
            [KeyboardButton(text="📋 Pending Requests"), KeyboardButton(text="📢 Broadcast")],
            [KeyboardButton(text="📊 Stats"),          KeyboardButton(text="📺 Channels")],
            [KeyboardButton(text="📝 Live Orders"),   KeyboardButton(text="🎫 Tickets")],
            [KeyboardButton(text="📖 More Commands")],
            [KeyboardButton(text="🏠 Main Menu")],
        ],
        resize_keyboard=True
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Cancel")]],
        resize_keyboard=True
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
