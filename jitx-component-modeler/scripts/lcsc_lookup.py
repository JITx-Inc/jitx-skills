#!/usr/bin/env python3
"""Look up LCSC/JLCPCB parts: stock, pricing, datasheet, and KiCad footprint.

Uses easyeda2kicad (pip install easyeda2kicad) for footprint/symbol data
and the LCSC public API for real-time stock and pricing.

Usage:
    # Check stock and pricing
    python lcsc_lookup.py C165948

    # Download KiCad footprint
    python lcsc_lookup.py C165948 --footprint -o usb_c.kicad_mod

    # Get pinout data
    python lcsc_lookup.py C165948 --pinout

    # Full pipeline: lookup + footprint + convert to JITX
    python lcsc_lookup.py C165948 --footprint -o usb_c.kicad_mod && \\
        python kicad_to_jitx.py usb_c.kicad_mod --class-name USB_C_16P

    # All info at once
    python lcsc_lookup.py C165948 --all -o usb_c.kicad_mod

Setup:
    pip install easyeda2kicad requests
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' package required. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# LCSC Stock/Price API (real-time, no auth)
# ---------------------------------------------------------------------------

LCSC_DETAIL_URL = "https://wmsc.lcsc.com/ftps/wm/product/detail"


def lcsc_stock(lcsc_id: str) -> dict | None:
    """Fetch real-time stock and pricing from LCSC.

    Returns dict with: mpn, manufacturer, description, stock, prices,
    datasheet_url, package, category. Returns None on failure.
    """
    try:
        resp = requests.get(
            LCSC_DETAIL_URL,
            params={"productCode": lcsc_id},
            headers={"User-Agent": "jitx-skill/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"LCSC API error: {e}", file=sys.stderr)
        return None

    result = data.get("result")
    if not result:
        return None

    # Extract pricing tiers
    prices = []
    for tier in result.get("productPriceList", []):
        try:
            price = float(tier.get("productPrice", 0))
        except (ValueError, TypeError):
            price = 0.0
        prices.append({
            "qty": tier.get("startPurchasedNumber", 0),
            "price_usd": price,
        })

    return {
        "lcsc": lcsc_id,
        "mpn": result.get("productModel", ""),
        "manufacturer": result.get("brandNameEn", ""),
        "description": result.get("productIntroEn", ""),
        "stock": result.get("stockNumber", 0),
        "stock_domestic": result.get("stockSz", 0),
        "stock_overseas": result.get("stockJs", 0),
        "prices": prices,
        "datasheet_url": result.get("pdfUrl", ""),
        "package": result.get("encapStandard", ""),
        "category": result.get("parentCatalogName", ""),
        "min_qty": result.get("minBuyNumber", 1),
        "product_url": f"https://www.lcsc.com/product-detail/{lcsc_id}.html",
    }


# ---------------------------------------------------------------------------
# EasyEDA footprint/symbol via easyeda2kicad
# ---------------------------------------------------------------------------

def get_footprint(lcsc_id: str, output_path: str | None = None) -> str | None:
    """Download KiCad footprint for an LCSC part.

    Returns the .kicad_mod content as a string, or None on failure.
    Optionally writes to output_path.
    """
    try:
        from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
        from easyeda2kicad.easyeda.easyeda_importer import EasyedaFootprintImporter
        from easyeda2kicad.kicad.export_kicad_footprint import ExporterFootprintKicad
    except ImportError:
        print("Error: 'easyeda2kicad' package required. Run: pip install easyeda2kicad", file=sys.stderr)
        return None

    try:
        api = EasyedaApi()
        cad_data = api.get_cad_data_of_component(lcsc_id=lcsc_id)
        if not cad_data:
            print(f"No CAD data found for {lcsc_id}", file=sys.stderr)
            return None

        fp_importer = EasyedaFootprintImporter(easyeda_cp_cad_data=cad_data)
        fp = fp_importer.get_footprint()
        exporter = ExporterFootprintKicad(footprint=fp)

        if output_path:
            outpath = Path(output_path)
            outpath.parent.mkdir(parents=True, exist_ok=True)
            exporter.export(
                footprint_full_path=str(outpath),
                model_3d_path=str(outpath.parent / "3d"),
            )
            return outpath.read_text()
        else:
            # Export to temp file and read back
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".kicad_mod", delete=False, mode="w") as tmp:
                tmp_path = tmp.name
            exporter.export(
                footprint_full_path=tmp_path,
                model_3d_path="/tmp/3d",
            )
            content = Path(tmp_path).read_text()
            Path(tmp_path).unlink(missing_ok=True)
            return content

    except Exception as e:
        print(f"Footprint error: {e}", file=sys.stderr)
        return None


def get_pinout(lcsc_id: str) -> list[dict] | None:
    """Get pin names and numbers from EasyEDA symbol data.

    Returns list of {name, number, type} dicts, or None on failure.
    """
    try:
        from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
        from easyeda2kicad.easyeda.easyeda_importer import EasyedaSymbolImporter
    except ImportError:
        print("Error: 'easyeda2kicad' package required. Run: pip install easyeda2kicad", file=sys.stderr)
        return None

    try:
        api = EasyedaApi()
        cad_data = api.get_cad_data_of_component(lcsc_id=lcsc_id)
        if not cad_data:
            return None

        sym_importer = EasyedaSymbolImporter(easyeda_cp_cad_data=cad_data)
        symbol = sym_importer.get_symbol()

        pins = []
        for pin in symbol.pins:
            pins.append({
                "name": pin.name.text,
                "number": pin.settings.spice_pin_number,
                "type": pin.settings.type if hasattr(pin.settings, "type") else "unspecified",
            })
        return pins

    except Exception as e:
        print(f"Pinout error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Look up LCSC/JLCPCB parts: stock, pricing, and KiCad footprint.",
    )
    parser.add_argument("lcsc_id", help="LCSC part code (e.g., C165948, C8734)")
    parser.add_argument("--footprint", action="store_true", help="Download KiCad footprint")
    parser.add_argument("--pinout", action="store_true", help="Get pin names and numbers")
    parser.add_argument("--all", action="store_true", help="Stock + footprint + pinout")
    parser.add_argument("-o", "--output", help="Output path for .kicad_mod file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    lcsc_id = args.lcsc_id.upper()
    if not lcsc_id.startswith("C"):
        lcsc_id = "C" + lcsc_id

    do_footprint = args.footprint or args.all
    do_pinout = args.pinout or args.all

    result = {}

    # Stock/pricing (always)
    t0 = time.time()
    stock_data = lcsc_stock(lcsc_id)
    stock_time = time.time() - t0

    if stock_data:
        result["stock"] = stock_data
        if not args.json:
            s = stock_data
            print(f"{'Part:':<14} {s['mpn']} ({s['manufacturer']})")
            print(f"{'LCSC:':<14} {s['lcsc']}")
            print(f"{'Package:':<14} {s['package']}")
            print(f"{'Stock:':<14} {s['stock']:,}")
            print(f"{'Description:':<14} {s['description'][:80]}")
            if s["prices"]:
                p1 = s["prices"][0]
                print(f"{'Price:':<14} ${p1['price_usd']:.4f} (qty {p1['qty']}+)")
            if s["datasheet_url"]:
                print(f"{'Datasheet:':<14} {s['datasheet_url']}")
            print(f"{'Lookup:':<14} {stock_time:.2f}s")
    else:
        print(f"Part {lcsc_id} not found on LCSC", file=sys.stderr)
        if not do_footprint and not do_pinout:
            sys.exit(1)

    # Footprint
    if do_footprint:
        print(f"\nDownloading footprint...", file=sys.stderr)
        t0 = time.time()
        fp_content = get_footprint(lcsc_id, args.output)
        fp_time = time.time() - t0

        if fp_content:
            result["footprint_path"] = args.output or "(stdout)"
            result["footprint_size"] = len(fp_content)
            if not args.json:
                if args.output:
                    print(f"{'Footprint:':<14} {args.output} ({len(fp_content)} bytes, {fp_time:.2f}s)")
                else:
                    print(f"\n--- KiCad Footprint ({fp_time:.2f}s) ---")
                    print(fp_content)
        else:
            print("Failed to download footprint", file=sys.stderr)

    # Pinout
    if do_pinout:
        t0 = time.time()
        pins = get_pinout(lcsc_id)
        pin_time = time.time() - t0

        if pins:
            result["pins"] = pins
            if not args.json:
                print(f"\n{'Pinout:':<14} {len(pins)} pins ({pin_time:.2f}s)")
                for pin in pins:
                    print(f"  {pin['number']:>6s}  {pin['name']}")
        else:
            print("Failed to get pinout", file=sys.stderr)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        print()


if __name__ == "__main__":
    main()
