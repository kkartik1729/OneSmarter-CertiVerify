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
import re

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


def _get_font(size: int, bold: bool = False, family: str = "Arial"):
    """Load the requested family; missing family files fall back to Arial candidates, then Pillow's built-in font."""
    family_candidates = {
        "Arial": (_BOLD_CANDIDATES, _REGULAR_CANDIDATES),
        "DejaVu Sans": (["DejaVuSans-Bold.ttf", *_BOLD_CANDIDATES], ["DejaVuSans.ttf", *_REGULAR_CANDIDATES]),
        "Serif": (["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf", *_BOLD_CANDIDATES], ["DejaVuSerif.ttf", "LiberationSerif-Regular.ttf", *_REGULAR_CANDIDATES]),
        "Monospace": (["DejaVuSansMono-Bold.ttf"], ["DejaVuSansMono.ttf", *_REGULAR_CANDIDATES]),
    }
    bold_candidates, regular_candidates = family_candidates.get(family, family_candidates["Arial"])
    if bold:
        font = _try_load_font(bold_candidates, size)
        if font:
            return font
    font = _try_load_font(regular_candidates, size)
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


def load_template_image(template_path: str) -> Image.Image:
    """Decode a template once so bulk generation can reuse its pristine background."""
    from PIL import ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    if str(template_path).lower().endswith(".pdf"):
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(template_path)
            try:
                return pdf[0].render(scale=200 / 72.0).to_pil().convert("RGBA")
            finally:
                pdf.close()
        except Exception as exc:
            logger.warning("pypdfium2 failed to render PDF template %s: %s", template_path, exc)
            return Image.open(template_path).convert("RGBA")
    with Image.open(template_path) as source:
        source.load()
        return source.convert("RGBA")


# ---------------------------------------------------------------------------
# Layout configuration & coordinate resolution
# ---------------------------------------------------------------------------

def _resolve_coord(val, total: int, fallback_ratio: float) -> int:
    """
    Resolve a layout coordinate to absolute pixels.
    Supports:
    - None -> total * fallback_ratio
    - float between 0.0 and 1.0 -> total * val
    - percentage string (e.g. '45%') -> total * 0.45
    - int or float > 1.0 -> absolute pixels, bounded within [0, total]
    """
    if val is None:
        return int(total * fallback_ratio)
    if isinstance(val, str):
        s = val.strip().rstrip("%")
        try:
            f = float(s)
            if "%" in val:
                return int(total * (f / 100.0))
            if 0.0 < f < 1.0:
                return int(total * f)
            return min(max(0, int(f)), total)
        except ValueError:
            return int(total * fallback_ratio)
    if isinstance(val, (int, float)):
        if 0.0 < val < 1.0:
            return int(total * val)
        return min(max(0, int(val)), total)
    return int(total * fallback_ratio)


def _portrait_layout(w: int, h: int) -> dict:
    """
    Proportional layout for portrait templates (height > width).
    Calculated relative to actual template dimensions for universal scaling.
    """
    return {
        "left_margin":    int(w * 0.09),
        "right_margin":   int(w * 0.91),
        "name_y":         int(h * 0.43),
        "name_align":     "center",
        "name_color":     (30, 30, 30),
        "draw_underline": False,
        "para_top":       int(h * 0.53),
        "para_color":     (50, 50, 50),
        "meta_top":       int(h * 0.69),
        "meta_color":     (60, 60, 60),
        "sig_top":        int(h * 0.80),
        "mask_rect":      None,
        "bg_color":       (250, 250, 250),
    }


