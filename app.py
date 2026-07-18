"""
QR Code Generator
------------------
A Streamlit web app that turns any link (or text) into a clean,
customizable QR code image, ready to preview and download.

Run with:
    streamlit run qr_code_generator_app.py

Dependencies:
    pip install streamlit qrcode pillow
"""

import io
import re
from datetime import datetime

import qrcode
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers import (
    RoundedModuleDrawer,
    SquareModuleDrawer,
    CircleModuleDrawer,
)


# ----------------------------------------------------------------------
# Page configuration
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="QR Code Generator",
    page_icon="🔗",
    layout="centered",
)

BRAND_FOOTER = "Powered by Kailash Chaudhary"


# ----------------------------------------------------------------------
# Font helper (robust across OSes -- see notes below)
# ----------------------------------------------------------------------
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "DejaVuSans.ttf",
]


@st.cache_resource(show_spinner=False)
def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
MODULE_DRAWERS = {
    "Square (classic)": SquareModuleDrawer(),
    "Rounded": RoundedModuleDrawer(),
    "Dots": CircleModuleDrawer(),
}


def normalize_link(raw: str) -> str:
    """Add a https:// scheme if the user forgot one and it looks like a
    bare domain/URL rather than plain text."""
    raw = raw.strip()
    if not raw:
        return raw
    looks_like_url = bool(re.match(r"^[\w\-]+(\.[\w\-]+)+(/.*)?$", raw))
    has_scheme = bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", raw))
    if looks_like_url and not has_scheme:
        return "https://" + raw
    return raw


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def build_qr_image(
    data: str,
    fg_color: str,
    bg_color: str,
    style: str,
    box_size: int,
    logo_bytes: bytes | None,
) -> Image.Image:
    """Generate the styled QR code, optionally with a center logo."""
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # high, so a logo can sit on top
        box_size=box_size,
        border=4,  # standard quiet zone -- keep this to stay scannable
    )
    qr.add_data(data)
    qr.make(fit=True)

    kwargs = dict(
        image_factory=StyledPilImage,
        module_drawer=MODULE_DRAWERS[style],
        color_mask=SolidFillColorMask(
            front_color=hex_to_rgb(fg_color), back_color=hex_to_rgb(bg_color)
        ),
    )

    if logo_bytes:
        logo_buf = io.BytesIO(logo_bytes)
        kwargs["embeded_image_path"] = None
        qr_img = qr.make_image(**{k: v for k, v in kwargs.items() if k != "embeded_image_path"})
        qr_img = qr_img.convert("RGB")
        logo = Image.open(logo_buf).convert("RGBA")

        qr_w, qr_h = qr_img.size
        logo_target = int(qr_w * 0.22)  # keep the logo small enough to stay scannable
        logo.thumbnail((logo_target, logo_target), Image.LANCZOS)

        # White rounded backing behind the logo so it stays legible
        pad = 14
        backing = Image.new(
            "RGBA", (logo.width + pad * 2, logo.height + pad * 2), (255, 255, 255, 255)
        )
        backing.paste(logo, (pad, pad), logo)

        pos = ((qr_w - backing.width) // 2, (qr_h - backing.height) // 2)
        qr_img.paste(backing, pos, backing)
        return qr_img

    qr_img = qr.make_image(**kwargs).convert("RGB")
    return qr_img


def add_branded_frame(qr_img: Image.Image, caption: str, bg_color: str) -> Image.Image:
    """Places the QR code on a clean card with the optional caption on
    top. (No credit/watermark is baked into the downloadable image --
    that only appears in the app's own UI footer.)"""
    margin = 50
    caption_font = load_font(28)

    qr_w, qr_h = qr_img.size

    caption_h = 0
    if caption:
        caption_h = caption_font.getbbox("Ag")[3] + 24

    canvas_w = qr_w + margin * 2
    canvas_h = qr_h + margin * 2 + caption_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), hex_to_rgb(bg_color))
    draw = ImageDraw.Draw(canvas)

    y = margin
    if caption:
        bbox = draw.textbbox((0, 0), caption, font=caption_font)
        cw = bbox[2] - bbox[0]
        draw.text(((canvas_w - cw) // 2, y), caption, font=caption_font, fill=(30, 30, 30))
        y += caption_h

    canvas.paste(qr_img, ((canvas_w - qr_w) // 2, y))

    return canvas


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------
st.title("🔗 QR Code Generator")
st.caption("Turn any link into a clean, downloadable QR code — style it, "
           "brand it, and share it anywhere.")

if "qr_image_bytes" not in st.session_state:
    st.session_state.qr_image_bytes = None
if "qr_preview_img" not in st.session_state:
    st.session_state.qr_preview_img = None

link = st.text_input(
    "Enter Link *",
    placeholder="e.g. https://yourwebsite.com.np",
    help="Paste any URL (or plain text). If you skip https://, it's added automatically.",
)

with st.expander("🎨 Customize appearance", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        fg_color = st.color_picker("QR Color", "#141414")
        style = st.selectbox("Pattern Style", list(MODULE_DRAWERS.keys()), index=1)
    with col2:
        bg_color = st.color_picker("Background Color", "#FFFFFF")
        box_size = st.slider("Resolution (box size)", min_value=6, max_value=16, value=10)

    caption = st.text_input(
        "Caption above QR (optional)",
        placeholder="e.g. Scan to visit my website",
        max_chars=60,
    )

    logo_file = st.file_uploader(
        "Center logo (optional)", type=["png", "jpg", "jpeg"],
        help="A small logo placed in the middle. High error-correction is used "
             "automatically so the code stays scannable.",
    )

generate = st.button("✨ Generate QR Code", use_container_width=True, type="primary")

if generate:
    clean_link = normalize_link(link)
    if not clean_link:
        st.error("⚠️ Please enter a link before generating the QR code.")
        st.session_state.qr_image_bytes = None
        st.session_state.qr_preview_img = None
    else:
        logo_bytes = logo_file.getvalue() if logo_file else None
        qr_img = build_qr_image(
            data=clean_link,
            fg_color=fg_color,
            bg_color=bg_color,
            style=style,
            box_size=box_size,
            logo_bytes=logo_bytes,
        )
        final_img = add_branded_frame(qr_img, caption.strip(), bg_color)

        buf = io.BytesIO()
        final_img.save(buf, format="PNG")  # PNG keeps the QR pattern lossless & scannable
        st.session_state.qr_image_bytes = buf.getvalue()
        st.session_state.qr_preview_img = final_img
        st.success(f"✅ QR code generated for: {clean_link}")

# ----------------------------------------------------------------------
# Preview + Download
# ----------------------------------------------------------------------
st.subheader("Preview")

if st.session_state.qr_image_bytes:
    st.image(st.session_state.qr_image_bytes, use_container_width=False, width=340)

    file_stub = f"qr_code_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "⬇️ Download PNG (recommended)",
            data=st.session_state.qr_image_bytes,
            file_name=f"{file_stub}.png",
            mime="image/png",
            use_container_width=True,
        )
    with dl_col2:
        jpg_buf = io.BytesIO()
        st.session_state.qr_preview_img.convert("RGB").save(jpg_buf, format="JPEG", quality=95)
        st.download_button(
            "⬇️ Download JPG",
            data=jpg_buf.getvalue(),
            file_name=f"{file_stub}.jpg",
            mime="image/jpeg",
            use_container_width=True,
        )
else:
    st.info("Enter a link above and click **Generate QR Code** to see a preview here.")
    st.button("⬇️ Download PNG", disabled=True, use_container_width=True)

st.markdown(
    f"<p style='text-align:center; color:gray; font-size:0.8rem;'>{BRAND_FOOTER}</p>",
    unsafe_allow_html=True,
)
