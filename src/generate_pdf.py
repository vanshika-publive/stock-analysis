"""Generate stock_report.pdf from aggregated.json — mirrors PPT structure."""

import json
import math
from pathlib import Path

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph,
    PageBreak, HRFlowable, KeepTogether,
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ── paths ────────────────────────────────────────────────────────────────────
INPUT  = Path(__file__).parent / "outputs" / "aggregated.json"
OUTPUT = Path(__file__).parent / "outputs" / "stock_report.pdf"

# ── palette ──────────────────────────────────────────────────────────────────
DARK_BG    = colors.HexColor("#0D1B2A")
CARD_BG    = colors.HexColor("#172A3E")
ACCENT     = colors.HexColor("#00B4D8")
WHITE      = colors.HexColor("#FFFFFF")
LIGHT_GREY = colors.HexColor("#CCD6E0")
GREEN      = colors.HexColor("#06D66A")
ORANGE     = colors.HexColor("#FF6B35")
RED        = colors.HexColor("#FF2D55")
YELLOW     = colors.HexColor("#FFD166")

RISK_COLORS = {
    "Conservative": GREEN,
    "Moderate":     YELLOW,
    "Aggressive":   ORANGE,
    "Speculative":  RED,
}

PAGE_W, PAGE_H = landscape(A4)   # 841.9 × 595.3 pt
MARGIN = 0.45 * inch

# ── styles ───────────────────────────────────────────────────────────────────
def S(name, **kw) -> ParagraphStyle:
    defaults = dict(fontName="Helvetica", fontSize=11,
                    textColor=WHITE, backColor=None,
                    leading=14, spaceAfter=0, spaceBefore=0)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

st_title    = S("title",   fontSize=34, fontName="Helvetica-Bold",
                leading=40, alignment=TA_CENTER)
st_subtitle = S("sub",     fontSize=13, textColor=LIGHT_GREY,
                leading=17, alignment=TA_CENTER)
st_h1       = S("h1",      fontSize=22, fontName="Helvetica-Bold", leading=28)
st_h2       = S("h2",      fontSize=14, fontName="Helvetica-Bold",
                textColor=ACCENT, leading=18)
st_body     = S("body",    fontSize=10, textColor=LIGHT_GREY, leading=14)
st_small    = S("small",   fontSize=8,  textColor=LIGHT_GREY,
                leading=11, alignment=TA_CENTER)
st_center   = S("center",  fontSize=11, textColor=WHITE,
                leading=14, alignment=TA_CENTER)
st_accent   = S("accent",  fontSize=11, fontName="Helvetica-Bold",
                textColor=ACCENT, leading=14, alignment=TA_CENTER)
st_ticker   = S("ticker",  fontSize=28, fontName="Helvetica-Bold",
                textColor=WHITE, leading=34)
st_stat_val = S("stat_val",fontSize=20, fontName="Helvetica-Bold",
                textColor=WHITE, leading=24)
st_stat_lbl = S("stat_lbl",fontSize=8,  textColor=LIGHT_GREY,
                leading=11, alignment=TA_CENTER)

def cagr(d):
    mult = d["ath_price"] / d["atl_price"]
    return (mult ** (365.0 / d["days_between"]) - 1) * 100


# ── custom flowables ─────────────────────────────────────────────────────────

class DarkPage(Flowable):
    """Full-page dark background — drawn once at top of each page via canvas callback."""
    pass  # handled via onPage


class HBar(Flowable):
    """Thin horizontal rule."""
    def __init__(self, width=None, color=ACCENT, thickness=1.5):
        super().__init__()
        self._w   = width
        self.color = color
        self.thickness = thickness
        self.hAlign = "LEFT"

    def wrap(self, aw, ah):
        self.width  = self._w or aw
        self.height = self.thickness + 2
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.color)
        c.setLineWidth(self.thickness)
        c.line(0, 1, self.width, 1)


