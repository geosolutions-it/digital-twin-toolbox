import * as THREE from 'three';
import { MapControls } from 'three/examples/jsm/controls/MapControls.js';

const setDefaultCameraLocation = (camera, controls) => {
    camera.position.set(0, 1500, 1500);
    controls.target.set(0, 0, 0);
};

const getCameraLocation = (camera, controls) => {
    try {
        const {position, target} = JSON.parse(localStorage.getItem('camera'));
        camera.position.set(...position);
        controls.target.set(...target);
    } catch (e) {
        setDefaultCameraLocation(camera, controls);
    }
};

const initScene = () => {

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera( 75, window.innerWidth / window.innerHeight, 0.1, 1000000000 );

    const renderer = new THREE.WebGLRenderer();
    renderer.setSize(window.innerWidth, window.innerHeight);
    document.body.appendChild(renderer.domElement);

    const controls = new MapControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.dampingFactor = 0.05;
    getCameraLocation(camera, controls);
    const axesHelper = new THREE.AxesHelper( 500 );
    scene.add( axesHelper );

    const gridGround = new THREE.GridHelper( 3000, 150,0x3f3f3f, 0x3f3f3f );
    scene.add( gridGround );
    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
        localStorage.setItem('camera', JSON.stringify({
            position: camera.position.toArray(),
            target: controls.target.toArray()
        }));
    }
    animate();

    const group = new THREE.Group();
    scene.add(group);

    window.addEventListener( 'resize', onWindowResize, false );
    function onWindowResize(){
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize( window.innerWidth, window.innerHeight );
    }
    return {
        scene,
        camera,
        renderer,
        group,
        setInitCameraLocation: () => setDefaultCameraLocation(camera, controls)
    };
};

export default initScene;
