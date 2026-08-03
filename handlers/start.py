"""handlers/start.py — /start, welcome, disclaimer, channels."""

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import ADMIN_IDS, BOT_NAME
from utils.db_helpers import register_user, get_setting, get_all_channels
from utils.messages import welcome_msg, new_user_alert, DIVIDER
from keyboards.reply import main_menu, admin_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user      = message.from_user
    username  = user.username or ""
    full_name = user.full_name or user.first_name or "User"

    is_new  = register_user(user.id, username, full_name)
    support = get_setting("support_username") or "@admin"

    # Admins get admin keyboard on /start
    markup = admin_menu() if user.id in ADMIN_IDS else main_menu()

    await message.answer(
        welcome_msg(user.first_name or "there", BOT_NAME, support),
        reply_markup=markup,
        parse_mode="HTML"
    )

    if is_new:
        alert = new_user_alert(username, user.id, full_name)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, alert, parse_mode="HTML")
            except Exception:
                pass


@router.message(F.text == "📜 Disclaimer")
async def disclaimer(message: Message):
    await message.answer(
        f"┌────────────────────┐\n"
        f"│   📜  DISCLAIMER   │\n"
        f"└────────────────────┘\n\n"
        f"⚠️  All vouchers sold here are digital products.\n\n"
        f"• No refunds once codes are delivered\n"
        f"• Codes are valid at time of delivery\n"
        f"• We are not responsible for misuse\n"
        f"• Payment issues? Contact support\n\n"
        f"{DIVIDER}\n"
        f"<i>By purchasing, you agree to these terms.</i>",
        parse_mode="HTML"
    )


@router.message(F.text == "📢 Our Channels")
async def our_channels(message: Message):
    channels = get_all_channels()
    if not channels:
        await message.answer("📢 No channels added yet. Check back soon!")
        return

    lines = [f"🔗 <a href='{ch['link']}'>{ch['name']}</a>" for ch in channels]
    await message.answer(
        f"📢 <b>OUR CHANNELS</b>\n{DIVIDER}\n\n"
        + "\n".join(lines)
        + f"\n\n{DIVIDER}\n<i>Join to stay updated with the latest deals!</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
