"""Ordered PostgreSQL schema migrations."""

from clearspend.database.postgresql_migrations import (
    v001_observation_reviews,
    v002_transaction_browsing,
    v003_merchant_management,
    v004_import_linkage,
)


DEFAULT_POSTGRESQL_MIGRATIONS = (
    v001_observation_reviews,
    v002_transaction_browsing,
    v003_merchant_management,
    v004_import_linkage,
)
