import initClientSocket from './socket.js';
import initScene from './scene.js';
import initGui from './gui.js';

const { socket } = initClientSocket();
const { scene, setInitCameraLocation, group } = initScene();
const {} = initGui({ socket, scene, setInitCameraLocation, group });
