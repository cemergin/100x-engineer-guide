CREATE TABLE IF NOT EXISTS events (
  id SERIAL PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  artist VARCHAR(255) NOT NULL,
  venue_id INTEGER NOT NULL REFERENCES venues(id),
  date TIMESTAMPTZ NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  total_tickets INTEGER NOT NULL CHECK (total_tickets > 0),
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_venue_id ON events(venue_id);
CREATE INDEX IF NOT EXISTS idx_events_artist ON events(artist);
