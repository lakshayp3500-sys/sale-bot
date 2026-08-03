"""qr_generator.py — Generate UPI QR code image with amount label."""

import io
import qrcode
from PIL import Image, ImageDraw, ImageFont


def generate_qr_with_label(upi_link: str, amount: float, shop_name: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_link)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    qr_w, qr_h = qr_img.size
    label_h = 65
    final = Image.new("RGB", (qr_w, qr_h + label_h), "white")
    final.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(final)
    try:
        font_big = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_sm = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        font_big = ImageFont.load_default()
        font_sm = ImageFont.load_default()

    draw.text((qr_w // 2, qr_h + 8),
              f"Pay Exactly: Rs.{amount:.2f}",
              fill="black", font=font_big, anchor="mt")
    draw.text((qr_w // 2, qr_h + 38),
              shop_name,
              fill="gray", font=font_sm, anchor="mt")

    buf = io.BytesIO()
    final.save(buf, format="PNG")
    buf.seek(0)
    return buf
