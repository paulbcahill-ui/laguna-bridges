# -*- coding: utf-8 -*-
"""Bridge timber rail inserts — FreeCAD model + carpenter fabrication drawing.

Runs as a FreeCAD macro on Windows, or headless via freecadcmd on Linux.
Outputs land in ../exports relative to this file (no hardcoded paths).

Source brief: docs/rails.docx (Laguna Quays Body Corporate bridge inserts).
"""
from __future__ import annotations

import math
import os
import sys

import FreeCAD as App
import Part

# ---------------------------------------------------------------------------
# Parameters (mm) — swap here if the section orientation is confirmed otherwise
# ---------------------------------------------------------------------------
# Doc says L x H 0.3 x W 0.2, clearance 175, top "just below wall" at 375.
# Conflict: 175 + 300 = 475, not 375. Resolve by laying the section flat:
#   RAIL_W = 300 (across the wall line), RAIL_H = 200 (up), so 175 + 200 = 375.
RAIL_W = 300.0          # width across the kerb line (laid flat)
RAIL_H = 200.0          # height above clearance
RAIL_CLEAR = 175.0      # clear gap under rail to pavement
RAIL_TOP = RAIL_CLEAR + RAIL_H  # 375
WALL_H = 400.0
WALL_W = 400.0
WALL_STUB = 1000.0      # length of each rock-wall end / mid stub (assumed)
GAP = 100.0             # clear gap rock wall <-> timber, each end
DECK_W = 4000.0         # deck width kerb-to-kerb outside (assumed; not in brief)
DECK_T = 250.0          # deck slab thickness (assumed)
CHAMFER = 15.0          # top-edge chamfer on timber

# Bridge 1: 4 rails of 2150 (2 openings per side)
# Bridge 2: 2 rails of 3600 (1 opening per side)
B1_RAIL_L = 2150.0
B1_N_PER_SIDE = 2
B2_RAIL_L = 3600.0
B2_N_PER_SIDE = 1

# Proposed fixings (not in brief — marked 'proposed' on drawing)
BRACKET_FROM_END_FRAC = 0.20   # ~L/5
BRACKET_SHS = 100.0            # 100x100x6 SHS post size (OD)
BRACKET_SHS_T = 6.0
BRACKET_BASE = 150.0           # base plate square
BRACKET_BASE_T = 10.0
BRACKET_UP = 180.0             # upright height under / beside rail
ANCHOR_D = 12.0                # M12 chemical anchors
ANCHOR_EMBED = 100.0
BOLT_D = 12.0                  # M12 through / coach bolts through rail

# Colours (RGB 0..1)
COL_DECK = (0.72, 0.72, 0.70)
COL_WALL = (0.62, 0.55, 0.45)
COL_RAIL = (0.72, 0.45, 0.20)
COL_STEEL = (0.45, 0.50, 0.45)
COL_ANCHOR = (0.35, 0.35, 0.38)


def _here():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # FreeCAD macro runner sometimes has no __file__
        return os.path.dirname(os.path.abspath(App.ActiveDocument.FileName)) if App.ActiveDocument and App.ActiveDocument.FileName else os.getcwd()


def exports_dir():
    base = os.path.dirname(_here())  # repo root (parent of macros/)
    out = os.path.join(base, "exports")
    os.makedirs(out, exist_ok=True)
    return out


def _box(doc, name, L, W, H, placement, colour, group):
    """Axis-aligned box: L along X, W along Y, H along Z; placement is corner min."""
    shp = Part.makeBox(L, W, H)
    shp.translate(App.Vector(*placement))
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shp
    if hasattr(obj, "ViewObject") and obj.ViewObject is not None:
        obj.ViewObject.ShapeColor = colour
    group.addObject(obj)
    return obj


