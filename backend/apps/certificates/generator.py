"""
Certificate image generator using Pillow.

Renders personalized text (student name, course details, dates, certificate
number) over an uploaded template background image.

Design decisions:
- Masks the template's existing placeholder text and separator line before
  drawing dynamic content, so no artefacts bleed through.
- Layout uses absolute pixel positions derived from the actual template
  dimensions (1414 x 2000 for the OneSmarter portrait template) with a
  proportional fallback for other template sizes.
- Text positions are measured using Pillow's textbbox so every region
  knows its exact height before the next region is placed.
- Long student / course names are handled by auto-shrinking font size;
  the paragraph is word-wrapped to the available width.
- Returns raw PNG bytes + SHA-256 hash.
"""

import hashlib
import io
import logging

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

_BOLD_CANDIDATES = [
    "arialbd.ttf",
    "Arial Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
    "FreeSansBold.ttf",
]

_REGULAR_CANDIDATES = [
    "arial.ttf",
    "Arial.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "FreeSans.ttf",
]


def _try_load_font(candidates: list[str], size: int):
    """Attempt to load the first available font from *candidates*."""
    for name in candidates:
        cache_key = (name, size)
        if cache_key in _FONT_CACHE:
            return _FONT_CACHE[cache_key]
        try:
            font = ImageFont.truetype(name, size)
            _FONT_CACHE[cache_key] = font
            return font
        except (OSError, IOError):
            continue
    return None


def _get_font(size: int, bold: bool = False):
    """Return the best available font at *size*."""
    if bold:
        font = _try_load_font(_BOLD_CANDIDATES, size)
        if font:
            return font
    font = _try_load_font(_REGULAR_CANDIDATES, size)
    if font:
        return font
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Text measurement helpers
# ---------------------------------------------------------------------------