def _landscape_layout(w: int, h: int) -> dict:
    """
    Proportional layout for landscape and square templates.
    Places the recipient's name in the designated focal band (45% of height)
    so it does not overwrite the certificate header or decorative banners.
    """
    return {
        "left_margin":    int(w * 0.08),
        "right_margin":   int(w * 0.92),
        "name_y":         int(h * 0.45),
        "name_align":     "center",
        "name_color":     (30, 30, 30),
        "draw_underline": False,
        "para_top":       int(h * 0.54),
        "para_color":     (50, 50, 50),
        "meta_top":       int(h * 0.72),
        "meta_color":     (60, 60, 60),
        "sig_top":        int(h * 0.84),
        "mask_rect":      None,
        "bg_color":       (255, 255, 255),
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
    template_image: Image.Image | None = None,
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
                                If empty, no description is rendered, preserving pre-printed template text.
        layout_overrides:       Optional dict with coordinate overrides or layout_config.
        output_format:          Target format: "PNG", "JPEG" / "JPG", or "PDF".

    Returns:
        (file_bytes, sha256_hex) — the generated certificate in requested format and its hash.
    """
    from PIL import ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    # ------------------------------------------------------------------
    # 1. Load template (supports PNG, JPG/JPEG, and PDF)
    # ------------------------------------------------------------------
    img = template_image.copy() if template_image is not None else load_template_image(template_path)

    w, h = img.size

    # Choose layout: portrait when height >= 1.15 x width, landscape otherwise
    if h >= w * 1.15:
        layout = _portrait_layout(w, h)
    else:
        layout = _landscape_layout(w, h)

    if layout_overrides and isinstance(layout_overrides, dict):
        layout.update(layout_overrides)

    left_x         = layout.get("left_margin", int(w * 0.10))
    right_x        = layout.get("right_margin", int(w * 0.90))
    sig_top        = layout.get("sig_top", int(h * 0.80))
    bg_color       = layout.get("bg_color", (255, 255, 255))
    max_text_width = max(100, right_x - left_x)

    # ------------------------------------------------------------------
    # 2. Format dates strictly as DD/MM/YYYY
    # ------------------------------------------------------------------
    start_disp = _fmt_date(start_date)
    end_disp   = _fmt_date(end_date)
    issue_disp = _fmt_date(issue_date)

    # ------------------------------------------------------------------
    # 3. Build paragraph & resolve all dynamic placeholders (if provided)
    # ------------------------------------------------------------------
    student_name = (student_name or "").strip()
    course_name = (course_name or "").strip()
    certificate_number = (certificate_number or "").strip()

    saved_field_values = layout.get("field_values", {}) or {}
    saved_course_description = saved_field_values.get("course_description", "")
    resolved_course_description = (completion_description or "").strip() or (
        "" if saved_course_description is None else str(saved_course_description).strip()
    )
    if resolved_course_description.lower() in {"none", "null"}:
        resolved_course_description = ""
    elif re.search(r"\{\{\s*[A-Za-z_][A-Za-z0-9_]*\s*\}\}", resolved_course_description):
        # A configured paragraph template is not itself the resolved course description.
        resolved_course_description = ""

    context = {
        "recipient_name": student_name,
        "certificate_id": certificate_number,
        "student_name": student_name,
        "course_name": course_name,
        "start_date": start_disp,
        "end_date": end_disp,
        "issue_date": issue_disp,
        "course_description": resolved_course_description,
        "completion_description": resolved_course_description,
        "certificate_number": certificate_number,
        "issuer": issuer_name,
        "issuer_name": issuer_name,
    }
    # Template editor objects are stored per-template in layout_config. Coordinates
    # are normalized (0..1) so a saved layout works at any source resolution.
    # Only literal placeholders are resolved; no expressions are evaluated.
    reserved_fields = set(context)
    for field_key, value in (layout.get("field_values", {}) or {}).items():
        if isinstance(field_key, str) and field_key.replace("_", "").isalnum():
            if field_key in reserved_fields:
                continue
            safe_value = "" if value is None else str(value)
            context[field_key] = "" if safe_value.strip().lower() in {"none", "null"} else safe_value

    paragraph = ""
    if completion_description and completion_description.strip():
        paragraph = completion_description.strip()
        def resolve_paragraph(match):
            key = match.group(1) or match.group(2)
            # Recipient names belong in explicit editor layers or the legacy
            # primary-name position, never both that position and a description.
            if key in {"recipient_name", "student_name"}:
                return ""
            value = context.get(key, "")
            value = "" if value is None else str(value)
            return "" if value.strip().lower() in {"none", "null"} else value
        paragraph = re.sub(
            r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}",
            resolve_paragraph,
            paragraph,
        )

    # ------------------------------------------------------------------
    # 4. Optional template masking (ONLY if explicitly configured)
    # ------------------------------------------------------------------
    draw = ImageDraw.Draw(img)

    elements = [element for element in (layout.get("elements", []) or []) if isinstance(element, dict)]
    # A localized cover is reversible: the source template is untouched and the
    # replacement region is persisted as part of this template's layout.
    for cover in layout.get("redactions", []) or []:
        if not isinstance(cover, dict):
            continue
        def cover_coord(key, axis_size):
            raw = cover.get(key, 0)
            if isinstance(raw, (int, float)) and 0 <= raw <= 1:
                return int(raw * axis_size)
            return int(raw) if isinstance(raw, (int, float)) else 0
        x0 = cover_coord("x", w)
        y0 = cover_coord("y", h)
        x1 = x0 + cover_coord("width", w)
        y1 = y0 + cover_coord("height", h)
        draw.rectangle([x0, y0, x1, y1], fill=cover.get("color", "#ffffff"))

    normalized_fields = set()
    for element in elements:
        text_value = str(element.get("text", ""))
        normalized_fields.update(re.findall(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", text_value))
        if text_value.strip().casefold() in {"certificate_id", "certificate_number"}:
            normalized_fields.add(text_value.strip().casefold())

    if layout.get("mask_rect"):
        mx0, my0, mx1, my1 = layout["mask_rect"]
        draw.rectangle([mx0, my0, mx1, my1], fill=bg_color + (255,))

    certificate_id_layer_rendered = False
    for element in elements:
        if not isinstance(element, dict) or element.get("type", "text") != "text":
            continue
        value = element.get("text", "")
        if not isinstance(value, str):
            continue
        has_certificate_id = bool(re.search(
            r"\{\{\s*(?:certificate_id|certificate_number)\s*\}\}", value, re.IGNORECASE
        )) or value.strip().casefold() in {"certificate_id", "certificate_number"}
        if has_certificate_id:
            # A template must show one identifier layer, even if an older saved
            # layout accidentally contains the field more than once.
            if certificate_id_layer_rendered:
                continue
            certificate_id_layer_rendered = True
        text_value = re.sub(
            r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}",
            lambda match: context.get(match.group(1), ""),
            value,
        )
        if text_value.strip().casefold() in {"certificate_id", "certificate_number"}:
            # Support older layouts that stored the field name without braces.
            text_value = certificate_number
        if has_certificate_id:
            id_value = re.sub(r"Certificate\s+ID\s*:\s*", "", text_value, flags=re.IGNORECASE).strip()
            text_value = f"Certificate ID: {id_value}"
        if not text_value:
            continue
        def coord(key, fallback):
            raw = element.get(key, fallback)
            if isinstance(raw, (int, float)) and 0 <= raw <= 1:
                return int(raw * (w if key in ("x", "width") else h))
            return int(raw) if isinstance(raw, (int, float)) else fallback
        x, y = coord("x", int(w * .2)), coord("y", int(h * .5))
        box_w = max(1, coord("width", int(w * .6)))
        size = max(6, min(300, int(element.get("fontSize", max(14, min(w, h) * .03)))))
        font = _get_font(size, bold=bool(element.get("bold", False)), family=element.get("fontFamily", "Arial"))
        color = element.get("color", "#202020")
        lines = []
        for paragraph_line in text_value.splitlines() or [""]:
            words = paragraph_line.split()
            line = ""
            for word in words:
                candidate = f"{line} {word}".strip()
                if line and _text_width(draw, candidate, font) > box_w:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            lines.append(line)
        line_height = max(1, _text_height(draw, "Ag", font))
        align = element.get("align", "left")
        for line_index, line in enumerate(lines):
            text_width = _text_width(draw, line, font)
            text_x = x + ((box_w - text_width) // 2 if align == "center" else (box_w - text_width if align == "right" else 0))
            draw.text((text_x, y + line_index * line_height), line, font=font, fill=color)

    # ------------------------------------------------------------------
    # 5. Choose font sizes & measurement
    # ------------------------------------------------------------------
    base = min(w, h)
    max_name_width = min(max_text_width, int(w * 0.82))

    # Student name: start at comfortable size, shrink until fits max_name_width
    configured_name_size = layout.get("name_font_size")
    name_font_size = int(configured_name_size) if configured_name_size else max(int(base * 0.052), 26)
    min_name_font_size = layout.get("min_name_font_size") or max(int(base * 0.020), 14)

    while name_font_size > min_name_font_size:
        nf = _get_font(name_font_size, bold=True)
        if _text_width(draw, student_name, nf) <= max_name_width:
            break
        name_font_size -= 1
    name_font = _get_font(name_font_size, bold=True)

    para_size = layout.get("para_font_size") or max(int(base * 0.021), 16)
    para_font = _get_font(para_size, bold=False)

    detail_size = layout.get("detail_font_size") or max(int(base * 0.017), 13)
    detail_font = _get_font(detail_size, bold=False)

    # ------------------------------------------------------------------
    # 6. Colours & alignment
    # ------------------------------------------------------------------
    name_color   = layout.get("name_color", (30, 30, 30))
    para_color   = layout.get("para_color", (50, 50, 50))
    detail_color = layout.get("detail_color", (60, 60, 60))
    name_align   = layout.get("name_align", "center")

    # ------------------------------------------------------------------
    # 7. Draw student name (vertically & horizontally centered in focal band)
    # ------------------------------------------------------------------
    fallback_name_ratio = 0.43 if h >= w * 1.05 else 0.45
    target_name_y = _resolve_coord(layout.get("name_y"), h, fallback_name_ratio)

    name_bb = draw.textbbox((0, 0), student_name, font=name_font)
    name_tw = name_bb[2] - name_bb[0]
    name_th = name_bb[3] - name_bb[1]

    # Center text vertically on target_name_y
    name_draw_y = target_name_y - (name_th // 2) - name_bb[1]

    if name_align == "left":
        name_x = left_x
    elif name_align == "right":
        name_x = max(left_x, right_x - name_tw)
    else:
        name_x = max(left_x, (w - name_tw) // 2)

    # The legacy automatic name field is retained for layouts without an explicit
    # recipient layer. Once the editor places that field, it becomes the sole
    # source of the recipient's visible name.
    has_explicit_name = bool(normalized_fields.intersection({"recipient_name", "student_name"}))
    if not has_explicit_name:
        draw.text((name_x, name_draw_y), student_name, font=name_font, fill=name_color)

    # Optional underline (only if configured)
    if layout.get("draw_underline", False) and not has_explicit_name:
        underline_tw = name_tw + max(16, int(name_font_size * 0.18))
        underline_x0 = max(left_x, (w - underline_tw) // 2)
        underline_x1 = min(right_x, underline_x0 + underline_tw)
        underline_thickness = max(2, int(name_font_size * 0.05))
        underline_y = name_draw_y + name_bb[3] + max(4, int(name_font_size * 0.10))
        draw.rectangle(
            [underline_x0, underline_y, underline_x1, underline_y + underline_thickness],
            fill=name_color,
        )
        current_y = underline_y + underline_thickness
    else:
        current_y = name_draw_y + name_bb[3]

    # ------------------------------------------------------------------
    # 8. Draw completion paragraph (ONLY if non-empty)
    # ------------------------------------------------------------------
    para_gap = int(h * 0.022)
    meta_gap = int(h * 0.025)
    meta_h   = _text_height(draw, "Ag", detail_font)
    fallback_sig_ratio = 0.80 if h >= w * 1.05 else 0.84
    sig_top = _resolve_coord(layout.get("sig_top"), h, fallback_sig_ratio)

    if paragraph:
        para_line_spacing = max(4, int(para_size * 0.38))
        fallback_para_ratio = 0.53 if h >= w * 1.05 else 0.54
        configured_para_top = _resolve_coord(layout.get("para_top"), h, fallback_para_ratio)
        para_start_y = max(current_y + para_gap, configured_para_top)
        wrapped_lines = _wrap_text(paragraph, para_font, max_text_width, draw)
        line_h = _text_height(draw, "Ay", para_font)
        total_para_h = len(wrapped_lines) * (line_h + para_line_spacing)

        # If paragraph would overflow into signature area, compress line spacing
        if para_start_y + total_para_h + meta_gap + meta_h > sig_top:
            para_line_spacing = max(2, para_line_spacing - 3)
            total_para_h = len(wrapped_lines) * (line_h + para_line_spacing)

        py = para_start_y
        for line in wrapped_lines:
            _draw_centered(draw, line, py, para_font, para_color, w)
            py += line_h + para_line_spacing
        para_end_y = py
    else:
        # No description provided: preserve template's existing background text
        para_end_y = current_y

    # ------------------------------------------------------------------
    # 9. Draw Certificate ID and Issue Date (metadata row above signatures)
    # ------------------------------------------------------------------
    fallback_meta_ratio = 0.69 if h >= w * 1.05 else 0.72
    configured_meta_top = _resolve_coord(layout.get("meta_top"), h, fallback_meta_ratio)
    if paragraph:
        meta_y = max(para_end_y + meta_gap, configured_meta_top)
    else:
        meta_y = configured_meta_top

    # Ensure metadata does not collide with signatures
    meta_y = min(meta_y, sig_top - meta_h - int(h * 0.015))

    cert_text = f"Certificate ID: {certificate_number}"
    date_text = f"Issue Date: {issue_disp}"

    has_explicit_certificate_id = bool(normalized_fields.intersection({"certificate_id", "certificate_number"}))
    has_explicit_issue_date = "issue_date" in normalized_fields
    if layout.get("show_cert_id", True) and not has_explicit_certificate_id:
        draw.text((left_x, meta_y), cert_text, font=detail_font, fill=detail_color)
    # Issue dates remain in the certificate record for audit and verification,
    # but only appear in the artwork when the template explicitly opts in.
    if layout.get("show_issue_date", False) and not has_explicit_issue_date:
        date_tw = _text_width(draw, date_text, detail_font)
        draw.text((right_x - date_tw, meta_y), date_text, font=detail_font, fill=detail_color)

    # ------------------------------------------------------------------
    # 10. Serialise in requested format (preserving PNG transparency when requested)
    # ------------------------------------------------------------------
    buffer = io.BytesIO()
    fmt = output_format.upper()
    if fmt == "PNG":
        # Preserve full alpha transparency and resolution
        img.save(buffer, format="PNG", optimize=True)
    elif fmt in ("JPEG", "JPG"):
        output_img = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            output_img.paste(img, mask=img.split()[3])
        else:
            output_img.paste(img)
        output_img.save(buffer, format="JPEG", quality=95)
    elif fmt == "PDF":
        output_img = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            output_img.paste(img, mask=img.split()[3])
        else:
            output_img.paste(img)
        output_img.save(buffer, format="PDF", resolution=150)
    else:
        img.save(buffer, format="PNG", optimize=True)

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

