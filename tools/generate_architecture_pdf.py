#!/usr/bin/env python3
"""Render the AABOS architecture Markdown report as a judge-ready PDF.

Mermaid is excellent in GitHub, but plain PDF readers do not execute Mermaid.
This generator preserves the complete report text and replaces each Mermaid
source block with an equivalent ReportLab vector diagram.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "SYSTEM_ARCHITECTURE_AABOS.md"
OUTPUT = ROOT / "output" / "pdf" / "AABOS_System_Architecture.pdf"

NAVY = HexColor("#102548")
BLUE = HexColor("#1D6FD7")
CYAN = HexColor("#22A6B3")
GREEN = HexColor("#168168")
AMBER = HexColor("#E6A300")
RED = HexColor("#C9454A")
INK = HexColor("#172B4D")
MUTED = HexColor("#52667D")
PANEL = HexColor("#F3F7FC")
LINE = HexColor("#C9D7E6")
WHITE = colors.white


def sanitize(text: str) -> str:
    """Use ASCII punctuation in the PDF and escape text for ReportLab XML."""
    replacements = {
        "→": "->",
        "←": "<-",
        "↔": "<->",
        "≥": ">=",
        "≤": "<=",
        "°": " deg ",
        "–": "-",
        "—": "-",
        "…": "...",
        "•": "-",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return html.escape(text)


def inline(text: str) -> str:
    """Small Markdown subset suitable for Paragraph markup."""
    escaped = sanitize(text)
    escaped = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r'<font color="#1D6FD7">\1</font>', escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier" color="#1D6FD7">\1</font>', escaped)
    return escaped


class ArchitectureDiagram(Flowable):
    """A compact vector version of one architecture Mermaid diagram."""

    TITLES = [
        "End-to-end AABOS architecture",
        "One deterministic fast control cycle",
        "Kafka telemetry boundary and safe degraded mode",
        "Two-horizon autonomy and event triggers",
        "Asynchronous local-LLM policy handoff",
        "MCP inspection and safety-governed policy path",
        "Bounded telemetry and log transformation",
        "Safety Sentinel and self-healing state path",
        "Runtime EnergyPlus IDF injection",
        "Automation Memory and bounded policy evolution",
        "Recommended three-minute evidence sequence",
    ]

    HEIGHTS = [270, 215, 150, 245, 195, 215, 160, 220, 170, 175, 145]

    def __init__(self, index: int) -> None:
        super().__init__()
        self.index = index
        self.width = 0
        self.height = self.HEIGHTS[min(index, len(self.HEIGHTS) - 1)]

    def wrap(self, avail_width: float, avail_height: float):
        self.width = avail_width
        return avail_width, self.height

    def _box(self, c, x, y, w, h, title, detail="", fill=PANEL, accent=BLUE, font=7.2):
        c.setStrokeColor(accent)
        c.setFillColor(fill)
        c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", font)
        self._center(c, title, x + w / 2, y + h - 12, max_width=w - 8, size=font)
        if detail:
            c.setFillColor(MUTED)
            c.setFont("Helvetica", max(5.8, font - 1.1))
            for i, line in enumerate(detail.split("\n")):
                self._center(c, line, x + w / 2, y + h - 25 - i * 8, max_width=w - 8, size=max(5.8, font - 1.1))

    def _center(self, c, text, cx, y, max_width, size):
        text = str(text)
        if stringWidth(text, "Helvetica", size) > max_width:
            words, lines, current = text.split(), [], ""
            for word in words:
                proposed = (current + " " + word).strip()
                if current and stringWidth(proposed, "Helvetica", size) > max_width:
                    lines.append(current)
                    current = word
                else:
                    current = proposed
            if current:
                lines.append(current)
        else:
            lines = [text]
        for i, line in enumerate(lines[:2]):
            c.drawCentredString(cx, y - i * (size + 1), line)

    def _arrow(self, c, x1, y1, x2, y2, color=BLUE, dashed=False):
        c.saveState()
        c.setStrokeColor(color)
        c.setFillColor(color)
        c.setLineWidth(1)
        if dashed:
            c.setDash(3, 2)
        c.line(x1, y1, x2, y2)
        angle = 0
        if abs(x2 - x1) >= abs(y2 - y1):
            angle = 0 if x2 >= x1 else 180
        else:
            angle = 90 if y2 >= y1 else -90
        c.saveState()
        c.translate(x2, y2)
        c.rotate(angle)
        c.setDash()
        c.line(-5, 3, 0, 0)
        c.line(-5, -3, 0, 0)
        c.restoreState()
        c.restoreState()

    def _label(self, c, text, x, y, color=MUTED, size=6.2):
        c.setFillColor(color)
        c.setFont("Helvetica", size)
        c.drawCentredString(x, y, text)

    def _title(self, c):
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0, self.height - 12, self.TITLES[self.index])
        c.setStrokeColor(LINE)
        c.line(0, self.height - 17, self.width, self.height - 17)

    def draw(self):
        c = self.canv
        self._title(c)
        renderer = getattr(self, f"_draw_{self.index}", self._draw_0)
        renderer(c)

    def _draw_0(self, c):
        w = self.width
        y = self.height - 65
        labels = [
            ("EnergyPlus", "physics digital twin", GREEN),
            ("Runner", "normalizes output", BLUE),
            ("Kafka", "aabos.telemetry", CYAN),
            ("Shared state", "live values + setpoints", BLUE),
        ]
        bw, bh, gap, x = (w - 3 * 11) / 4, 34, 11, 0
        for i, (title, detail, color) in enumerate(labels):
            self._box(c, x, y, bw, bh, title, detail, accent=color)
            if i:
                self._arrow(c, x - gap + 2, y + bh / 2, x - 2, y + bh / 2)
            x += bw + gap
        y2 = self.height - 125
        labels2 = [
            ("4 fast agents", "comfort | energy\noccupancy | carbon", BLUE),
            ("Decision Engine", "scored policy", BLUE),
            ("Safety Sentinel", "bounds + anti-oscillation", RED),
            ("Runtime IDF writer", "approved model update", GREEN),
        ]
        x = 0
        for i, (title, detail, color) in enumerate(labels2):
            self._box(c, x, y2, bw, 42, title, detail, accent=color)
            if i:
                self._arrow(c, x - gap + 2, y2 + 21, x - 2, y2 + 21)
            x += bw + gap
        self._arrow(c, w - 15, y2, w - 15, y + 2, color=GREEN)
        self._label(c, "next EnergyPlus cycle", w - 49, y + 7, GREEN)
        y3 = 28
        self._box(c, 0, y3, 118, 38, "AGMS", "event / goal / review", fill=HexColor("#FFF8E8"), accent=AMBER)
        self._box(c, 140, y3, 118, 38, "Strategic worker", "background queue", fill=HexColor("#FFF8E8"), accent=AMBER)
        self._box(c, 280, y3, 118, 38, "Local Llama 3.2", "MCP inspection", fill=HexColor("#FFF8E8"), accent=AMBER)
        self._box(c, 420, y3, max(92, w - 420), 38, "Latest policy handoff", "next cycle only", fill=HexColor("#FFF8E8"), accent=AMBER)
        for x1, x2 in ((118, 140), (258, 280), (398, 420)):
            self._arrow(c, x1 + 2, y3 + 19, x2 - 2, y3 + 19, color=AMBER)
        self._arrow(c, 472, y3 + 38, 472, y2 - 2, color=AMBER)
        self._label(c, "slow strategic path: never blocks fast control", w / 2, 13, AMBER)

    def _draw_1(self, c):
        actors = ["EnergyPlus", "Runner", "Kafka / state", "4 agents", "Decision", "Sentinel", "Runtime IDF"]
        n, left, right = len(actors), 6, self.width - 6
        xs = [left + i * (right - left) / (n - 1) for i in range(n)]
        top, bottom = self.height - 42, 18
        for x, name in zip(xs, actors):
            self._box(c, x - 31, top - 22, 62, 19, name, "", fill=HexColor("#E9F2FC"), accent=BLUE, font=6.3)
            c.setStrokeColor(LINE); c.setDash(2, 2); c.line(x, bottom, x, top - 23); c.setDash()
        events = [
            (0, 1, top - 45, "outputs"),
            (1, 2, top - 69, "normalized telemetry"),
            (2, 3, top - 93, "current snapshot"),
            (3, 4, top - 117, "scored recommendations"),
            (4, 5, top - 141, "policy + setpoints"),
            (5, 6, top - 165, "approved configuration"),
        ]
        for a, b, y, label in events:
            self._arrow(c, xs[a] + 4, y, xs[b] - 4, y)
            self._label(c, label, (xs[a] + xs[b]) / 2, y + 4)
        c.setFillColor(GREEN); c.setFont("Helvetica-Oblique", 6.4)
        c.drawCentredString(self.width / 2, 5, "Rejected proposals retain the last known safe state; next cycle continues.")

    def _draw_2(self, c):
        y = self.height - 70
        boxes = [
            ("EnergyPlus runner", "producer", GREEN),
            ("Kafka", "aabos.telemetry", CYAN),
            ("Retrying consumer", "background thread", BLUE),
            ("Shared state", "current values", BLUE),
        ]
        bw, gap = (self.width - 3 * 12) / 4, 12
        x = 0
        for i, (title, detail, color) in enumerate(boxes):
            self._box(c, x, y, bw, 39, title, detail, accent=color)
            if i:
                self._arrow(c, x - gap + 2, y + 19, x - 2, y + 19, color=CYAN)
            x += bw + gap
        self._box(c, 20, 26, 137, 38, "Broker unavailable", "direct safe delivery", fill=HexColor("#FFF4F2"), accent=RED)
        self._box(c, self.width - 157, 26, 137, 38, "Control continues", "state + energy + window", fill=HexColor("#F0FBF5"), accent=GREEN)
        self._arrow(c, bw / 2, y, 88, 64, color=RED, dashed=True)
        self._arrow(c, 157, 45, self.width - 157, 45, color=GREEN, dashed=True)
        self._arrow(c, self.width - 88, 64, self.width - bw / 2, y, color=GREEN, dashed=True)
        self._label(c, "Kafka adds decoupling and independent consumers, but never becomes a safety dependency.", self.width / 2, 10, MUTED)

    def _draw_3(self, c):
        self._box(c, 10, self.height - 82, self.width - 20, 41, "FAST HORIZON - every EnergyPlus cycle", "telemetry -> four agents -> Decision Engine -> Safety Sentinel -> next runtime IDF", fill=HexColor("#EAF3FF"), accent=BLUE, font=8)
        self._box(c, 10, self.height - 154, 105, 62, "Events", "power >= 7 kW\ncomfort deviation\nlow occupancy", fill=HexColor("#FFF8E8"), accent=AMBER)
        self._box(c, 130, self.height - 154, 105, 62, "AGMS", "deduplicate\nprioritize goals", fill=HexColor("#FFF8E8"), accent=AMBER)
        self._box(c, 250, self.height - 154, 105, 62, "Work queue", "background worker", fill=HexColor("#FFF8E8"), accent=AMBER)
        self._box(c, 370, self.height - 154, self.width - 380, 62, "Local LLM", "periodic review\nnew human goal\ncompact evidence", fill=HexColor("#FFF8E8"), accent=AMBER)
        for x1, x2 in ((115, 130), (235, 250), (355, 370)):
            self._arrow(c, x1 + 2, self.height - 123, x2 - 2, self.height - 123, color=AMBER)
        self._arrow(c, 425, self.height - 154, 400, 63, color=AMBER)
        self._box(c, 85, 25, self.width - 170, 38, "LATEST-POLICY HANDOFF - one supervisory proposal is consumed only by a later safety-validated fast cycle", fill=HexColor("#FFF8E8"), accent=AMBER, font=7.4)
        self._label(c, "The LLM is invoked for significant changes and reviews, not for every telemetry tick.", self.width / 2, 10, AMBER)

    def _draw_4(self, c):
        actors = ["Fast cycle", "Work queue", "Worker", "Ollama", "Handoff", "Next cycle"]
        xs = [8 + i * (self.width - 16) / 5 for i in range(6)]
        top, bottom = self.height - 42, 18
        for x, name in zip(xs, actors):
            self._box(c, x - 31, top - 22, 62, 19, name, "", fill=HexColor("#FFF8E8") if name in ("Ollama", "Work queue", "Worker") else HexColor("#EAF3FF"), accent=AMBER if name in ("Ollama", "Work queue", "Worker") else BLUE, font=6.3)
            c.setStrokeColor(LINE); c.setDash(2, 2); c.line(x, bottom, x, top - 23); c.setDash()
        events = [
            (0, 1, top - 44, "submit; return immediately", BLUE),
            (1, 2, top - 70, "dequeue", AMBER),
            (2, 3, top - 96, "compact evidence", AMBER),
            (3, 2, top - 122, "policy + rationale", AMBER),
            (2, 4, top - 148, "publish newest", AMBER),
            (5, 4, top - 174, "consume once", BLUE),
        ]
        for a, b, y, label, color in events:
            self._arrow(c, xs[a] + (4 if b > a else -4), y, xs[b] + (-4 if b > a else 4), y, color=color)
            self._label(c, label, (xs[a] + xs[b]) / 2, y + 4, color)
        self._label(c, "If the local model is unavailable or invalid, the worker creates a deterministic plan and fast control remains active.", self.width / 2, 5, MUTED)

    def _draw_5(self, c):
        y = self.height - 66
        stages = [
            ("Strategic worker", "goal + window summary", AMBER),
            ("Local Llama", "must inspect first", AMBER),
            ("FastMCP", "read-only runtime evidence", CYAN),
            ("Policy handoff", "named policy only", AMBER),
            ("Safety Sentinel", "final authority", RED),
            ("Runtime IDF", "next approved model", GREEN),
        ]
        bw, gap = (self.width - 5 * 8) / 6, 8
        x = 0
        for i, (title, detail, color) in enumerate(stages):
            self._box(c, x, y, bw, 48, title, detail, fill=HexColor("#F7FAFE"), accent=color, font=6.7)
            if i:
                self._arrow(c, x - gap + 2, y + 24, x - 2, y + 24, color=color)
            x += bw + gap
        self._box(c, 15, 42, self.width - 30, 46, "inspect_building_runtime = telemetry + approved setpoints + generated-IDF header + bounded 600-character error tail", fill=HexColor("#EBF9FA"), accent=CYAN, font=7.2)
        self._arrow(c, self.width / 2, 88, self.width / 2, y, color=CYAN)
        self._label(c, "A tool call is mandatory; no LLM response is a direct actuator command.", self.width / 2, 18, RED)

    def _draw_6(self, c):
        y = self.height - 76
        boxes = [
            ("EnergyPlus outputs", "large local files", MUTED),
            ("Normalize", "temperature, humidity\noccupancy, power", BLUE),
            ("Fixed 12-sample window", "bounded deque", CYAN),
            ("Compact summary", "avg/min/max + peaks\nestimated energy", GREEN),
            ("LLM prompt", "small strategic context", AMBER),
        ]
        bw, gap = (self.width - 4 * 8) / 5, 8
        x = 0
        for i, (title, detail, color) in enumerate(boxes):
            self._box(c, x, y, bw, 47, title, detail, accent=color, font=6.5)
            if i:
                self._arrow(c, x - gap + 2, y + 23, x - 2, y + 23, color=color)
            x += bw + gap
        self._box(c, 115, 32, self.width - 230, 39, "Raw logs remain local. MCP may provide only a bounded diagnostic tail; full simulation files never enter the LLM context.", fill=HexColor("#FFF8E8"), accent=AMBER, font=7.2)
        self._label(c, "Bounded context controls cost and latency as simulation duration grows.", self.width / 2, 12, MUTED)

    def _draw_7(self, c):
        boxes = [
            ("Observe", "new telemetry\nor proposal", BLUE),
            ("Candidate", "fast decision\nor LLM handoff", BLUE),
            ("Validate", "bounds + reversal\ncheck", RED),
            ("Apply", "safe setpoints", GREEN),
            ("Next result", "EnergyPlus feedback", GREEN),
        ]
        y, bw, gap = self.height - 78, (self.width - 4 * 8) / 5, 8
        x = 0
        for i, (title, detail, color) in enumerate(boxes):
            self._box(c, x, y, bw, 46, title, detail, accent=color)
            if i:
                self._arrow(c, x - gap + 2, y + 23, x - 2, y + 23, color=color)
            x += bw + gap
        self._box(c, 0, 52, 160, 42, "Rejected LLM policy", "retain last safe state\nor try balanced fallback", fill=HexColor("#FFF4F2"), accent=RED)
        self._box(c, self.width - 160, 52, 160, 42, "Comfort shortfall", "store failure ->\ncomfort-first recovery", fill=HexColor("#FFF4F2"), accent=RED)
        self._arrow(c, bw * 2 + gap * 2 - 5, y, 80, 94, color=RED, dashed=True)
        self._arrow(c, self.width - bw * 1.5, y, self.width - 80, 94, color=RED, dashed=True)
        self._box(c, self.width / 2 - 96, 16, 192, 25, "All recovery actions return to the same Safety Sentinel", fill=HexColor("#F0FBF5"), accent=GREEN, font=6.8)

    def _draw_8(self, c):
        y = self.height - 74
        boxes = [
            ("baseline.idf", "immutable reference", MUTED),
            ("RuntimeIDFWriter", "atomic generation", BLUE),
            ("modified.idf", "approved configuration", GREEN),
            ("EnergyPlus", "next subprocess run", GREEN),
            ("Telemetry", "measured outcome", CYAN),
        ]
        bw, gap = (self.width - 4 * 10) / 5, 10
        x = 0
        for i, (title, detail, color) in enumerate(boxes):
            self._box(c, x, y, bw, 43, title, detail, accent=color)
            if i:
                self._arrow(c, x - gap + 2, y + 21, x - 2, y + 21, color=color)
            x += bw + gap
        self._box(c, 55, 40, self.width - 110, 43, "Writer updates cooling/heating schedules and scales lighting. The generated header records all approved HVAC, ventilation, and lighting targets.", fill=HexColor("#F7FAFE"), accent=BLUE, font=7.1)
        self._label(c, "The model file is an inspectable closed-loop artifact, not a static deliverable.", self.width / 2, 16, MUTED)

    def _draw_9(self, c):
        y = self.height - 80
        boxes = [
            ("Measured outcome", "energy + comfort", CYAN),
            ("Automation episode", "policy + reward", BLUE),
            ("Memory", "up to 500 episodes", BLUE),
            ("Policy performance", "reward average", AMBER),
            ("APEE", "max +/-0.15", AMBER),
            ("Decision Engine", "bounded tie-breaker", GREEN),
        ]
        bw, gap = (self.width - 5 * 8) / 6, 8
        x = 0
        for i, (title, detail, color) in enumerate(boxes):
            self._box(c, x, y, bw, 45, title, detail, accent=color, font=6.5)
            if i:
                self._arrow(c, x - gap + 2, y + 22, x - 2, y + 22, color=color)
            x += bw + gap
        self._box(c, 75, 38, self.width - 150, 42, "Safety Sentinel remains final authority. This is bounded online policy adaptation, not unconstrained RL exploration or foundation-model training.", fill=HexColor("#FFF8E8"), accent=AMBER, font=7.1)
        self._label(c, "Optional PostgreSQL persistence occurs asynchronously and never blocks a control tick.", self.width / 2, 16, MUTED)

    def _draw_10(self, c):
        labels = [
            "1. Live telemetry",
            "2. Agent decision",
            "3. modified.idf",
            "4. Savings + comfort",
            "5. LLM MCP audit",
            "6. Safe correction",
        ]
        bw, gap, y = (self.width - 5 * 8) / 6, 8, self.height - 76
        x = 0
        for i, label in enumerate(labels):
            color = [CYAN, BLUE, GREEN, GREEN, AMBER, RED][i]
            self._box(c, x, y, bw, 48, label, "", fill=HexColor("#F7FAFE"), accent=color, font=6.8)
            if i:
                self._arrow(c, x - gap + 2, y + 24, x - 2, y + 24, color=color)
            x += bw + gap
        self._box(c, 80, 35, self.width - 160, 38, "Show the loop, then show its evidence: decision -> safety -> runtime model -> measured outcome -> fallback when needed.", fill=HexColor("#F0FBF5"), accent=GREEN, font=7.2)
        self._label(c, "A rejection is evidence of protection, not a failed demo.", self.width / 2, 15, MUTED)


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("AABOSTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=27, leading=31, textColor=NAVY, alignment=TA_CENTER, spaceAfter=10),
        "subtitle": ParagraphStyle("AABOSSubtitle", parent=base["Normal"], fontName="Helvetica", fontSize=11.5, leading=16, textColor=MUTED, alignment=TA_CENTER),
        "h2": ParagraphStyle("AABOSH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=NAVY, spaceBefore=16, spaceAfter=7, keepWithNext=True),
        "h3": ParagraphStyle("AABOSH3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=BLUE, spaceBefore=11, spaceAfter=5, keepWithNext=True),
        "body": ParagraphStyle("AABOSBody", parent=base["BodyText"], fontName="Helvetica", fontSize=8.8, leading=12.5, textColor=INK, spaceAfter=6),
        "quote": ParagraphStyle("AABOSQuote", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=9.5, leading=14, leftIndent=16, rightIndent=16, textColor=NAVY, borderColor=CYAN, borderWidth=1, borderPadding=7, spaceBefore=5, spaceAfter=8),
        "code": ParagraphStyle("AABOSCode", parent=base["Code"], fontName="Courier", fontSize=6.7, leading=8.4, textColor=INK, backColor=HexColor("#F2F5F8"), borderColor=LINE, borderWidth=0.5, borderPadding=6, spaceBefore=4, spaceAfter=8),
        "table": ParagraphStyle("AABOSTable", parent=base["BodyText"], fontName="Helvetica", fontSize=6.55, leading=8.1, textColor=INK),
        "tablehead": ParagraphStyle("AABOSTableHead", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=6.6, leading=8.2, textColor=WHITE),
        "bullet": ParagraphStyle("AABOSBullet", parent=base["BodyText"], fontName="Helvetica", fontSize=8.6, leading=12, textColor=INK, leftIndent=10, spaceAfter=2),
    }


def table_flow(lines, st):
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            rows.append(cells)
    if not rows:
        return Spacer(1, 1)
    cols = max(len(row) for row in rows)
    normalized = [row + [""] * (cols - len(row)) for row in rows]
    width = A4[0] - 0.72 * inch * 2
    if cols == 2:
        widths = [width * 0.29, width * 0.71]
    elif cols == 3:
        widths = [width * 0.22, width * 0.48, width * 0.30]
    elif cols == 4:
        widths = [width * 0.19, width * 0.22, width * 0.25, width * 0.34]
    else:
        widths = [width / cols] * cols
    data = []
    for r, row in enumerate(normalized):
        row_style = st["tablehead"] if r == 0 else st["table"]
        data.append([Paragraph(inline(cell), row_style) for cell in row])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, HexColor("#F7FAFE")]),
    ]))
    return KeepTogether([table, Spacer(1, 7)])


def parse_report(path: Path, st):
    lines = path.read_text(encoding="utf-8").splitlines()
    story = []
    buffer = []
    diagram_index = 0

    def flush():
        if buffer:
            joined = " ".join(part.strip() for part in buffer).strip()
            if joined:
                story.append(Paragraph(inline(joined), st["body"]))
            buffer.clear()

    index = 0
    title_done = False
    while index < len(lines):
        line = lines[index]
        if line.startswith("```mermaid"):
            flush()
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                index += 1
            story.extend([ArchitectureDiagram(diagram_index), Spacer(1, 10)])
            diagram_index += 1
        elif line.startswith("```"):
            flush()
            code = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(sanitize(lines[index]))
                index += 1
            story.append(Preformatted("\n".join(code), st["code"]))
        elif line.startswith("# "):
            flush()
            if not title_done:
                story.append(Spacer(1, 1.2 * inch))
                story.append(Paragraph(inline(line[2:]), st["title"]))
                story.append(Paragraph("Judge-facing technical architecture report", st["subtitle"]))
                story.append(Spacer(1, 0.32 * inch))
                story.append(ArchitectureDiagram(0))
                story.append(Spacer(1, 0.2 * inch))
                story.append(Paragraph("EnergyPlus digital twin | Kafka telemetry | Four fast agents | Local Llama 3.2 | MCP | Safety Sentinel", st["subtitle"]))
                story.append(PageBreak())
                title_done = True
            else:
                story.append(Paragraph(inline(line[2:]), st["h2"]))
        elif line.startswith("## "):
            flush()
            story.append(Paragraph(inline(line[3:]), st["h2"]))
        elif line.startswith("### "):
            flush()
            story.append(Paragraph(inline(line[4:]), st["h3"]))
        elif line.startswith("|"):
            flush()
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            story.append(table_flow(table_lines, st))
            index -= 1
        elif line.startswith("> "):
            flush()
            story.append(Paragraph(inline(line[2:]), st["quote"]))
        elif line.startswith("- "):
            flush()
            items = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append(ListItem(Paragraph(inline(lines[index][2:]), st["bullet"])))
                index += 1
            story.append(ListFlowable(items, bulletType="bullet", start="circle", leftIndent=17, bulletFontSize=7, spaceAfter=6))
            index -= 1
        elif re.match(r"^\d+\. ", line):
            flush()
            items = []
            while index < len(lines) and re.match(r"^\d+\. ", lines[index]):
                items.append(ListItem(Paragraph(inline(re.sub(r"^\d+\. ", "", lines[index])), st["bullet"])))
                index += 1
            story.append(ListFlowable(items, bulletType="1", leftIndent=20, bulletFontSize=7, spaceAfter=6))
            index -= 1
        elif not line.strip():
            flush()
        else:
            buffer.append(line)
        index += 1
    flush()
    return story


def page_decorator(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(WHITE)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 23, width, 23, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 7.2)
    canvas.drawString(0.72 * inch, height - 15, "AABOS - SYSTEM ARCHITECTURE")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(width - 0.72 * inch, 18, f"Honeywell Hackathon | Page {doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(0.72 * inch, 25, width - 0.72 * inch, 25)
    canvas.restoreState()


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    st = styles()
    frame = Frame(0.72 * inch, 0.42 * inch, A4[0] - 1.44 * inch, A4[1] - 0.78 * inch, id="body")
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=0.72 * inch, rightMargin=0.72 * inch,
        topMargin=0.35 * inch, bottomMargin=0.38 * inch, title="AABOS System Architecture",
        author="AABOS Team", subject="EnergyPlus closed-loop building control architecture",
    )
    doc.addPageTemplates([PageTemplate(id="AABOS", frames=[frame], onPage=page_decorator)])
    doc.build(parse_report(SOURCE, st))
    print(OUTPUT)


if __name__ == "__main__":
    build()
