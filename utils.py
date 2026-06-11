import streamlit as st
import vl_convert as vlc
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_LEFT
import pandas as pd
import json

def build_pdf() -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2*cm,
        leftMargin=2*cm,
        rightMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    user_style = styles["Normal"].clone("UserStyle")
    user_style.alignment = TA_RIGHT
    user_style.textColor = "#1e5fa8"
    user_style.fontSize = 10

    ai_style = styles["Normal"].clone("AiStyle")
    ai_style.alignment = TA_LEFT
    ai_style.fontSize = 10

    label_user = styles["Normal"].clone("LabelUser")
    label_user.alignment = TA_RIGHT
    label_user.fontSize = 8
    label_user.textColor = "#7ab8f5"

    label_ai = styles["Normal"].clone("LabelAi")
    label_ai.alignment = TA_LEFT
    label_ai.fontSize = 8
    label_ai.textColor = "#4a90d9"

    story = [
        Paragraph("DataAgent — Histórico da Conversa", styles["Title"]),
        Spacer(1, 0.5*cm),
    ]

    chart_idx = 0
    table_idx = 0
    charts = st.session_state.charts
    tables = st.session_state.tables

    table_cell_style = styles["Normal"].clone("TableCell")
    table_cell_style.fontSize = 8
    table_cell_style.leading = 10

    table_header_style = table_cell_style.clone("TableHeader")
    table_header_style.textColor = colors.white
    table_header_style.fontName = "Helvetica-Bold"

    for msg in st.session_state.display_messages:
        content = msg["content"].replace("\n", "<br/>")
        if msg["role"] == "user":
            story.append(Paragraph("VOCÊ", label_user))
            story.append(Paragraph(content, user_style))
        else:
            story.append(Paragraph("DATAAGENT", label_ai))
            story.append(Paragraph(content, ai_style))

            if msg.get("has_chart") and chart_idx < len(charts):
                try:
                    spec = json.loads(charts[chart_idx])
                    spec.setdefault("width", 600)
                    spec.setdefault("height", 350)
                    spec["autosize"] = {"type": "fit", "contains": "padding"}
                    png_bytes = vlc.vegalite_to_png(vl_spec=spec, scale=2)
                    img = RLImage(io.BytesIO(png_bytes))
                    img.drawWidth = 16*cm
                    img.drawHeight = img.drawWidth * (img.imageHeight / img.imageWidth)
                    if img.drawHeight > 11*cm:
                        img.drawHeight = 11*cm
                        img.drawWidth = img.drawHeight * (img.imageWidth / img.imageHeight)
                    story.append(Spacer(1, 0.3*cm))
                    story.append(img)
                except Exception:
                    pass
                chart_idx += 1

            if msg.get("has_table") and table_idx < len(tables):
                try:
                    df = pd.read_csv(io.StringIO(tables[table_idx]))

                    header = [Paragraph(str(c), table_header_style) for c in df.columns]
                    body = [
                        [Paragraph(str(v), table_cell_style) for v in row]
                        for row in df.values.tolist()
                    ]
                    data = [header] + body

                    n_cols = len(df.columns)
                    col_width = (16*cm) / max(n_cols, 1)

                    tbl = Table(data, colWidths=[col_width]*n_cols, repeatRows=1)
                    tbl.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e5fa8")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f7")]),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    story.append(Spacer(1, 0.3*cm))
                    story.append(tbl)
                except Exception:
                    pass
                table_idx += 1

        story.append(Spacer(1, 0.4*cm))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()