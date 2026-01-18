import streamlit as st
import json
from pathlib import Path
import base64
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4
MIN_LINE_GAP = 0.8   # this is your 0.08 paragraph spacing (in points)

def wrap_lines(text, max_width, font="Helvetica", size=9.5):
    """Return wrapped lines (list[str]) without drawing."""
    words = str(text).split()
    if not words:
        return []

    line = ""
    lines = []
    for w in words:
        test = (line + " " + w).strip()
        if stringWidth(test, font, size) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def draw_boxed_block(c, x, y, width, lines, padding=6, font="Helvetica", size=9.5, leading=11, line_gap=0):
    """
    Draws a thin bordered box with wrapped text lines.
    (x,y) is top-left of the box.
    Returns (new_y, box_height)
    """
    # Calculate height first
    text_lines = []
    for ln in lines:
        # allow lines to already be wrapped or not; if not, keep as is
        text_lines.append(str(ln))

    box_height = padding * 2 + (len(text_lines) * leading) + (max(0, len(text_lines) - 1) * line_gap)

    # Border
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(x, y - box_height, width, box_height, stroke=0, fill=0)

    # Text
    c.setFont(font, size)
    ty = y - padding - size  # small baseline adjustment
    for ln in text_lines:
        c.drawString(x + padding, ty, ln)
        ty -= leading + line_gap

    return y , box_height


def draw_wrapped_text(
    c, text, x, y, max_width,
    font="Helvetica", size=9.5,
    leading=11,
    min_gap=MIN_LINE_GAP
):
    c.setFont(font, size)
    words = str(text).split()
    line = ""
    lines = []

    for w in words:
        test = (line + " " + w).strip()
        if stringWidth(test, font, size) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)

    for ln in lines:
        c.drawString(x, y, ln)
        y -= leading

    # 🔥 BLANKET RULE: minimum paragraph gap
    y -= min_gap

    return y


def draw_section_title(c, title, x, y, size=11):
    c.setFont("Helvetica-Bold", size)
    c.drawString(x, y, str(title).upper())
    return y - (14 + MIN_LINE_GAP)


def draw_bullets(c, bullets, x, y, max_width, font="Helvetica", size=10, leading=12, bullet_indent=10):
    c.setFont(font, size)
    for b in (bullets or []):
        # bullet marker
        c.drawString(x, y, "•")
        # wrapped bullet text
        y = draw_wrapped_text(
            c,
            b,
            x + bullet_indent,
            y,
            max_width - bullet_indent,
            font=font,
            size=size,
            leading=leading
        )
        y -= MIN_LINE_GAP

    return y

def draw_divider(c, x_start, x_end, y, thickness=0.7):
    c.setLineWidth(thickness)
    c.line(x_start, y, x_end, y)
    return y - 8

def draw_page_border(c, page_w, page_h, margin=.2*cm, thickness=0.5):
    """
    Draws a thin black border around the page.
    """
    c.setLineWidth(thickness)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(
        margin,
        margin,
        page_w - 1.85 * margin,
        page_h - 2 * margin,
        stroke=1,
        fill=0
    )