class FilledRect(Flowable):
    """Coloured rectangle — useful for stat cards."""
    def __init__(self, w, h, fill, stroke=None, radius=3):
        super().__init__()
        self._fw   = w
        self._fh   = h
        self.fill   = fill
        self.stroke = stroke
        self.radius = radius

    def wrap(self, aw, ah):
        self.width  = self._fw
        self.height = self._fh
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(self.fill)
        if self.stroke:
            c.setStrokeColor(self.stroke)
        else:
            c.setStrokeColor(self.fill)
        c.roundRect(0, 0, self._fw, self._fh, self.radius, fill=1, stroke=0)


class HBarChart(Flowable):
    """Horizontal bar chart drawn directly onto canvas."""
    def __init__(self, rows, max_val, bar_h=14, gap=6, label_w=50,
                 val_w=55, chart_w=None, color_fn=None):
        super().__init__()
        self._rows    = rows      # [(label, value, sub_label, color), ...]
        self._max     = max_val
        self._bar_h   = bar_h
        self._gap     = gap
        self._label_w = label_w
        self._val_w   = val_w
        self._chart_w = chart_w
        self._color_fn= color_fn or (lambda r: ACCENT)

    def wrap(self, aw, ah):
        self.width  = aw
        self.height = len(self._rows) * (self._bar_h + self._gap)
        self._avail = aw
        return self.width, self.height

    def draw(self):
        c        = self.canv
        bar_area = (self._chart_w or self._avail) - self._label_w - self._val_w
        y        = self.height

        for label, value, sub, color in self._rows:
            y -= self._bar_h
            bar_len = max(bar_area * (value / self._max), 2)

            # ticker label
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(ACCENT)
            c.drawRightString(self._label_w - 4, y + 3, label)

            # bar
            c.setFillColor(color)
            c.roundRect(self._label_w, y, bar_len, self._bar_h - 2, 2, fill=1, stroke=0)

            # value text
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(WHITE)
            c.drawString(self._label_w + bar_len + 4, y + 3, sub)

            y -= self._gap


class StatCard(Flowable):
    """Single stat card: label / big value / sub-text, dark bg with accent top stripe."""
    def __init__(self, label, value, sub, w, h, accent_color=ACCENT):
        super().__init__()
        self._label  = label
        self._value  = value
        self._sub    = sub
        self._w      = w
        self._h      = h
        self._accent = accent_color

    def wrap(self, aw, ah):
        self.width  = self._w
        self.height = self._h
        return self.width, self.height

    def draw(self):
        c = self.canv
        # card bg
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, self._w, self._h, 4, fill=1, stroke=0)
        # top stripe
        c.setFillColor(self._accent)
        c.rect(0, self._h - 5, self._w, 5, fill=1, stroke=0)
        # label
        c.setFont("Helvetica", 8)
        c.setFillColor(LIGHT_GREY)
        c.drawCentredString(self._w / 2, self._h - 20, self._label)
        # value
        c.setFont("Helvetica-Bold", 17)
        c.setFillColor(WHITE)
        c.drawCentredString(self._w / 2, self._h - 44, self._value)
        # sub
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(LIGHT_GREY)
        c.drawCentredString(self._w / 2, self._h - 60, self._sub)


class RiskChip(Flowable):
    """Small chip showing ticker + risk label."""
    def __init__(self, ticker, risk, w=70, h=32):
        super().__init__()
        self._ticker = ticker
        self._risk   = risk
        self._w      = w
        self._h      = h

    def wrap(self, aw, ah):
        self.width  = self._w
        self.height = self._h
        return self.width, self.height

    def draw(self):
        c = self.canv
        color = RISK_COLORS.get(self._risk, ACCENT)
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, self._w, self._h, 3, fill=1, stroke=0)
        c.setFillColor(color)
        c.rect(0, self._h - 3, self._w, 3, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(ACCENT)
        c.drawCentredString(self._w / 2, self._h - 14, self._ticker)
        c.setFont("Helvetica", 7)
        c.setFillColor(LIGHT_GREY)
        c.drawCentredString(self._w / 2, 4, self._risk[:4] + ".")


# ── page background callback ─────────────────────────────────────────────────

def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK_BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # top accent bar
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_H - 4, PAGE_W, 4, fill=1, stroke=0)
    # footer
    canvas.setFont("Helvetica-Oblique", 7)
    canvas.setFillColor(LIGHT_GREY)
    canvas.drawCentredString(
        PAGE_W / 2, 10,
        "Source: Yahoo Finance  ·  Split-adjusted daily bars  ·  Not investment advice"
    )
    canvas.restoreState()


