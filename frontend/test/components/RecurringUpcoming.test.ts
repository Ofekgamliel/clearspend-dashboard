import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import type { RecurringUpcomingResponse } from '../../src/api/contracts';
import RecurringUpcoming from '../../src/features/recurring/RecurringUpcoming.vue';

const response: RecurringUpcomingResponse = {
  generated_as_of: '2030-04-02T10:00:00+03:00',
  anchor_month: '2030-04',
  horizon_start: '2030-04',
  horizon_end: '2030-06',
  selected_card: 'all',
  months: [
    {
      month: '2030-04', confirmed_total: 100, forecast_total: 0, comparable_total: 100,
      unknown_amount_count: 0, payment_count: 1, comparison_label: null,
      annual_count: 0, ending_installment_count: 0,
      payments: [{
        occurrence_id: 'occurrence-a', expected_date: '2030-04-10', date_evidence: 'confirmed',
        display_name: 'Synthetic Service', card: { provider: 'synthetic', last4: '0001' },
        payment_type: 'Fixed recurring', amount: 100, amount_evidence: 'confirmed', amount_confidence: null, occurrence_status: 'confirmed',
        recent_range: null,
        installment_number: null, installment_total: null, annual: false, ending: false,
      }],
    },
    {
      month: '2030-05', confirmed_total: 0, forecast_total: 75, comparable_total: 75,
      unknown_amount_count: 0, payment_count: 1, comparison_label: null,
      annual_count: 0, ending_installment_count: 1,
      payments: [{
        occurrence_id: 'occurrence-b', expected_date: null, date_evidence: 'month_only',
        display_name: 'Synthetic Device', card: { provider: 'synthetic', last4: '0001' },
        payment_type: 'Installment', amount: 75, amount_evidence: 'estimate', amount_confidence: 'established', occurrence_status: 'expected',
        recent_range: null,
        installment_number: 3, installment_total: 3, annual: false, ending: true,
      }],
    },
    {
      month: '2030-06', confirmed_total: 0, forecast_total: 1200, comparable_total: 1200,
      unknown_amount_count: 0, payment_count: 1, comparison_label: 'highest_expected',
      annual_count: 1, ending_installment_count: 0,
      payments: [{
        occurrence_id: 'occurrence-c', expected_date: '2030-06-15', date_evidence: 'estimated',
        display_name: 'Synthetic Annual', card: { provider: 'synthetic', last4: '0002' },
        payment_type: 'Scheduled obligation', amount: 1200, amount_evidence: 'estimate', amount_confidence: 'established', occurrence_status: 'expected',
        recent_range: null,
        installment_number: null, installment_total: null, annual: true, ending: false,
      }],
    },
  ],
  unresolved: [{
    source_kind: 'recurring_profile', source_id: 'unresolved-a',
    display_name: 'Synthetic Unclear', card: null, reason: 'ambiguous_phase',
  }],
};

describe('RecurringUpcoming', () => {
  it('selects month cards locally and renders evidence and ending labels', async () => {
    const wrapper = mount(RecurringUpcoming, { props: { data: response } });
    const cards = wrapper.findAll('.recurring-upcoming-months button');

    expect(cards).toHaveLength(3);
    expect(cards[0]?.attributes('aria-pressed')).toBe('true');
    expect(cards[0]?.text()).toContain('Known expected');
    expect(wrapper.find('.recurring-upcoming-context').exists()).toBe(false);
    expect(wrapper.find('.recurring-month-selected').exists()).toBe(false);
    expect(wrapper.text()).toContain('Confirmed');
    expect(wrapper.get('.recurring-upcoming-columns').text()).toContain('Type / evidence');
    expect(wrapper.findAll('[role="columnheader"]')).toHaveLength(4);
    expect(wrapper.findAll('[role="row"]')).toHaveLength(2);
    expect(wrapper.findAll('[role="cell"]')).toHaveLength(4);
    expect(wrapper.get('.recurring-upcoming-payment-list').attributes()).toMatchObject({
      role: 'region', tabindex: '0', 'aria-label': 'April 2030 expected payments',
    });
    expect(wrapper.text()).not.toContain('Known expected total');
    await cards[1]?.trigger('click');
    expect(cards[1]?.attributes('aria-pressed')).toBe('true');
    expect(wrapper.text()).toContain('Final installment');
    expect(wrapper.text()).toContain('3/3');
  });

  it('keeps unresolved items in a neutral horizon-level disclosure', () => {
    const wrapper = mount(RecurringUpcoming, { props: { data: response } });

    expect(wrapper.get('.recurring-unresolved summary').text()).toBe('Not forecast · 1');
    expect(wrapper.get('.recurring-unresolved').text()).toContain('Schedule unclear');
    expect(wrapper.findAll('.recurring-upcoming-months button')).toHaveLength(3);
  });

  it('labels a first-payment forecast as provisional', () => {
    const provisional = structuredClone(response);
    provisional.months[0]!.payments[0]!.amount_evidence = 'estimate';
    provisional.months[0]!.payments[0]!.amount_confidence = 'provisional';
    provisional.months[0]!.payments[0]!.occurrence_status = 'expected';

    const wrapper = mount(RecurringUpcoming, { props: { data: provisional } });

    expect(wrapper.text()).toContain('Based on first payment');
  });
});
