#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
siser_hpgl.py

Turns flattened cut/score/draw point lists into an HPGL command stream
for the Siser cutter, including per-tool speed/pressure setup and the
ContourCut ("TB"/"CT1") registration-mark preamble.

Siser uses a different coordinate convention from normal SVG/HPGL -
this is the ONE thing this module changes from skycut_c_hpgl.py
(everything else - settings-per-tool structure, emission order, etc.
- is unchanged):
SVG:
    X right, Y down

Siser HPGL (bottom-left origin, 90-degree rotation - NOT SkyCut's
swap+invert):
    hpgl_x = max_y - y        (left -> right)
    hpgl_y = x - min_x         (bottom -> top)

For comparison, SkyCut's convention (skycut_c_hpgl.py) swaps AND
inverts both axes, anchored to the reference box's bottom-RIGHT
corner:
    hpgl_x = max_y - y
    hpgl_y = max_x - x

Siser's formula is anchored to the reference box's bottom-LEFT corner
instead - machine (0,0) is always at SVG (min_x, max_y), for every
cut_mode (wysiwyg/origin/contourcut) consistently. This is fully
box-relative the same way SkyCut's is, just mirrored to the other
corner - both `min_x` and `max_y` come from the actual reference box
computed in siser_reference.py, not from an assumption that the
artwork/page/marks happen to start at SVG x=0.

(An earlier version of this file used `hpgl_y = x` directly, matching
the old sisercommand_cut_score_contour_S1.py script exactly - that
only produced a true bottom-left origin when the reference box's own
min_x happened to be 0, e.g. Origin mode with artwork not flush
against the document's left edge would be offset. Threading min_x
through fixes that for every mode.)

Settings (speed/pressure/offset/overcut) live per PHYSICAL TOOL rather
than per operation - each tool is independently assigned to work the
Full Cut layer, the Kiss Cut layer, the Crease layer, the Draw layer,
or nothing (None). A "side" here is a dict with keys:
    side      - a name for this physical tool, e.g. "left"/"right" (two-
                tool machines) or "tool" (single-tool machines)
    kind      - "cut" | "score" | "draw" | "crease" | "none"
    paths     - list of (pts, kind) tuples, already run through
                build_cut_path with this tool's offset/overcut
    up_speed, speed, pressure, offset - this tool's settings

Emission order is simply the order `sides` is passed in - callers
with more than one tool (e.g. Operation Mode's Left/Right ordering)
decide that order themselves before calling in; a tool whose kind is
"none" is always skipped regardless of position.
"""

from siser_constants import SCALE


def emit_polyline(hpgl, pts, min_x, max_y, scale=SCALE):
    """
    Append U/D HPGL commands for one polyline.

    Applies Siser coordinate conversion, anchored to the reference
    box's bottom-left corner (min_x, max_y) - see module docstring.

    pts have already been through build_cut_path() (see
    siser_pathbuild.py), which is where knife/score offset actually
    gets applied - as direction-aware overshoot/return excursions at
    each corner, matching a swiveling drag-knife's real behavior
    (blade trails behind the pivot along the current direction of
    travel). On straight runs between corners that trailing model
    needs no correction at all, so no offset is applied here - doing
    so a second time distorted the corner geometry that build_cut_path
    already places precisely.
    """
    for i, (x, y) in enumerate(pts):
        hpgl_x = max_y - y      # rotate 90 deg CCW: machine X (left -> right)
        hpgl_y = x - min_x       # machine Y (bottom -> top), box-relative

        hpgl.append(
            ("U" if i == 0 else "D") +
            f"{int(round(hpgl_x * scale))},{int(round(hpgl_y * scale))};"
        )


def _tool_command(side):
    """
    Siser tool-select command: P0 selects the primary/left tool head,
    P1 selects the right tool head. Selected per-block (each tool can
    be doing different work), rather than once globally - so each
    tool's settings actually take effect independently. Single-tool
    setups (side name anything other than "right") always get P0.
    """
    return "P0;" if side != "right" else "P1;"


def _rounded_points_natural(pts, scale=SCALE):
    """
    Same HPGL-unit rounding as the real output, but WITHOUT the
    Siser axis-swap conversion.

    The physical cutter needs the swap (Siser's X/Y differ from
    other cutters), but that's a machine-orientation detail, not
    something the person looking at the viewer needs to mentally
    undo - the viewer shows the artwork in its natural Inkscape
    orientation instead. Corner overshoots, overcuts, offset (already
    baked into pts via build_cut_path), and rounding all still match
    the real output exactly - only the final swap step (a display/
    machine-orientation concern, not a geometry one) is skipped here.
    """
    out = []
    for x, y in pts:
        out.append((
            round(x * scale) / scale,
            round(y * scale) / scale,
        ))
    return out


def _emit_side_block(hpgl, side_data, min_x, max_y, scale=SCALE):
    hpgl.append(_tool_command(side_data["side"]))
    hpgl.extend([
        f"US{side_data['up_speed']};",
        f"VS{side_data['speed']};",
        f"!FS{side_data['pressure']};",
    ])
    for pts, _kind in side_data["paths"]:
        emit_polyline(hpgl, pts, min_x, max_y, scale)


def build_render_segments(sides, options, scale=SCALE):
    """
    Build viewer geometry in natural (unrotated) Inkscape orientation.

    The real HPGL output (assemble_hpgl/emit_polyline) still applies
    Siser's axis-swap conversion, since the physical cutter needs
    it. The viewer intentionally does NOT apply that swap - it shows
    the artwork the way it looks in Inkscape, so what's on screen is
    recognizable at a glance, while offsets/overcuts/corner handling
    still match the real output exactly.

    Emits in the order `sides` is given - a tool with kind "none" is
    always skipped.
    """
    segments = []
    for s in sides:
        if s["kind"] == "none":
            continue
        for pts, _k in s["paths"]:
            segments.append({
                "kind": s["kind"],
                "side": s["side"],
                "points": _rounded_points_natural(pts, scale),
            })
    return segments


def assemble_hpgl(sides, options, min_x, min_y, max_x, max_y, scale=SCALE):
    """
    Build complete HPGL stream for Siser.

    `sides` is the list of per-tool dicts described at the top of
    this module (one entry per physical side that has geometry to
    emit).
    """

    hpgl = ["IN;"]

    if options.cut_mode == "contourcut":
        width_units = int(round((max_x - min_x) * scale))
        height_units = int(round((max_y - min_y) * scale))

        hpgl.append(
            f"TB26,{height_units},{width_units};"
        )
        hpgl.append("CT1;")

    hpgl.append("PA;")

    for s in sides:
        if s["kind"] == "none":
            continue
        _emit_side_block(hpgl, s, min_x, max_y, scale)

    hpgl.extend([
        "U0,0;",
        "@;"
    ])

    if options.cut_mode == "contourcut":
        hpgl.append("@;")

    return "\n".join(hpgl)
