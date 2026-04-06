import 'dotenv/config';
import express from 'express';
import { env } from './config/environment.js';
import { pool } from './config/database.js';
import { redisClient } from './config/redis.js';
import { createRouter } from './routes/index.js';
import { requestLogger } from './middleware/request-logger.js';
import { errorHandler } from './middleware/error-handler.js';

const app = express();

// Middleware
app.use(express.json());
app.use(requestLogger);

// Routes
app.use('/api', createRouter());

// Error handling (must be last)
app.use(errorHandler);

// Start server
const server = app.listen(env.PORT, async () => {
  // Run migrations
  const fs = await import('fs');
  const path = await import('path');
  const migrationsDir = path.join(import.meta.dirname, 'db', 'migrations');
  const files = fs.readdirSync(migrationsDir).sort();

  for (const file of files) {
    if (file.endsWith('.sql')) {
      const sql = fs.readFileSync(path.join(migrationsDir, file), 'utf-8');
      await pool.query(sql);
      console.log(`[INFO] Applied migration: ${file}`);
    }
  }

  // Seed if in development
  if (env.NODE_ENV === 'development') {
    const { seed } = await import('./db/seed.js');
    await seed();
    console.log('[INFO] Seeding complete');
  }

  console.log(`[INFO] TicketPulse API listening on port ${env.PORT}`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('[INFO] SIGTERM received, shutting down...');
  server.close();
  await pool.end();
  await redisClient.quit();
  process.exit(0);
});
