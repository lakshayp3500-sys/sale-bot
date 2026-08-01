# Sale Bot — Full Project Blueprint

> **Purpose of this document:** This MD file contains every detail needed to build this Telegram bot from scratch. Any AI reading this should be able to produce the exact same bot without any additional input.

---

## 1. What This Bot Does

A **premium Telegram Voucher/Coupon Selling Bot** written in Python using `aiogram 3.x`.

- Customers browse available voucher products inside Telegram
- They select a product + quantity → bot generates a UPI QR code
- Customer pays and submits a 12-digit UTR (bank reference number)
- Admin receives notification and manually approves/rejects the payment
- On approval → voucher codes are automatically delivered from stock
- Full admin panel inside Telegram (no web dashboard needed)
- Deployed on **Render** (free tier) with **Supabase PostgreSQL** as database
- Self-ping every 5 minutes to prevent Render free tier sleep

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Bot Framework | aiogram 3.13.1 |
| Web Server | aiohttp (for self-ping endpoint) |
| Database | Supabase PostgreSQL (production) / SQLite (local dev) |
| DB Driver | psycopg2-binary (PostgreSQL), aiosqlite (SQLite) |
| QR Code | qrcode + Pillow |
| Config | python-dotenv |
| Deployment | Render (free tier) |

---

## 3. Environment Variables (.env)

```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321          # Comma-separated Telegram user IDs
UPI_ID=yourname@bank                    # UPI ID for payments
SHOP_NAME=Your Shop Name
BOT_NAME=Your Bot Name
ORDER_EXPIRY_MINUTES=10                 # Minutes before unpaid order expires
DATABASE_URL=postgresql://...           # Supabase connection string (if empty → SQLite)
PORT=5001                               # aiohttp server port (Render sets this automatically)
RENDER_EXTERNAL_URL=https://your-app.onrender.com  # Set after deploy for self-ping
```

---

## 4. Complete File Structure

```
sale-bot/
├── main.py                  # Entry point: bot + aiohttp server (self-ping)
├── config.py                # Load all env vars
├── database.py              # Unified SQLite/PostgreSQL connection layer
├── order_manager.py         # Order lifecycle: create, expire, fetch
├── qr_generator.py          # Generate UPI QR code image with amount label
├── requirements.txt
├── Procfile                 # For Render: web: python main.py
├── runtime.txt              # python-3.11.0
├── .env.example
├── handlers/
│   ├── __init__.py
│   ├── start.py             # /start, welcome, disclaimer, channels
│   ├── buy.py               # Full purchase flow (product → QR → UTR → pending)
│   ├── orders.py            # My Orders, order history with codes
│   ├── admin.py             # Full admin panel
│   └── support.py           # Support ticket system
├── keyboards/
│   ├── __init__.py
│   ├── inline.py            # All InlineKeyboardMarkup builders
│   └── reply.py             # All ReplyKeyboardMarkup builders
├── states/
│   ├── __init__.py
│   └── states.py            # All FSM state groups
└── utils/
    ├── __init__.py
    ├── db_helpers.py        # All database operations (functions only)
    └── messages.py          # All message text templates
```

---

## 5. Database Schema

### Table: `users`
```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    full_name TEXT,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `vouchers`
```sql
CREATE TABLE IF NOT EXISTS vouchers (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    price REAL NOT NULL,
    disclaimer TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `codes`
```sql
CREATE TABLE IF NOT EXISTS codes (
    id SERIAL PRIMARY KEY,
    voucher_id INTEGER REFERENCES vouchers(id),
    code TEXT NOT NULL,
    is_used INTEGER DEFAULT 0,
    used_in_order TEXT
);
```

### Table: `orders`
```sql
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,               -- Random 12-char hex e.g. "A1B2C3D4E5F6"
    user_id BIGINT NOT NULL,
    voucher_id INTEGER REFERENCES vouchers(id),
    quantity INTEGER NOT NULL,
    total_price REAL NOT NULL,
    utr TEXT,                          -- 12-digit bank reference number
    status TEXT DEFAULT 'pending',     -- pending | approved | rejected | expired | cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_at TIMESTAMP,
    approved_at TIMESTAMP
);
```

### Table: `order_codes`
```sql
CREATE TABLE IF NOT EXISTS order_codes (
    id SERIAL PRIMARY KEY,
    order_id TEXT REFERENCES orders(id),
    code TEXT NOT NULL
);
```

### Table: `used_utrs`
```sql
-- Stores every UTR that has been approved, to prevent reuse
CREATE TABLE IF NOT EXISTS used_utrs (
    utr TEXT PRIMARY KEY,
    order_id TEXT,
    approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `settings`
```sql
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
-- Default rows to insert on init:
-- ('support_username', '@admin')
-- ('shop_name', 'My Shop')
```

### Table: `channels`
```sql
CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    link TEXT NOT NULL
);
```

### Table: `tickets`
```sql
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    user_id BIGINT,
    category TEXT,
    subject TEXT,
    message TEXT,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `ticket_replies`
