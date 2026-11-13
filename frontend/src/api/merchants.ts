import { getJson, postJson } from './client.ts';
import type { ManageRecurringProfileRequest, ManageRecurringProfileResponse, MerchantReferenceResponse, SaveMerchantRequest, SaveMerchantResponse } from './contracts.ts';

export function getMerchantReference(): Promise<MerchantReferenceResponse> {
  return getJson<MerchantReferenceResponse>('/api/merchants', 'Could not load merchant reference data');
}

export function manageRecurringProfile(
  request: ManageRecurringProfileRequest,
): Promise<ManageRecurringProfileResponse> {
  return postJson<ManageRecurringProfileResponse, ManageRecurringProfileRequest>(
    '/api/recurring-profile/manage',
    request,
    'Could not update recurring decision',
  );
}

export function saveMerchant(request: SaveMerchantRequest): Promise<SaveMerchantResponse> {
  return postJson<SaveMerchantResponse, SaveMerchantRequest>(
    '/api/merchants',
    request,
    'Could not save merchant changes',
  );
}
