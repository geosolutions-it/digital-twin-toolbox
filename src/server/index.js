
import { createStatic } from './static.js';
import { createSocket } from './socket.js';

// internal ports
const staticPort = 3000;
const socketPort = 3001;

createStatic(staticPort);
createSocket(socketPort);
