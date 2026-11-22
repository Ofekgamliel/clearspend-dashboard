from __future__ import annotations

from typing import Any


VERSION = 3
NAME = "merchant_management"

TABLE_COLUMNS = {
    "merchant_mappings": {
        "merchant_normalized", "category", "subcategory", "updated_at",
    },
    "import_coverage": {
        "import_id", "card_last4", "statement_month", "statement_period",
        "statement_as_of_date", "purchase_date_from", "purchase_date_to",
        "billing_date_from", "billing_date_to", "finalized_rows", "pending_rows",
        "outside_cycle_rows", "official_total",
    },
    "recurring_profiles": {
        "canonical_group_id", "display_name", "verdict", "recurring_type",
        "cadence", "cadence_months", "lifecycle_status", "end_month",
        "review_count", "updated_at",
    },
    "recurring_profile_members": {
        "canonical_group_id", "merchant_normalized", "included", "updated_at",
    },
}

INDEXES = {
    "idx_import_coverage_card_month",
    "idx_recurring_members_merchant",
}

CREATE_STATEMENTS = (
    """CREATE TABLE clearspend.merchant_mappings (
      merchant_normalized TEXT PRIMARY KEY,
      category TEXT NOT NULL,
      subcategory TEXT,
      updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE clearspend.import_coverage (
      import_id BIGINT NOT NULL REFERENCES clearspend.imports(id) ON DELETE CASCADE,
      card_last4 TEXT NOT NULL,
      statement_month TEXT,
      statement_period TEXT,
      statement_as_of_date TEXT,
      purchase_date_from TEXT,
      purchase_date_to TEXT,
      billing_date_from TEXT,
      billing_date_to TEXT,
      finalized_rows INTEGER NOT NULL DEFAULT 0,
      pending_rows INTEGER NOT NULL DEFAULT 0,
      outside_cycle_rows INTEGER NOT NULL DEFAULT 0,
      official_total TEXT,
      PRIMARY KEY(import_id,card_last4)
    )""",
    """CREATE INDEX idx_import_coverage_card_month
    ON clearspend.import_coverage(card_last4,statement_month)""",
    """CREATE TABLE clearspend.recurring_profiles (
      canonical_group_id TEXT PRIMARY KEY,
      display_name TEXT NOT NULL,
      verdict TEXT NOT NULL CHECK(verdict IN ('recurring','not_recurring')),
      recurring_type TEXT,
      cadence TEXT,
      cadence_months INTEGER,
      lifecycle_status TEXT NOT NULL DEFAULT 'active'
        CHECK(lifecycle_status IN ('active','ended','paused','unknown')),
      end_month TEXT,
      review_count INTEGER NOT NULL DEFAULT 1,
      updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE clearspend.recurring_profile_members (
      canonical_group_id TEXT NOT NULL
        REFERENCES clearspend.recurring_profiles(canonical_group_id) ON DELETE CASCADE,
      merchant_normalized TEXT NOT NULL,
      included BOOLEAN NOT NULL DEFAULT TRUE,
      updated_at TEXT NOT NULL,
      PRIMARY KEY(canonical_group_id,merchant_normalized)
    )""",
    """CREATE INDEX idx_recurring_members_merchant
    ON clearspend.recurring_profile_members(merchant_normalized,included)""",
    """CREATE FUNCTION clearspend.apply_merchant_mapping_after_insert()
    RETURNS TRIGGER LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
    DECLARE
      mapped_category TEXT;
      mapped_subcategory TEXT;
    BEGIN
      SELECT mapping.category,mapping.subcategory
      INTO mapped_category,mapped_subcategory
      FROM clearspend.merchant_mappings AS mapping
      WHERE mapping.merchant_normalized=NEW.merchant_normalized;
      IF FOUND THEN
        NEW.user_category := mapped_category;
        NEW.user_subcategory := mapped_subcategory;
      END IF;
      RETURN NEW;
    END
    $$""",
    """CREATE TRIGGER apply_merchant_mapping_after_insert
    BEFORE INSERT ON clearspend.transactions
    FOR EACH ROW EXECUTE FUNCTION clearspend.apply_merchant_mapping_after_insert()""",
)

PRIVILEGE_STATEMENTS = (
    """REVOKE ALL PRIVILEGES ON TABLE
    clearspend.merchant_mappings, clearspend.import_coverage,
    clearspend.recurring_profiles, clearspend.recurring_profile_members
    FROM PUBLIC, anon, authenticated, service_role""",
    """GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    clearspend.merchant_mappings, clearspend.import_coverage,
    clearspend.recurring_profiles, clearspend.recurring_profile_members
    TO clearspend_app""",
    """REVOKE ALL PRIVILEGES ON FUNCTION
    clearspend.apply_merchant_mapping_after_insert()
    FROM PUBLIC, anon, authenticated, service_role, clearspend_app""",
)


