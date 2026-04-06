export interface Venue {
  id: number;
  name: string;
  city: string;
  capacity: number;
  address: string | null;
  created_at: Date;
}
