# Map data: regions, polities, claims and control

This folder is the source of truth for the map. Edit these files, then run:

```
python3 build/validate.py      # checks only; exit 1 on errors
python3 build/build_atlas.py   # validates, then writes data/atlas.topo.json and data/atlas.json
```

`research/` holds the original research and fact-check files. They were converted into this folder once by
`build/migrate.py`, which now refuses to run again so it cannot overwrite hand edits.

## The model

**Regions** (`regions.json`) are named shapes: a khanate, a tribal range, an occupation zone, a treaty parcel.
Each one is built from modern admin units (`units`, keys from `build/catalog.md`), optionally minus other units,
a hand-made `custom` shape, other regions (`minus_regions`), or clipped to a region (`clip_to_region`).
Regions may overlap freely. `kind` is `frontier`, `internal` (inside modern Iran), `core` or `reference`.

**Atoms** are a build product, not something you edit. The build overlays every region and cuts the map into
the smallest pieces that are each covered by exactly the same set of regions. Records stay keyed to regions;
when a new region is added, the atoms are recomputed and no record has to change.

**Polities** (`polities.json`) are the actors: states, khanates, principalities, sheikhdoms, tribal
confederations, movements and rebel governments, with optional `from`/`to` lifespans. `iran` carries its regimes
(Qajar, Pahlavi, Islamic Republic). The validator warns when a record has a polity acting outside its lifespan.

**Claims** (`claims.jsonl`, one record per line) are the de jure layer: `polity` claims `region` from `from` to
`to` (`null` = still claimed), as `sovereignty` or `suzerainty`. The map shows Iran's claims (Tehran's own
position at the time), but any polity's claims can be recorded.

**Control** (`control.jsonl`) is the de facto layer: in `region`, from `from` to `to`, the `controller` held the
land in a given `mode`:

| mode | meaning |
|---|---|
| `administered` | the controller governed through its own officials |
| `occupied` | military occupation |
| `autonomous` | a local ruler governed, acknowledging `allegiance` as overlord |
| `independent` | no state authority at all (stateless tribes) |
| `insurgent` | a rebel or rival government rejecting the claimant |
| `contested` | a front line or fluid insurgency; list the other side(s) in `contested_with` |

`allegiance` is only meaningful for `autonomous` records. `controller_note` keeps the specific people and
units involved. The map's categories (direct rule, autonomous under the shah, held by another power, and so on)
are derived from controller, allegiance and mode relative to Iran, so they are never stored.

`precedence` (default 1) is 0 only for baseline records, such as direct rule over the core, which any more
specific record should override.

**Overlaps.** Several control records may cover the same place at once (a tribe's autonomy inside a foreign
occupation zone). The map draws all of them. Where one summary per atom is needed (area totals, outlines,
divergence, tooltip headline), the record with the highest precedence wins, then the most severe loss of
control (foreign > rival > contested > independent > autonomous > direct), then the smaller region, then the
later start. The same rule runs in `build/build_atlas.py` and in `index.html`;
`build/check_consistency.js` confirms they agree at every change point.

**Events** (`events.jsonl`) are dated happenings (treaties, battles, occupations) with `layers` tags.
Records point to them through `start_event` and `end_event`.

**Sources** (`sources.json`) are a bibliography. Records cite works by id: `"cites": ["s012", {"src": "s040",
"note": "cross-check only"}]`, with an optional pinpoint note.

Dates are `YYYY`, `YYYY-MM` or `YYYY-MM-DD` (Gregorian). Every record carries a `date_confidence` and every
region a `geometry_confidence` (`high`, `medium`, `low`).

## Adding an earlier period

The model does not assume a single Iranian state, so competing claimants (for example the courts of 1722–29
or 1747–96) are separate polities, each with its own claims and control records. The map currently focuses on
`iran`: the focal polity is one constant (`FOCAL`) in `build_atlas.py`, passed to the page in `atlas.json`.
