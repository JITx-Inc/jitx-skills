# Answers

## 1

Environment setup belongs to the base `jitx` skill; the substrate skill defers to it. Run that first.

## 2

On the substrate. Put the layer-to-via mapping on the `Substrate` subclass, for example as a property:

```python
class MySubstrate(Substrate):
    @property
    def signal_via(self) -> dict[int, type[Via]]:
        return {1: self.uVia_L1_L2, 2: self.uVia_L1_L4}
```

The design then queries `self.substrate.signal_via[layer]` instead of keeping its own dict.

## 3

Neither inline subclass: instantiate it, `stackup = GenericStackup()`. An empty `@inline class stackup(GenericStackup): pass` adds nothing. Inline-subclass only when the body declares layers.

## 4

Ordinary Python: put the via classes on a mixin class and inherit it in both substrates.

```python
class SharedVias:
    class StdVia(Via): ...

class SubstrateA(Substrate, SharedVias): ...
class SubstrateB(Substrate, SharedVias): ...
```

## 5

`velocity` is in mm/s (millimetres per second; `phase_velocity` returns mm/s), and `insertion_loss` is in dB/mm.

## 6

The gap between the P and N conductors, edge to edge, in mm. It is not a centre-to-centre pitch.

## 7

- `offset`: the centre-to-centre distance between fence via rows. It is also the default for `initial_offset` when that is unset.
- `initial_offset`: the perpendicular distance from the boundary of the route or copper feature to the centres of the first row of vias. Positive is outwards, and it must be positive for routes.

## 8

For pours only: when true, the fence follows the pour's original pre-isolation outline; when false, the post-isolation shape. It defaults to true.

## 9

The last listed layer must be a `Dielectric`; it becomes the innermost (centre) dielectric. Anything else raises `TypeError` when the stackup is instantiated.

## 10

Give the layers a `ViaDiameter` with `nfp=` in the via's `diameters`:

```python
diameters = {0: 0.5, (1, 2): ViaDiameter(0.5, nfp=0.2), -1: 0.5}
```

## 11

By the via's layer span: `stop_layer` sets the depth of a bottom backdrill (the via connects down to that layer and the stub below is drilled out), and `start_layer` sets a top backdrill's depth. `Backdrill` itself has no depth field.

## 12

Proxies, not instances of your classes. Read fields off the element itself; `type(layer).roughness` raises `AttributeError`. Each element only carries its own class's fields, so decompose by `Dielectric` to read `dielectric_coefficient` and by `Conductor` for `roughness`.

## 13

The test is outside the JITX instantiation context, so the design is never instantiated and `decompose` finds nothing without raising. Subclass `jitx.test.TestCase` instead of `unittest.TestCase`.

## 14

No, never both: set it on the class or pass it to the constructor. Both raises `ValueError` (so does neither).

## 15

`dielectric_coefficient` holds Dk and `loss_tangent` holds Df.

## 16

No. Via layer indices count conductors only; dielectrics and solder mask take no index. `-1` (`Side.Bottom`) is the bottom conductor.

## 17

Define a routing structure for that section on the substrate, tag the route segment with a `Tag` subclass, and apply the structure by tag: `design_constraint(NarrowTag()).routing_structure(MySubstrate.RS_NARROW, ref_net=self.GND)`. Not a NeckDown.

## 18

`jitxexamples.patterns.fenced_pour_outline`. It composes a `Tag`, a `design_constraint(FenceOutlineTag()).fence_via(via, pattern)` rule on the substrate, a tagged `Pour` on the ground net, and an optional `KeepOut` over the same outline.

## 19

(a) The narrow-strip limit, eps_eff = (er + 1) / 2 = (3.6 + 1) / 2 = 2.3. The real eps_eff of a 50 ohm line is higher, so that value overstates the velocity: the docstring puts the error at about 11% for a 50 ohm line on er = 4.4.

(b) With equal heights, eps_eff = (3.2 + 3.8) / 2 = 3.5, exact for a thin strip.
