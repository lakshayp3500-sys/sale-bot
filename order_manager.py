"""order_manager.py — Order lifecycle: create, fetch, expire."""

import uuid
from datetime import datetime, timedelta

from database import get_conn, IS_POSTGRES


def create_order(user_id: int, voucher_id: int, voucher_name: str,
                 quantity: int, total_price: float, expiry_minutes: int = 10) -> str:
    order_id = uuid.uuid4().hex.upper()[:12]
    now = datetime.now()
    expiry_at = now + timedelta(minutes=expiry_minutes)
    conn = get_conn()
    conn.execute(
        """INSERT INTO orders
           (id, user_id, voucher_id, voucher_name, quantity, total_price,
            status, created_at, expiry_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (order_id, user_id, voucher_id, voucher_name,
         quantity, total_price, now, expiry_at)
    )
    conn.commit()
    conn.close()
    return order_id


def get_order_by_id(order_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def expire_orders() -> list[dict]:
    """Mark all expired pending orders and return list of expired ones."""
    now = datetime.now()
    conn = get_conn()
    rows = conn.execute(
    """
    SELECT * FROM orders
    WHERE status = 'pending'
      AND utr IS NULL
      AND expiry_at <= ?
    """,
    (now,)
).fetchall()
    expired = [dict(r) for r in rows]
    if expired:
        ids = tuple(r["id"] for r in expired)
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE orders SET status = 'expired' WHERE id IN ({placeholders})", ids
        )
        conn.commit()
    conn.close()
    return expired
