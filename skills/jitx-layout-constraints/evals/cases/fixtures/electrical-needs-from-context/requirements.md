# PSU-ISO-01 requirements (synthetic example)

PSU-ISO-01 takes the rack's 48 V bus and gives the controller board an isolated
3.3 V logic supply. Design file: `fixture_electrical_needs_from_context.py`.

1. Input: 48 V nominal, 57 V maximum, on J1 (pad 1 +48 V, pad 2 return). Net
   names VIN48 and GND_P.
2. Output: 3.3 V on J2 (pad 1 +3.3 V, pad 2 return) to the controller board.
   Net names V3V3 and GND_S.
3. The 3.3 V side is isolated from the 48 V input. U1, the Corrow CPI-4833
   module, is the only thing that crosses between them, and GND_S is not tied
   to GND_P anywhere on this board. The PCB layout requirements for the module
   are in its datasheet; the part we need is in `corrow_cpi4833_excerpt.md`.
4. Spacing on our boards follows the house rules in `house_spacing_rules.md`.
5. Fab is Pellingham, 4-layer standard build (`pellingham_lc_fab_sheet.md`).
6. We have not picked the end product's safety standard yet. Compliance is
   working on it, so anything that depends on it stays open for now.