def create_resume_pdf(
    json_path="resume_data.json",
    output_path="Rachit_Sharma_Resume_Generated.pdf"):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    c = canvas.Canvas(output_path, pagesize=A4)
    draw_page_border(c, PAGE_W, PAGE_H)

    # ===== Layout constants (UNCHANGED aesthetic) =====
    left = 0.5 * cm
    right = 0.5 * cm
    top = 0.75 * cm
    bottom = 0 * cm

    content_w = PAGE_W - left - right
    y = PAGE_H - top

    # Helper: page break only if required (won't affect 1-page resumes)
    def new_page_if_needed(ypos):
        if ypos < bottom + 2 * cm:
            c.showPage()
            return PAGE_H - top
        return ypos

    # ===== Header (now dynamic) =====
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, y, data.get("name", "YOUR NAME"))
    y -= 15

    c.setFont("Helvetica", 9)
    c.drawString(left, y, data.get("contact", "Location | Phone | Email"))
    y -= 8

    # ===== CAREER OBJECTIVE (dynamic) =====
    y = draw_divider(c, left, left + content_w, y)
    y -= 3
    y = new_page_if_needed(y)

    y = draw_section_title(c, "CAREER OBJECTIVE", left, y, size=11)

    objective = data.get("career_objective", "")
    y = draw_wrapped_text(c, objective, left, y, content_w, font="Helvetica", size=10, leading=12)
    y -= 10

    # ===== SKILLS SNAPSHOT (dynamic, same layout) =====
    y = new_page_if_needed(y)
    y = draw_section_title(c, "SKILLS SNAPSHOT", left, y, size=11)

    # Same columns as your old file
    label_w = 4.2 * cm
    gap = 0.6 * cm
    value_x = left + label_w + gap
    value_w = content_w - label_w - gap

    for item in (data.get("skills_snapshot") or []):
        y = new_page_if_needed(y)

        label = item.get("label", "")
        value = item.get("value", "")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(left, y, label)

        y = draw_wrapped_text(c, value, value_x, y, value_w, font="Helvetica", size=10, leading=12)
        y -= 2

    y -= 10

    # ===== EXPERIENCE (dynamic) =====
    y = new_page_if_needed(y)
    y = draw_section_title(c, "EXPERIENCE", left, y, size=11)

    def exp_block(company, role_line, bullets):
        nonlocal y
        y = new_page_if_needed(y)

        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(left, y, company)
        y -= 13

        c.setFont("Helvetica-Bold", 10)
        y = draw_wrapped_text(c, role_line, left, y, content_w, font="Helvetica-Bold", size=10, leading=12)
        y -= 2

        y = draw_bullets(c, bullets, left, y, content_w, font="Helvetica", size=10, leading=12)
        y -= 6

    # Uses SAME key your old JSON had: "experience"
    for exp in (data.get("experience") or []):
        exp_block(
            exp.get("company", ""),
            exp.get("role_line", ""),
            exp.get("bullets", [])
        )

    # ===== EDUCATION (dynamic) =====
    y = draw_section_title(c, "EDUCATION", left, y, size=11)
    y += 15

    # --- 2-column layout settings
    col_gap = 0.6 * cm
    col_w = (content_w - col_gap) / 2
    x1 = left
    x2 = left + col_w + col_gap

    card_padding = 6
    font = "Helvetica"
    size = 8.5
    leading = 11

    edu_items = data.get("education", []) or []

    # draw in pairs (left/right)
    i = 0
    while i < len(edu_items):
        # page break check (rough)
        if y < bottom + 4 * cm:
            c.showPage()
            y = PAGE_H - top
            # (optional) if you redraw border each page, call your border function here

        left_item = edu_items[i]
        right_item = edu_items[i + 1] if (i + 1) < len(edu_items) else None

        # Build lines for left card (wrap inside column)
        left_lines = []
        deg = left_item.get("degree", "")
        det = left_item.get("details", "")

        # Wrap degree + details to fit column width minus padding
        left_lines += wrap_lines(deg, col_w - 2 * card_padding, font=font, size=size)
        left_lines += wrap_lines(det, col_w - 2 * card_padding, font=font, size=size)

        # Build lines for right card if present
        right_lines = []
        if right_item:
            deg2 = right_item.get("degree", "")
            det2 = right_item.get("details", "")
            right_lines += wrap_lines(deg2, col_w - 2 * card_padding, font=font, size=size)
            right_lines += wrap_lines(det2, col_w - 2 * card_padding, font=font, size=size)

        # We want both cards same height per row (take max lines)
        max_lines = max(len(left_lines), len(right_lines) if right_item else 0)
        if len(left_lines) < max_lines:
            left_lines += [""] * (max_lines - len(left_lines))
        if right_item and len(right_lines) < max_lines:
            right_lines += [""] * (max_lines - len(right_lines))

        # Draw both cards at same y
        y_after_left, h_left = draw_boxed_block(
            c, x1, y, col_w, left_lines,
            padding=card_padding, font=font, size=size, leading=leading
        )

        if right_item:
            y_after_right, h_right = draw_boxed_block(
                c, x2, y, col_w, right_lines,
                padding=card_padding, font=font, size=size, leading=leading
            )
            row_height = max(h_left, h_right)
        else:
            row_height = h_left

        # Move y down for next row (+ some gap)
        y = y - row_height - 10  # gap between rows

        i += 2

    """# ===== PROJECT HIGHLIGHTS (optional, dynamic) =====
    projects = data.get("project_highlights") or []
    if projects:
        y = new_page_if_needed(y)
        y = draw_section_title(c, "PROJECT HIGHLIGHTS", left, y, size=11)
        y = draw_bullets(c, projects, left, y, content_w)
        y -= 8
    """
    # ===== CERTIFICATIONS (optional, dynamic) =====
    certs = data.get("certifications") or []
    if certs:
        y = new_page_if_needed(y)
        y = draw_section_title(c, "CERTIFICATIONS", left, y, size=11)
        y = draw_bullets(c, certs, left, y, content_w)
        y = draw_divider(c, left, left + content_w, y)
        y -= 0
    # ===== REFERENCE (optional, dynamic) =====
    refs = data.get("references") or []
    if refs:
        y = new_page_if_needed(y)
        y = draw_section_title(c, "REFERENCE", left, y-2, size=11)
        for r in refs:
            y = new_page_if_needed(y)
            y = draw_wrapped_text(c, r, left, y, content_w, font="Helvetica", size=8, leading=6)
            y -= 4

    c.save()
    print(f"✅ Created: {output_path}")

"""
if __name__ == "__main__":
    create_resume_pdf(
        json_path="resume_data.json",
        output_path="RachitS_IT_WB.pdf"
    )
    
"""

st.set_page_config(page_title="Resume Generator", page_icon="📄")

st.title("📄 Resume Generator")
st.caption("Edit JSON → Generate PDF → Download")

JSON_PATH = Path("resume_data.json")

if not JSON_PATH.exists():
    st.error("resume_data.json not found in repo root")
    st.stop()

json_text = JSON_PATH.read_text(encoding="utf-8")

edited_json = st.text_area(
    "Edit resume_data.json",
    value=json_text,
    height=450
)

def safe_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9 _-]+", "", name)
    name = re.sub(r"\s+", "_", name)
    return name or "resume"

default_name = f"Resume_{datetime.now().strftime('%Y%m%d_%H%M')}"
out_name = st.text_input("Output filename (no .pdf needed)", value=default_name)
output_pdf = f"{safe_filename(out_name)}.pdf"

if st.button("⚙️ Generate PDF"):
    try:
        # validate + save JSON
        data = json.loads(edited_json)
        JSON_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # generate pdf
        create_resume_pdf(json_path=str(JSON_PATH), output_path=output_pdf)

        st.success("PDF generated successfully!")

        # auto-open in new tab
        pdf_bytes = Path(output_pdf).read_bytes()
        open_pdf_in_new_tab(pdf_bytes)

    except Exception as e:
        st.error(str(e))

# show download button (dynamic filename)
if Path(output_pdf).exists():
    st.download_button(
        "⬇️ Download PDF",
        data=Path(output_pdf).read_bytes(),
        file_name=output_pdf,
        mime="application/pdf"
    )





