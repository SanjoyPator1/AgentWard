# HAPI FHIR

The FHIR server the agent and fhir-mcp both talk to. Runs from the
`docker-compose.yml` at the repo root, pinned to `hapiproject/hapi:v8.10.0-3`,
backed by Postgres (`postgres:17`) rather than the default in-memory database.

## Why Postgres, and what that does and doesn't give you

Two reasons: switching databases later, once features actually depend on
this server, would cost much more than doing it now. And data persisting
across normal restarts means not reloading patients every time Docker
restarts.

What it doesn't give you: a readable view of the data. HAPI stores FHIR
resources in its own internal tables (`HFJ_RESOURCE`, `HFJ_RES_VER`, and
search-index tables), mostly as serialized blobs, not one row per Patient
with columns you'd recognize. For actually looking at data, use the FHIR API
or HAPI's own web UI, not raw SQL.

## A schema error you might hit

The very first startup against a fresh Postgres can fail with
`syntax error at or near "seq_resource_type"` (Hibernate running ANSI
`select next value for X` instead of Postgres's own `nextval('X')`), which
breaks schema creation partway through and leaves the database half-built.
Fixed by setting `spring.jpa.properties.hibernate.dialect` explicitly to
HAPI's own Postgres dialect class, Hibernate doesn't reliably auto-detect it
otherwise. If you hit this, `./reset.sh` first, don't just restart, the
schema is already broken and won't self-heal.

## A heap size crash you might hit

Loading a batch of patients can fail partway through with
`OutOfMemoryError: Java heap space`, seen first while still on the old H2
setup. The image's built-in default JVM heap is small and doesn't scale up
just because your machine has memory to spare, some Synthea patient bundles
are tens of MB, and enough of those processed in a row can exceed it. Fixed
here by setting `JAVA_TOOL_OPTIONS: -Xmx4g` on the hapi-fhir service. If it
recurs at a larger population size, that's the number to raise, alongside
checking Docker Desktop's own memory allocation actually has room for it.

## Starting it

```
docker compose up -d hapi-fhir
```

This also starts Postgres, since hapi-fhir depends on it. FHIR base URL:
`http://localhost:8080/fhir`. HAPI's own browsable UI is at
`http://localhost:8080/`. Takes a little while to finish starting,
`load_synthea_data.sh` waits for it automatically.

## Resetting to empty

```
./reset.sh
```

This wipes the Postgres volume, not just the container, since data now
persists across a normal restart. Use this when you need a guaranteed clean
slate, for example before an eval run.

## Loading a dataset

```
./load_synthea_data.sh <label>
```

`<label>` matches a folder under `data/synthea_output/`, e.g. `seed-1000-n200`.
Loads in the only order that actually works: hospitals, then practitioners,
then every patient bundle. See `data/README.md` for why that order matters.

## Typical cycle

```
./reset.sh
./load_synthea_data.sh seed-1000-n200
```

Gives you the same known-good state every time, no matter what got created,
updated, or deleted on the server since the last reset. If you're just
picking up dev work again and didn't reset, your previously loaded data is
still there, that's the point of Postgres.

## Adminer (raw DB browser)

```
docker compose up -d adminer
```

At `http://localhost:8081`, log in with system Postgres, server `postgres`,
username `hapi`, password `hapi`, database `hapi`. You'll see HAPI's internal
tables, not FHIR resources directly, this is for looking at the database
layer itself, not for reading patient data.
