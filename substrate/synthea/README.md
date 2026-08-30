# Synthea

Generates the synthetic patients everything else in this project runs on.
Built from source, pinned to release `v4.0.0`, so the exact version used is
never a moving target.

## Running it

```
./generate.sh <seed> <population> [label]
```

Output lands in `data/synthea_output/<label>/`, one subfolder per generation
run, so a dev cohort and a held-out cohort (different seeds, per the
anti-leakage rule in the project brief) never overwrite each other.

## Things worth knowing before picking numbers

- **Population size affects which conditions show up, there's no flag to
  force a condition.** Synthea's disease modules fire based on realistic
  age/race/gender incidence, not a toggle you flip. A small population may
  simply not contain enough patients matching a specific cohort query. If a
  feature's oracle keeps coming up empty, check population size before
  assuming the agent or the query is wrong.
- Default export is FHIR R4, which is what HAPI FHIR and fhir-mcp both
  expect. No custom `synthea.properties` is needed yet, defaults are enough
  for now; one goes in `data/config/` if and when we need to override
  something.
- Bumping `SYNTHEA_VERSION` in the Dockerfile changes what "the same seed"
  actually produces. Treat a version bump as a deliberate decision, recorded
  in `data/README.md`, not a silent side effect of a routine rebuild.