```sql
CREATE TABLE IF NOT EXISTS ticket_replies (
    id SERIAL PRIMARY KEY,
    ticket_id TEXT REFERENCES tickets(id),
    from_admin INTEGER DEFAULT 0,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. config.py

```python
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_NAME = os.getenv("BOT_NAME", "Sale Bot")
SHOP_NAME = os.getenv("SHOP_NAME", "My Shop")

ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = list(map(int, ADMIN_IDS_RAW.split(","))) if ADMIN_IDS_RAW.strip() else []

UPI_ID = os.getenv("UPI_ID", "yourname@upi")
ORDER_EXPIRY_MINUTES = int(os.getenv("ORDER_EXPIRY_MINUTES", "10"))

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_PATH = "sale_bot.db"

PORT = int(os.getenv("PORT", "5001"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")
```

---

## 7. database.py

Unified connection layer — same code works for both SQLite (local) and PostgreSQL (Supabase).

Key points:
- `IS_POSTGRES = bool(DATABASE_URL)`
- PostgreSQL: use `psycopg2`, replace `?` with `%s`, replace `INTEGER PRIMARY KEY AUTOINCREMENT` with `SERIAL PRIMARY KEY`
- SQLite: use `sqlite3` with `row_factory = sqlite3.Row`
- `get_conn()` returns a `UnifiedConn` context manager that auto-commits and closes
- All rows returned as `dict`-like objects accessible by key (`row["column_name"]`)
- `init_db()` creates all tables if not exist
- `run_migrations()` adds new columns safely using `ALTER TABLE IF NOT EXISTS` pattern

---

## 8. Full Purchase Flow (handlers/buy.py)

### Step 1 — User taps "🛍 Buy Vouchers"
- Fetch all vouchers with stock count from DB
- If no vouchers: show "Shop Closed / No products" message
- Show inline keyboard: each voucher as a button
  - Format: `🔥 Voucher Name — ₹Price | X pcs` (if stock > 0)
  - Format: `😴 Voucher Name — Out of Stock` (if stock == 0)
  - Out-of-stock buttons are still shown but clicking them shows an alert

### Step 2 — User selects a voucher
- Show voucher detail + quantity selection
- Quantity buttons: **1**, **5**, **10**, **20**, **✏️ Custom**
- All 5 buttons always shown
- If user taps a qty > available stock: show alert "Not enough stock!"
- Custom: ask user to type a number

### Step 3 — Show Disclaimer
- Show product T&C / disclaimer text
- Buttons: `✅ Accept & Continue` | `❌ Cancel`

### Step 4 — Generate UPI QR and Payment Screen
```
┌──────────────────────┐
│   💳 PAYMENT DETAILS  │
└──────────────────────┘

🛍  Voucher Name × Qty
💰  Total: ₹Amount
🆔  Order: #ORDERID

Pay within 10 minutes ⏳
```
- Generate QR code image using `qr_generator.py`
  - UPI link format: `upi://pay?pa=UPI_ID&pn=SHOP_NAME&am=AMOUNT&cu=INR`
  - QR image has amount label at bottom: "Pay Exactly: Rs.XXX.00" + shop name
- Send QR as photo with caption
- Buttons below:
  - `📲 Open UPI App` (url button → upi:// link)
  - `✅ I Have Paid`
  - `❌ Cancel Order`
- Save order to DB with status `pending`
- Order ID: random 12-char uppercase hex e.g. `A1B2C3D4E5F6`
- Set `expiry_at = now + ORDER_EXPIRY_MINUTES`

### Step 5 — User taps "I Have Paid"
- Set FSM state to `BuyStates.waiting_utr`
- Ask: "Please enter your 12-digit UTR / Reference Number:"
- Cancel button shown

### Step 6 — User enters UTR
- Validate: must be exactly 12 digits (all numeric)
- If invalid: "❌ Invalid UTR! Enter exactly 12 numeric digits." (stay in state)
- **Check if UTR already used (in `used_utrs` table):**
  - If yes: show "⚠️ Payment verification with another order. This UTR has already been used. Contact support if this is an error."
  - Clear state, do NOT save
- If UTR is new and valid:
  - Save UTR to order: `UPDATE orders SET utr = ? WHERE id = ?`
  - Show user: 
    ```
    ✅ UTR Submitted!
    
    🆔 Order: #ORDERID
    🧾 UTR: XXXXXXXXXXXX
    
    ⏳ Payment sent for verification.
    Please wait up to 5 minutes.
    Our team will verify and deliver your codes shortly.
    ```
  - Send admin notification (to ALL admin IDs):
    ```
    🔔 NEW PAYMENT REQUEST
    ━━━━━━━━━━━━━━━━━━━━
    👤 User: Full Name (@username)
    🆔 User ID: 123456789
    🛍 Item: Voucher Name × Qty
    💰 Amount: ₹XXX
    🆔 Order ID: #ORDERID
    🧾 UTR: XXXXXXXXXXXX
    ━━━━━━━━━━━━━━━━━━━━
    ```
    With inline buttons: `[✅ Approve & Deliver]  [❌ Reject]`

### Step 7 — Admin approves
- Mark UTR as used: insert into `used_utrs(utr, order_id)`
- Deliver codes from stock (idempotent — check `order_codes` first)
- Update order status to `approved`, set `approved_at`
- Mark codes as used in `codes` table
- Send user:
  ```
  🎉 Payment Approved!
  ━━━━━━━━━━━━━━━━━━━━
  🛍 Voucher Name × Qty
  🆔 Order: #ORDERID
  
  🔑 Your Codes:
  CODE1
  CODE2
  ...
  ━━━━━━━━━━━━━━━━━━━━
  Thank you for shopping! 🙏
  ```
- Update admin message: append "✅ APPROVED & DELIVERED"

### Step 7b — Admin rejects
- Update order status to `rejected`
- Send user:
  ```
  ❌ Payment Rejected
  ━━━━━━━━━━━━━━━━━━━━
  🆔 Order: #ORDERID
  🧾 UTR: XXXXXXXXXXXX
  
  Your payment could not be verified.
  Please contact support: @support_username
  ```
- Update admin message: append "❌ REJECTED"

---

## 9. Admin Panel (handlers/admin.py)

### Access
- Only users whose Telegram ID is in `ADMIN_IDS` can access
- `/admin` command opens the admin panel

### Admin Panel Message
```
╔════════════════════╗
   🔐  ADMIN PANEL
╚════════════════════╝

  📅 Today
  💰 Revenue    :  ₹XXXX
  🛒 Orders     :  XX

  📊 All Time
  👥 Users      :  XXX
  ✅ Completed  :  XXX
  ⏳ Pending    :  XX

━━━━━━━━━━━━━━━━━━━━
```

### Admin Reply Keyboard Buttons (admin_menu)
Row 1: `📦 Stock Manager` | `➕ Add Voucher`
Row 2: `🔑 Add Codes` | `💰 Set Price`
Row 3: `📋 Pending Requests` | `📢 Broadcast`
Row 4: `📊 Stats` | `📺 Channels`
Row 5: `📝 Live Orders` | `🎫 Tickets`
Row 6: `📖 More Commands`
Row 7: `🏠 Main Menu`

---

### Feature: 📦 Stock Manager
- Show all vouchers with: ID, name, price, stock count, disclaimer status
- Format per voucher:
  ```
  🆔 ID: 5
  📦 Name: Shein ₹800 Voucher
  💰 Price: ₹150
  🔢 Stock: 23 codes
  📋 Disclaimer: ✅ Set
  ─────────────────────
  ```
- Inline buttons per voucher: `[🗑 Delete]  [📝 Edit Disclaimer]`

---

### Feature: ➕ Add Voucher
FSM flow (AdminStates.add_voucher_name → add_voucher_price):
1. Ask: "Enter voucher name (e.g. Shein ₹800 Off):"
2. Ask: "Enter price per code (in ₹):"
3. Save to `vouchers` table
4. Confirm: "✅ Voucher 'Name' added at ₹Price"

---

### Feature: 🔑 Add Codes
FSM flow (AdminStates.add_codes_voucher → add_codes_input):
1. Show inline keyboard of all vouchers → admin picks one
2. Ask: "Send codes — one per line or comma-separated:"
3. Parse: split by newline or comma, strip each
4. Bulk insert into `codes` table
5. Confirm: "✅ X codes added to 'Voucher Name'. Total stock: Y"

---

### Feature: 💰 Set Price
FSM flow (AdminStates.set_price_voucher → set_price_value):
1. Show inline keyboard of all vouchers → admin picks one
2. Ask: "Enter new price (₹):"
3. Update `vouchers.price`
4. Confirm: "✅ Price updated: ₹Old → ₹New"

---

### Feature: 📋 Pending Requests
- Fetch all orders with `status = 'pending'` AND `utr IS NOT NULL`
- If none: "✅ No pending payment requests right now."
- For each pending order, send a separate message:
  ```
  🔔 PENDING REQUEST
  ━━━━━━━━━━━━━━━━━━━━
  👤 User: Full Name (@username)
  🆔 User ID: 123456789
  🛍  Item: Voucher Name × Qty
  💰 Amount: ₹XXX
  🆔 Order ID: #ORDERID
  🧾 UTR: XXXXXXXXXXXX
  ⏰ Submitted: 2024-01-15 14:30
  ━━━━━━━━━━━━━━━━━━━━
  ```
  With buttons: `[✅ Approve & Deliver]  [❌ Reject]`

---

### Feature: 📢 Broadcast
FSM flow (AdminStates.broadcast_message):
1. Ask: "Send the message (text/photo) to broadcast. Send /cancel to abort."
2. On receive: copy message to ALL users in `users` table
3. Show progress: "⏳ Sending to X users..."
4. Result: "✅ Broadcast Complete!\n🟢 Sent: X\n🔴 Failed: Y"
- Use `asyncio.sleep(0.05)` between sends to avoid Telegram flood limit

---

### Feature: 📊 Stats
```
📊 STATISTICS
━━━━━━━━━━━━━━━━━━━━

📅 Today
💰 Revenue     :  ₹XXXX
🛒 Orders      :  XX
👤 New Users   :  X

📈 All Time
👥 Total Users :  XXX
✅ Delivered   :  XXX
❌ Rejected    :  XX
⌛ Expired     :  XX
💰 Total Rev   :  ₹XXXXX

📦 Stock Status
🟢 In Stock    :  X products
🔴 Out of Stock:  X products
━━━━━━━━━━━━━━━━━━━━
```

---

### Feature: 📺 Channels
- List all channels from `channels` table
- Admin can add: name + link
- Admin can remove by ID
- These are shown to users via "📢 Our Channels" button

---

### Feature: 📝 Live Orders
- Show all orders with `status = 'pending'` (with or without UTR)
- Format: Order ID, user, voucher, qty, amount, time, UTR (if submitted)
- Approve/Reject buttons on each

---

### Feature: 🎫 Tickets
- Show all open support tickets
- Admin can reply to each ticket (user gets the reply in bot)
- Admin can close ticket

---

### Feature: 📖 More Commands
Send this message when "More Commands" tapped:
```
📖 ALL ADMIN COMMANDS
━━━━━━━━━━━━━━━━━━━━

🔍 LOOKUP COMMANDS
/order <ORDER_ID>
  → Full detail: who bought, what, when, UTR, codes, status
  Example: /order A1B2C3D4E5F6

/info <USER_ID>
  → User profile: name, username, join date, total orders,
    total spent, order history with all codes
  Example: /info 123456789

📦 STOCK COMMANDS
/add      → Add new voucher (guided)
/addcode  → Add codes to existing voucher
/del <VOUCHER_ID>  → Delete voucher (keeps order history)
/setprice <VOUCHER_ID> <PRICE>  → Update price
/setdisclaimer <VOUCHER_ID> <TEXT>  → Set T&C for voucher

📢 OTHER COMMANDS
/broadcast  → Send message to all users
/pending    → View pending payment requests
/stats      → Quick stats summary
/admin      → Open admin panel

━━━━━━━━━━━━━━━━━━━━
```

---

### Admin Slash Commands

#### `/order <ORDER_ID>`
Fetch order from DB. Show:
```
🔍 ORDER DETAIL
━━━━━━━━━━━━━━━━━━━━
🆔 Order: #ORDERID
👤 Buyer: Full Name (@username)
🆔 User ID: 123456789
🛍  Product: Voucher Name × Qty
💰 Base Amount: ₹XXX
📊 Status: ✅ Delivered / ⏳ Pending / ❌ Rejected
📅 Created: 2024-01-15 14:30
🧾 UTR: XXXXXXXXXXXX (if submitted)
✅ Approved: 2024-01-15 14:35 (if approved)

🔑 Delivered Codes:
CODE1
CODE2
━━━━━━━━━━━━━━━━━━━━
```
If not found: "❌ Order #ORDERID not found."

#### `/info <USER_ID>`
Fetch user + all their orders. Show:
```
👤 USER INFO
━━━━━━━━━━━━━━━━━━━━
🆔 Telegram ID: 123456789
📛 Name: Full Name
🔖 Username: @username
📅 Joined: 2024-01-10 09:00

📊 Order Stats
✅ Completed   :  5
⏳ Pending     :  1
❌ Rejected    :  0
💰 Total Spent :  ₹750

📦 Order History:
#ORDER1 — Voucher Name × 2 — ₹300 — ✅ Delivered
#ORDER2 — Voucher Name × 1 — ₹150 — ✅ Delivered
...
━━━━━━━━━━━━━━━━━━━━
```

---

## 10. User Menu (handlers/start.py)

### /start
- Register user (or update username/name if returning)
- If new user: send new user alert to ALL admins:
  ```
  🆕 NEW USER JOINED
  ━━━━━━━━━━━━━━━━━━━━
  📛 Name: Full Name
  🔖 Username: @username
  🆔 User ID: 123456789
  📅 Time: 2024-01-15 14:00
  ━━━━━━━━━━━━━━━━━━━━
  ```
- Show welcome message with main menu reply keyboard

### Main Menu Reply Keyboard
Row 1: `🛍 Buy Vouchers` | `📦 My Orders`
Row 2: `📢 Our Channels` | `🆘 Support`
Row 3: `📜 Disclaimer`

### My Orders (handlers/orders.py)
- Fetch all user orders (newest first)
- Show summary: Delivered count, Pending count, Total count
- Inline keyboard: one button per order
  - Format: `✅ Voucher Name • #ORDERID` (status emoji changes)
  - Status emojis: ✅ approved, ⏳ pending, ❌ rejected, 🚫 cancelled, ⌛ expired
- Tap order → show full detail with codes (if approved)
- **Important**: Even if voucher was deleted, order history and codes must still show

### Our Channels
- Fetch from `channels` table
- Show as clickable links

### Support (handlers/support.py)
- Show categories: 💸 Payment Issue | 🎫 Code Not Working | 📦 Order Problem | ❓ Other
- Also show: `📋 My Tickets`
- User selects category → auto FAQ shown → option to "Still need help? Write message"
- Creates ticket in DB → admin gets notification with Reply/Close buttons

### Disclaimer
```
┌────────────────────┐
│   📜 DISCLAIMER    │
└────────────────────┘

⚠️  All vouchers sold here are digital products.

• No refunds once codes are delivered
• Codes are valid at time of delivery
• We are not responsible for misuse
• Payment issues? Contact support

━━━━━━━━━━━━━━━━━━━━
By purchasing, you agree to these terms.
```

---

## 11. states/states.py

```python
from aiogram.fsm.state import State, StatesGroup

class BuyStates(StatesGroup):
    select_voucher = State()
    select_quantity = State()
    custom_quantity = State()
    disclaimer_confirm = State()
    waiting_payment = State()
    waiting_utr = State()       # NEW: waiting for user to enter UTR

class AdminStates(StatesGroup):
    add_voucher_name = State()
    add_voucher_price = State()
    add_codes_voucher = State()
    add_codes_input = State()
    set_price_voucher = State()
    set_price_value = State()
    reject_reason = State()
    broadcast_message = State()
    set_disclaimer_voucher = State()
    set_disclaimer_text = State()
    add_channel_name = State()
    add_channel_link = State()
    remove_channel = State()
    set_support = State()
    reply_ticket = State()

class SupportStates(StatesGroup):
    write_message = State()
```

---

## 12. qr_generator.py

```python
import io
import qrcode
from PIL import Image, ImageDraw, ImageFont

def generate_qr_with_label(upi_link: str, amount: float, shop_name: str) -> io.BytesIO:
    # Generate QR code
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H,
                        box_size=10, border=4)
    qr.add_data(upi_link)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    
    # Add label below QR
    qr_w, qr_h = qr_img.size
    label_h = 65
    final = Image.new("RGB", (qr_w, qr_h + label_h), "white")
    final.paste(qr_img, (0, 0))
    draw = ImageDraw.Draw(final)
    
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_sm  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        font_big = font_sm = ImageFont.load_default()
    
    draw.text((qr_w//2, qr_h+8),  f"Pay Exactly: Rs.{amount:.2f}", fill="black", font=font_big, anchor="mt")
    draw.text((qr_w//2, qr_h+38), shop_name, fill="gray", font=font_sm, anchor="mt")
    
    buf = io.BytesIO()
    final.save(buf, format="PNG")
    buf.seek(0)
    return buf
```

---

## 13. main.py (Entry Point)

```python
import asyncio, logging, sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS, PORT, RENDER_EXTERNAL_URL
from database import init_db
from handlers import start, buy, orders, admin, support

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── SELF-PING (prevent Render sleep) ─────────────────────────────────────────
async def self_ping():
    """Ping own server every 5 minutes to prevent Render free tier sleep."""
    if not RENDER_EXTERNAL_URL:
        return
    import aiohttp
    await asyncio.sleep(60)  # wait 1 min after start
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{RENDER_EXTERNAL_URL}/ping", timeout=aiohttp.ClientTimeout(total=10)):
                    pass
            logger.info("Self-ping sent.")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")
        await asyncio.sleep(300)  # every 5 minutes

# ── AIOHTTP ROUTES ────────────────────────────────────────────────────────────
async def ping_handler(request: web.Request) -> web.Response:
    return web.Response(text="pong")

async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        sys.exit(1)

    init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(buy.router)
    dp.include_router(orders.router)
    dp.include_router(support.router)
    dp.include_router(admin.router)

    # aiohttp web server for /ping and /health
    app = web.Application()
    app.router.add_get("/ping", ping_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

    # Start self-ping loop
    asyncio.create_task(self_ping())

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started — polling active.")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()
        await dp.storage.close()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
```

---

## 14. requirements.txt

```
aiogram==3.13.1
python-dotenv==1.0.1
aiosqlite==0.20.0
qrcode==8.0
Pillow==11.2.1
aiohttp==3.10.11
psycopg2-binary==2.9.9
```

---

## 15. Procfile & runtime.txt

**Procfile:**
```
web: python main.py
```

**runtime.txt:**
```
python-3.11.0
```

---

## 16. UTR Duplicate Check Logic

```python
# In utils/db_helpers.py

def is_utr_used(utr: str) -> bool:
    """Returns True if this UTR has already been approved."""
    conn = get_conn()
    row = conn.execute("SELECT utr FROM used_utrs WHERE utr = ?", (utr,)).fetchone()
    conn.close()
    return row is not None

def mark_utr_used(utr: str, order_id: str):
    """Mark a UTR as used after approval."""
    conn = get_conn()
    conn.execute("INSERT INTO used_utrs (utr, order_id) VALUES (?, ?)", (utr, order_id))
    conn.commit()
    conn.close()
```

**In buy.py UTR handler:**
```python
@router.message(BuyStates.waiting_utr, F.text)
async def process_utr(message: Message, state: FSMContext):
    utr = message.text.strip()
    
    # Validate: 12 digits only
    if not utr.isdigit() or len(utr) != 12:
        await message.answer("❌ Invalid UTR!\n\nEnter exactly <b>12 numeric digits</b>.\nExample: 123456789012", parse_mode="HTML")
        return  # Stay in state, ask again
    
    # Check if UTR already used
    if is_utr_used(utr):
        await message.answer(
            "⚠️ <b>Payment Verification with Another Order</b>\n\n"
            "This UTR has already been used for a previous order.\n"
            "If you believe this is an error, contact support.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Save UTR to order and notify admin
    data = await state.get_data()
    order_id = data.get("order_id")
    # ... update DB, send admin notification ...
    await state.clear()
```

---

## 17. Key Design Rules

1. **Idempotent code delivery**: Before delivering codes, always check `order_codes` table. If codes already there, return them without re-assigning. This prevents double delivery.

2. **UTR reuse prevention**: Every approved UTR is stored in `used_utrs`. On UTR submission, always check this table first.

3. **Deleted voucher history**: When a voucher is deleted from `vouchers`, only delete its unused `codes`. Do NOT delete `orders` or `order_codes`. Users can still see their old order history and codes.

4. **Multi-admin support**: `ADMIN_IDS` is a list. Notifications go to ALL admin IDs. All admin handlers check `user_id in ADMIN_IDS`.

5. **Order expiry**: A background task or on-demand check expires orders where `expiry_at < now AND status = 'pending'`. Expired orders do not deliver codes.

6. **Stock display**: Always show out-of-stock products with a 😴 sign. Never hide them.

7. **SQLite vs PostgreSQL**: Use `?` placeholders in SQLite, `%s` in PostgreSQL. Use `SERIAL PRIMARY KEY` instead of `INTEGER PRIMARY KEY AUTOINCREMENT` in PostgreSQL.

---

## 18. Deployment: Render + Supabase

### Supabase Setup
1. Go to supabase.com → New Project
2. After creation, go to Settings → Database → Connection String → URI
3. Copy the `postgresql://...` connection string
4. Set it as `DATABASE_URL` in Render environment variables

### Render Setup
1. Go to render.com → New Web Service → Connect GitHub repo
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `python main.py`
4. Environment Variables to set:
   - `BOT_TOKEN`
   - `ADMIN_IDS` (e.g. `123456789`)
   - `UPI_ID`
   - `SHOP_NAME`
   - `BOT_NAME`
   - `ORDER_EXPIRY_MINUTES` = `10`
   - `DATABASE_URL` (from Supabase)
   - `RENDER_EXTERNAL_URL` = `https://your-app-name.onrender.com` (set after first deploy)
5. Free tier: 512MB RAM, sleeps after 15 min inactivity → self-ping prevents this

---

## 19. Message Style Guide

Use this style consistently across all messages:

- **Headers**: `╔════════════════════╗\n  TITLE \n╚════════════════════╝`
- **Sections**: `┌────────────────────┐\n│  SECTION TITLE     │\n└────────────────────┘`
- **Dividers**: `━━━━━━━━━━━━━━━━━━━━`
- **Parse mode**: Always `HTML` (use `<b>bold</b>`, `<code>monospace</code>`, `<i>italic</i>`)
- **No raw Markdown** — always use `parse_mode="HTML"`
- **Code/IDs**: always wrap in `<code>` tags
- **Emojis**: use meaningfully, not decoratively on every line
- **Small caps Unicode**: NOT used (was in old py file) — use normal English text

---

*End of Blueprint — This document is sufficient to build the complete bot.*
