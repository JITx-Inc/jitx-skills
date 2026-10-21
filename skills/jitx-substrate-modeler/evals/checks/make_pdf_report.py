#!/usr/bin/env python3
"""Render the stackup-from-pdf-report case's PDF from its grader-side CSV twin.

Usage:
  make_pdf_report.py

Reads testdata/case_b/TIC-8L_Stackup-Report_RevC.csv and writes
evals/cases/fixtures/pdf_TIC-8L_Stackup-Report_RevC.pdf. The committed PDF is
the fixture; run this only to change it, and then run the self-tests, which
check with pdftotext that the PDF states what the twin holds.

Needs PyMuPDF (imported as ``fitz``; 1.26.7 renders the committed PDF), which
the grader's own environment does not carry: run it with an interpreter that
has PyMuPDF installed. Nothing in the test run imports it.

The PDF differs from the twin exactly where the case sets its traps:

- the inner copper is given as a weight (1 oz) with no thickness;
- the L5-L6 core has no thickness, and the finished total is given;
- the L4-L5 prepreg's mm cell reads 0.1000 against its 4.00 mil, and the
  report declares mil controlling;
- BD-1 is listed as drilled L1 to L8 and backdrilled from L8 keeping L1 to
  L4, with the full drilled depth and its ratio;
- UV-1's annular ring is still the Rev B figure, from before Rev C enlarged
  its pad;
- the fab rules carry no mm column and no JITX field names: lengths in mil,
  board maximums in inches, ratios and counts as such;
- the depth basis for the aspect ratio is stated only in a footnote under the
  via table, and nothing says whether the limits are inclusive.
"""

from __future__ import annotations

import html
import importlib
import io
from pathlib import Path
from typing import Any

import fabcsv

CHECKS = Path(__file__).resolve().parent
TWIN = CHECKS / "testdata" / "case_b" / "TIC-8L_Stackup-Report_RevC.csv"
PDF = CHECKS.parent / "cases" / "fixtures" / "pdf_TIC-8L_Stackup-Report_RevC.pdf"

UNSTATED = ""
MM_PER_MIL = 0.0254
PREPREG_SEQ_WITH_BAD_MM = "9"
"""STACKUP Seq of the L4-L5 prepreg, whose mm cell disagrees with its mil."""
BAD_MM = "0.1000"
UNSTATED_THICKNESS_MATERIAL = "D-CORE-T"
STALE_RING_MIL = {"UV-1": "2.50"}
"""Annular ring as Rev B stated it, from the 9.0 mil pad."""

CSS = """
* { font-family: sans-serif; }
body { font-size: 8pt; }
h1 { font-size: 14pt; margin-bottom: 2pt; }
h2 { font-size: 10pt; margin-top: 10pt; margin-bottom: 3pt; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 0.5pt solid #555; padding: 1.5pt 3pt; text-align: left; }
th { background-color: #ddd; }
p.note { font-size: 7pt; margin-top: 2pt; }
"""


def mil(mm: str) -> str:
    return f"{float(mm) / MM_PER_MIL:.2f}"


def table(header: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(cell)}</th>" for cell in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><tr>{head}</tr>{body}</table>"


def document_section(twin: dict[str, fabcsv.Rows]) -> str:
    doc = {row["Field"]: row for row in twin["DOCUMENT"]}
    shown = [
        ("Fabricator", doc["Fabricator"]["Value"]),
        ("Quote number", doc["Quote number"]["Value"]),
        ("Revision", doc["Revision"]["Value"]),
        ("Issue date", doc["Issue date"]["Value"]),
        ("Customer part number", doc["Customer part number"]["Value"]),
        (
            "Board size",
            f"{doc['Board size']['Value']} mm, {doc['Board size']['Notes']}",
        ),
        ("Layer count", doc["Layer count"]["Value"]),
        (
            "Construction",
            f"{doc['Construction']['Value']}. {doc['Construction']['Notes']}",
        ),
        (
            "Overall thickness",
            f"{doc['Overall thickness']['Notes'].split(' - ')[0]} "
            "(including soldermask both sides)",
        ),
        (
            "Finished thickness",
            f"{doc['Finished thickness']['Notes'].split(' - ')[0]} "
            "(copper and dielectric, excluding soldermask)",
        ),
        ("Thickness tolerance", "+/-10 %"),
        ("Surface finish", doc["Surface finish"]["Value"]),
        ("Soldermask", f"{doc['Soldermask']['Value']}, both sides"),
        ("Copper plating class", doc["Copper plating class"]["Value"]),
        ("Impedance tolerance", "+/-10 %, all controlled structures"),
        ("Impedance model", doc["Impedance model"]["Value"]),
        ("Impedance test frequency", "5.0 GHz"),
        ("Dk/Df reference frequency", "2.0 GHz"),
        (
            "Units",
            "Dimensions are in mil. Where a mm value is also given it is for "
            "reference only; the mil value controls.",
        ),
    ]
    return "<h2>1. Document</h2>" + table(["Field", "Value"], [list(r) for r in shown])


