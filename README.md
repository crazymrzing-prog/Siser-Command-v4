# Siser Command v4

An Inkscape extension for sending cut/score/crease/draw jobs from Inkscape directly to a Siser vinyl cutter — over WiFi, over USB, or saved to a `.plt` file — with a built-in HPGL preview viewer, registration-mark generation for print-and-cut workflows, and one-click layer setup.

Ported from a SkyCut Command Model C3 extension, keeping the same modular architecture and tool model. The only functional change from SkyCut is the coordinate conversion in `siser_hpgl.py` — Siser cutters use a different origin/rotation convention than SkyCut.

## Features

- **Single-tool model** — one physical tool head, no tool-changing routine. A single "Tool" selection picks which layer(s) get sent, and the matching speed/pressure settings (Blade or Pen/Crease) are applied automatically.
- **Full Cut & Kiss Cut combo** — run both in one job, one blade, no re-initializing the cutter in between.
- **Three cut/reference modes** — Origin Point (bounding box of the artwork), WYSIWYG (the SVG page), and Contour Cut (registration marks, for aligning a cut to a separately printed sheet).
- **Knife-offset compensation** — corner overshoot/return loops and a final overcut, matching a swiveling drag-knife's real behavior.
- **HPGL preview viewer** — inspect the exact toolpath, in natural (unrotated) orientation, before sending anything to the machine.
- **Registration mark generation** — L-shaped corner marks plus an orientation indicator, offset from your artwork or inset from the page.
- **One-click layer setup** — creates/refreshes the standard Full Cut / Kiss Cut / Crease / Draw / Print / Marks layers with the correct names and colors.
- **Three delivery options** — send over WiFi (TCP), send over USB (Windows only), or save a `.plt` file to disk.
- **Automatic shape-to-path conversion** — rectangles, circles, ellipses, polygons, and lines drawn with Inkscape's shape tools aren't `<svg:path>` elements, so they'd otherwise be silently skipped when cutting. Every run scans all four source layers for these and converts them to paths automatically (the same result as **Path → Object to Path**), then stops so you can check the result on the canvas before sending the job.

## Requirements

- Inkscape 1.x (uses the `inkex` Python API)
- Python 3 (the interpreter bundled with Inkscape)
- Windows, if using **Send to Machine USB** (uses `ctypes`/SetupAPI/kernel32 — no third-party dependencies)
- `tkinter` (ships with Inkscape's bundled Python on Windows) for the USB device picker; USB sending falls back to a non-interactive path if it isn't available

No external Python packages are required — everything besides `inkex` itself is standard library.

## Installation

1. Copy every file in this repo into your Inkscape user extensions folder:
   - **Windows:** `%APPDATA%\inkscape\extensions\`
   - **macOS:** `~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/`
   - **Linux:** `~/.config/inkscape/extensions/`
2. Restart Inkscape.
3. The extension appears under **Extensions → Siser Command v4**.

## Usage

### 1. Set up your layers

Run **Extensions → Siser Command v4** with **Action** set to **Layer Setup**. This creates (or refreshes the color/style of) six standard layers:

```
Marks
Print
Full Cut
Kiss Cut
Crease
Draw
```

Draw your artwork into whichever of `Full Cut`, `Kiss Cut`, `Crease`, or `Draw` matches the operation you want (layer names are matched case-insensitively).

### 2. Choose a Tool and Cut Mode

- **Tool** selects which layer(s) this run sends: Full Cut, Kiss Cut, Full Cut & Kiss Cut (combo), Crease Tool, Draw, or None.
- **Cut Mode** selects the reference box machine `(0,0)` is measured from — it doesn't change what gets cut, only where it lands on the material:
  - **Origin Point** — bounding box of the artwork itself; the page is ignored.
  - **WYSIWYG** — the SVG page; artwork position on the page is preserved on the material.
  - **Contour Cut** — four registration marks in a `Marks` layer; used for aligning a cut to a separately printed sheet. Run **Action → Add Marks** first to generate these.

### 3. Adjust tool settings

- **Blade Tool Settings** — separate pressure for Full Cut vs. Kiss Cut, shared speed/up-speed, offset (knife compensation), overcut, and passes.
- **Pen / Crease Tool Settings** — same shape of settings for the Crease and Draw passes. Offset should normally stay at `0` here — the extension warns (without blocking the job) if it isn't.

### 4. Pick an Action

| Action | What it does |
|---|---|
| Send to Machine Wifi | Sends the job to the cutter over TCP (IP Address / Port) |
| Send to Machine USB | Sends the job directly over USB (Windows only) |
| Save PLT File Only | Writes the job to a timestamped `.plt` file under `~/Documents/Skycut Data` |
| Preview Path | Opens the HPGL preview viewer (standalone window, falling back to a browser tab) |
| Preview Path in Web Browser | Same viewer, always opened in a browser tab |
| Layer Setup | Creates/refreshes the standard layers only — nothing is cut |
| Add Marks | Replaces the `Marks` layer with fresh registration marks, using the settings below it — nothing is cut |

### Adding registration marks

With **Action** set to **Add Marks**, configure:

- **Mark Placement** — *Offset from Objects* (marks sit outside the bounding box of every vector object) or *Inset from Page Border* (marks sit inside the page edge).
- **Offset / Inset (mm)**, **Mark Arm Length (mm)**, **Stroke Width (mm)**.

This writes a fresh, locked `Marks` layer that **Contour Cut** mode reads from.

## File overview

| File | Purpose |
|---|---|
| `siser_command_v4.py` | Inkscape entry point / effect class — wires every module below together |
| `siser_command_v4.inx` | Inkscape UI definition (parameters, tabs, help text) |
| `siser_constants.py` | Shared master switches and numeric constants |
| `siser_geometry.py` | Pure 2D vector math and cubic-Bezier flattening (no `inkex` dependency) |
| `siser_pathbuild.py` | Knife-offset corner overshoot/return generation and final overcut |
| `siser_reference.py` | Origin/WYSIWYG/Contour Cut reference-box computation |
| `siser_layers.py` | SVG layer management and geometry collection (mixin) |
| `siser_hpgl.py` | HPGL command stream assembly, including Siser's coordinate conversion |
| `siser_output.py` | Delivery: save to `.plt`, send over WiFi, or send over USB |
| `siser_usb.py` | Windows USB-Printer-class device discovery and raw send |
| `siser_viewer.py` | HTML-based HPGL preview viewer |
| `siser_layer_setup.py` | Action: Layer Setup |
| `siser_add_marks.py` | Action: Add Marks |
| `siser_arrows.py` | Debug-only cut-direction arrowhead helpers |

## Coordinate system

Inkscape uses a top-left-origin, Y-down document coordinate system. Siser cutters use a bottom-left-origin, Y-up machine coordinate system, reached with a 90-degree axis rotation rather than a simple swap+invert:

```
hpgl_x = max_y - y      (left  -> right)
hpgl_y = x - min_x       (bottom -> top)
```

`min_x` and `max_y` come from the reference box computed for whichever Cut Mode is active (Origin / WYSIWYG / Contour Cut) — see `siser_reference.py` and `siser_hpgl.py` for details.

## License

SPDX-License-Identifier: `GPL-3.0-or-later`
