from aiogram.fsm.state import State, StatesGroup


class BuyStates(StatesGroup):
    select_voucher    = State()
    select_quantity   = State()
    custom_quantity   = State()
    disclaimer_confirm = State()
    waiting_utr       = State()


class AdminStates(StatesGroup):
    add_voucher_name      = State()
    add_voucher_price     = State()
    add_codes_voucher     = State()
    add_codes_input       = State()
    set_price_voucher     = State()
    set_price_input       = State()
    set_disclaimer_voucher = State()
    set_disclaimer_input  = State()
    broadcast_message     = State()
    add_channel_name      = State()
    add_channel_link      = State()
    remove_channel        = State()
    set_support           = State()
    reply_ticket          = State()


class SupportStates(StatesGroup):
    write_message = State()
