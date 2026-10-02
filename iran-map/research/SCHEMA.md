# Data schema for the Iran territorial map (c. 1800 – present)

Two independent layers, never mixed:

- **De jure** = *Tehran's own position at the time*: what the Iranian state asserted as its sovereign
  territory (or territory under its suzerainty), regardless of whether others recognized it. A claim
  ends when Tehran renounced it (treaty, ratified arbitration, formal acceptance) — not when it lost control.
- **De facto** = who actually exercised control on the ground. Graded, and includes areas *inside*
  Iran where the central government had no or only nominal authority (tribal confederations,
  autonomous valis/sheikhs/khans, rebel or breakaway governments, foreign occupation), plus foreign
  territory held by Iran.

Geometry is shared through named **regions**; each layer has its own records referencing them.

## File format (JSON)

```jsonc
{
  "regions": [
    {
      "id": "f_erivan_khanate",            // prefix f_ (frontier agent) or i_ (internal agent)
      "name": "Erivan Khanate",
      "name_fa": "خانات ایروان",
      "units": ["ARM1_9", "TUR1_37"],       // keys from build/catalog.md, union = region
      "minus_units": [],                     // optional keys to subtract
      "custom": null,                        // OR, if units cannot express it, a description plus
                                             // an approximate polygon/line [[lon,lat],...] and how to use it
                                             // e.g. {"op":"clip_north_of", "line":[[..],[..]], "within_units":[...], "note":"..."}
      "geometry_confidence": "high|medium|low",
      "geometry_note": "why these units; what the historical extent really was and how it differs"
    }
  ],
  "dejure": [                                // Tehran's position
    {
      "region": "f_erivan_khanate",
      "from": "1800",                        // ISO date, as precise as known: YYYY, YYYY-MM, YYYY-MM-DD
      "to": "1828-02-21",                    // null = still claimed today
      "status": "integral|suzerainty",      // integral = part of the realm; suzerainty = vassal under Iranian overlordship
      "start_event": null, "end_event": "f_ev_turkmenchay",
      "note": "1–3 sentences",
      "date_confidence": "high|medium|low",
      "sources": ["short citation (+URL where possible)"]
    }
  ],
  "defacto": [
    {
      "region": "f_erivan_khanate",
      "from": "1800", "to": "1827-10-01",
      "status": "direct|indirect|contested|none|foreign_occupation|breakaway|iranian_held",
      "controller": "Hosein Qoli Khan Qajar, sardar of Erivan (Iranian governor)",
      "start_event": null, "end_event": "f_ev_fall_of_erivan",
      "note": "...", "date_confidence": "...", "sources": ["..."]
    }
  ],
  "events": [
    {
      "id": "f_ev_turkmenchay",
      "date": "1828-02-21", "end_date": null,
      "title": "Treaty of Turkmenchay",
      "type": "treaty|war|conquest|occupation|withdrawal|arbitration|agreement|renunciation|rebellion|campaign|other",
      "summary": "2–4 sentences: what happened and the territorial effect",
      "layers": ["dejure","defacto"],         // which layer(s) it changes
      "sources": ["..."]
    }
  ]
}
```

### De facto status vocabulary
| status | meaning |
|---|---|
| `direct` | Administered by governors/officials appointed from the Iranian centre. |
| `indirect` | Hereditary local ruler / tribal chief / vali / sheikh / khan who acknowledged the shah (tribute, hostages, khutba) but ran the area himself. |
| `contested` | Active war front or fluid insurgency where control flipped; neither side clearly held it. |
| `none` | Claimed by Tehran but no effective Iranian authority and no other state holding it (e.g. independent tribes). |
| `foreign_occupation` | Held by a foreign state's forces/administration (name it in `controller`). |
| `breakaway` | Held by a rival/separatist government that rejected Tehran (name it). |
| `iranian_held` | Iranian forces/administration holding territory **outside** Tehran's de jure claim at that time. |

Rules:
- Records for one region in one layer must not overlap in time. Gaps are fine (gap = not applicable).
- Inside modern Iran, the internal agent only writes **exceptions**; the renderer assumes `direct` control
  of the core where no record exists. So an internal record is needed wherever control was *not* direct.
- Dates: give the best-supported date; mention alternatives in `note`; set `date_confidence`.
- Sources: prefer Encyclopaedia Iranica, treaty texts, Cambridge History of Iran vol. 7, peer-reviewed
  scholarship and serious monographs (e.g. Kazemzadeh, Atkin, Kashani-Sabet, Schofield, Cronin,
  Atabaki, Beck, Garthwaite, Amanat, Tapper, Ateş). Wikipedia only as a cross-check, not a sole source.
  **Never use or cite Grokipedia.**
