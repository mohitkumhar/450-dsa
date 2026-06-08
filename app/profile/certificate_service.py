import io
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont


def _load_fonts():
    try:
        return {
            "title": ImageFont.truetype("arialbd.ttf", 56),
            "subtitle": ImageFont.truetype("arial.ttf", 28),
            "name": ImageFont.truetype("arialbd.ttf", 48),
            "detail": ImageFont.truetype("arial.ttf", 26),
        }
    except IOError:
        try:
            return {
                "title": ImageFont.truetype("DejaVuSans-Bold.ttf", 56),
                "subtitle": ImageFont.truetype("DejaVuSans.ttf", 28),
                "name": ImageFont.truetype("DejaVuSans-Bold.ttf", 48),
                "detail": ImageFont.truetype("DejaVuSans.ttf", 26),
            }
        except IOError:
            default = ImageFont.load_default()
            return {
                "title": default,
                "subtitle": default,
                "name": default,
                "detail": default,
            }


def _center_text(draw, text, font, y, width, fill):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
    except Exception:
        text_width = draw.textsize(text, font=font)[0]
    x = (width - text_width) / 2
    draw.text((x, y), text, font=font, fill=fill)


def generate_milestone_certificate(name, milestone_label, awarded_on=None):
    width, height = 1200, 850
    bg_color = (248, 247, 244)
    border_color = (34, 34, 34)
    accent = (245, 158, 11)
    text_color = (20, 20, 20)

    card = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(card)
    fonts = _load_fonts()

    # Border
    draw.rectangle([(30, 30), (width - 30, height - 30)], outline=border_color, width=3)

    title = "Certificate of Achievement"
    subtitle = "Presented to"
    display_name = (name or "Anonymous").strip() or "Anonymous"
    if len(display_name) > 30:
        display_name = display_name[:27] + "..."

    _center_text(draw, title, fonts["title"], 110, width, text_color)
    _center_text(draw, subtitle, fonts["subtitle"], 220, width, text_color)
    _center_text(draw, display_name, fonts["name"], 270, width, accent)

    detail = f"For completing the milestone: {milestone_label}"
    _center_text(draw, detail, fonts["detail"], 370, width, text_color)

    awarded_on = awarded_on or datetime.utcnow().date().isoformat()
    _center_text(draw, f"Awarded on {awarded_on}", fonts["detail"], 440, width, text_color)

    _center_text(draw, "450 DSA Tracker", fonts["subtitle"], 640, width, text_color)

    img_io = io.BytesIO()
    card.save(img_io, "PNG")
    img_io.seek(0)
    return img_io