def revision_section(twin: dict[str, fabcsv.Rows]) -> str:
    rows = [[r["Revision"], r["Date"], r["Change"]] for r in twin["REVISION_HISTORY"]]
    return "<h2>2. Revision history</h2>" + table(["Rev", "Date", "Change"], rows)


def materials_section(twin: dict[str, fabcsv.Rows]) -> str:
    dielectrics = [
        [
            r["Material_ID"],
            r["Manufacturer"],
            r["Product"],
            r["Type"],
            r["Glass_style"],
            r["Resin_pct"],
            r["Dk"],
            r["Df"],
            r["Tg_C"],
        ]
        for r in twin["MATERIALS_DIELECTRIC"]
    ]
    copper = []
    for r in twin["MATERIALS_COPPER"]:
        outer = r["Plating_um"] not in ("", "0.0")
        finished = (
            f"{mil(r['Finished_thickness_mm'])} mil finished (base foil plus plating)"
            if outer
            else UNSTATED
        )
        copper.append(
            [
                r["Copper_ID"],
                r["Manufacturer"],
                r["Product"],
                r["Foil_type"],
                f"{float(r['Nominal_weight_oz']):g} oz",
                finished,
                r["Rz_matte_um"],
                r["Rz_drum_um"],
            ]
        )
    return (
        "<h2>3. Materials</h2>"
        + table(
            [
                "ID",
                "Manufacturer",
                "Product",
                "Type",
                "Glass",
                "Resin %",
                "Dk",
                "Df",
                "Tg C",
            ],
            dielectrics,
        )
        + "<p class='note'>Dk and Df at 2.0 GHz.</p>"
        + table(
            [
                "ID",
                "Manufacturer",
                "Product",
                "Foil",
                "Weight",
                "Thickness",
                "Rz matte um",
                "Rz drum um",
            ],
            copper,
        )
    )


def stackup_section(twin: dict[str, fabcsv.Rows]) -> str:
    weights = {r["Copper_ID"]: r for r in twin["MATERIALS_COPPER"]}
    rows = []
    for r in twin["STACKUP"]:
        thickness_mil, thickness_mm = r["Thickness_mil"], r["Thickness_mm"]
        weight = ""
        if r["Type"] == "Copper":
            foil = weights[r["Material_ID"]]
            weight = f"{float(foil['Nominal_weight_oz']):g} oz"
            if foil["Plating_um"] in ("", "0.0"):
                thickness_mil = thickness_mm = UNSTATED
            else:
                weight += " + plating"
        if r["Material_ID"] == UNSTATED_THICKNESS_MATERIAL:
            thickness_mil = thickness_mm = UNSTATED
        if r["Seq"] == PREPREG_SEQ_WITH_BAD_MM:
            thickness_mm = BAD_MM
        rows.append(
            [
                r["Seq"],
                r["Type"],
                r["Layer"],
                r["Function"],
                r["Material_ID"],
                weight,
                thickness_mil,
                thickness_mm,
                r["Dk"],
                r["Df"],
            ]
        )
    return (
        "<h2>4. Stackup</h2>"
        + table(
            [
                "Seq",
                "Type",
                "Layer",
                "Function",
                "Material",
                "Copper",
                "mil",
                "mm",
                "Dk",
                "Df",
            ],
            rows,
        )
        + "<p class='note'>Layers numbered from the top: L1 is top copper, L8 is "
        "bottom copper. L2 is voided under every L1 controlled route.</p>"
    )


