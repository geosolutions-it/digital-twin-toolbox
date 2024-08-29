
import earcut, { flatten } from 'earcut'

const coordinates = JSON.parse(process.argv[2])
const data = flatten(coordinates);
const triangles = earcut(data.vertices, data.holes, data.dimensions);

process.stdout.write(triangles.join(','));
