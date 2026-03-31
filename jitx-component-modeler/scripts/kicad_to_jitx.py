#!/usr/bin/env python3
"""Convert KiCad .kicad_mod footprint files to JITX Python component code.

Parses the S-expression format used by KiCad footprint libraries and generates
a complete JITX Component class with Landpattern, Ports, BoxSymbol, and PadMapping.

Usage:
    # From a file
    python kicad_to_jitx.py footprint.kicad_mod

    # From stdin (e.g., piped from MCP tool output)
    echo '(footprint ...)' | python kicad_to_jitx.py --stdin

    # With options
    python kicad_to_jitx.py footprint.kicad_mod --class-name USB_C_Connector \\
        --manufacturer "Molex" --mpn "2012670005" --ref-prefix J \\
        -o components/connectors/molex_2012670005.py

    # Dump parsed pad data as JSON (for debugging)
    python kicad_to_jitx.py footprint.kicad_mod --dump-pads
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import textwrap
from dataclasses import dataclass, field, asdict
from io import StringIO
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# S-expression tokenizer and parser
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Tokenize a KiCad S-expression string into a flat list of tokens.

    Handles:
    - Parentheses as separate tokens
    - Double-quoted strings (with escaped quotes inside)
    - Unquoted tokens (space/paren delimited)
    """
    tokens: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\n\r":
            i += 1
        elif c == "(":
            tokens.append("(")
            i += 1
        elif c == ")":
            tokens.append(")")
            i += 1
        elif c == '"':
            # Quoted string
            j = i + 1
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    j += 1
            tokens.append(text[i + 1 : j])  # strip quotes
            i = j + 1
        else:
            # Unquoted token
            j = i
            while j < n and text[j] not in " \t\n\r()\"":
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def parse_sexpr(tokens: list[str], pos: int = 0) -> tuple[Any, int]:
    """Parse tokens into a nested list structure (iterative, stack-based).

    Returns (parsed_value, next_position).
    '(' starts a list, ')' ends it, everything else is an atom.
    """
    if pos >= len(tokens):
        raise ValueError("Unexpected end of tokens")

    if tokens[pos] != "(":
        return tokens[pos], pos + 1

    # Iterative stack-based parser to avoid recursion limits
    stack: list[list[Any]] = []
    current: list[Any] = []
    pos += 1  # skip opening '('

    while pos < len(tokens):
        tok = tokens[pos]
        if tok == "(":
            stack.append(current)
            current = []
            pos += 1
        elif tok == ")":
            if stack:
                parent = stack.pop()
                parent.append(current)
                current = parent
            else:
                return current, pos + 1
            pos += 1
        else:
            current.append(tok)
            pos += 1

    return current, pos


def parse_kicad_mod(text: str) -> list[Any]:
    """Parse a complete .kicad_mod file into a nested list."""
    tokens = tokenize(text)
    result, _ = parse_sexpr(tokens, 0)
    return result


# ---------------------------------------------------------------------------
# Data structures for extracted pad info
# ---------------------------------------------------------------------------

@dataclass
class DrillInfo:
    """Drill specification for through-hole pads."""
    diameter: float
    width: float | None = None  # For oval drills
    oval: bool = False
    offset_x: float = 0.0
    offset_y: float = 0.0


@dataclass
class PadInfo:
    """Extracted pad information from a KiCad footprint."""
    name: str
    pad_type: str  # smd, thru_hole, np_thru_hole, connect
    shape: str  # rect, circle, oval, roundrect, trapezoid, custom
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    width: float = 0.0  # size X
    height: float = 0.0  # size Y
    drill: DrillInfo | None = None
    layers: list[str] = field(default_factory=list)
    roundrect_rratio: float = 0.25  # default for roundrect
    # For custom pads, store the bounding box of primitives
    custom_primitives: list[Any] = field(default_factory=list)
    custom_anchor: str = "circle"
    custom_bbox: tuple[float, float] | None = None  # (width, height)


# ---------------------------------------------------------------------------
# Pad extraction from parsed S-expression
# ---------------------------------------------------------------------------

def find_nodes(sexpr: list, tag: str) -> list[list]:
    """Find all child nodes with the given tag name."""
    return [node for node in sexpr if isinstance(node, list) and len(node) > 0 and node[0] == tag]


def find_node(sexpr: list, tag: str) -> list | None:
    """Find the first child node with the given tag name."""
    nodes = find_nodes(sexpr, tag)
    return nodes[0] if nodes else None


