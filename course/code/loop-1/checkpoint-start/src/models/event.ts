export interface Event {
  id: number;
  title: string;
  artist: string;
  venue_id: number;
  date: Date;
  description: string;
  total_tickets: number;
  price_cents: number;
  created_at: Date;
}

export interface CreateEventInput {
  title: string;
  artist: string;
  venue_id: number;
  date: string;
  description: string;
  total_tickets: number;
  price_cents: number;
}
