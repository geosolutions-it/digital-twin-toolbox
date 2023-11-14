import { io } from 'socket.io-client';
import logger from './logger.js';

const initClientSocket = () => {
    const socket = io({ path: '/socket/socket.io' });
    socket.on('log', logger);
    return { socket };
};

export default initClientSocket;
