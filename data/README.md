# Data

Nothing generated lives in git here. `synthea_output/` holds the raw Synthea
bundles and is gitignored entirely, it can run into gigabytes at the 20,000
patient scale.

What's committed instead:

- this README's generation log below.
- a `config/` folder, if and when we actually need a custom
  `synthea.properties` beyond Synthea's defaults. Doesn't exist yet, every
  batch so far has used defaults, no need to have an empty folder for it.

## Regenerating

Built and run from `substrate/synthea/`:

```
../substrate/synthea/generate.sh <seed> <population> [label]
```

Pinned to Synthea `v4.0.0` (set in `substrate/synthea/Dockerfile`).

## Generation log

| Label | Seed | Population | Synthea version | Purpose |
|---|---|---|---|---|
| seed-1000-n200 | 1000 | 200 | v4.0.0 | first substrate smoke test, 214 patients (200 alive). Verified: valid FHIR bundles, 63 diabetes, 37 hypertension, 13 CKD cases |

Add a row here every time a dataset actually gets generated, so any of them
can be reproduced later without guessing which seed made which folder.
