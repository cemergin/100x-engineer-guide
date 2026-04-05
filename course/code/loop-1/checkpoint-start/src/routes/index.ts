import { Router } from 'express';
import { createEventsRouter } from './events.js';
import { createTicketsRouter } from './tickets.js';
import { createHealthRouter } from './health.js';

export function createRouter(): Router {
  const router = Router();

  router.use('/health', createHealthRouter());
  router.use('/events', createEventsRouter());
  router.use('/tickets', createTicketsRouter());

  return router;
}
