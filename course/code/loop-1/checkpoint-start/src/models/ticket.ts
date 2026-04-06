export type TicketStatus = 'available' | 'reserved' | 'purchased' | 'cancelled';

export interface Ticket {
  id: number;
  event_id: number;
  status: TicketStatus;
  purchaser_email: string | null;
  purchased_at: Date | null;
  created_at: Date;
}

export interface PurchaseTicketInput {
  event_id: number;
  email: string;
}
