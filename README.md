# Sale Bot 🛒

Premium Telegram Voucher Selling Bot — **Manual UTR payment verification**, full admin panel, support tickets, broadcast, and more.

## Features

| Category | Details |
|---|---|
| 💳 Payments | UPI QR code generation, manual 12-digit UTR submission, duplicate UTR detection |
| 📦 Orders | Create, approve, reject, expire; full order history preserved even after voucher deletion |
| 🔐 Admin Panel | Stock manager, add vouchers/codes, set price, set disclaimer, pending requests, live orders, broadcast, channel manager, stats, support tickets, `/order`, `/info` commands |
| 🆘 Support | Categorised ticket system with admin reply & close; user ticket history |
| 🔔 Notifications | Real-time alerts to all admins for new users, payment requests, and tickets |
| ♾️ Self-ping | Pings itself every 5 min to stay awake on Render free tier |

---

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/lakshayp3500-sys/sale-bot.git
cd sale-bot
pip install -r requirements.txt
```

### 2. Environment Variables

Copy `.env.example` to `.env` and fill in:

```
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789          # comma-separated for multiple admins
UPI_ID=yourname@upi
SHOP_NAME=MyVoucherStore
BOT_NAME=VoucherBot
DATABASE_URL=postgresql://...  # leave blank for local SQLite
PORT=8000
RENDER_EXTERNAL_URL=https://your-app.onrender.com
ORDER_EXPIRY_MINUTES=10
```

### 3. Run

```bash
python main.py
```

---

## Deployment on Render (Free Tier)

1. Create a new **Web Service** on [render.com](https://render.com)
2. Connect this GitHub repo
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `python main.py`
5. Set all env vars in Render dashboard (see above)
6. Add `RENDER_EXTERNAL_URL` = your Render app URL
7. The bot self-pings every 5 min to prevent sleep

---

## Admin Panel Buttons

```
📦 Stock Manager   ➕ Add Voucher
🔑 Add Codes       💰 Set Price
📋 Pending Requests   📢 Broadcast
📊 Stats           📺 Channels
📝 Live Orders     🎫 Tickets
📖 More Commands
🏠 Main Menu
```

### Slash Commands (admin only)
| Command | Description |
|---|---|
| `/admin` | Open admin panel |
| `/order ORDER_ID` | Full order detail — buyer, UTR, codes, status |
| `/info USER_ID` | User profile + full order history + total spent |
| `/stats` | Quick stats |
| `/pending` | List pending payment requests |
| `/broadcast` | Broadcast message to all users |
| `/add` | Add new voucher (guided) |
| `/del VOUCHER_ID` | Delete voucher |
| `/setprice VOUCHER_ID PRICE` | Update voucher price |
| `/setdisclaimer VOUCHER_ID TEXT` | Set terms & conditions |

---

## Tech Stack

- **Python 3.11**
- **aiogram 3.x** — Telegram bot framework
- **aiohttp** — Async web server (ping endpoint)
- **SQLite** (dev) / **PostgreSQL** (production via Supabase)
- **qrcode + Pillow** — UPI QR generation
- **Render** — Free tier hosting
