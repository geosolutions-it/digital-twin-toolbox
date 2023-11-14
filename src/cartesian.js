import * as Cesium from 'cesium';
import * as THREE from 'three';

export const convertToCartesian = ([longitude, latitude, height]) => {
    const cartesian = Cesium.Cartesian3.fromDegrees(longitude, latitude, height);
    return [cartesian.x, cartesian.y, cartesian.z];
};

// from  https://stackoverflow.com/a/52978898
const computeCartesianEuler = (cartesian) => {
    // Set starting and ending vectors
    const myVector = new THREE.Vector3(...cartesian);
    const targetVector = new THREE.Vector3(0, 0, 1);

    // Normalize vectors to make sure they have a length of 1
    myVector.normalize();
    targetVector.normalize();

    // Create a quaternion, and apply starting, then ending vectors
    const quaternion = new THREE.Quaternion();
    quaternion.setFromUnitVectors(myVector, targetVector);

    // Quaternion now has rotation data within it. 
    // We'll need to get it out with a THREE.Euler()
    const euler = new THREE.Euler();
    euler.setFromQuaternion(quaternion);
    return euler;
};

export const translateAndRotate = ([x, y, z], translate) => {
    const vector = new THREE.Vector3(x - translate[0], y - translate[1], z - translate[2]);
    const euler = computeCartesianEuler([x, y, z]);
    vector.applyEuler(euler);
    vector.applyEuler(new THREE.Euler(-Math.PI / 2, 0, -Math.PI / 2));
    return [vector.x, vector.y, vector.z];
};
