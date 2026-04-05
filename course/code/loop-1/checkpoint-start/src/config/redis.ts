import { createClient } from 'redis';
import { env } from './environment.js';

export const redisClient = createClient({ url: env.REDIS_URL });

redisClient.on('error', (err) => console.error('[Redis] Connection error:', err));
redisClient.on('connect', () => console.log('[Redis] Connected'));

await redisClient.connect();
