import { Router } from 'express';
import { pool } from '../config/database.js';
import { redisClient } from '../config/redis.js';

export function createHealthRouter(): Router {
  const router = Router();

  router.get('/', async (_req, res) => {
    let database = 'disconnected';
    let cache = 'disconnected';

    try {
      await pool.query('SELECT 1');
      database = 'connected';
    } catch {
      database = 'error';
    }

    try {
      await redisClient.ping();
      cache = 'connected';
    } catch {
      cache = 'error';
    }

    const status = database === 'connected' && cache === 'connected' ? 'ok' : 'degraded';

    res.json({
      status,
      uptime: process.uptime(),
      database,
      cache,
    });
  });

  return router;
}
