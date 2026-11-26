# Lake DAG store

Derived SQLite database built by `tools/rh-fix/lake-dag.py`.

## Sources

- `.lake/build/lib/lean/**/*.trace` — Lake's own build state (JSON).
- `src/**/*.lean` — source `import` edges.
- `times-rich.txt` — optional measured compile costs.

## Schema

```sql
modules(name TEXT PRIMARY KEY,
        path TEXT,
        dep_hash TEXT,       -- trace depHash
        source_hash TEXT,    -- hash of the .lean input
        olean_hash TEXT,
        ilean_hash TEXT,
        ir_hash TEXT,
        c_hash TEXT,
        schema_version TEXT)

imports(src TEXT, dst TEXT, PRIMARY KEY(src, dst))

costs(module TEXT PRIMARY KEY, median_s REAL, max_s REAL, n INTEGER)
```

Indexes: `imports(dst)`, `modules(dep_hash)`.

## Actual counts (M4, 2026-11-26)

| Table | Rows |
|---|---:|
| modules | 47,886 |
| traced (dep_hash) | **47,868** |
| imports | 528,337 |
| costs | 47,297 |
| DB size | 259 MB |

- `ir_hash` is present for **47,866** modules — i.e. the current
  `Main:elabArts` invocation still produces IR for essentially the whole tree.
  Treat IR as unavoidable until the Lake facet behavior is fixed.
- Average internal project imports per module: **10.7**.

## Example queries

Reverse dependency closure (what rebuilds if `X` changes):

```sql
WITH RECURSIVE cone(m) AS (
  SELECT 'Some.Module'
  UNION
  SELECT i.src FROM imports i JOIN cone c ON i.dst = c.m
)
SELECT COUNT(*) FROM cone;
```

Changed modules by trace hash (compare two DB snapshots):

```sql
ATTACH 'old.sqlite' AS old;
SELECT new.name
FROM modules new JOIN old.modules old USING(name)
WHERE new.dep_hash IS NOT old.dep_hash;
```

Facet coverage:

```sql
SELECT
  SUM(olean_hash IS NOT NULL) AS oleans,
  SUM(ilean_hash IS NOT NULL) AS ileans,
  SUM(ir_hash IS NOT NULL)    AS ir,
  SUM(c_hash IS NOT NULL)     AS c_files
FROM modules;
```

Top internal fan-in:

```sql
SELECT dst, COUNT(*) n FROM imports
WHERE dst NOT LIKE 'Mathlib%'
GROUP BY dst ORDER BY n DESC LIMIT 20;
```

## Limits

- Trace `deps.imports` stores **aggregate transitive hashes**, not the full
  module edge list; edges come from source imports (or `lean --deps`).
- Traces exist only for targets already built.
- Schema is Lake-version-specific (currently `2025-09-10`).
- Derived data: rebuild after significant tree/build changes.