def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _text_height(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font,
    fill,
    img_width: int,
) -> None:
    """Draw *text* centred horizontally at vertical position *y*."""
    tw = _text_width(draw, text, font)
    x = (img_width - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list:
    """Word-wrap *text* so that every line fits within *max_width* pixels."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------

def _fmt_date(d) -> str:
    """Return *d* formatted as DD/MM/YYYY regardless of its input type."""
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    s = str(d).strip()
    # Accept YYYY-MM-DD ISO strings
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        parts = s.split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return s


# ---------------------------------------------------------------------------
# Layout configuration
# ---------------------------------------------------------------------------

def _portrait_layout(w: int, h: int) -> dict:
    """
    Return pixel-coordinate layout for a portrait template (e.g. 1414x2000).

    These values are tuned for the OneSmarter Red & Gold template.
    The template has:
      - "For Honorable Achievement To" gold heading ending at y~758
      - Placeholder dark-red cursive student name from y~855 to y~1030
      - Dark-red separator/underline at y~1037-1047
      - Decorative gold side elements from y~1125-1280
      - Signature blocks starting at y~1456
    """
    return {
        # Usable horizontal bounds (inside ribbons / decorations)
        "left_margin":  int(w * 0.106),   # x ~ 150
        "right_margin": int(w * 0.894),   # x ~ 1264

        # Student name: just below the gold achievement heading
        "name_y":       int(h * 0.412),   # y ~ 824

        # Paragraph: well below the masked placeholder area and separator
        "para_top":     int(h * 0.540),   # y ~ 1080

        # Metadata row minimum y (cert ID + issue date)
        "meta_top":     int(h * 0.660),   # y ~ 1320

        # Top of signature area — nothing dynamic goes here or below
        "sig_top":      int(h * 0.728),   # y ~ 1456

        # Rectangle to blank-out the template's placeholder text + line.
        # Covers: dark-red cursive name placeholder, decorative strokes,
        # and the horizontal separator line at y~1040.
        # x: 150..1050  y: 855..1055
        "mask_rect":    (
            int(w * 0.106),   # x0 ~ 150
            int(h * 0.427),   # y0 ~ 854
            int(w * 0.743),   # x1 ~ 1050
            int(h * 0.528),   # y1 ~ 1056
        ),

        # Background fill colour (sampled from template body ≈ 250,250,250)
        "bg_color": (250, 250, 250),
    }


def _landscape_layout(w: int, h: int) -> dict:
    """Generic layout for landscape or square templates."""
    return {
        "left_margin":  int(w * 0.10),
        "right_margin": int(w * 0.90),
        "name_y":       int(h * 0.40),
        "para_top":     int(h * 0.52),
        "meta_top":     int(h * 0.72),
        "sig_top":      int(h * 0.85),
        "mask_rect":    None,
        "bg_color":     (255, 255, 255),
    }


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_certificate_image(
    template_path: str,
    student_name: str,
    course_name: str,
    start_date: str,
    end_date: str,
    issue_date: str,
    certificate_number: str,
    issuer_name: str = "OneSmarter, Inc.",
    completion_description: str = "",
    layout_overrides: dict | None = None,
    output_format: str = "PNG",
) -> tuple:
    """
    Generate a personalized certificate image.

    Args:
        template_path:          Absolute path to the template background image or PDF.
        student_name:           Full name of the student (1–29 characters).
        course_name:            Name of the course completed.
        start_date:             Course start date (date object or DD/MM/YYYY string).
        end_date:               Course end date (date object or DD/MM/YYYY string).
        issue_date:             Certificate issue date (date object or DD/MM/YYYY string).
        certificate_number:     Unique certificate identifier (the saved DB value).
        issuer_name:            Organisation name.
        completion_description: Optional custom text supporting {{student_name}}, {{course_name}}, etc.
        layout_overrides:       Optional dict with coordinate overrides.
        output_format:          Target format: "PNG", "JPEG" / "JPG", or "PDF".

    Returns:
        (file_bytes, sha256_hex) — the generated certificate in requested format and its hash.
    """
    # ------------------------------------------------------------------
    # 1. Load template (supports PNG, JPG/JPEG, and PDF)
    # ------------------------------------------------------------------
    if str(template_path).lower().endswith(".pdf"):
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(template_path)
            page = pdf[0]
            # Render at 200 dpi (200 / 72.0 scale) for crisp vector reproduction
            scale = 200 / 72.0
            img = page.render(scale=scale).to_pil().convert("RGBA")
        except Exception as exc:
            logger.warning("pypdfium2 failed to render PDF template %s: %s", template_path, exc)
            img = Image.open(template_path).convert("RGBA")
    else:
        img = Image.open(template_path).convert("RGBA")

    w, h = img.size

    # Choose layout: portrait when height >= 1.2 x width
    if h >= w * 1.2:
        layout = _portrait_layout(w, h)
    else:
        layout = _landscape_layout(w, h)

    if layout_overrides and isinstance(layout_overrides, dict):
        layout.update(layout_overrides)

    left_x         = layout["left_margin"]
    right_x        = layout["right_margin"]
    sig_top        = layout["sig_top"]
    bg_color       = layout["bg_color"]
    max_text_width = right_x - left_x

    # ------------------------------------------------------------------
    # 2. Format dates strictly as DD/MM/YYYY
    # ------------------------------------------------------------------
    start_disp = _fmt_date(start_date)
    end_disp   = _fmt_date(end_date)
    issue_disp = _fmt_date(issue_date)

    # ------------------------------------------------------------------
    # 3. Build paragraph & resolve all dynamic placeholders
    # ------------------------------------------------------------------
    student_name = (student_name or "").strip()
    course_name = (course_name or "").strip()
    certificate_number = (certificate_number or "").strip()

    context = {
        "student_name": student_name,
        "course_name": course_name,
        "start_date": start_disp,
        "end_date": end_disp,
        "issue_date": issue_disp,
        "certificate_number": certificate_number,
        "issuer": issuer_name,
        "issuer_name": issuer_name,
    }

    if completion_description and completion_description.strip():
        paragraph = completion_description.strip()
        for k, v in context.items():
            paragraph = paragraph.replace(f"{{{{{k}}}}}", str(v))
            paragraph = paragraph.replace(f"{{{k}}}", str(v))
    else:
        paragraph = (
            f""
        )

    # ------------------------------------------------------------------
    # 4. Mask template placeholder text and separator line
    # ------------------------------------------------------------------
    draw = ImageDraw.Draw(img)

    if layout.get("mask_rect") is not None:
        mx0, my0, mx1, my1 = layout["mask_rect"]
        draw.rectangle([mx0, my0, mx1, my1], fill=bg_color + (255,))

    # ------------------------------------------------------------------
    # 5. Choose font sizes
    # ------------------------------------------------------------------
    base = min(w, h)

    # Student name: start at comfortable size, shrink until fits max_text_width
    name_font_size = max(int(base * 0.050), 30)
    while name_font_size > 18:
        nf = _get_font(name_font_size, bold=True)
        if _text_width(draw, student_name, nf) <= max_text_width:
            break
        name_font_size -= 2
    name_font = _get_font(name_font_size, bold=True)

    # Paragraph: readable but not oversized
    para_size = max(int(base * 0.021), 18)
    para_font = _get_font(para_size, bold=False)

    # Metadata: slightly smaller than paragraph
    detail_size = max(int(base * 0.018), 14)
    detail_font = _get_font(detail_size, bold=False)

    # ------------------------------------------------------------------
    # 6. Colours
    # ------------------------------------------------------------------
    name_color   = (30,  30,  30)    # Near-black — professional
    para_color   = (50,  50,  50)    # Dark grey for body text
    detail_color = (60,  60,  60)    # Slightly lighter for metadata

    # ------------------------------------------------------------------
    # 7. Draw student name (centred, bold) and bold underline
    # ------------------------------------------------------------------
    name_y  = layout["name_y"]
    name_h  = _text_height(draw, student_name, name_font)
    name_tw = _text_width(draw, student_name, name_font)
    name_bb = draw.textbbox((0, 0), student_name, font=name_font)
    name_draw_y = name_y - name_bb[1]
    _draw_centered(draw, student_name, name_draw_y, name_font, name_color, w)

    # Draw bold, clearly visible underline centered directly beneath name
    underline_tw = name_tw + max(16, int(name_font_size * 0.18))
    underline_x0 = (w - underline_tw) // 2
    underline_x1 = underline_x0 + underline_tw
    underline_thickness = max(3, int(name_font_size * 0.06))
    underline_y = name_draw_y + name_bb[3] + max(6, int(name_font_size * 0.12))
    draw.rectangle(
        [underline_x0, underline_y, underline_x1, underline_y + underline_thickness],
        fill=name_color,
    )

    # Track vertical cursor below the underline
    current_y = underline_y + underline_thickness

    # ------------------------------------------------------------------
    # 8. Draw completion paragraph (wrapped, centred)
    # ------------------------------------------------------------------
    para_gap          = int(h * 0.025)
    para_line_spacing = max(4, int(para_size * 0.40))

    # Never start paragraph before layout.para_top
    para_start_y = max(current_y + para_gap, layout["para_top"])

    wrapped_lines = _wrap_text(paragraph, para_font, max_text_width, draw)

    line_h       = _text_height(draw, "Ay", para_font)
    total_para_h = len(wrapped_lines) * (line_h + para_line_spacing)
    meta_h       = _text_height(draw, "Ag", detail_font)
    meta_gap     = int(h * 0.028)

    # If paragraph + metadata would overflow into signature area, compress
    needed = para_start_y + total_para_h + meta_gap + meta_h
    if needed > sig_top - int(h * 0.01):
        para_line_spacing = max(2, para_line_spacing - 4)
        meta_gap          = max(int(h * 0.012), meta_gap - int(h * 0.010))
        total_para_h      = len(wrapped_lines) * (line_h + para_line_spacing)

    py = para_start_y
    for line in wrapped_lines:
        _draw_centered(draw, line, py, para_font, para_color, w)
        py += line_h + para_line_spacing
    para_end_y = py

    # ------------------------------------------------------------------
    # 9. Draw Certificate ID and Issue Date (metadata row above signatures)
    # ------------------------------------------------------------------
    meta_y = max(para_end_y + meta_gap, layout["meta_top"])
    meta_y = min(meta_y, sig_top - meta_h - int(h * 0.015))

    cert_text = f"Certificate ID: {certificate_number}"
    date_text = f"Issue Date: {issue_disp}"

    draw.text((left_x, meta_y), cert_text, font=detail_font, fill=detail_color)
    date_tw = _text_width(draw, date_text, detail_font)
    draw.text((right_x - date_tw, meta_y), date_text, font=detail_font, fill=detail_color)

    # ------------------------------------------------------------------
    # 10. Serialise in requested format (PNG, JPEG, or PDF)
    # ------------------------------------------------------------------
    output_img = Image.new("RGB", img.size, (255, 255, 255))
    if img.mode == "RGBA":
        output_img.paste(img, mask=img.split()[3])
    else:
        output_img.paste(img)

    buffer = io.BytesIO()
    fmt = output_format.upper()
    if fmt in ("JPEG", "JPG"):
        output_img.save(buffer, format="JPEG", quality=95)
    elif fmt == "PDF":
        output_img.save(buffer, format="PDF", resolution=150)
    else:
        output_img.save(buffer, format="PNG", optimize=True)

    result_bytes = buffer.getvalue()
    sha256 = hashlib.sha256(result_bytes).hexdigest()

    logger.info(
        "Generated certificate for %s — %s (%d bytes, fmt=%s, sha256=%.12s)",
        student_name,
        certificate_number,
        len(result_bytes),
        fmt,
        sha256,
    )

    return result_bytes, sha256


def convert_certificate_image_to_formats(png_bytes: bytes) -> dict[str, bytes]:
    """
    Produce PNG, JPEG, and PDF bytes from the same generated certificate raster.
    Ensures 100% visual identity across all output formats.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")

    # JPEG
    jpg_buf = io.BytesIO()
    img.save(jpg_buf, format="JPEG", quality=95)

    # PDF
    pdf_buf = io.BytesIO()
    img.save(pdf_buf, format="PDF", resolution=150)

    return {
        "png": png_bytes,
        "jpeg": jpg_buf.getvalue(),
        "pdf": pdf_buf.getvalue(),
    }



# ---------------------------------------------------------------------------
# Certificate number generator
# ---------------------------------------------------------------------------

def generate_certificate_number(prefix: str = "OSCV") -> str:
    """
    Generate a unique certificate number.

    Format: OSCV-YYYY-XXXXXXXX  (X = random upper-case hex)
    """
    import secrets
    from django.utils import timezone

    now  = timezone.now()
    year = now.strftime("%Y")
    rand = secrets.token_hex(4).upper()
    return f"{prefix}-{year}-{rand}"