def _rail_shape(length):
    """Timber rail: length along X, width along Y (RAIL_W), height along Z (RAIL_H),
    with small chamfers on the two top long edges."""
    # Base box then chamfer top long edges if possible
    box = Part.makeBox(length, RAIL_W, RAIL_H)
    try:
        # FreeCAD edge index: find top long edges (Z = RAIL_H, parallel to X)
        edges = []
        for i, e in enumerate(box.Edges):
            v1, v2 = e.Vertexes[0].Point, e.Vertexes[1].Point
            if abs(v1.z - RAIL_H) < 1e-6 and abs(v2.z - RAIL_H) < 1e-6:
                if abs(v1.x - v2.x) > length * 0.5:  # long edge
                    edges.append(i + 1)  # 1-based for makeChamfer in some APIs
        if edges and CHAMFER > 0:
            # Part.Shape.makeChamfer takes radius and list of edges (Edge objects)
            edge_objs = [box.Edges[i - 1] for i in edges]
            box = box.makeChamfer(CHAMFER, edge_objs)
    except Exception:
        pass  # keep plain box if chamfer fails
    return box


def _bracket_shape():
    """Simple stirrup / post-support: base plate + open-top U around the rail underside.

    Sits on the deck; uprights rise RAIL_CLEAR, then short cheeks beside the rail.
    Flood-friendly: open under the rail (water passes through the 175 mm gap).
    """
    bp = Part.makeBox(BRACKET_BASE, BRACKET_BASE, BRACKET_BASE_T)
    # Centre the assembly on X=0, Y=0 of the bracket local frame; base from z=0
    bp.translate(App.Vector(-BRACKET_BASE / 2, -BRACKET_BASE / 2, 0))

    # Two upright cheeks under the rail edges (Y), rising through clearance into rail height
    cheek_t = 8.0
    cheek_h = RAIL_CLEAR + RAIL_H * 0.6
    cheek_x = BRACKET_SHS  # length along rail
    # Cheeks sit just outside the rail width, so clear gap between cheeks = RAIL_W
    y_out = RAIL_W / 2 + cheek_t
    c1 = Part.makeBox(cheek_x, cheek_t, cheek_h)
    c1.translate(App.Vector(-cheek_x / 2, -y_out, BRACKET_BASE_T))
    c2 = Part.makeBox(cheek_x, cheek_t, cheek_h)
    c2.translate(App.Vector(-cheek_x / 2, RAIL_W / 2, BRACKET_BASE_T))
    # Cross bar under the rail (at z = RAIL_CLEAR) — the seat
    seat_t = 8.0
    seat = Part.makeBox(cheek_x, RAIL_W, seat_t)
    seat.translate(App.Vector(-cheek_x / 2, -RAIL_W / 2, RAIL_CLEAR))
    return bp.fuse(c1).fuse(c2).fuse(seat)


def _anchor_shape():
    """M12 chemical anchor stub into the deck (visual only)."""
    cyl = Part.makeCylinder(ANCHOR_D / 2, ANCHOR_EMBED)
    return cyl


def _opening_span(rail_l):
    """Clear opening between rock-wall ends = rail + 100 mm each side."""
    return rail_l + 2 * GAP


def _deck_length(rail_l, n_per_side):
    """Wall stubs + openings along the bridge length."""
    n_open = n_per_side
    n_stubs = n_open + 1
    return n_stubs * WALL_STUB + n_open * _opening_span(rail_l)