# ── section builders ─────────────────────────────────────────────────────────

def section_title(data):
    tickers = "  ·  ".join(d["ticker"] for d in data)
    return [
        Spacer(1, 1.4 * inch),
        Paragraph("Stock Performance Analysis", st_title),
        Spacer(1, 0.18 * inch),
        HBar(color=ACCENT, thickness=2),
        Spacer(1, 0.14 * inch),
        Paragraph(
            "ATL → ATH Journey  ·  10 Tickers  ·  10-Year Daily Bars (Split-Adjusted)",
            st_subtitle,
        ),
        Spacer(1, 0.1 * inch),
        Paragraph(tickers, S("chips", fontSize=11, textColor=ACCENT,
                             leading=16, alignment=TA_CENTER)),
        PageBreak(),
    ]


def section_overview_table(data):
    header = ["Ticker", "ATL Price", "ATL Date", "ATH Price",
              "ATH Date", "Days", "Mult.", "Speed", "Risk"]
    rows = [header]
    for d in data:
        mult = d["ath_price"] / d["atl_price"]
        rows.append([
            d["ticker"],
            f"${d['atl_price']:,.2f}",
            d["atl_date"],
            f"${d['ath_price']:,.2f}",
            d["ath_date"],
            f"{d['days_between']:,}",
            f"{mult:.1f}×",
            d["speed_label"],
            d["risk_label"],
        ])

    col_w = [
        0.68*inch, 0.82*inch, 0.88*inch,
        0.82*inch, 0.88*inch, 0.65*inch,
        0.58*inch, 1.15*inch, 1.0*inch,
    ]

    style = TableStyle([
        # header
        ("BACKGROUND",  (0, 0), (-1, 0),  ACCENT),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  DARK_BG),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  9),
        ("ALIGN",       (0, 0), (-1, 0),  "CENTER"),
        # data
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 1), (-1, -1), LIGHT_GREY),
        ("ALIGN",       (0, 1), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CARD_BG, DARK_BG]),
        # ticker col
        ("FONTNAME",    (0, 1), (0, -1),  "Helvetica-Bold"),
        ("TEXTCOLOR",   (0, 1), (0, -1),  ACCENT),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0,0), (-1, -1), 5),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#1E3A55")),
    ])

    # color risk column per row
    for i, d in enumerate(data, start=1):
        rc = RISK_COLORS.get(d["risk_label"], WHITE)
        style.add("TEXTCOLOR", (8, i), (8, i), rc)
        style.add("FONTNAME",  (8, i), (8, i), "Helvetica-Bold")

    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(style)

    return [
        Paragraph("Overview — All Tickers", st_h1),
        Spacer(1, 0.12 * inch),
        HBar(),
        Spacer(1, 0.15 * inch),
        t,
        PageBreak(),
    ]


