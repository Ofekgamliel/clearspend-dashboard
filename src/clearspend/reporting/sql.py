"""Shared SQL expressions for the established reporting-date contract."""

REPORTING_MONTH_SQL = (
    "COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))"
)
REPORTING_DATE_SQL = (
    "CASE WHEN billing_date IS NOT NULL THEN billing_date "
    "WHEN billing_month IS NOT NULL AND substr(transaction_date,1,7)=billing_month THEN transaction_date "
    "WHEN billing_month IS NOT NULL THEN billing_month||'-01' ELSE transaction_date END"
)
