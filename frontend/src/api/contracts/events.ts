import type { PeriodKey, ReportingPeriod } from './common';

export interface EventTransaction {
  id: number; merchant_raw: string; merchant_display_name: string; category: string; transaction_date: string; provider: string;
  card_last4: string; amount: number; personal_amount: number;
}
export interface EventSummary {
  id: string; name: string; event_type: string; destination: string | null; icon: string | null; start_date: string; end_date: string;
  status: string; budget: number | null; notes: string | null; transactions: EventTransaction[]; transaction_count: number; amount: number;
  total_transaction_count: number; total_amount: number; category_count: number; card_count: number;
}
export interface AvailableEvent {
  id: string; name: string; event_type: string; destination: string | null; icon: string | null; start_date: string; end_date: string; status: string;
}
export interface EventsResponse { period: ReportingPeriod; selected_card: string; events: EventSummary[]; available_events: AvailableEvent[] }
export interface EventsQuery { period: PeriodKey; month?: string; card: string }
export interface EventMutationRecord {
  id: string; name: string; event_type: string; destination: string | null; icon: string | null; start_date: string; end_date: string;
  status: string; budget: number | null; notes: string | null;
}
export interface CreateEventRequest {
  name: string; event_type: string; destination: string; start_date: string; end_date: string; budget: number | null;
  status: 'planned' | 'active' | 'completed';
}
export interface CreateEventResponse { status: 'created'; event: EventMutationRecord }
export interface SaveEventRequest extends Omit<CreateEventRequest, 'status'> { event_id: string; status: 'planned' | 'active' | 'completed' | 'cancelled' }
export interface SaveEventResponse { status: 'updated'; event: EventMutationRecord }
