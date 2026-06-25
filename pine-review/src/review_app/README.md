# Pine Review App (ICT + Structure labels)

## Structure-to-Drawing mapping

### ICT overlay endpoint

`GET /api/ict-overlay`

Returns overlay primitives (drawn on the canvas as the _overlay layer_):

- `fvgs`: FVG rectangles (not persisted as drawings)
- `order_blocks`: Order Block rectangles (not persisted as drawings)
- `liquidity`: unswept liquidity lines (not persisted as drawings)
- `structure_breaks`: BOS/CHoCH labeled boxes (not persisted as drawings)

#### Swing structure labels (new)

- `swing_labels`: array of `{ time, price, label }` where `label ∈ { "HH", "HL", "LL", "LH" }`

### Which items become persisted drawings?

On the client, when ICT overlay is enabled (`toggleIct`):

- `swing_labels[]` are converted into persisted, editable drawings:
  - drawing `type`: `"text"`
  - `note`: the label (`HH`, `HL`, `LL`, `LH`)
  - `points`: `[{ time, price }]`

Drawings created from `swing_labels` are marked with:

- `drawing.style.generated_structure_labels === true`

So they can be removed when ICT is toggled off, and they avoid polluting user drawings.

### Dedupe strategy

Generated text drawings use a deterministic id derived from:

- `symbol`, `timeframe`, `label`, `time`, `price` (rounded)

The client removes all previous generated label drawings and recreates them on each overlay load.
