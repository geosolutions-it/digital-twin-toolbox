
import initVectorWorkflow from './vector.js';
import initPointCloudWorkflow from './pointcloud.js';
import initPointInstanceWorkflow from './pointinstance.js';
import initMeshWorkflow from './mesh.js';
export default {
    vector: initVectorWorkflow,
    pointCloud: initPointCloudWorkflow,
    pointInstance: initPointInstanceWorkflow,
    mesh: initMeshWorkflow
};
