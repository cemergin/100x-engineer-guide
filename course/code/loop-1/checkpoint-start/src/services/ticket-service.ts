import { pool } from '../config/database.js';
import { cacheService } from './cache-service.js';
import type { Ticket } from '../models/ticket.js';

export async function getTicketsForEvent(eventId: number): Promise<Ticket[]> {
  const result = await pool.query(
    'SELECT * FROM tickets WHERE event_id = $1 ORDER BY id ASC',
    [eventId]
  );
  return result.rows;
}

export async function purchaseTicket(eventId: number, email: string): Promise<Ticket> {
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    // Find an available ticket with a row-level lock
    const available = await client.query(
      `SELECT id FROM tickets
       WHERE event_id = $1 AND status = 'available'
       LIMIT 1
       FOR UPDATE SKIP LOCKED`,
      [eventId]
    );

    if (available.rows.length === 0) {
      await client.query('ROLLBACK');
      throw new TicketSoldOutError(eventId);
    }

    // Mark the ticket as purchased
    const result = await client.query(
      `UPDATE tickets
       SET status = 'purchased', purchaser_email = $1, purchased_at = NOW()
       WHERE id = $2
       RETURNING *`,
      [email, available.rows[0].id]
    );

    await client.query('COMMIT');

    // Invalidate event cache (available count changed)
    await cacheService.del(`events:${eventId}`);

    return result.rows[0];
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

export class TicketSoldOutError extends Error {
  public statusCode = 409;

  constructor(eventId: number) {
    super(`No available tickets for event ${eventId}`);
    this.name = 'TicketSoldOutError';
  }
}
