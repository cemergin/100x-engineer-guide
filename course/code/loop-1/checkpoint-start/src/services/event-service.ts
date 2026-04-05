import { pool } from '../config/database.js';
import { cacheService } from './cache-service.js';
import type { Event, CreateEventInput } from '../models/event.js';

export async function getAllEvents(limit: number, offset: number): Promise<Event[]> {
  const cacheKey = `events:list:${limit}:${offset}`;

  return cacheService.getOrSet(cacheKey, async () => {
    const result = await pool.query(
      `SELECT e.*, v.name as venue_name, v.city as venue_city
       FROM events e
       JOIN venues v ON e.venue_id = v.id
       ORDER BY e.date ASC
       LIMIT $1 OFFSET $2`,
      [limit, offset]
    );
    return result.rows;
  }, 60);
}

export async function getEventById(id: number): Promise<Event | null> {
  const cacheKey = `events:${id}`;

  return cacheService.getOrSet(cacheKey, async () => {
    const result = await pool.query(
      `SELECT e.*, v.name as venue_name, v.city as venue_city,
              (SELECT COUNT(*) FROM tickets t WHERE t.event_id = e.id AND t.status = 'available') as available_tickets
       FROM events e
       JOIN venues v ON e.venue_id = v.id
       WHERE e.id = $1`,
      [id]
    );
    return result.rows[0] || null;
  }, 30);
}

export async function createEvent(input: CreateEventInput): Promise<Event> {
  const result = await pool.query(
    `INSERT INTO events (title, artist, venue_id, date, description, total_tickets, price_cents)
     VALUES ($1, $2, $3, $4, $5, $6, $7)
     RETURNING *`,
    [input.title, input.artist, input.venue_id, input.date, input.description, input.total_tickets, input.price_cents]
  );

  // Invalidate list cache
  await cacheService.del('events:list:*');

  return result.rows[0];
}
