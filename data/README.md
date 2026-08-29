# Data

Nothing generated lives in git here. `synthea_output/` holds the raw Synthea
bundles and is gitignored entirely, it can run into gigabytes at the 20,000
patient scale.

What's committed instead:

- `config/` — the Synthea properties files and module lists used to generate
  each dataset.
- this README, once the substrate is built, gets the exact command, Synthea
  version, and seed used for each generation run, so any dataset here can be
  reproduced from scratch rather than stored.