def to_float(val: Any) -> float:
    """Convert a token to float, handling edge cases."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def extract_drill(node: list) -> DrillInfo:
    """Extract drill information from a (drill ...) node."""
    info = DrillInfo(diameter=0.0)
    idx = 1
    if idx < len(node) and node[idx] == "oval":
        info.oval = True
        idx += 1
    if idx < len(node) and not isinstance(node[idx], list):
        info.diameter = to_float(node[idx])
        idx += 1
    if idx < len(node) and not isinstance(node[idx], list):
        info.width = to_float(node[idx])
        info.oval = True
        idx += 1
    # Check for offset
    offset_node = find_node(node, "offset")
    if offset_node and len(offset_node) >= 3:
        info.offset_x = to_float(offset_node[1])
        info.offset_y = to_float(offset_node[2])
    return info


def compute_custom_bbox(primitives_node: list) -> tuple[float, float]:
    """Compute bounding box of custom pad primitives.

    Returns (width, height) of the bounding box centered on origin.
    """
    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")

    for prim in primitives_node[1:] if len(primitives_node) > 1 else primitives_node:
        if not isinstance(prim, list):
            continue
        ptype = prim[0] if prim else ""
        if ptype == "gr_poly":
            pts_node = find_node(prim, "pts")
            if pts_node:
                for pt in pts_node[1:]:
                    if isinstance(pt, list) and pt[0] == "xy" and len(pt) >= 3:
                        px, py = to_float(pt[1]), to_float(pt[2])
                        min_x = min(min_x, px)
                        max_x = max(max_x, px)
                        min_y = min(min_y, py)
                        max_y = max(max_y, py)
        elif ptype == "gr_line":
            start_node = find_node(prim, "start")
            end_node = find_node(prim, "end")
            if start_node and len(start_node) >= 3:
                min_x = min(min_x, to_float(start_node[1]))
                max_x = max(max_x, to_float(start_node[1]))
                min_y = min(min_y, to_float(start_node[2]))
                max_y = max(max_y, to_float(start_node[2]))
            if end_node and len(end_node) >= 3:
                min_x = min(min_x, to_float(end_node[1]))
                max_x = max(max_x, to_float(end_node[1]))
                min_y = min(min_y, to_float(end_node[2]))
                max_y = max(max_y, to_float(end_node[2]))
        elif ptype == "gr_circle":
            center_node = find_node(prim, "center")
            end_node = find_node(prim, "end")
            if center_node and end_node:
                cx, cy = to_float(center_node[1]), to_float(center_node[2])
                ex, ey = to_float(end_node[1]), to_float(end_node[2])
                r = math.sqrt((ex - cx) ** 2 + (ey - cy) ** 2)
                min_x = min(min_x, cx - r)
                max_x = max(max_x, cx + r)
                min_y = min(min_y, cy - r)
                max_y = max(max_y, cy + r)
        elif ptype == "gr_rect":
            start_node = find_node(prim, "start")
            end_node = find_node(prim, "end")
            if start_node and end_node:
                x1, y1 = to_float(start_node[1]), to_float(start_node[2])
                x2, y2 = to_float(end_node[1]), to_float(end_node[2])
                min_x = min(min_x, x1, x2)
                max_x = max(max_x, x1, x2)
                min_y = min(min_y, y1, y2)
                max_y = max(max_y, y1, y2)

    if min_x == float("inf"):
        return (0.0, 0.0)
    return (max_x - min_x, max_y - min_y)


def extract_pad(node: list) -> PadInfo:
    """Extract a PadInfo from a parsed (pad ...) S-expression node.

    Expected format:
        (pad NAME TYPE SHAPE (at X Y [ROT]) (size W H) [(drill ...)] (layers ...) ...)
    """
    pad = PadInfo(
        name=str(node[1]) if len(node) > 1 else "",
        pad_type=str(node[2]) if len(node) > 2 else "smd",
        shape=str(node[3]) if len(node) > 3 else "rect",
    )

    # Position
    at_node = find_node(node, "at")
    if at_node:
        pad.x = to_float(at_node[1]) if len(at_node) > 1 else 0.0
        pad.y = to_float(at_node[2]) if len(at_node) > 2 else 0.0
        pad.rotation = to_float(at_node[3]) if len(at_node) > 3 else 0.0

    # Size
    size_node = find_node(node, "size")
    if size_node:
        pad.width = to_float(size_node[1]) if len(size_node) > 1 else 0.0
        pad.height = to_float(size_node[2]) if len(size_node) > 2 else 0.0

    # Drill
    drill_node = find_node(node, "drill")
    if drill_node:
        pad.drill = extract_drill(drill_node)

    # Layers
    layers_node = find_node(node, "layers")
    if layers_node:
        pad.layers = [str(l) for l in layers_node[1:] if not isinstance(l, list)]

    # Roundrect ratio
    for child in node:
        if isinstance(child, list) and len(child) >= 2 and child[0] == "roundrect_rratio":
            pad.roundrect_rratio = to_float(child[1])

    # Custom pad primitives
    if pad.shape == "custom":
        options_node = find_node(node, "options")
        if options_node:
            anchor_node = find_node(options_node, "anchor")
            if anchor_node and len(anchor_node) >= 2:
                pad.custom_anchor = str(anchor_node[1])

        primitives_node = find_node(node, "primitives")
        if primitives_node:
            pad.custom_primitives = primitives_node[1:]
            pad.custom_bbox = compute_custom_bbox(primitives_node)

    return pad


def extract_footprint_name(sexpr: list) -> str:
    """Extract the footprint name from the top-level S-expression."""
    if len(sexpr) > 1 and isinstance(sexpr[1], str):
        return sexpr[1]
    return "UnknownFootprint"


def extract_pads(sexpr: list) -> list[PadInfo]:
    """Extract all pad definitions from a parsed footprint."""
    pads = []
    for child in sexpr:
        if isinstance(child, list) and len(child) > 0 and child[0] == "pad":
            pads.append(extract_pad(child))
    return pads


# ---------------------------------------------------------------------------
# Layer geometry extraction (silkscreen, courtyard, fab)
# ---------------------------------------------------------------------------

@dataclass
class LineSegment:
    """A line segment from fp_line."""
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    layer: str


@dataclass
class CircleGeom:
    """A circle from fp_circle."""
    cx: float
    cy: float
    radius: float
    width: float
    layer: str


@dataclass
class TextGeom:
    """A text element from fp_text."""
    text_type: str  # "reference", "value", "user"
    text: str
    x: float
    y: float
    size: float
    layer: str


@dataclass
class LayerGeometry:
    """All non-pad geometry extracted from a footprint."""
    silkscreen_lines: list[LineSegment] = field(default_factory=list)
    silkscreen_circles: list[CircleGeom] = field(default_factory=list)
    courtyard_lines: list[LineSegment] = field(default_factory=list)
    fab_lines: list[LineSegment] = field(default_factory=list)
    texts: list[TextGeom] = field(default_factory=list)


def extract_layer_geometry(sexpr: list) -> LayerGeometry:
    """Extract silkscreen, courtyard, fab lines and texts from a footprint."""
    geom = LayerGeometry()

    for child in sexpr:
        if not isinstance(child, list) or not child:
            continue

        tag = child[0]

        if tag == "fp_line":
            start = find_node(child, "start")
            end = find_node(child, "end")
            layer_node = find_node(child, "layer")
            width_node = find_node(child, "width")
            if not (start and end and layer_node):
                continue
            layer = str(layer_node[1]) if len(layer_node) > 1 else ""
            seg = LineSegment(
                x1=to_float(start[1]) if len(start) > 1 else 0.0,
                y1=to_float(start[2]) if len(start) > 2 else 0.0,
                x2=to_float(end[1]) if len(end) > 1 else 0.0,
                y2=to_float(end[2]) if len(end) > 2 else 0.0,
                width=to_float(width_node[1]) if width_node and len(width_node) > 1 else 0.15,
                layer=layer,
            )
            if layer == "F.SilkS":
                geom.silkscreen_lines.append(seg)
            elif layer == "F.CrtYd":
                geom.courtyard_lines.append(seg)
            elif layer == "F.Fab":
                geom.fab_lines.append(seg)

        elif tag == "fp_circle":
            center = find_node(child, "center")
            end = find_node(child, "end")
            layer_node = find_node(child, "layer")
            width_node = find_node(child, "width")
            if not (center and end and layer_node):
                continue
            cx = to_float(center[1]) if len(center) > 1 else 0.0
            cy = to_float(center[2]) if len(center) > 2 else 0.0
            ex = to_float(end[1]) if len(end) > 1 else 0.0
            ey = to_float(end[2]) if len(end) > 2 else 0.0
            radius = math.sqrt((ex - cx) ** 2 + (ey - cy) ** 2)
            layer = str(layer_node[1]) if len(layer_node) > 1 else ""
            circ = CircleGeom(
                cx=cx, cy=cy, radius=radius,
                width=to_float(width_node[1]) if width_node and len(width_node) > 1 else 0.15,
                layer=layer,
            )
            if layer == "F.SilkS":
                geom.silkscreen_circles.append(circ)

        elif tag == "fp_text":
            text_type = str(child[1]) if len(child) > 1 else ""
            text_val = str(child[2]) if len(child) > 2 else ""
            at_node = find_node(child, "at")
            layer_node = find_node(child, "layer")
            effects_node = find_node(child, "effects")
            x = to_float(at_node[1]) if at_node and len(at_node) > 1 else 0.0
            y = to_float(at_node[2]) if at_node and len(at_node) > 2 else 0.0
            layer = str(layer_node[1]) if layer_node and len(layer_node) > 1 else ""
            size = 1.0
            if effects_node:
                font_node = find_node(effects_node, "font")
                if font_node:
                    size_node = find_node(font_node, "size")
                    if size_node and len(size_node) > 1:
                        size = to_float(size_node[1])
            geom.texts.append(TextGeom(
                text_type=text_type, text=text_val,
                x=x, y=y, size=size, layer=layer,
            ))

    return geom


def courtyard_rect_from_lines(lines: list[LineSegment]) -> tuple[float, float] | None:
    """Compute bounding rectangle from courtyard line segments.

    Returns (width, height) or None if no lines.
    """
    if not lines:
        return None
    min_x = min(min(l.x1, l.x2) for l in lines)
    max_x = max(max(l.x1, l.x2) for l in lines)
    min_y = min(min(l.y1, l.y2) for l in lines)
    max_y = max(max(l.y1, l.y2) for l in lines)
    return (max_x - min_x, max_y - min_y)


# ---------------------------------------------------------------------------
# Pad classification and grouping
# ---------------------------------------------------------------------------

@dataclass
class PadGroup:
    """A group of pads that share the same name."""
    name: str
    pads: list[PadInfo]

    @property
    def count(self) -> int:
        return len(self.pads)

    @property
    def is_array(self) -> bool:
        return self.count > 1


def group_pads_by_name(pads: list[PadInfo]) -> list[PadGroup]:
    """Group pads by their name, preserving order of first appearance."""
    groups: dict[str, PadGroup] = {}
    order: list[str] = []
    for pad in pads:
        if pad.name not in groups:
            groups[pad.name] = PadGroup(name=pad.name, pads=[])
            order.append(pad.name)
        groups[pad.name].pads.append(pad)
    return [groups[name] for name in order]


def classify_pad(pad: PadInfo) -> str:
    """Classify a pad into a functional category.

    Returns one of: 'signal', 'mounting', 'shield', 'npth'
    """
    if pad.pad_type == "np_thru_hole":
        return "npth"
    name_upper = pad.name.upper()
    if name_upper in ("", "MP", "MH", "MNT", "MOUNT") or name_upper.startswith("MP"):
        if pad.pad_type == "np_thru_hole":
            return "npth"
        return "mounting"
    if name_upper in ("S", "S1", "SH", "SHIELD") or name_upper.startswith("S"):
        # Check if it's a shield pad (typically large mounting/grounding pads)
        if pad.drill and pad.width > 0.8:
            return "shield"
    return "signal"


def sanitize_name(name: str) -> str:
    """Convert a KiCad pad name to a valid Python identifier.

    Rules:
    - Replace non-alphanumeric chars (except underscore) with underscores
    - Prefix with 'p' if starts with digit
    - Convert common special names
    """
    if not name:
        return "NC"

    # Common USB-C / connector pad name mappings
    name = name.replace("+", "p").replace("-", "n").replace(".", "_")

    # Replace any remaining invalid chars
    result = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    # Strip leading/trailing underscores
    result = result.strip("_")

    if not result:
        return "PAD"

    # Prefix with 'p' if starts with digit
    if result[0].isdigit():
        result = "p" + result

    return result


def make_port_name(pad_name: str) -> str:
    """Create a JITX-appropriate port name from a pad name.

    Keeps functional names (VBUS, GND, CC1, etc.) and sanitizes others.
    """
    # Known functional names that should be preserved
    known = {
        "VBUS", "GND", "CC1", "CC2", "SBU1", "SBU2",
        "DP", "DM", "DN", "D+", "D-",
        "TX1+", "TX1-", "TX2+", "TX2-",
        "RX1+", "RX1-", "RX2+", "RX2-",
        "SHIELD", "SHELL", "MH", "MP",
        "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11", "A12",
        "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", "B11", "B12",
        "S1", "S2", "S3", "S4",
    }
    return sanitize_name(pad_name)


# ---------------------------------------------------------------------------
# Effective pad dimensions (handles custom pads with primitives)
# ---------------------------------------------------------------------------

def effective_pad_size(pad: PadInfo) -> tuple[float, float]:
    """Get the effective width and height for a pad.

    For custom pads with tiny size but primitives, use the bounding box.
    For normal pads, use the size directly.
    """
    if pad.shape == "custom" and pad.custom_bbox:
        bw, bh = pad.custom_bbox
        if bw > pad.width and bh > pad.height:
            return (bw, bh)
    return (pad.width, pad.height)


def effective_pad_shape(pad: PadInfo) -> str:
    """Determine the effective shape for code generation.

    Maps KiCad shapes to the closest JITX representation:
    - rect, roundrect -> rectangle
    - circle -> circle
    - oval -> capsule
    - custom -> rectangle (using bounding box)
    - trapezoid -> rectangle (approximation)
    """
    if pad.shape in ("rect", "roundrect", "trapezoid"):
        return "rectangle"
    if pad.shape == "circle":
        return "circle"
    if pad.shape == "oval":
        return "capsule"
    if pad.shape == "custom":
        # For custom pads, check if primitives define a rectangular shape
        return "rectangle"
    return "rectangle"


# ---------------------------------------------------------------------------
# JITX code generation
# ---------------------------------------------------------------------------

def fmt_float(val: float, precision: int = 4) -> str:
    """Format a float for code output, stripping trailing zeros."""
    s = f"{val:.{precision}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def needs_rotation(pad: PadInfo) -> bool:
    """Check if the pad has a non-zero rotation that matters."""
    return abs(pad.rotation) > 0.01


def generate_pad_class(
    pad: PadInfo,
    class_name: str,
) -> str:
    """Generate a JITX Pad subclass definition for a pad shape.

    Uses the class-based pattern:
        class PadFoo(Pad):
            shape = rectangle(w, h)
    """
    w, h = effective_pad_size(pad)
    eshape = effective_pad_shape(pad)

    if pad.pad_type == "np_thru_hole":
        # Non-plated through hole: just a cutout, no copper
        if pad.drill:
            d = pad.drill.diameter
            if pad.drill.oval and pad.drill.width:
                dw = pad.drill.width
                return (
                    f"class {class_name}(Pad):\n"
                    f"    \"\"\"Non-plated through-hole (oval {fmt_float(d)} x {fmt_float(dw)} mm).\"\"\"\n"
                    f"    shape = capsule({fmt_float(max(d, dw))}, {fmt_float(min(d, dw))})\n"
                    f"    cutout = Cutout(capsule({fmt_float(max(d, dw))}, {fmt_float(min(d, dw))}))\n"
                )
            return (
                f"class {class_name}(Pad):\n"
                f"    \"\"\"Non-plated through-hole ({fmt_float(d)} mm).\"\"\"\n"
                f"    shape = circle({fmt_float(d / 2)})\n"
                f"    cutout = Cutout(circle({fmt_float(d / 2)}))\n"
            )
        return (
            f"class {class_name}(Pad):\n"
            f"    shape = circle({fmt_float(w / 2)})\n"
            f"    cutout = Cutout(circle({fmt_float(w / 2)}))\n"
        )

    if pad.pad_type == "thru_hole":
        drill = pad.drill
        if not drill:
            drill = DrillInfo(diameter=min(w, h) * 0.5)

        if drill.oval and drill.width:
            cutout_shape = f"capsule({fmt_float(max(drill.diameter, drill.width))}, {fmt_float(min(drill.diameter, drill.width))})"
        else:
            cutout_shape = f"circle({fmt_float(drill.diameter / 2)})"

        if eshape == "circle":
            copper_shape = f"circle({fmt_float(w / 2)})"
        elif eshape == "capsule":
            copper_shape = f"capsule({fmt_float(max(w, h))}, {fmt_float(min(w, h))})"
        else:
            copper_shape = f"rectangle({fmt_float(w)}, {fmt_float(h)})"

        return (
            f"class {class_name}(Pad):\n"
            f"    \"\"\"Through-hole pad.\"\"\"\n"
            f"    shape = {copper_shape}\n"
            f"    cutout = Cutout({cutout_shape})\n"
        )

    # SMD or connect pad
    if eshape == "circle":
        diameter = max(w, h)
        shape_str = f"circle({fmt_float(diameter / 2)})"
    elif eshape == "capsule":
        shape_str = f"capsule({fmt_float(max(w, h))}, {fmt_float(min(w, h))})"
    else:
        shape_str = f"rectangle({fmt_float(w)}, {fmt_float(h)})"

    return (
        f"class {class_name}(Pad):\n"
        f"    \"\"\"SMD pad ({fmt_float(w)} x {fmt_float(h)} mm).\"\"\"\n"
        f"    shape = {shape_str}\n"
    )


def generate_jitx_code(
    pads: list[PadInfo],
    footprint_name: str,
    class_name: str | None = None,
    manufacturer: str = "",
    mpn: str = "",
    datasheet: str = "",
    ref_prefix: str = "J",
    description: str = "",
    layer_geom: LayerGeometry | None = None,
) -> str:
    """Generate complete JITX Python component code from extracted pads.

    Args:
        pads: List of extracted pad info
        footprint_name: Original footprint name from .kicad_mod
        class_name: Python class name (auto-generated if None)
        manufacturer: Component manufacturer
        mpn: Manufacturer part number
        datasheet: Datasheet URL
        ref_prefix: Reference designator prefix (U, J, etc.)
        description: Component description

    Returns:
        Complete Python source code as a string
    """
    if not class_name:
        class_name = sanitize_name(footprint_name)
        if class_name[0].islower():
            class_name = class_name[0].upper() + class_name[1:]

    # Group pads by name to identify arrays
    groups = group_pads_by_name(pads)

    # Filter out unnamed NPTH pads (mechanical holes, not electrical)
    signal_groups = []
    npth_unnamed = []
    for g in groups:
        if g.name == "" and all(p.pad_type == "np_thru_hole" for p in g.pads):
            npth_unnamed.extend(g.pads)
        else:
            signal_groups.append(g)

    # Build unique pad shape classes
    # Key: (pad_type, effective_shape, effective_w, effective_h, drill_key) -> class_name
    pad_shape_map: dict[tuple, str] = {}
    pad_class_defs: list[str] = []
    pad_class_counter = 0

    def get_pad_class(pad: PadInfo) -> str:
        nonlocal pad_class_counter
        w, h = effective_pad_size(pad)
        # Round dimensions to avoid floating-point noise creating duplicate classes
        w = round(w, 4)
        h = round(h, 4)
        eshape = effective_pad_shape(pad)
        drill_key: tuple = ()
        if pad.drill:
            drill_key = (
                round(pad.drill.diameter, 4),
                round(pad.drill.width, 4) if pad.drill.width else None,
                pad.drill.oval,
            )
        key = (pad.pad_type, eshape, w, h, drill_key)
        if key in pad_shape_map:
            return pad_shape_map[key]

        pad_class_counter += 1
        cname = f"Pad{pad_class_counter}"
        pad_shape_map[key] = cname
        pad_class_defs.append(generate_pad_class(pad, cname))
        return cname

    # Pre-compute pad class assignments
    group_pad_classes: dict[str, list[str]] = {}
    for group in signal_groups:
        classes = []
        for pad in group.pads:
            classes.append(get_pad_class(pad))
        group_pad_classes[group.name] = classes

    npth_classes = [get_pad_class(p) for p in npth_unnamed]

    # Build port names
    port_names: dict[str, str] = {}  # group.name -> python port name
    port_is_array: dict[str, bool] = {}
    for group in signal_groups:
        pname = make_port_name(group.name)
        # Handle potential collisions
        base = pname
        suffix = 2
        while pname in port_names.values():
            pname = f"{base}_{suffix}"
            suffix += 1
        port_names[group.name] = pname
        port_is_array[group.name] = group.is_array

    # Classify groups for symbol layout
    power_ports = []
    ground_ports = []
    left_ports = []
    right_ports = []

    for group in signal_groups:
        pname = port_names[group.name]
        name_upper = group.name.upper()
        if name_upper in ("VCC", "VDD", "V+", "VBUS") or name_upper.startswith("VCC") or name_upper.startswith("VDD") or name_upper.startswith("VBUS"):
            power_ports.append((pname, group))
        elif name_upper in ("GND", "VSS", "V-", "GROUND") or name_upper.startswith("GND") or name_upper.startswith("VSS"):
            ground_ports.append((pname, group))
        elif name_upper in ("SHIELD", "SHELL", "S1", "S2", "S3", "S4", "MH", "MP") or name_upper.startswith("SHIELD") or name_upper.startswith("S") and len(name_upper) <= 3:
            right_ports.append((pname, group))
        else:
            left_ports.append((pname, group))

    # --- Start building output ---
    out = StringIO()

    # Module docstring
    desc = description or f"Component converted from KiCad footprint: {footprint_name}"
    out.write(f'"""\n{desc}\n\nAuto-generated from KiCad footprint: {footprint_name}\n"""\n\n')

    # Check what layer features we need
    has_silkscreen = bool(layer_geom and (layer_geom.silkscreen_lines or layer_geom.silkscreen_circles))
    has_courtyard = bool(layer_geom and layer_geom.courtyard_lines)
    has_fab_text = bool(layer_geom and any(t.text_type in ("value", "user") for t in layer_geom.texts))
    has_ref_text = bool(layer_geom and any(t.text_type == "reference" for t in layer_geom.texts))

    # Imports
    out.write("import jitx\n")
    out.write("from jitx import PadMapping\n")

    features = ["Cutout"]
    if has_courtyard:
        features.append("Courtyard")
    if has_silkscreen or has_ref_text:
        features.append("Silkscreen")
    if has_fab_text:
        features.append("Custom")
    out.write(f"from jitx.feature import {', '.join(sorted(features))}\n")

    out.write("from jitx.landpattern import Landpattern, Pad\n")
    out.write("from jitx.net import Port\n")

    # Determine which shape imports we need
    shape_funcs = set()
    for pad in pads:
        es = effective_pad_shape(pad)
        if es == "rectangle":
            shape_funcs.add("rectangle")
        elif es == "circle":
            shape_funcs.add("circle")
        elif es == "capsule":
            shape_funcs.add("capsule")
    # Check for cutouts (through-hole)
    has_thru = any(p.pad_type in ("thru_hole", "np_thru_hole") for p in pads)
    if has_thru:
        shape_funcs.add("circle")  # cutouts often circular
    if has_courtyard:
        shape_funcs.add("rectangle")

    composites_imports = sorted(shape_funcs & {"rectangle", "capsule"})
    primitive_imports = sorted(shape_funcs & {"circle"})

    # Primitive shapes needed for silkscreen
    prim_types = set()
    if has_silkscreen and layer_geom:
        if layer_geom.silkscreen_lines:
            prim_types.add("Polyline")
        if layer_geom.silkscreen_circles:
            prim_types.update(["ArcPolyline", "Arc"])
    if has_ref_text or has_fab_text:
        prim_types.add("Text")

    if composites_imports:
        out.write(f"from jitx.shapes.composites import {', '.join(composites_imports)}\n")
    prim_shape_items = sorted(set(primitive_imports) | prim_types)
    if prim_shape_items:
        out.write(f"from jitx.shapes.primitive import {', '.join(prim_shape_items)}\n")
    if has_ref_text or has_fab_text:
        out.write("from jitx.anchor import Anchor\n")

    out.write("from jitxlib.symbols.box import BoxSymbol, PinGroup, Row, Column\n")
    out.write("\n\n")

    # Pad classes
    out.write("# " + "=" * 70 + "\n")
    out.write("# Pad shape definitions\n")
    out.write("# " + "=" * 70 + "\n\n")
    for pdef in pad_class_defs:
        out.write(pdef + "\n\n")

    # Pad classes for unnamed NPTHs
    for i, npth in enumerate(npth_unnamed):
        get_pad_class(npth)  # ensure class is generated

    # Component class
    out.write("# " + "=" * 70 + "\n")
    out.write("# Component\n")
    out.write("# " + "=" * 70 + "\n\n")
    out.write(f"class {class_name}(jitx.Component):\n")
    out.write(f'    """{desc}"""\n\n')

    if mpn:
        out.write(f'    mpn = "{mpn}"\n')
    if manufacturer:
        out.write(f'    manufacturer = "{manufacturer}"\n')
    out.write(f'    reference_designator_prefix = "{ref_prefix}"\n')
    if datasheet:
        out.write(f'    datasheet = "{datasheet}"\n')
    out.write("\n")

    # Port definitions
    out.write("    # --- Ports ---\n")
    for group in signal_groups:
        pname = port_names[group.name]
        if group.is_array:
            out.write(f"    {pname} = [Port() for _ in range({group.count})]  # Pad \"{group.name}\" x{group.count}\n")
        else:
            out.write(f"    {pname} = Port()  # Pad \"{group.name}\"\n")
    out.write("\n")

    # __init__ with landpattern
    out.write("    def __init__(self):\n")
    out.write("        # --- Landpattern ---\n")
    out.write("        # Pad instances positioned at KiCad coordinates\n")
    out.write("        # NOTE: KiCad Y-axis is inverted vs JITX (KiCad Y+ = down, JITX Y+ = up)\n")
    out.write("        # All Y coordinates are negated during conversion.\n")

    # Generate pad instantiation lines
    # We need to track each pad instance for the PadMapping
    pad_instance_refs: list[tuple[str, str]] = []  # (port_ref, pad_var_name)

    pad_var_counter = 0
    group_pad_vars: dict[str, list[str]] = {}  # group_name -> list of pad var names

    for group in signal_groups:
        pname = port_names[group.name]
        pad_vars = []
        for i, pad in enumerate(group.pads):
            pad_cls = group_pad_classes[group.name][i]
            x = pad.x
            y = -pad.y  # Negate Y for JITX coordinate system
            rot = pad.rotation

            if group.is_array:
                var_name = f"pad_{pname}_{i}"
                port_ref = f"self.{pname}[{i}]"
            else:
                var_name = f"pad_{pname}"
                port_ref = f"self.{pname}"

            rot_str = ""
            if abs(rot) > 0.01:
                rot_str = f", rotate={fmt_float(rot)}"

            out.write(f"        {var_name} = {pad_cls}().at({fmt_float(x)}, {fmt_float(y)}{rot_str})\n")
            pad_vars.append(var_name)
            pad_instance_refs.append((port_ref, var_name))

        group_pad_vars[group.name] = pad_vars

    # Unnamed NPTH pads (no port, just mechanical holes)
    npth_vars = []
    for i, npth in enumerate(npth_unnamed):
        ncls = npth_classes[i]
        x = npth.x
        y = -npth.y
        var_name = f"pad_npth_{i}"
        out.write(f"        {var_name} = {ncls}().at({fmt_float(x)}, {fmt_float(y)})\n")
        npth_vars.append(var_name)

    out.write("\n")

    # Build the Landpattern as an inline class with dict-based p attribute
    # Using the pattern from the U.FL example
    out.write("        @jitx.container.inline\n")
    out.write("        class _lp(Landpattern):\n")
    out.write(f'            name = "{footprint_name}"\n')

    # Collect all pad vars for the landpattern
    all_pad_entries = []
    pad_idx = 1
    idx_map: dict[str, int] = {}  # pad_var_name -> numeric index

    for group in signal_groups:
        for var_name in group_pad_vars[group.name]:
            all_pad_entries.append((pad_idx, var_name))
            idx_map[var_name] = pad_idx
            pad_idx += 1

    for var_name in npth_vars:
        all_pad_entries.append((pad_idx, var_name))
        idx_map[var_name] = pad_idx
        pad_idx += 1

    out.write("            p = {\n")
    for idx, var_name in all_pad_entries:
        out.write(f"                {idx}: {var_name},\n")
    out.write("            }\n")

    # Layer geometry inside the landpattern class
    if layer_geom:
        # Reference designator
        ref_texts = [t for t in layer_geom.texts if t.text_type == "reference"]
        if ref_texts:
            t = ref_texts[0]
            out.write(f"            reference_designator = Silkscreen("
                      f"Text(\">REF\", {fmt_float(t.size)}, Anchor.W)"
                      f".at(({fmt_float(t.x)}, {fmt_float(-t.y)})))\n")

        # Value label on Fab
        val_texts = [t for t in layer_geom.texts if t.text_type in ("value", "user")]
        if val_texts:
            t = val_texts[0]
            out.write(f"            value_label = Custom("
                      f"Text(\">VALUE\", {fmt_float(t.size)}, Anchor.W)"
                      f".at(({fmt_float(t.x)}, {fmt_float(-t.y)})), name=\"Fab\")\n")

        # Silkscreen lines
        if layer_geom.silkscreen_lines:
            out.write("            silkscreen = [\n")
            # Group connected line segments by width for cleaner output
            for seg in layer_geom.silkscreen_lines:
                out.write(f"                Silkscreen(Polyline({fmt_float(seg.width)}, "
                          f"[({fmt_float(seg.x1)}, {fmt_float(-seg.y1)}), "
                          f"({fmt_float(seg.x2)}, {fmt_float(-seg.y2)})])),\n")
            # Silkscreen circles
            for circ in layer_geom.silkscreen_circles:
                out.write(f"                Silkscreen(ArcPolyline({fmt_float(circ.width)}, "
                          f"[Arc(({fmt_float(circ.cx)}, {fmt_float(-circ.cy)}), "
                          f"{fmt_float(circ.radius)}, 0, -360)])),\n")
            out.write("            ]\n")
        elif layer_geom.silkscreen_circles:
            out.write("            silkscreen = [\n")
            for circ in layer_geom.silkscreen_circles:
                out.write(f"                Silkscreen(ArcPolyline({fmt_float(circ.width)}, "
                          f"[Arc(({fmt_float(circ.cx)}, {fmt_float(-circ.cy)}), "
                          f"{fmt_float(circ.radius)}, 0, -360)])),\n")
            out.write("            ]\n")

        # Courtyard
        court_rect = courtyard_rect_from_lines(layer_geom.courtyard_lines)
        if court_rect:
            w, h = court_rect
            out.write(f"            courtyard = Courtyard(rectangle({fmt_float(w)}, {fmt_float(h)}))\n")

    out.write("\n")
    out.write("        self.landpattern = _lp\n\n")

    # Symbol
    out.write("        # --- Symbol ---\n")

    def port_ref_for_symbol(pname: str, group: PadGroup) -> str:
        """Generate the port reference for symbol PinGroup."""
        if group.is_array:
            return f"*self.{pname}"
        return f"self.{pname}"

    # Build symbol arguments
    has_rows = bool(left_ports or right_ports)
    has_columns = bool(power_ports or ground_ports)

    out.write("        self.symbol = BoxSymbol(\n")

    if has_rows:
        out.write("            rows=Row(\n")
        if left_ports:
            refs = ", ".join(port_ref_for_symbol(pn, g) for pn, g in left_ports)
            out.write(f"                left=PinGroup({refs}),\n")
        if right_ports:
            refs = ", ".join(port_ref_for_symbol(pn, g) for pn, g in right_ports)
            out.write(f"                right=PinGroup({refs}),\n")
        out.write("            ),\n")

    if has_columns:
        out.write("            columns=Column(\n")
        if power_ports:
            refs = ", ".join(port_ref_for_symbol(pn, g) for pn, g in power_ports)
            out.write(f"                up=PinGroup({refs}),\n")
        if ground_ports:
            refs = ", ".join(port_ref_for_symbol(pn, g) for pn, g in ground_ports)
            out.write(f"                down=PinGroup({refs}),\n")
        out.write("            ),\n")

    # If nothing was classified into rows/columns, put everything in left
    if not has_rows and not has_columns:
        all_refs = ", ".join(port_ref_for_symbol(port_names[g.name], g) for g in signal_groups)
        out.write("            rows=Row(\n")
        out.write(f"                left=PinGroup({all_refs}),\n")
        out.write("            ),\n")

    out.write("        )\n\n")

    # PadMapping
    out.write("        # --- Pad Mapping ---\n")
    out.write("        lp = self.landpattern\n")
    out.write("        self.pad_mapping = PadMapping({\n")

    for port_ref, pad_var in pad_instance_refs:
        idx = idx_map[pad_var]
        out.write(f"            {port_ref}: lp.p[{idx}],\n")

    out.write("        })\n")

    out.write("\n\n")
    out.write(f"Device: type[{class_name}] = {class_name}\n")

    return out.getvalue()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert KiCad .kicad_mod footprint to JITX Python component code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
                python kicad_to_jitx.py USB_C.kicad_mod
                python kicad_to_jitx.py USB_C.kicad_mod --class-name USB_C_Receptacle
                echo '(footprint ...)' | python kicad_to_jitx.py --stdin
                python kicad_to_jitx.py USB_C.kicad_mod --dump-pads
        """),
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("file", nargs="?", help="Path to .kicad_mod file")
    input_group.add_argument("--stdin", action="store_true", help="Read S-expression from stdin")

    parser.add_argument("--class-name", help="Python class name for the component")
    parser.add_argument("--manufacturer", default="", help="Component manufacturer")
    parser.add_argument("--mpn", default="", help="Manufacturer part number")
    parser.add_argument("--datasheet", default="", help="Datasheet URL")
    parser.add_argument("--ref-prefix", default="J", help="Reference designator prefix (default: J)")
    parser.add_argument("--description", default="", help="Component description")
    parser.add_argument("-o", "--output", help="Output file path (default: stdout)")
    parser.add_argument("--dump-pads", action="store_true", help="Dump parsed pad data as JSON and exit")

    args = parser.parse_args()

    # Read input
    if args.stdin:
        text = sys.stdin.read()
    else:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        text = filepath.read_text(encoding="utf-8")

    # Parse
    try:
        sexpr = parse_kicad_mod(text)
    except Exception as e:
        print(f"Error parsing S-expression: {e}", file=sys.stderr)
        sys.exit(1)

    footprint_name = extract_footprint_name(sexpr)
    pads = extract_pads(sexpr)
    layer_geom = extract_layer_geometry(sexpr)

    if not pads:
        print("Warning: No pads found in footprint.", file=sys.stderr)

    # Dump mode
    if args.dump_pads:
        pad_dicts = []
        for p in pads:
            d = {
                "name": p.name,
                "type": p.pad_type,
                "shape": p.shape,
                "x": p.x,
                "y": p.y,
                "rotation": p.rotation,
                "width": p.width,
                "height": p.height,
                "layers": p.layers,
            }
            if p.drill:
                d["drill"] = {
                    "diameter": p.drill.diameter,
                    "width": p.drill.width,
                    "oval": p.drill.oval,
                }
            if p.shape == "custom" and p.custom_bbox:
                d["custom_bbox"] = list(p.custom_bbox)
            pad_dicts.append(d)

        json.dump({"footprint": footprint_name, "pad_count": len(pads), "pads": pad_dicts}, sys.stdout, indent=2)
        print()
        sys.exit(0)

    # Generate
    code = generate_jitx_code(
        pads=pads,
        footprint_name=footprint_name,
        class_name=args.class_name,
        manufacturer=args.manufacturer,
        mpn=args.mpn,
        datasheet=args.datasheet,
        ref_prefix=args.ref_prefix,
        description=args.description,
        layer_geom=layer_geom,
    )

    if args.output:
        outpath = Path(args.output)
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text(code, encoding="utf-8")
        print(f"Written to {outpath}", file=sys.stderr)
    else:
        print(code)


if __name__ == "__main__":
    main()