def via_rows(twin: dict[str, fabcsv.Rows], n_copper: int) -> list[list[str]]:
    rows = []
    for r in twin["VIAS"]:
        span = f"{r['From_layer']}-{r['To_layer']}"
        depth_mm, ratio = r["Depth_mm"], r["Aspect_ratio"]
        if r["Backdrill_side"]:
            span = f"L1-L{n_copper}, backdrilled from L{n_copper} keeping {r['From_layer']}-{r['To_layer']}"
            depth_mm = f"{sum(float(s['Thickness_mm']) for s in twin['STACKUP'] if s['Type'] != 'Soldermask'):.4f}"
            ratio = f"{float(depth_mm) / float(r['Finished_hole_mm']):.2f}"
        hole, pad = float(r["Finished_hole_mm"]), float(r["Pad_mm"])
        ring = STALE_RING_MIL.get(r["Via_ID"], f"{(pad - hole) / 2 / MM_PER_MIL:.2f}")
        structure = r["Structure"]
        if int(r["Stacked_levels"] or 1) > 1:
            structure += f", {r['Stacked_levels']} levels"
        rows.append(
            [
                r["Via_ID"],
                structure,
                r["Drill"],
                span,
                f"{r['Finished_hole_mil']} ({r['Finished_hole_mm']})",
                f"{r['Pad_mil']} ({r['Pad_mm']})",
                f"{mil(depth_mm)} ({depth_mm})",
                f"{ratio}:1 *",
                ring,
                r["Fill"],
                r["Capped"],
                r["Tented"],
                r["Via_in_pad"],
            ]
        )
    return rows


def vias_section(twin: dict[str, fabcsv.Rows], n_copper: int) -> str:
    backdrill = [
        [
            r["Via_ID"],
            f"From L{n_copper}" if r["Backdrill_side"] == "Bottom" else "From L1",
            f"Keep {r['From_layer']}-{r['To_layer']}",
            mil(r["Backdrill_diameter_mm"]),
            mil(r["Backdrill_startpad_mm"]),
            mil(r["Backdrill_mask_opening_mm"]),
            mil(r["Backdrill_copper_clearance_mm"]),
        ]
        for r in twin["VIAS"]
        if r["Backdrill_side"]
    ]
    nfp = [
        [
            r["Via_ID"],
            r["NFP_layers"].replace(";", ", "),
            f"{mil(r['NFP_pad_mm'])} ({r['NFP_pad_mm']})",
            f"{r['Pad_mil']} ({r['Pad_mm']}) on every other layer",
        ]
        for r in twin["VIAS"]
        if r["NFP_layers"]
    ]
    return (
        "<h2>5. Drill and via table</h2>"
        + table(
            [
                "Via",
                "Structure",
                "Drill",
                "Span",
                "Hole mil (mm)",
                "Pad mil (mm)",
                "Depth mil (mm)",
                "Aspect ratio",
                "Ring mil",
                "Fill",
                "Capped",
                "Tented",
                "Via in pad",
            ],
            via_rows(twin, n_copper),
        )
        + "<p class='note'>* Aspect ratio = depth / finished hole. Mechanical "
        "depth is the full drilled depth, copper at both ends included. Laser "
        "depth runs from the bottom of the entry copper to the top of the target "
        "copper (end foils excluded).</p>"
        + "<h2>5a. Backdrill</h2>"
        + table(
            [
                "Via",
                "Side",
                "Keeps",
                "Drill mil",
                "Start pad mil",
                "Mask opening mil",
                "Copper clearance mil",
            ],
            backdrill,
        )
        + "<h2>5b. Non-functional pad removal</h2>"
        + table(
            ["Via", "Layers", "Reduced pad mil (mm)", "Functional pad mil (mm)"], nfp
        )
    )


