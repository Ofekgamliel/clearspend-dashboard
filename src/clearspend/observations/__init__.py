"""Financial-observation rules, review state, and read models.

Transaction anomalies, monthly comparisons, recurring amount changes, and
recurring billing-cycle, standalone-fee, and historical-pattern primitives now
have a pure Python owner. Single-month and long-period rules also share typed
coordination, read-model adapter, and presentation boundaries. The existing
browser engine remains authoritative while the new unified read service and
compatibility serializer stay internal, until full cross-engine parity and API
integration are complete.
"""