def apply(connection: Any) -> None:
    for statement in CREATE_STATEMENTS + PRIVILEGE_STATEMENTS:
        connection.execute(statement)


def _privileges(connection: Any, object_name: str) -> set[str]:
    return {
        row["privilege_type"]
        for row in connection.execute(
            """SELECT privilege_type FROM information_schema.table_privileges
            WHERE table_schema='clearspend' AND table_name=?
            AND grantee='clearspend_app'""",
            (object_name,),
        ).fetchall()
    }


def verify(connection: Any) -> list[str]:
    problems: list[str] = []
    expected_privileges = {"SELECT", "INSERT", "UPDATE", "DELETE"}
    for table, expected_columns in TABLE_COLUMNS.items():
        row = connection.execute(
            "SELECT to_regclass(?) IS NOT NULL AS present",
            (f"clearspend.{table}",),
        ).fetchone()
        if not row["present"]:
            problems.append(f"Missing table: clearspend.{table}")
            continue
        columns = connection.execute(
            """SELECT column_name FROM information_schema.columns
            WHERE table_schema='clearspend' AND table_name=?""",
            (table,),
        ).fetchall()
        actual_columns = {column["column_name"] for column in columns}
        for column in sorted(expected_columns - actual_columns):
            problems.append(f"Missing column: clearspend.{table}.{column}")
        if _privileges(connection, table) != expected_privileges:
            problems.append(f"Incorrect clearspend_app privileges: clearspend.{table}")

    for index in sorted(INDEXES):
        row = connection.execute(
            "SELECT to_regclass(?) IS NOT NULL AS present",
            (f"clearspend.{index}",),
        ).fetchone()
        if not row["present"]:
            problems.append(f"Missing index: clearspend.{index}")

    trigger = connection.execute(
        """SELECT EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger trigger
        JOIN pg_catalog.pg_class relation ON relation.oid=trigger.tgrelid
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid=relation.relnamespace
        WHERE namespace.nspname='clearspend' AND relation.relname='transactions'
        AND trigger.tgname='apply_merchant_mapping_after_insert'
        AND NOT trigger.tgisinternal) AS present"""
    ).fetchone()
    if not trigger["present"]:
        problems.append("Missing merchant-mapping transaction trigger")

    function = connection.execute(
        """SELECT owner.rolname AS owner,
        has_function_privilege('clearspend_app', routine.oid, 'EXECUTE') AS runtime_execute,
        has_function_privilege('anon', routine.oid, 'EXECUTE') AS anon_execute,
        has_function_privilege('authenticated', routine.oid, 'EXECUTE') AS authenticated_execute,
        has_function_privilege('service_role', routine.oid, 'EXECUTE') AS service_execute
        FROM pg_catalog.pg_proc routine
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid=routine.pronamespace
        JOIN pg_catalog.pg_roles owner ON owner.oid=routine.proowner
        WHERE namespace.nspname='clearspend'
        AND routine.proname='apply_merchant_mapping_after_insert'"""
    ).fetchone()
    if function is None:
        problems.append("Missing merchant-mapping trigger function")
    else:
        if function["owner"] == "clearspend_app":
            problems.append("clearspend_app owns merchant-mapping trigger function")
        if any(function[key] for key in (
            "runtime_execute", "anon_execute", "authenticated_execute", "service_execute",
        )):
            problems.append("Application or API roles can execute merchant-mapping function")

    unexpected = connection.execute(
        """SELECT grantee,table_name,privilege_type
        FROM information_schema.table_privileges
        WHERE table_schema='clearspend' AND table_name=ANY(?)
        AND grantee IN ('PUBLIC','anon','authenticated','service_role')""",
        (list(TABLE_COLUMNS),),
    ).fetchall()
    if unexpected:
        problems.append("API roles or PUBLIC can access migration 3 tables")

    owners = connection.execute(
        """SELECT tablename FROM pg_catalog.pg_tables
        WHERE schemaname='clearspend' AND tablename=ANY(?)
        AND tableowner='clearspend_app'""",
        (list(TABLE_COLUMNS),),
    ).fetchall()
    if owners:
        problems.append("clearspend_app owns migration 3 tables")
    return problems