def section_multiplier_chart(data):
    sorted_d = sorted(data, key=lambda d: d["ath_price"] / d["atl_price"])
    max_mult = max(d["ath_price"] / d["atl_price"] for d in sorted_d)
    avail_w  = PAGE_W - 2 * MARGIN

    rows = [
        (d["ticker"],
         d["ath_price"] / d["atl_price"],
         f"{d['ath_price']/d['atl_price']:.1f}×",
         RISK_COLORS.get(d["risk_label"], ACCENT))
        for d in sorted_d
    ]

    chart = HBarChart(rows, max_mult, bar_h=20, gap=8,
                      label_w=52, val_w=65, chart_w=avail_w)

    return [
        Paragraph("Price Multiplier: ATH ÷ ATL", st_h1),
        Spacer(1, 0.06 * inch),
        Paragraph("Colour = risk tier  ·  sorted low → high", st_body),
        Spacer(1, 0.12 * inch),
        HBar(),
        Spacer(1, 0.2 * inch),
        chart,
        PageBreak(),
    ]


def section_days_chart(data):
    sorted_d = sorted(data, key=lambda d: d["days_between"])
    max_days = max(d["days_between"] for d in sorted_d)
    avail_w  = PAGE_W - 2 * MARGIN

    rows = [
        (d["ticker"],
         d["days_between"],
         f"{d['days_between']:,} days",
         ACCENT)
        for d in sorted_d
    ]

    chart = HBarChart(rows, max_days, bar_h=20, gap=8,
                      label_w=52, val_w=72, chart_w=avail_w)

    return [
        Paragraph("Days from ATL to ATH", st_h1),
        Spacer(1, 0.06 * inch),
        Paragraph("Sorted fastest → slowest journey", st_body),
        Spacer(1, 0.12 * inch),
        HBar(),
        Spacer(1, 0.2 * inch),
        chart,
        PageBreak(),
    ]


