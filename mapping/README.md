# Mapping tables

Hand-curated, version-controlled tables that glue the open data layers together
(design doc §6). All of them are validated by `anatomy-build validate` against the
FMA import: every ID must exist in the MSK subset, and for `muscle_groups.yaml`
the FMA preferred name (or a synonym) must contain `expect_name`, so a wrong but
existing ID fails loudly instead of mapping an exercise to the wrong muscle.

| File | Purpose |
|---|---|
| `muscle_groups.yaml` | informal exercise-db group (`hamstrings`) → FMA IDs |
| `relations.yaml` | authored `antagonist_of` / `synergist_of` pairs (symmetric) |
| `joints.yaml` | joint FMA ID → the two bones it connects; resolves derived `crosses_joint` |
| `local_ids.yaml` | `ax:` structures that have no FMA entry |

**Status:** the FMA IDs below were entered from memory of the FMA numbering and have
not yet been checked against a real FMA import in this repository. Run
`anatomy-build validate --fma-file …` after fetching FMA; anything the validator
flags must be corrected before the first bundle is built.
