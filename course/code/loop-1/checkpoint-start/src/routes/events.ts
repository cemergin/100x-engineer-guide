import { Router } from 'express';
import { z } from 'zod';
import * as eventService from '../services/event-service.js';
import { validate } from '../middleware/validate.js';

const createEventSchema = z.object({
  title: z.string().min(1).max(255),
  artist: z.string().min(1).max(255),
  venue_id: z.number().int().positive(),
  date: z.string().datetime(),
  description: z.string().max(2000).default(''),
  total_tickets: z.number().int().positive(),
  price_cents: z.number().int().nonnegative(),
});

export function createEventsRouter(): Router {
  const router = Router();

  // List all events
  router.get('/', async (req, res, next) => {
    try {
      const limit = Math.min(Number(req.query.limit) || 50, 100);
      const offset = Number(req.query.offset) || 0;
      const events = await eventService.getAllEvents(limit, offset);
      res.json({ events, limit, offset });
    } catch (err) {
      next(err);
    }
  });

  // Get single event
  router.get('/:id', async (req, res, next) => {
    try {
      const event = await eventService.getEventById(Number(req.params.id));
      if (!event) {
        res.status(404).json({ error: 'Event not found' });
        return;
      }
      res.json(event);
    } catch (err) {
      next(err);
    }
  });

  // Create event
  router.post('/', validate(createEventSchema), async (req, res, next) => {
    try {
      const event = await eventService.createEvent(req.body);
      res.status(201).json(event);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
