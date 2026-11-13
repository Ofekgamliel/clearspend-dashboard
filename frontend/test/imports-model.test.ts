import assert from 'node:assert/strict';
import test from 'node:test';
import type { StagedImportBatch, StagedMerchant } from '../src/api/contracts.ts';
import { canContinue, displayMatchScore, initialDecision, previewRows, strongIdentity } from '../src/features/imports/model.ts';

const merchant: StagedMerchant = { merchant_normalized:'synthetic branch',merchant_raw:'Synthetic Branch 147',display_name:'Synthetic Branch 147',canonical_group_id:null,category:'Needs review',subcategory:null,provider_category:null,needs_review:true,match_source:'unmapped',transactions:2,amount:40,providers:['synthetic'],first_date:'2030-01-01',last_date:'2030-01-02' };
const identity = { canonical_group_id:'synthetic',display_name:'Synthetic',aliases:3,transactions:9,alias_names:['synthetic branch'],category_status:'unanimous' as const,category:'Household',categories:[{category:'Household',aliases:3}] };
const batch = { batch_id:'batch',files:[],merchants:[merchant],categories:['Household'],display_identities:[identity],exact_duplicates:[],possible_duplicates:[],new_transactions:[{filename:'statement.xlsx',merchant:'Synthetic Branch',merchant_normalized:'synthetic branch',transaction_date:'2030-01-01',amount:20}],pending_transactions:[],coverage_warnings:[],upload_errors:[] } as StagedImportBatch;

test('suggests only a strong unambiguous existing display identity',()=>{ assert.ok(displayMatchScore('Synthetic Branch 147','Synthetic Branch')>=80); assert.equal(strongIdentity(merchant.merchant_raw,[identity])?.canonical_group_id,'synthetic'); assert.equal(initialDecision(merchant,[identity]).resolution,'link'); });
test('keeps excluded merchant rows out of the insertion preview',()=>{ const decision=initialDecision(merchant,[]); decision.resolution='exclude'; const rows=previewRows(batch,new Map([[merchant.merchant_normalized,decision]]),new Map()); assert.equal(rows.length,0); });
test('gates duplicate and reconciliation stages independently',()=>{ const duplicateBatch={...batch,possible_duplicates:[{candidate_id:'candidate',filename:'x',merchant:'X',merchant_normalized:'x',transaction_date:'2030-01-01',amount:10}]} as StagedImportBatch; assert.equal(canContinue(1,duplicateBatch,new Map(),new Map(),new Set()),false); assert.equal(canContinue(1,duplicateBatch,new Map(),new Map([['candidate','skip']]),new Set()),true); });
