import { Router } from 'express';
import { z } from 'zod';
import * as ticketService from '../services/ticket-service.js';
import { validate } from '../middleware/validate.js';

const purchaseSchema = z.object({
  event_id: z.number().int().positive(),
  email: z.string().email(),
});

export function createTicketsRouter(): Router {
  const router = Router();

  // List tickets for an event
  router.get('/', async (req, res, next) => {
    try {
      const eventId = Number(req.query.event_id);
      if (!eventId) {
        res.status(400).json({ error: 'event_id query parameter is required' });
        return;
      }
      const tickets = await ticketService.getTicketsForEvent(eventId);
      res.json({ tickets });
    } catch (err) {
      next(err);
    }
  });

  // Purchase a ticket
  router.post('/', validate(purchaseSchema), async (req, res, next) => {
    try {
      const ticket = await ticketService.purchaseTicket(req.body.event_id, req.body.email);
      res.status(201).json(ticket);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