def _add_bridge(doc, tag, rail_l, n_per_side, origin_x):
    """Build one bridge group at world X = origin_x (deck starts there).

    Coordinate frame:
      X = along the road / bridge length
      Y = across the deck (0 at deck centre)
      Z = up (0 at top of pavement / deck top)
    Deck occupies z = -DECK_T .. 0.
    Rock walls sit on the deck, centred on each kerb line.
    Rails sit on each kerb line, raised RAIL_CLEAR above pavement.
    """
    group = doc.addObject("App::DocumentObjectGroup", tag.replace(" ", "_"))
    group.Label = tag

    deck_l = _deck_length(rail_l, n_per_side)
    # Deck: full length x DECK_W, thickness down
    _box(
        doc,
        f"{tag}_DECK".replace(" ", "_"),
        deck_l,
        DECK_W,
        DECK_T,
        (origin_x, -DECK_W / 2, -DECK_T),
        COL_DECK,
        group,
    )

    # Kerb lines: outside face of wall flush with deck edge
    # Wall centred so outer face at y = ±DECK_W/2
    y_wall_c = [
        DECK_W / 2 - WALL_W / 2,   # +Y kerb (right when looking +X)
        -(DECK_W / 2 - WALL_W / 2),  # -Y kerb
    ]

    rail_names = []
    bracket_count = 0
    open_span = _opening_span(rail_l)

    for side_i, yc in enumerate(y_wall_c):
        side = "R" if side_i == 0 else "L"
        x = origin_x
        # Leading wall stub
        for oi in range(n_per_side + 1):
            _box(
                doc,
                f"{tag}_WALL_{side}_{oi}".replace(" ", "_"),
                WALL_STUB,
                WALL_W,
                WALL_H,
                (x, yc - WALL_W / 2, 0),
                COL_WALL,
                group,
            )
            x += WALL_STUB
            if oi < n_per_side:
                # Opening then rail centred in it (100 mm gap each end)
                rail_x0 = x + GAP
                shp = _rail_shape(rail_l)
                # Rail centred on kerb line (yc)
                shp.translate(App.Vector(rail_x0, yc - RAIL_W / 2, RAIL_CLEAR))
                rname = f"{tag}_RAIL_{side}_{oi+1}".replace(" ", "_")
                robj = doc.addObject("Part::Feature", rname)
                robj.Shape = shp
                if hasattr(robj, "ViewObject") and robj.ViewObject is not None:
                    robj.ViewObject.ShapeColor = COL_RAIL
                group.addObject(robj)
                rail_names.append(rname)

                # Two proposed brackets per rail, ~L/5 from each end
                for end, sign in (("A", 1), ("B", -1)):
                    if end == "A":
                        bx = rail_x0 + BRACKET_FROM_END_FRAC * rail_l
                    else:
                        bx = rail_x0 + rail_l - BRACKET_FROM_END_FRAC * rail_l
                    bshp = _bracket_shape()
                    bshp.translate(App.Vector(bx, yc, 0))
                    bname = f"{tag}_BRK_{side}_{oi+1}_{end}".replace(" ", "_")
                    bobj = doc.addObject("Part::Feature", bname)
                    bobj.Shape = bshp
                    if hasattr(bobj, "ViewObject") and bobj.ViewObject is not None:
                        bobj.ViewObject.ShapeColor = COL_STEEL
                    group.addObject(bobj)
                    bracket_count += 1

                    # Two M12 chemical anchors per bracket base (visual)
                    for ay in (-BRACKET_BASE * 0.3, BRACKET_BASE * 0.3):
                        ash = _anchor_shape()
                        # Anchor goes down into deck from z=0
                        ash.translate(App.Vector(bx, yc + ay, -ANCHOR_EMBED))
                        aname = f"{tag}_ANC_{side}_{oi+1}_{end}_{'P' if ay>0 else 'M'}".replace(" ", "_")
                        aobj = doc.addObject("Part::Feature", aname)
                        aobj.Shape = ash
                        if hasattr(aobj, "ViewObject") and aobj.ViewObject is not None:
                            aobj.ViewObject.ShapeColor = COL_ANCHOR
                        group.addObject(aobj)

                x += open_span

    return {
        "group": group,
        "deck_l": deck_l,
        "rail_l": rail_l,
        "n_per_side": n_per_side,
        "n_rails": n_per_side * 2,
        "rail_names": rail_names,
        "brackets": bracket_count,
        "origin_x": origin_x,
    }


def build_model():
    out = exports_dir()
    name = "Bridge_Rails"
    if name in App.listDocuments():
        App.closeDocument(name)
    doc = App.newDocument(name)

    info1 = _add_bridge(doc, "Bridge_1", B1_RAIL_L, B1_N_PER_SIDE, 0.0)
    # Park Bridge 2 further along +Y offset so both fit in one view
    # Place Bridge 2 along X after Bridge 1 with a gap, same Y
    gap_between = 2000.0
    info2 = _add_bridge(
        doc,
        "Bridge_2",
        B2_RAIL_L,
        B2_N_PER_SIDE,
        info1["deck_l"] + gap_between,
    )

    doc.recompute()
    fcstd = os.path.join(out, "Bridge_Rails.FCStd")
    doc.saveAs(fcstd)
    print("SAVED", fcstd)
    return doc, {"B1": info1, "B2": info2, "out": out, "fcstd": fcstd}


