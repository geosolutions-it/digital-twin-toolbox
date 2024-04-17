
let socket;

export const setLoggerSocket = (_socket) => {
    socket = _socket;
}

const logger = ({ message, type, options = {} }) => {
    console.log(message);
    if (socket) {
        socket.emit('log', {
            message,
            type,
            options
        });
    }
}

export default logger;
