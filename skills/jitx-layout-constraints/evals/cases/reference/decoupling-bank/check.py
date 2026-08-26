#!/usr/bin/env python3
"""Capture and check the built decoupling-bank reference."""

import math

import jitx
from jitxlib.parts import Capacitor
from jitx.via import Via

from .design import DecouplingReference, query_capacitor_geometry


def main() -> int:
    with jitx.runtime as runtime:  # pyright: ignore[reportAttributeAccessIssue]
        rd = runtime.submit(DecouplingReference)
        rd.capture()

    bank = rd.root.circuit.decoupling
    unrealized = [route for route in bank.escape_routes if not route.traces]
    if unrealized:
        raise AssertionError(f"{len(unrealized)} escape routes did not realize")
    print(
        f"[PASS] escape routes realized: "
        f"{len(bank.escape_routes)}/{len(bank.escape_routes)}"
    )

    queried_caps = [
        cap
        for _, cap in rd.query(Capacitor)
        if any(cap is owned for owned in bank.capacitors)
    ]
    if len(queried_caps) != len(bank.capacitors):
        raise AssertionError(
            f"queried {len(queried_caps)} owned capacitors, "
            f"expected {len(bank.capacitors)}"
        )
    queried_geometry = tuple(query_capacitor_geometry(cap) for cap in queried_caps)
    expected_geometry = (bank.cap_geometry, bank.package_rotation)
    if any(item != expected_geometry for item in queried_geometry):
        raise AssertionError("captured capacitor geometry differs from solver input")
    print(f"[PASS] queried capacitor geometry: {len(queried_geometry)}")

    tolerance = 1e-6  # skill default: 0.000001 mm placement readback tolerance
    for cap in queried_caps:
        index = next(
            index
            for index, owned in enumerate(bank.capacitors)
            if cap is owned
        )
        expected = bank.solution.placements[index]
        if cap.transform is None:
            raise AssertionError("captured capacitor has no placement transform")
        actual = cap.transform.translation
        error = math.hypot(actual[0] - expected.center[0], actual[1] - expected.center[1])
        if error > tolerance:
            raise AssertionError(
                f"capacitor placement error {error:.9f} mm exceeds {tolerance:.9f} mm"
            )
    print(
        f"[PASS] solver placements read back with jitx.query: "
        f"{len(queried_caps)}/{len(bank.capacitors)}"
    )

    owned_vias = (*bank.power_vias, *bank.return_vias)
    queried_vias = [
        via
        for _, via in rd.query(Via)
        if any(via is owned for owned in owned_vias)
    ]
    if len(queried_vias) != len(owned_vias):
        raise AssertionError(
            f"queried {len(queried_vias)} owned vias, expected {len(owned_vias)}"
        )
    nets = rd.nets()
    for via in queried_vias:
        if any(via is owned for owned in bank.power_vias):
            index = next(i for i, owned in enumerate(bank.power_vias) if via is owned)
            expected = bank.solution.placements[index].power_via
            expected_net_member = bank.capacitors[index].p1
        else:
            index = next(i for i, owned in enumerate(bank.return_vias) if via is owned)
            expected = bank.solution.placements[index].return_via
            expected_net_member = bank.capacitors[index].p2
        if via.transform is None:
            raise AssertionError("captured via has no placement transform")
        actual = via.transform.translation
        error = math.hypot(actual[0] - expected[0], actual[1] - expected[1])
        if error > tolerance:
            raise AssertionError(
                f"via placement error {error:.9f} mm exceeds {tolerance:.9f} mm"
            )
        if nets.find(via) is not nets.find(expected_net_member):
            raise AssertionError("captured via resolved to the wrong net")
    print(f"[PASS] solver vias and net membership: {len(queried_vias)}")
    print(
        "[PASS] solver loop areas: "
        + ", ".join(f"{area:.6f} mm^2" for area in bank.loop_areas)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
