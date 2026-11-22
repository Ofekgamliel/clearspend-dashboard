# Python 3.9 compatibility ledger

ClearSpend currently runs on Python 3.9. This ledger records compatibility
workarounds encountered during development so they can be reviewed and removed
deliberately when the runtime is upgraded. Add an entry only after a concrete
Python 3.9 issue is encountered; this is not a list of speculative cleanup.

## Open compatibility items

### Database-driver versions

**Encountered during:** PostgreSQL migration foundation.

The project pins `psycopg[binary]==3.2.13` and `psycopg-pool==3.2.8` because
these are the selected release lines compatible with the current Python 3.9
runtime. Newer driver lines require a newer Python runtime.

**After upgrading Python:** review current supported Psycopg and psycopg-pool
releases together, update both pins, and rerun the database connection, pool,
TLS, migration, and dual-engine test suites before removing this entry.

### Runtime union type aliases

**Encountered during:** PostgreSQL connection-boundary implementation.

Python 3.9 cannot evaluate a standalone runtime type alias using the `|` union
operator. `from __future__ import annotations` defers function and class
annotations, but it does not defer the value assigned here. The compatible
form is therefore:

```python
DatabaseTarget = Union[DatabaseSource, PostgreSQLPool]
```

instead of:

```python
DatabaseTarget = DatabaseSource | PostgreSQLPool
```

**After upgrading Python:** once the minimum version supports PEP 604 runtime
unions, replace this workaround with the `|` form and rerun the synthetic suite.

## Maintenance rule

Whenever development exposes another Python 3.9-specific dependency pin,
syntax restriction, standard-library gap, or behavioral workaround:

1. Record where it was encountered and the exact workaround.
2. State the upgrade-time adjustment and the tests needed to validate it.
3. Keep the workaround in code until the project's declared minimum Python
   version has actually changed.
4. Remove the ledger entry only when the workaround has been removed and its
   replacement verified.
