
import initMeshWorkflow from './mesh.js';
import initPointCloudWorkflow from './pointcloud.js';
import pointInstanceWorkflow from './pointinstance.js';
export default {
    mesh: initMeshWorkflow,
    pointCloud: initPointCloudWorkflow,
    pointInstance: pointInstanceWorkflow
};
