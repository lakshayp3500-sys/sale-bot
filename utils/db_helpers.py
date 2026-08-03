"""utils/db_helpers.py — All database operations."""

import uuid
from datetime import datetime

from database import get_conn, IS_POSTGRES


# ── USERS ─────────────────────────────────────────────────────────────────────

def register_user(telegram_id: int, username: str, full_name: str) -> bool:
    """Register or update user. Returns True if brand-new user."""
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE users SET username = ?, full_name = ? WHERE telegram_id = ?",
            (username, full_name, telegram_id)
        )
        conn.commit()
        conn.close()
        return False
    conn.execute(
        "INSERT INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)",
        (telegram_id, username, full_name)
    )
    conn.commit()
    conn.close()
    return True


def get_user(telegram_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── VOUCHERS ──────────────────────────────────────────────────────────────────

def get_all_vouchers_with_stock() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT v.id, v.name, v.price, v.disclaimer,
               COUNT(CASE WHEN c.is_used = 0 THEN 1 END) AS stock
        FROM vouchers v
        LEFT JOIN codes c ON c.voucher_id = v.id
        GROUP BY v.id, v.name, v.price, v.disclaimer
        ORDER BY v.created_at ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_voucher(voucher_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("""
        SELECT v.id, v.name, v.price, v.disclaimer,
               COUNT(CASE WHEN c.is_used = 0 THEN 1 END) AS stock
        FROM vouchers v
        LEFT JOIN codes c ON c.voucher_id = v.id
        WHERE v.id = ?
        GROUP BY v.id, v.name, v.price, v.disclaimer
    """, (voucher_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_voucher_stock(voucher_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM codes WHERE voucher_id = ? AND is_used = 0",
        (voucher_id,)
    ).fetchone()
    conn.close()
    return row["c"] if row else 0


def add_voucher(name: str, price: float) -> bool:
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM vouchers WHERE name = ?", (name,)
    ).fetchone()
    if existing:
        conn.close()
        return False
    conn.execute(
        "INSERT INTO vouchers (name, price) VALUES (?, ?)", (name, price)
    )
    conn.commit()
    conn.close()
    return True


def delete_voucher(voucher_id: int):
    conn = get_conn()
    conn.execute(
        "DELETE FROM codes WHERE voucher_id = ? AND is_used = 0", (voucher_id,)
    )
    conn.execute("DELETE FROM vouchers WHERE id = ?", (voucher_id,))
    conn.commit()
    conn.close()


def update_price(voucher_id: int, price: float):
    conn = get_conn()
    conn.execute("UPDATE vouchers SET price = ? WHERE id = ?", (price, voucher_id))
    conn.commit()
    conn.close()


def set_voucher_disclaimer(voucher_id: int, text: str):
    conn = get_conn()
    conn.execute("UPDATE vouchers SET disclaimer = ? WHERE id = ?", (text, voucher_id))
    conn.commit()
    conn.close()


def add_codes_bulk(voucher_id: int, raw_text: str) -> int:
    lines: list[str] = []
    for chunk in raw_text.replace(",", "\n").splitlines():
        chunk = chunk.strip()
        if chunk:
            lines.append(chunk)
    if not lines:
        return 0
    conn = get_conn()
    conn.executemany(
        "INSERT INTO codes (voucher_id, code, is_used) VALUES (?, ?, 0)",
        [(voucher_id, code) for code in lines]
    )
    conn.commit()
    conn.close()
    return len(lines)


def remove_all_codes(voucher_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM codes WHERE voucher_id = ? AND is_used = 0",
        (voucher_id,)
    ).fetchone()
    count = row["c"] if row else 0
    conn.execute("DELETE FROM codes WHERE voucher_id = ? AND is_used = 0", (voucher_id,))
    conn.commit()
    conn.close()
    return count


# ── ORDERS ────────────────────────────────────────────────────────────────────

def get_order(order_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_orders(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_active_order(user_id: int) -> dict | None:
    now = datetime.now()
    conn = get_conn()
    row = conn.execute(
    """SELECT * FROM orders
       WHERE user_id = ?
         AND status = 'pending'
         AND (expiry_at > ? OR utr IS NOT NULL)
       ORDER BY created_at DESC LIMIT 1""",
    (user_id, now)
).fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_orders() -> list[dict]:
    """All pending orders that have a UTR submitted — awaiting admin action."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT o.*, u.username, u.full_name
           FROM orders o
           LEFT JOIN users u ON u.telegram_id = o.user_id
           WHERE o.status = 'pending' AND o.utr IS NOT NULL
           ORDER BY o.created_at ASC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_live_orders() -> list[dict]:
    """All pending orders (with or without UTR)."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT o.*, u.username, u.full_name
           FROM orders o
           LEFT JOIN users u ON u.telegram_id = o.user_id
           WHERE o.status = 'pending'
           ORDER BY o.created_at ASC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_utr(order_id: str, utr: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET utr = ? WHERE id = ?", (utr, order_id))
    conn.commit()
    conn.close()


def cancel_order(order_id: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()


def reject_order(order_id: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()


def get_order_codes(order_id: str) -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT code FROM order_codes WHERE order_id = ?", (order_id,)
    ).fetchall()
    conn.close()
    return [r["code"] for r in rows]


def deliver_codes(order_id: str, voucher_id: int, quantity: int) -> list[str] | None:
    """Idempotent delivery. Returns None if not enough stock."""
    conn = get_conn()
    # Idempotency check
    already = conn.execute(
        "SELECT code FROM order_codes WHERE order_id = ?", (order_id,)
    ).fetchall()
    if already:
        conn.close()
        return [r["code"] for r in already]

    available = conn.execute(
        "SELECT id, code FROM codes WHERE voucher_id = ? AND is_used = 0 LIMIT ?",
        (voucher_id, quantity)
    ).fetchall()

    if len(available) < quantity:
        conn.close()
        return None

    codes: list[str] = []
    for row in available:
        codes.append(row["code"])
        conn.execute(
            "UPDATE codes SET is_used = 1, used_in_order = ? WHERE id = ?",
            (order_id, row["id"])
        )
        conn.execute(
            "INSERT INTO order_codes (order_id, code) VALUES (?, ?)",
            (order_id, row["code"])
        )

    conn.execute(
        "UPDATE orders SET status = 'approved', approved_at = ? WHERE id = ?",
        (datetime.now(), order_id)
    )
    conn.commit()
    conn.close()
    return codes


# ── UTR ───────────────────────────────────────────────────────────────────────

def is_utr_used(utr: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT utr FROM used_utrs WHERE utr = ?", (utr,)).fetchone()
    conn.close()
    return row is not None


def mark_utr_used(utr: str, order_id: str):
    conn = get_conn()
    existing = conn.execute("SELECT utr FROM used_utrs WHERE utr = ?", (utr,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO used_utrs (utr, order_id) VALUES (?, ?)", (utr, order_id)
        )
        conn.commit()
    conn.close()


# ── SETTINGS ──────────────────────────────────────────────────────────────────

def get_setting(key: str) -> str | None:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key: str, value: str):
    conn = get_conn()
    existing = conn.execute("SELECT key FROM settings WHERE key = ?", (key,)).fetchone()
    if existing:
        conn.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    else:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# ── CHANNELS ──────────────────────────────────────────────────────────────────

def get_all_channels() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM channels ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_channel(name: str, link: str):
    conn = get_conn()
    conn.execute("INSERT INTO channels (name, link) VALUES (?, ?)", (name, link))
    conn.commit()
    conn.close()


def remove_channel(channel_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()


# ── STATS ─────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    conn = get_conn()
    if IS_POSTGRES:
        today_row = conn.execute("""
            SELECT COALESCE(SUM(total_price),0) AS revenue, COUNT(*) AS orders
            FROM orders WHERE status='approved' AND approved_at::date = CURRENT_DATE
        """).fetchone()
        new_users_row = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE joined_at::date = CURRENT_DATE"
        ).fetchone()
    else:
        today_row = conn.execute("""
            SELECT COALESCE(SUM(total_price),0) AS revenue, COUNT(*) AS orders
            FROM orders WHERE status='approved' AND DATE(approved_at)=DATE('now')
        """).fetchone()
        new_users_row = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE DATE(joined_at)=DATE('now')"
        ).fetchone()

    total_users   = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
    total_orders  = conn.execute("SELECT COUNT(*) AS c FROM orders WHERE status='approved'").fetchone()
    total_rev     = conn.execute("SELECT COALESCE(SUM(total_price),0) AS r FROM orders WHERE status='approved'").fetchone()
    pending       = conn.execute("SELECT COUNT(*) AS c FROM orders WHERE status='pending'").fetchone()
    rejected      = conn.execute("SELECT COUNT(*) AS c FROM orders WHERE status='rejected'").fetchone()
    expired       = conn.execute("SELECT COUNT(*) AS c FROM orders WHERE status='expired'").fetchone()
    in_stock      = conn.execute("""
        SELECT COUNT(DISTINCT v.id) AS c FROM vouchers v
        WHERE (SELECT COUNT(*) FROM codes WHERE voucher_id=v.id AND is_used=0) > 0
    """).fetchone()
    out_stock     = conn.execute("""
        SELECT COUNT(DISTINCT v.id) AS c FROM vouchers v
        WHERE (SELECT COUNT(*) FROM codes WHERE voucher_id=v.id AND is_used=0) = 0
    """).fetchone()
    conn.close()

    return {
        "today_earnings":  today_row["revenue"] if today_row else 0,
        "today_orders":    today_row["orders"]  if today_row else 0,
        "today_new_users": new_users_row["c"]   if new_users_row else 0,
        "total_users":     total_users["c"]     if total_users else 0,
        "total_orders":    total_orders["c"]    if total_orders else 0,
        "total_revenue":   total_rev["r"]       if total_rev else 0,
        "pending_orders":  pending["c"]         if pending else 0,
        "rejected_orders": rejected["c"]        if rejected else 0,
        "expired_orders":  expired["c"]         if expired else 0,
        "in_stock":        in_stock["c"]        if in_stock else 0,
        "out_of_stock":    out_stock["c"]       if out_stock else 0,
    }


# ── TICKETS ───────────────────────────────────────────────────────────────────

def create_ticket(user_id: int, username: str, full_name: str,
                  category: str, message: str) -> str:
    ticket_id = "TKT-" + uuid.uuid4().hex.upper()[:8]
    conn = get_conn()
    conn.execute(
        "INSERT INTO tickets (id, user_id, username, full_name, category, message) VALUES (?,?,?,?,?,?)",
        (ticket_id, user_id, username, full_name, category, message)
    )
    conn.commit()
    conn.close()
    return ticket_id


def get_ticket(ticket_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_tickets(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_open_tickets() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tickets WHERE status='open' ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ticket_replies(ticket_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM ticket_replies WHERE ticket_id = ? ORDER BY created_at ASC",
        (ticket_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_ticket_reply(ticket_id: str, message: str, from_admin: bool = False):
    conn = get_conn()
    conn.execute(
        "INSERT INTO ticket_replies (ticket_id, from_admin, message) VALUES (?,?,?)",
        (ticket_id, 1 if from_admin else 0, message)
    )
    conn.commit()
    conn.close()


def close_ticket(ticket_id: str):
    conn = get_conn()
    conn.execute("UPDATE tickets SET status='closed' WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()