def section_risk_breakdown(data):
    from collections import Counter
    counts = Counter(d["risk_label"] for d in data)
    labels = ["Conservative", "Moderate", "Aggressive", "Speculative"]

    card_w = (PAGE_W - 2 * MARGIN - 3 * 0.18 * inch) / 4
    card_h = 1.1 * inch

    cards = []
    for label in labels:
        count   = counts.get(label, 0)
        members = [d["ticker"] for d in data if d["risk_label"] == label]
        color   = RISK_COLORS[label]
        cards.append(StatCard(
            label,
            str(count),
            "  ".join(members) if members else "—",
            card_w, card_h,
            accent_color=color,
        ))

    gap = 0.18 * inch
    card_row = Table(
        [cards],
        colWidths=[card_w, gap, card_w, gap, card_w, gap, card_w],
    )
    card_row.setStyle(TableStyle([
        ("ALIGN",   (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",  (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    # chip table — all 10 tickers
    chip_w  = 0.75 * inch
    chip_h  = 0.38 * inch
    chips = [RiskChip(d["ticker"], d["risk_label"], w=chip_w*0.95, h=chip_h*1.6)
             for d in data]
    chip_row = Table(
        [chips],
        colWidths=[chip_w] * len(chips),
    )
    chip_row.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))

    return [
        Paragraph("Risk Profile Distribution", st_h1),
        Spacer(1, 0.12 * inch),
        HBar(),
        Spacer(1, 0.18 * inch),
        card_row,
        Spacer(1, 0.22 * inch),
        Paragraph("Per-Ticker Risk Label", st_h2),
        Spacer(1, 0.1 * inch),
        chip_row,
        PageBreak(),
    ]


def section_speed_breakdown(data):
    """Speed breakdown — one row per ticker, grouped by speed label."""
    speed_groups = [
        ("Rocket",         "CAGR > 70%/yr",   RED),
        ("Fast Mover",     "CAGR 35–70%/yr",  YELLOW),
        ("Steady Climber", "CAGR < 35%/yr",   GREEN),
    ]

    avail_w = PAGE_W - 2 * MARGIN
    col_widths = [0.72*inch, 0.95*inch, 0.95*inch, 0.95*inch,
                  0.85*inch, 0.9*inch, avail_w - 5.32*inch]

    items = [
        Paragraph("Speed Classification (CAGR-Based)", st_h1),
        Spacer(1, 0.06 * inch),
        Paragraph("Annualized return from ATL to ATH determines the speed tier", st_body),
        Spacer(1, 0.12 * inch),
        HBar(),
        Spacer(1, 0.14 * inch),
    ]

    for speed, rng, color in speed_groups:
        members = [d for d in data if d["speed_label"] == speed]
        if not members:
            continue

        color_hex = color.hexval()[2:]
        dark_hex  = DARK_BG.hexval()[2:]

        # group header
        hdr_row = [[
            Paragraph(
                f'<font color="#{dark_hex}"><b>{speed}</b></font>',
                S(f"gh_{speed}", fontSize=12, fontName="Helvetica-Bold",
                  alignment=TA_LEFT, leading=16),
            ),
            Paragraph(rng, S(f"gr_{speed}", fontSize=9, textColor=LIGHT_GREY,
                             alignment=TA_LEFT, leading=14)),
            Paragraph("ATL → ATH", S("ghc", fontSize=8, textColor=colors.HexColor(f"#{dark_hex}"),
                                     alignment=TA_CENTER, leading=12)),
            Paragraph("Multiplier", S("ghm", fontSize=8, textColor=colors.HexColor(f"#{dark_hex}"),
                                      alignment=TA_CENTER, leading=12)),
            Paragraph("CAGR", S("ghcagr", fontSize=8, textColor=colors.HexColor(f"#{dark_hex}"),
                                alignment=TA_CENTER, leading=12)),
            Paragraph("Risk", S("ghr", fontSize=8, textColor=colors.HexColor(f"#{dark_hex}"),
                                alignment=TA_CENTER, leading=12)),
            Paragraph("ATH Date", S("ghd", fontSize=8, textColor=colors.HexColor(f"#{dark_hex}"),
                                    alignment=TA_CENTER, leading=12)),
        ]]
        ht = Table(hdr_row, colWidths=col_widths)
        ht.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), color),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("SPAN",         (0, 0), (1,  0)),
        ]))
        items.append(ht)

        # member rows
        data_rows = []
        for d in members:
            mult       = d["ath_price"] / d["atl_price"]
            c_val      = cagr(d)
            risk_color = RISK_COLORS.get(d["risk_label"], WHITE)
            data_rows.append([
                Paragraph(f'<font color="#{color_hex}"><b>{d["ticker"]}</b></font>',
                          S(f"sp_tk_{d['ticker']}", fontSize=12,
                            fontName="Helvetica-Bold", leading=16)),
                Paragraph(f'{d["days_between"]:,}d',
                          S("sp_days", fontSize=9, textColor=LIGHT_GREY,
                            alignment=TA_CENTER, leading=13)),
                Paragraph(f'${d["atl_price"]:,.2f} → ${d["ath_price"]:,.2f}',
                          S("sp_px", fontSize=8, textColor=LIGHT_GREY,
                            alignment=TA_CENTER, leading=12)),
                Paragraph(f'{mult:.1f}×',
                          S("sp_mult", fontSize=10, fontName="Helvetica-Bold",
                            textColor=WHITE, alignment=TA_CENTER, leading=14)),
                Paragraph(f'{c_val:.1f}%',
                          S("sp_cagr", fontSize=10, fontName="Helvetica-Bold",
                            textColor=color, alignment=TA_CENTER, leading=14)),
                Paragraph(d["risk_label"],
                          S("sp_risk", fontSize=8, textColor=risk_color,
                            alignment=TA_CENTER, leading=12)),
                Paragraph(f'{d["atl_date"]} → {d["ath_date"]}',
                          S("sp_dates", fontSize=8, textColor=LIGHT_GREY,
                            alignment=TA_CENTER, leading=12)),
            ])

        dt = Table(data_rows, colWidths=col_widths)
        dt.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [CARD_BG, DARK_BG]),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#1E3A55")),
        ]))
        items.append(dt)
        items.append(Spacer(1, 0.14 * inch))

    items.append(PageBreak())
    return items