def impedance_section(twin: dict[str, fabcsv.Rows]) -> str:
    rows = []
    for r in twin["IMPEDANCE"]:
        if r["Controlled"] != "Yes":
            continue
        gap = (
            f"{mil(r['Pair_gap_mm'])} ({r['Pair_gap_mm']})" if r["Pair_gap_mm"] else ""
        )
        rows.append(
            [
                r["Structure_ID"],
                r["Layers"],
                r["Geometry"],
                f"{r['Target_Z_ohm']} +/-{r['Tolerance_pct']} %",
                f"{r['Line_width_mil']} ({r['Line_width_mm']})",
                gap,
                f"{mil(r['Clearance_mm'])} ({r['Clearance_mm']})",
                r["Ref_layers"].split(" for ")[0],
                r["Modelled_Z_ohm"],
                r["Eps_eff"],
                r["Delay_ps_per_mm"],
                r["Loss_dB_per_mm"],
            ]
        )
    standard = next(r for r in twin["IMPEDANCE"] if r["Controlled"] != "Yes")
    return (
        "<h2>6. Impedance</h2>"
        + table(
            [
                "Structure",
                "Layer",
                "Geometry",
                "Target ohm",
                "Width mil (mm)",
                "Gap mil (mm)",
                "Clearance mil (mm)",
                "Reference",
                "Modelled ohm",
                "Eps eff",
                "Delay ps/mm",
                "Loss dB/mm",
            ],
            rows,
        )
        + "<p class='note'>Differential gap is edge to edge. Uncontrolled "
        f"default routing: {standard['Line_width_mil']} mil line and space "
        f"({standard['Modelled_Z_ohm']} ohm modelled), not impedance "
        "controlled.</p>"
    )


def rules_section(twin: dict[str, fabcsv.Rows]) -> str:
    rows = []
    for r in twin["FAB_RULES"]:
        if r["Value_mil"] and r["Rule"] != "Maximum stacked microvia levels":
            rows.append([r["Rule"], f"{r['Value_mil']} mil"])
        elif "in)" in r["Notes"]:
            rows.append([r["Rule"], r["Notes"].split("(")[1].rstrip(")")])
        else:
            rows.append([r["Rule"], r["Value_mm"]])
    return "<h2>7. Fabrication rules and capability</h2>" + table(
        ["Rule", "Value"], rows
    )


def notes_section() -> str:
    return (
        "<h2>8. Notes</h2>"
        "<p class='note'>This is a synthetic example document. Tamsworth "
        "Interconnect Co. is a fictional fabricator, and Corvel Coatings, "
        "Ashgrove Laminates and Brightwell Foil, with every product named here, "
        "are fictional too. The Dk, Df and roughness figures are illustrative "
        "and describe no real material.</p>"
        "<p class='note'>Copper roughness is Rz in micrometres, matte and drum "
        "side.</p>"
    )


def render_pages(twin: dict[str, fabcsv.Rows]) -> list[str]:
    """The report's HTML, one string per printed page group. Each group
    starts a new page, so no table is split across a page break."""
    n_copper = sum(1 for row in twin["STACKUP"] if row["Type"] == "Copper")
    doc = {row["Field"]: row["Value"] for row in twin["DOCUMENT"]}
    title = f"<h1>{html.escape(doc['Fabricator'])}: {html.escape(doc['Document type'])}</h1>"
    return [
        title + document_section(twin) + revision_section(twin),
        materials_section(twin) + stackup_section(twin),
        vias_section(twin, n_copper),
        impedance_section(twin),
        rules_section(twin) + notes_section(),
    ]


def write_pdf(pages: list[str], out: Path) -> None:
    fitz: Any = importlib.import_module("fitz")
    buffer = io.BytesIO()
    writer = fitz.DocumentWriter(buffer)
    page = fitz.paper_rect("a4-l")
    where = page + (28, 28, -28, -28)
    for body in pages:
        story = fitz.Story(html=body, user_css=CSS)
        more = True
        while more:
            device = writer.begin_page(page)
            more, _ = story.place(where)
            story.draw(device)
            writer.end_page()
    writer.close()
    document = fitz.open("pdf", buffer.getvalue())
    document.set_metadata(
        {
            "title": "TIC-8L Stackup Report Rev C",
            "author": "Tamsworth Interconnect Co. (fictional)",
            "subject": "Synthetic example stackup report",
            "creator": "",
            "producer": "",
            "creationDate": "D:20261006000000Z",
            "modDate": "D:20261006000000Z",
        }
    )
    document.save(out, garbage=4, deflate=True, no_new_id=True)


def main() -> None:
    write_pdf(render_pages(fabcsv.sections(TWIN)), PDF)
    print(f"wrote {PDF}")


if __name__ == "__main__":
    main()