# ---------------------------------------------------------------------------
# Fabrication drawing + previews (matplotlib; works headless)
# ---------------------------------------------------------------------------
def _draw_fabrication(info, out_dir):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, Polygon, FancyArrowPatch
    from matplotlib.lines import Line2D

    pdf_path = os.path.join(out_dir, "Bridge_Rails_fabrication.pdf")
    png_path = os.path.join(out_dir, "Bridge_Rails_fabrication.png")

    fig = plt.figure(figsize=(16.54, 11.69), dpi=150)  # A3 landscape inches
    fig.suptitle(
        "Laguna Quays — Bridge Timber Rail Inserts  |  Fabrication drawing for carpenter",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    fig.text(
        0.5,
        0.955,
        "Prepared for Christine, Body Corporate Chairperson  ·  Client: Paul Cahill  ·  Not for structural certification",
        ha="center",
        fontsize=9,
        color="#444",
    )

    # --- helpers ---
    def dim_h(ax, x0, x1, y, text, side=1, offset=120):
        ax.annotate(
            "",
            xy=(x0, y + side * offset),
            xytext=(x1, y + side * offset),
            arrowprops=dict(arrowstyle="<->", color="#222", lw=0.8),
        )
        ax.text(
            (x0 + x1) / 2,
            y + side * offset + side * 60,
            text,
            ha="center",
            va="bottom" if side > 0 else "top",
            fontsize=7,
            color="#222",
        )
        ax.plot([x0, x0], [y, y + side * offset], color="#222", lw=0.5)
        ax.plot([x1, x1], [y, y + side * offset], color="#222", lw=0.5)

    def dim_v(ax, y0, y1, x, text, side=1, offset=120):
        ax.annotate(
            "",
            xy=(x + side * offset, y0),
            xytext=(x + side * offset, y1),
            arrowprops=dict(arrowstyle="<->", color="#222", lw=0.8),
        )
        ax.text(
            x + side * offset + side * 40,
            (y0 + y1) / 2,
            text,
            ha="left" if side > 0 else "right",
            va="center",
            fontsize=7,
            color="#222",
            rotation=90 if False else 0,
        )
        ax.plot([x, x + side * offset], [y0, y0], color="#222", lw=0.5)
        ax.plot([x, x + side * offset], [y1, y1], color="#222", lw=0.5)

    # ===================== Plan: Bridge 1 one edge =====================
    ax1 = fig.add_axes([0.04, 0.62, 0.45, 0.28])
    ax1.set_title("Bridge 1 — plan of one deck edge (2 openings)", fontsize=10, loc="left")
    _plan_edge(ax1, B1_RAIL_L, B1_N_PER_SIDE, dim_h)

    # ===================== Plan: Bridge 2 one edge =====================
    ax2 = fig.add_axes([0.52, 0.62, 0.45, 0.28])
    ax2.set_title("Bridge 2 — plan of one deck edge (1 opening)", fontsize=10, loc="left")
    _plan_edge(ax2, B2_RAIL_L, B2_N_PER_SIDE, dim_h)

    # ===================== Elevation of one rail =====================
    ax3 = fig.add_axes([0.04, 0.30, 0.45, 0.26])
    ax3.set_title(
        "Elevation — one rail in opening (Bridge 1 shown; Bridge 2 same section, L=3600)",
        fontsize=10,
        loc="left",
    )
    _elevation(ax3, B1_RAIL_L, dim_h, dim_v)

    # ===================== Cross section =====================
    ax4 = fig.add_axes([0.52, 0.30, 0.22, 0.26])
    ax4.set_title("Rail cross-section + proposed bracket", fontsize=10, loc="left")
    _section(ax4, dim_v)

    # ===================== Cut list =====================
    ax5 = fig.add_axes([0.76, 0.30, 0.21, 0.26])
    ax5.set_axis_off()
    ax5.set_title("Cut list & hardware", fontsize=10, loc="left")
    cut = [
        "TIMBER RAILS  (section 300 W × 200 H,",
        "  laid flat — see note)",
        "  Bridge 1:  4 × 2150 mm",
        "  Bridge 2:  2 × 3600 mm",
        "  Total:     6 rails",
        "",
        "PROPOSED FIXINGS (confirm on site)",
        "  Brackets:  2 per rail → 12 total",
        "    HDG steel stirrup / post support",
        "    ~100×100 seat, base plate 150 sq",
        "  Anchors:   2 × M12 chemical / bracket",
        "    → 24 × M12 into concrete deck",
        "  Bolts:     2 × M12 HDG coach or",
        "    through-bolt per bracket → 24",
        "",
        "Timber: H4 treated hardwood / pine,",
        "  or Class 1 hardwood (e.g. spotted gum).",
        "  Chamfer top long edges ~15 mm.",
    ]
    ax5.text(0.0, 0.98, "\n".join(cut), va="top", ha="left", fontsize=7.5, family="monospace",
             transform=ax5.transAxes, linespacing=1.25)

    # ===================== Notes =====================
    ax6 = fig.add_axes([0.04, 0.04, 0.92, 0.22])
    ax6.set_axis_off()
    ax6.set_title("Notes & assumptions", fontsize=10, loc="left")
    notes = [
        "SECTION ASSUMED 300 W × 200 H laid flat so 175 mm clearance + 200 mm rail = 375 mm top, just below the 400 mm rock wall. "
        "The brief states H 0.3 × W 0.2; if the section is stood on the 300 edge instead, the top would be 475 mm (above the wall). CONFIRM with Christine / carpenter before cutting.",
        "Gap rock-wall ↔ timber = 100 mm each end → opening = rail length + 200 mm (Bridge 1: 2350 mm; Bridge 2: 3800 mm).",
        "Bridge 1: 4 rails (2 openings per side). Bridge 2: 2 rails (1 opening per side). Matches brief totals; photos show stone kerb walls with breaks over the concrete deck.",
        "Deck width assumed 4000 mm kerb-outside to kerb-outside (not stated in brief). Rock-wall stubs modelled at 1000 mm long × 400 × 400; actual stub lengths follow existing stonework on site.",
        "Fixings are PROPOSED only (not in brief): 2 HDG brackets per rail at ~L/5 from each end; M12 chemical anchors to deck; M12 HDG coach/through-bolts through rail. Flood-friendly: open 175 mm under rail for water to clear. Confirm embedment & edge distances with installer.",
        "Model file: exports/Bridge_Rails.FCStd  ·  Groups: Bridge_1, Bridge_2  ·  All dimensions in millimetres.",
    ]
    y = 0.88
    for i, n in enumerate(notes, 1):
        ax6.text(0.0, y, f"{i}.  {n}", va="top", ha="left", fontsize=7.2, wrap=True,
                 transform=ax6.transAxes)
        y -= 0.155

    fig.text(0.99, 0.01, "A3 landscape  ·  mm  ·  Laguna Quays bridge inserts", ha="right", fontsize=7, color="#666")

    fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
    fig.savefig(png_path, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print("SAVED", pdf_path)
    print("SAVED", png_path)
    return pdf_path, png_path


def _plan_edge(ax, rail_l, n_per_side, dim_h):
    from matplotlib.patches import Rectangle

    open_span = rail_l + 2 * GAP
    deck_l = (n_per_side + 1) * WALL_STUB + n_per_side * open_span
    # Strip of deck along edge
    ax.add_patch(Rectangle((0, -200), deck_l, 600, facecolor="#d8d8d4", edgecolor="#666", lw=0.6))
    x = 0
    for oi in range(n_per_side + 1):
        ax.add_patch(Rectangle((x, 0), WALL_STUB, WALL_W, facecolor="#9a8870", edgecolor="#444", lw=0.7))
        ax.text(x + WALL_STUB / 2, WALL_W / 2, "rock\nwall", ha="center", va="center", fontsize=6, color="#333")
        x += WALL_STUB
        if oi < n_per_side:
            # gaps + rail
            ax.plot([x, x + GAP], [WALL_W / 2, WALL_W / 2], color="#aaa", lw=0.5, ls="--")
            ax.add_patch(
                Rectangle((x + GAP, (WALL_W - RAIL_W) / 2), rail_l, RAIL_W,
                          facecolor="#c48a4a", edgecolor="#5a3a1a", lw=0.8)
            )
            ax.text(x + GAP + rail_l / 2, WALL_W / 2, f"RAIL\n{rail_l:.0f}", ha="center", va="center", fontsize=7, color="#2a1a0a")
            # bracket marks
            for bx in (x + GAP + BRACKET_FROM_END_FRAC * rail_l,
                       x + GAP + rail_l - BRACKET_FROM_END_FRAC * rail_l):
                ax.add_patch(Rectangle((bx - 50, (WALL_W - RAIL_W) / 2 - 20), 100, RAIL_W + 40,
                                       fill=False, edgecolor="#2f5a3a", lw=1.0, ls="--"))
            # gap dims
            dim_h(ax, x, x + GAP, -50, "100", side=-1, offset=80)
            dim_h(ax, x + GAP, x + GAP + rail_l, -50, f"{rail_l:.0f}", side=-1, offset=80)
            dim_h(ax, x + GAP + rail_l, x + open_span, -50, "100", side=-1, offset=80)
            dim_h(ax, x, x + open_span, WALL_W + 40, f"opening {open_span:.0f}", side=1, offset=100)
            x += open_span

    ax.set_xlim(-200, deck_l + 200)
    ax.set_ylim(-450, WALL_W + 350)
    ax.set_aspect("equal")
    ax.set_xlabel("along bridge (mm)", fontsize=7)
    ax.tick_params(labelsize=6)


def _elevation(ax, rail_l, dim_h, dim_v):
    from matplotlib.patches import Rectangle

    open_span = rail_l + 2 * GAP
    # pavement line
    ax.axhline(0, color="#444", lw=1.0)
    ax.text(-80, -30, "pavement", fontsize=6, color="#444", ha="right")
    # wall stubs left/right
    ax.add_patch(Rectangle((-WALL_STUB, 0), WALL_STUB, WALL_H, facecolor="#9a8870", edgecolor="#444", lw=0.7))
    ax.add_patch(Rectangle((open_span, 0), WALL_STUB, WALL_H, facecolor="#9a8870", edgecolor="#444", lw=0.7))
    ax.text(-WALL_STUB / 2, WALL_H / 2, "rock\nwall\n400", ha="center", va="center", fontsize=6)
    ax.text(open_span + WALL_STUB / 2, WALL_H / 2, "rock\nwall\n400", ha="center", va="center", fontsize=6)
    # rail
    ax.add_patch(Rectangle((GAP, RAIL_CLEAR), rail_l, RAIL_H, facecolor="#c48a4a", edgecolor="#5a3a1a", lw=0.9))
    ax.text(GAP + rail_l / 2, RAIL_CLEAR + RAIL_H / 2, f"timber rail  {rail_l:.0f} L × {RAIL_W:.0f} W × {RAIL_H:.0f} H",
            ha="center", va="center", fontsize=7)
    # brackets (proposed)
    for bx in (GAP + BRACKET_FROM_END_FRAC * rail_l, GAP + rail_l - BRACKET_FROM_END_FRAC * rail_l):
        ax.add_patch(Rectangle((bx - 50, 0), 100, RAIL_CLEAR + 8, facecolor="#6a8070", edgecolor="#2f5a3a", lw=0.8))
        ax.text(bx, 40, "brk", ha="center", fontsize=6, color="#fff")
    # water arrow
    ax.annotate("water clears", xy=(GAP + rail_l / 2, RAIL_CLEAR / 2),
                xytext=(GAP + rail_l / 2, RAIL_CLEAR / 2),
                fontsize=6, color="#2a5a8a", ha="center", va="center",
                fontstyle="italic")
    ax.plot([GAP + 200, GAP + rail_l - 200], [RAIL_CLEAR / 2, RAIL_CLEAR / 2], color="#2a5a8a", lw=0.7, ls=":")

    # dims
    dim_h(ax, GAP, GAP + rail_l, RAIL_TOP, f"{rail_l:.0f}", side=1, offset=80)
    dim_h(ax, 0, GAP, -20, "100", side=-1, offset=100)
    dim_h(ax, GAP + rail_l, open_span, -20, "100", side=-1, offset=100)
    dim_v(ax, 0, RAIL_CLEAR, -40, "175", side=-1, offset=100)
    dim_v(ax, 0, RAIL_TOP, open_span + WALL_STUB + 40, "375 top", side=1, offset=80)
    dim_v(ax, 0, WALL_H, open_span + WALL_STUB + 40, "400 wall", side=1, offset=220)

    ax.set_xlim(-WALL_STUB - 350, open_span + WALL_STUB + 450)
    ax.set_ylim(-280, WALL_H + 280)
    ax.set_aspect("equal")
    ax.set_ylabel("mm", fontsize=7)
    ax.tick_params(labelsize=6)


def _section(ax, dim_v):
    from matplotlib.patches import Rectangle, FancyBboxPatch

    # deck
    ax.add_patch(Rectangle((-300, -DECK_T), 600, DECK_T, facecolor="#d8d8d4", edgecolor="#666", lw=0.6))
    # bracket base
    ax.add_patch(Rectangle((-BRACKET_BASE / 2, 0), BRACKET_BASE, BRACKET_BASE_T, facecolor="#6a8070", edgecolor="#2f5a3a", lw=0.7))
    # cheeks
    cheek_t = 8
    cheek_h = RAIL_CLEAR + RAIL_H * 0.6
    ax.add_patch(Rectangle((-RAIL_W / 2 - cheek_t, BRACKET_BASE_T), cheek_t, cheek_h - BRACKET_BASE_T,
                           facecolor="#6a8070", edgecolor="#2f5a3a", lw=0.7))
    ax.add_patch(Rectangle((RAIL_W / 2, BRACKET_BASE_T), cheek_t, cheek_h - BRACKET_BASE_T,
                           facecolor="#6a8070", edgecolor="#2f5a3a", lw=0.7))
    # seat
    ax.add_patch(Rectangle((-RAIL_W / 2, RAIL_CLEAR), RAIL_W, 8, facecolor="#6a8070", edgecolor="#2f5a3a", lw=0.7))
    # rail
    ax.add_patch(Rectangle((-RAIL_W / 2, RAIL_CLEAR), RAIL_W, RAIL_H, facecolor="#c48a4a", edgecolor="#5a3a1a", lw=0.9))
    # bolts through rail (dots)
    ax.plot([-RAIL_W / 4, RAIL_W / 4], [RAIL_CLEAR + RAIL_H / 2, RAIL_CLEAR + RAIL_H / 2],
            "o", color="#333", markersize=4)
    ax.text(0, RAIL_CLEAR + RAIL_H / 2 + 35, "2×M12", ha="center", fontsize=6)
    # anchors
    ax.plot([-BRACKET_BASE * 0.3, BRACKET_BASE * 0.3], [-ANCHOR_EMBED / 2, -ANCHOR_EMBED / 2],
            "s", color="#333", markersize=3)
    ax.text(0, -DECK_T - 30, "M12 chem. anchors (proposed)", ha="center", fontsize=6, color="#333")

    ax.text(0, RAIL_CLEAR + RAIL_H + 40, f"{RAIL_W:.0f} W × {RAIL_H:.0f} H", ha="center", fontsize=7)
    dim_v(ax, 0, RAIL_CLEAR, RAIL_W / 2 + cheek_t + 20, "175", side=1, offset=60)
    dim_v(ax, 0, RAIL_TOP, -RAIL_W / 2 - cheek_t - 20, "375", side=-1, offset=60)

    ax.set_xlim(-350, 350)
    ax.set_ylim(-DECK_T - 80, RAIL_TOP + 120)
    ax.set_aspect("equal")
    ax.tick_params(labelsize=6)


def _iso_preview(doc, out_dir):
    """Tessellate shapes and draw a simple isometric-ish matplotlib 3D preview."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np

    path = os.path.join(out_dir, "Bridge_Rails_iso.png")
    fig = plt.figure(figsize=(12, 7), dpi=140)
    ax = fig.add_subplot(111, projection="3d")

    def add_shape(shape, colour, alpha=1.0):
        try:
            tris = shape.tessellate(5.0)  # (points, triangles)
        except Exception:
            return
        pts = np.array([[p.x, p.y, p.z] for p in tris[0]])
        if len(pts) == 0:
            return
        faces = []
        for t in tris[1]:
            faces.append(pts[list(t)])
        if not faces:
            return
        coll = Poly3DCollection(faces, alpha=alpha)
        coll.set_facecolor(colour)
        coll.set_edgecolor((0.2, 0.2, 0.2, 0.15))
        coll.set_linewidth(0.1)
        ax.add_collection3d(coll)

    colour_map = {
        "DECK": COL_DECK,
        "WALL": COL_WALL,
        "RAIL": COL_RAIL,
        "BRK": COL_STEEL,
        "ANC": COL_ANCHOR,
    }
    # Only Bridge 1 for a readable iso (Bridge 2 is similar); include both lightly
    for obj in doc.Objects:
        if not hasattr(obj, "Shape") or obj.Shape.isNull():
            continue
        name = obj.Name
        col = COL_DECK
        alpha = 1.0
        for key, c in colour_map.items():
            if key in name:
                col = c
                break
        if "ANC" in name:
            alpha = 0.7
        if name.startswith("Bridge_2"):
            # skip Bridge 2 in iso to keep one clear view; model still has both
            continue
        add_shape(obj.Shape, col, alpha)

    # Bounds for Bridge 1
    deck_l = _deck_length(B1_RAIL_L, B1_N_PER_SIDE)
    ax.set_xlim(0, deck_l)
    ax.set_ylim(-DECK_W / 2 - 200, DECK_W / 2 + 200)
    ax.set_zlim(-DECK_T, WALL_H + 50)
    try:
        ax.set_box_aspect((deck_l, DECK_W + 400, WALL_H + DECK_T + 50))
    except Exception:
        pass
    ax.view_init(elev=28, azim=-55)
    ax.set_xlabel("along (mm)", fontsize=7)
    ax.set_ylabel("across (mm)", fontsize=7)
    ax.set_zlabel("up (mm)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title("Bridge 1 — 3D model preview (rails + proposed brackets)", fontsize=11)
    fig.text(0.5, 0.02, "Bridge 2 is in the same FCStd (group Bridge_2); same section, L=3600, 1 opening per side",
             ha="center", fontsize=8, color="#444")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print("SAVED", path)
    return path


def main():
    doc, info = build_model()
    out = info["out"]
    _draw_fabrication(info, out)
    try:
        _iso_preview(doc, out)
    except Exception as e:
        print("ISO preview failed:", e)
    # Keep document open when run as a GUI macro; close only headless if desired
    print("DONE exports in", out)
    print("KEY dims: rail section", RAIL_W, "W x", RAIL_H, "H; clear", RAIL_CLEAR, "; top", RAIL_TOP,
          "; wall", WALL_W, "x", WALL_H, "; gaps", GAP, "; deck W assumed", DECK_W)
    print("B1:", info["B1"]["n_rails"], "rails x", info["B1"]["rail_l"], "deck L", info["B1"]["deck_l"])
    print("B2:", info["B2"]["n_rails"], "rails x", info["B2"]["rail_l"], "deck L", info["B2"]["deck_l"])
    return info


# FreeCAD macros are exec'd as a script; run main unless BRIDGE_RAILS_NO_AUTO=1
if os.environ.get("BRIDGE_RAILS_NO_AUTO") != "1":
    main()
