import { pool } from '../config/database.js';

export async function seed(): Promise<void> {
  // Check if data already exists
  const existing = await pool.query('SELECT COUNT(*) FROM venues');
  if (Number(existing.rows[0].count) > 0) return;

  // Insert venues
  await pool.query(`
    INSERT INTO venues (name, city, capacity, address) VALUES
      ('Madison Square Garden', 'New York', 20000, '4 Pennsylvania Plaza, New York, NY 10001'),
      ('The O2 Arena', 'London', 20000, 'Peninsula Square, London SE10 0DX'),
      ('Tokyo Dome', 'Tokyo', 55000, '1-3-61 Koraku, Bunkyo, Tokyo 112-0004')
  `);

  // Insert events
  await pool.query(`
    INSERT INTO events (title, artist, venue_id, date, description, total_tickets, price_cents) VALUES
      ('Midnight Echoes — World Tour 2026', 'Midnight Echoes', 1, '2026-06-15 20:00:00+00', 'The biggest tour of the decade hits NYC. Three hours of pure energy.', 18000, 8500),
      ('Neon Waves Live', 'Neon Waves', 2, '2026-07-22 19:30:00+00', 'London gets loud. Neon Waves brings their new album to The O2.', 18000, 7500),
      ('Sakura Sessions', 'Yuki Tanaka', 3, '2026-08-10 18:00:00+00', 'An intimate evening of jazz and electronica at Tokyo Dome.', 40000, 6000),
      ('Bass Drop Festival', 'Various Artists', 1, '2026-09-01 16:00:00+00', 'Three stages, twelve hours, twenty artists. The bass never stops.', 20000, 12000),
      ('Acoustic Unplugged', 'Sarah Chen', 2, '2026-10-05 20:00:00+00', 'Just a voice, a guitar, and twenty thousand people holding their breath.', 15000, 9500),
      ('New Year Countdown', 'DJ Pulse', 3, '2026-12-31 21:00:00+00', 'Ring in 2027 with the biggest party in Tokyo. Fireworks included.', 50000, 15000)
  `);

  // Create available tickets for each event
  const events = await pool.query('SELECT id, total_tickets FROM events');
  for (const event of events.rows) {
    const ticketCount = Math.min(event.total_tickets, 100); // Seed 100 tickets per event for demo
    const values = Array.from({ length: ticketCount }, (_, i) =>
      `(${event.id}, 'available')`
    ).join(',\n      ');

    await pool.query(`INSERT INTO tickets (event_id, status) VALUES ${values}`);
  }
}

// Run directly if called as script
if (import.meta.url === `file://${process.argv[1]}`) {
  seed()
    .then(() => { console.log('Seeding complete'); process.exit(0); })
    .catch((err) => { console.error('Seeding failed:', err); process.exit(1); });
}
