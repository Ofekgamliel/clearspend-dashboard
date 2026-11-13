import type { ManageRecurringProfileRequest, MerchantRecord } from '../../api/contracts.ts';

export type RecurringVerdictFilter = 'all' | 'recurring' | 'not_recurring' | 'unreviewed';

export interface RecurringManagementDraft {
  recurring_type: string;
  cadence: string;
  lifecycle_status: string;
  end_month: string;
  included_aliases: string[];
}

export function merchantRecurringVerdict(merchant: MerchantRecord): Exclude<RecurringVerdictFilter, 'all'> {
  return merchant.recurring_profile?.verdict ?? 'unreviewed';
}

export function filterRecurringMerchants(
  merchants: MerchantRecord[],
  search: string,
  filter: RecurringVerdictFilter,
): MerchantRecord[] {
  const term = search.trim().toLocaleLowerCase();
  return merchants.filter((merchant) => {
    const text = `${merchant.display_name} ${merchant.aliases.map((alias) => `${alias.merchant_raw} ${alias.merchant_normalized}`).join(' ')}`.toLocaleLowerCase();
    return (!term || text.includes(term)) && (filter === 'all' || merchantRecurringVerdict(merchant) === filter);
  });
}

export function recurringManagementDraft(merchant: MerchantRecord): RecurringManagementDraft {
  const profile = merchant.recurring_profile;
  const included = merchant.aliases.filter((alias) => alias.recurring_included).map((alias) => alias.merchant_normalized);
  return {
    recurring_type: profile?.recurring_type ?? 'Fixed recurring',
    cadence: profile?.cadence ?? 'Monthly',
    lifecycle_status: profile?.lifecycle_status ?? 'active',
    end_month: profile?.end_month ?? '',
    included_aliases: included.length ? included : (!profile && merchant.aliases.length === 1 ? [merchant.aliases[0]!.merchant_normalized] : []),
  };
}

export function recurringManagementError(draft: RecurringManagementDraft): string {
  if (!draft.included_aliases.length) return 'Select at least one original merchant name.';
  if (draft.lifecycle_status === 'ended' && !draft.end_month) return 'Choose an end month for an ended profile.';
  return '';
}

export function recurringManagementPayload(
  merchant: MerchantRecord,
  draft: RecurringManagementDraft,
  verdict: 'recurring' | 'not_recurring',
): ManageRecurringProfileRequest {
  return {
    canonical_group_id: merchant.canonical_group_id,
    verdict,
    recurring_type: draft.recurring_type,
    cadence: draft.cadence,
    lifecycle_status: draft.lifecycle_status,
    end_month: verdict === 'recurring' && draft.lifecycle_status === 'ended' ? draft.end_month : '',
    included_aliases: verdict === 'recurring' ? [...draft.included_aliases] : [],
  };
}