def section_ticker(d):
    mult       = d["ath_price"] / d["atl_price"]
    c_val      = cagr(d)
    risk_color = RISK_COLORS.get(d["risk_label"], ACCENT)

    card_w  = (PAGE_W - 2 * MARGIN - 3 * 0.18 * inch) / 4
    card_h  = 1.05 * inch
    card_gap = 0.18 * inch

    stat_cards = [
        StatCard("ATL Price",  f"${d['atl_price']:,.2f}", d["atl_date"],
                 card_w, card_h, ACCENT),
        None,
        StatCard("ATH Price",  f"${d['ath_price']:,.2f}", d["ath_date"],
                 card_w, card_h, ACCENT),
        None,
        StatCard("Multiplier", f"{mult:.1f}×", f"CAGR {c_val:.1f}%/yr",
                 card_w, card_h, risk_color),
        None,
        StatCard("Days", f"{d['days_between']:,}", "ATL → ATH",
                 card_w, card_h, risk_color),
    ]

    card_table = Table(
        [stat_cards],
        colWidths=[card_w, card_gap, card_w, card_gap, card_w, card_gap, card_w],
    )
    card_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    risk_hex   = risk_color.hexval()[2:]
    accent_hex = ACCENT.hexval()[2:]

    return [
        KeepTogether([
            Paragraph(
                f'{d["ticker"]}  '
                f'<font size="13" color="#{risk_hex}">{d["speed_label"]}  ·  {d["risk_label"]}</font>',
                S("tkhdr", fontSize=28, fontName="Helvetica-Bold",
                  textColor=WHITE, leading=34),
            ),
            HBar(color=risk_color, thickness=2.5),
            Spacer(1, 0.14 * inch),
            card_table,
            Spacer(1, 0.18 * inch),
            Paragraph("Analysis", S("anlbl", fontSize=11, fontName="Helvetica-Bold",
                                    textColor=ACCENT, leading=15)),
            HBar(color=CARD_BG, thickness=0.8),
            Spacer(1, 0.08 * inch),
            Paragraph(d.get("analysis", ""), st_body),
        ]),
        PageBreak(),
    ]


def section_closing(data):
    bullets = [
        ("NVDA",        "246.7× gain — most extreme multiplier in the dataset"),
        ("META & COIN", "Fastest journeys: < 1,100 days from ATL to ATH"),
        ("SPY",         "Most conservative: 3.5× over 9.6 years — steady baseline"),
        ("TSLA & NVDA", "Rockets with > 3,000 days — multiplier dominates speed label"),
        ("Algorithm",   "Current: CAGR-only. Recommended upgrade: CAGR + Max Drawdown + Sharpe"),
    ]

    bullet_rows = []
    for ticker, text in bullets:
        bullet_rows.append([
            Paragraph(ticker,
                      S("blt", fontSize=10, fontName="Helvetica-Bold",
                        textColor=ACCENT, leading=14)),
            Paragraph(text,
                      S("blt2", fontSize=10, textColor=LIGHT_GREY, leading=14)),
        ])

    bt = Table(
        bullet_rows,
        colWidths=[1.3 * inch, PAGE_W - 2 * MARGIN - 1.4 * inch],
    )
    bt.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [CARD_BG, DARK_BG]),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#1E3A55")),
    ]))

    return [
        Paragraph("Key Takeaways", st_h1),
        Spacer(1, 0.12 * inch),
        HBar(),
        Spacer(1, 0.2 * inch),
        bt,
    ]


# ── build ─────────────────────────────────────────────────────────────────────

def build_pdf(data: list[dict]) -> None:
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=landscape(A4),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.55 * inch, bottomMargin=0.3 * inch,
    )

    story = []
    story += section_title(data)
    story += section_overview_table(data)
    story += section_multiplier_chart(data)
    story += section_days_chart(data)
    story += section_risk_breakdown(data)
    story += section_speed_breakdown(data)
    for d in data:
        story += section_ticker(d)
    story += section_closing(data)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    with open(INPUT) as f:
        data = json.load(f)
    build_pdf(data)
