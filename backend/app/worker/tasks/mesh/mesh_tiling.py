import logging
import bpy
import os
import bmesh
import time
import pathlib
import numpy as np
from app.worker.tasks.mesh.create_tileset import get_location_and_rotation, get_transform
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# clean up
def clean_up():

    if bpy.context.active_object:
        bpy.ops.object.mode_set(mode='OBJECT')
            
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
        obj.hide_set(False)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(True)

    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)

    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)

    for block in bpy.data.textures:
        if block.users == 0:
            bpy.data.textures.remove(block)

    for block in bpy.data.images:
        if block.users == 0:
            bpy.data.images.remove(block)

def remove_obj(target):
    if target:
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.data.meshes.remove(target.data)
        bpy.ops.object.delete()

def create_bake_material():
    name = "TileMaterial"
    bake_mat = bpy.data.materials.get(name)
    if bake_mat is None:
        bake_mat = bpy.data.materials.new(name=name)
        bake_mat.use_nodes = True
        bsdf = bake_mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs['Roughness'].default_value = 1
        texture_node = bake_mat.node_tree.nodes.new('ShaderNodeTexImage')
        texture_node.name = 'TileImageNode'
        texture_node.select = True
        bake_mat.node_tree.links.new(bsdf.inputs['Base Color'], texture_node.outputs['Color'])
        bake_mat.node_tree.nodes.active = texture_node
    return bake_mat

def create_image(bake_mat, size):
    texture_node = bake_mat.node_tree.nodes.new('ShaderNodeTexImage')
    texture_node.name = f'Bake_node_{size}'
    texture_node.select = False
    texture_node.image = bpy.data.images.new(name=f'TileImage_{size}', width=size, height=size, alpha=False)
    return texture_node

def setup_bake_setting():

    bpy.context.preferences.edit.use_global_undo = False
    bpy.context.preferences.edit.undo_steps = 0
    # setup render engine
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 1
    bpy.context.scene.cycles.preview_samples = 1
    bpy.context.scene.cycles.use_denoising = False
    bpy.context.scene.cycles.use_preview_denoising = False
    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False

    bpy.context.scene.render.bake.margin = 2

def merge_vertices(threshold=0.0001):
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=threshold)
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.editmode_toggle()

# import mesh
def import_mesh(filepath, forward_axis='Y', up_axis='Z'):
    extension = pathlib.Path(filepath).suffix
    if extension == '.ply':
        bpy.ops.wm.ply_import(filepath=filepath, forward_axis=forward_axis, up_axis=up_axis)
    else:
        bpy.ops.wm.obj_import(filepath=filepath, forward_axis=forward_axis, up_axis=up_axis)

    obj = bpy.context.object

    # non-default axes are stored as an object transform; bake into the mesh data so
    # AABB, ENU transform and export share one vertex frame
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    merge_vertices()

    top = float('-inf')
    left = float('inf')
    for vertex in obj.data.vertices:
        x = vertex.co[0]
        y = vertex.co[1]
        left = x if x < left else left
        top = y if y > top else top

    info = {
        'size': [obj.dimensions[0], obj.dimensions[1], obj.dimensions[2]],
        'top': top,
        'left': left
    }

    return [obj, info]

def apply_default_material(obj):
    mat = bpy.data.materials.new(name='EmissionMaterial')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]

    bsdf.inputs['Base Color'].default_value = (0, 0, 0, 1)
    bsdf.inputs['Roughness'].default_value = 1
    bsdf.inputs['Emission Strength'].default_value = 1

    vertex_color_node = mat.node_tree.nodes.new('ShaderNodeVertexColor')
    vertex_color_node.name = 'VertexColorNode'
    vertex_color_node.select = True
    mat.node_tree.links.new( vertex_color_node.outputs[0], bsdf.inputs['Emission Color'] )
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat

def export_gltf(filepath):
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_image_format='WEBP',
        export_image_quality=75,
        export_jpeg_quality=75,
        
        use_selection=True,
        export_format="GLB",
        export_draco_mesh_compression_enable=True,

        export_normals=False,

        # Values range 0 - 6
        export_draco_mesh_compression_level=6,

        # Values range 0 - 30
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
        export_draco_color_quantization=10,
        export_draco_generic_quantization=12,
        export_tangents=False,
        export_materials='EXPORT',
        export_original_specular=False,
        export_all_vertex_colors=False,
        export_vertex_color='NONE',
        export_attributes=False,
        use_mesh_edges=False,
        use_mesh_vertices=False,
        export_cameras=False,
        use_visible=False,
        use_renderable=False,
        use_active_collection_with_nested=True,
        use_active_collection=False,
        use_active_scene=False,
        export_extras=False,
        export_yup=True,
        export_apply=False,
        export_animations=False,
        export_frame_range=False,
        export_frame_step=1,
        export_force_sampling=True,
        export_animation_mode='ACTIONS',
        export_nla_strips_merged_animation_name='Animation',
        export_def_bones=False,
        export_hierarchy_flatten_bones=False,
        export_optimize_animation_size=True,
        export_optimize_animation_keep_anim_armature=True,
        export_optimize_animation_keep_anim_object=False,
        export_negative_frame='SLIDE',
        export_anim_slide_to_zero=False,
        export_bake_animation=False,
        export_anim_single_armature=False,
        export_reset_pose_bones=False,
        export_current_frame=False,
        export_rest_position_armature=False,
        export_anim_scene_split_object=False,
        export_skins=False,
        export_all_influences=False,
        export_morph=False,
        export_morph_normal=False,
        export_morph_tangent=False,
        export_morph_animation=False,
        export_morph_reset_sk_data=False,
        export_lights=False,
        export_nla_strips=False
    )

def export_obj(filepath):
    bpy.ops.wm.obj_export(
        filepath=filepath,
        export_selected_objects=True,
        export_uv=True,
        export_normals=True,
        export_colors=True,
        export_materials=True,
        forward_axis='Y', 
        up_axis='Z'
    )

def decimate_obj(obj, _faces_target):
    ratio = _faces_target / len(obj.data.polygons)
    logger.info(f"Object faces: {len(obj.data.polygons)}")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    if ratio < 1:
        logger.info(f"Decimate object by {ratio} ratio")
        decimate = obj.modifiers.new(type="DECIMATE", name="decimate")
        decimate.ratio = ratio
        decimate.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier="decimate")
        logger.info(f"Updated object faces: {len(obj.data.polygons)}")

def split_tile(params):

    target = params.get('target')
    bbox = params.get('bbox')
    margin = params.get('margin')
    filepath = params.get('filepath')
    name = params.get('name')
    bake_img = params.get('bake_img')
    bake_mat = params.get('bake_mat')
    target_model = params.get('target_model')
    tile_faces_target = params.get('tile_faces_target')
    apply_transform = params.get('apply_transform')
    cage_extrusion = params.get('cage_extrusion')
    should_decimate = params.get('should_decimate')
    location_and_rotation = params.get('location_and_rotation')
    transform = params.get('transform')
    default_mat = params.get('default_mat')
    export_asset = params.get('export_asset')
    unwrap_uv = params.get('unwrap_uv')
    factor_force_decimation = params.get('factor_force_decimation', 1)

    for obj in bpy.context.scene.objects:
        obj.select_set(False)
        obj.hide_set(False)

    # select the tile's bbox+margin verts directly on the level mesh (numpy box mask)
    minx = bbox[0] - margin
    miny = bbox[1] - margin
    maxx = bbox[2] + margin
    maxy = bbox[3] + margin

    verts = target.data.vertices
    count = len(verts)
    coords = np.empty(count * 3, dtype=np.float64)
    verts.foreach_get('co', coords)
    coords = coords.reshape(count, 3)
    in_tile = (
        (coords[:, 0] >= minx) & (coords[:, 0] <= maxx) &
        (coords[:, 1] >= miny) & (coords[:, 1] <= maxy)
    )

    if not in_tile.any():
        # nothing in this tile, skip and proceed with next
        return

    verts.foreach_set('select', in_tile)

    target.select_set(True)
    bpy.context.view_layer.objects.active = target

    # duplicate only the selected region; target keeps its geometry (incl margin overlap) for
    # the next tile, so we avoid copying the whole level mesh per tile
    existing = set(bpy.data.objects) # snapshot of current objects
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.duplicate()
    bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')

    # we look for new object created by duplicate
    new_objs = [o for o in bpy.data.objects if o not in existing]
    if not new_objs:
        return
    tile = new_objs[0]
    tile.name = 'tile'
    tile.hide_render = False
    bpy.ops.object.select_all(action="DESELECT")

    tile.select_set(True)
    bpy.context.view_layer.objects.active = tile

    merge_vertices()

    if len(tile.data.polygons) == 0:
        remove_obj(tile)
        return

    if should_decimate and tile_faces_target and tile_faces_target > 0:
        decimate_obj(tile, tile_faces_target)
        if len(tile.data.polygons) > tile_faces_target:
            merge_vertices(factor_force_decimation)
            if len(tile.data.polygons) > tile_faces_target:
                decimate_obj(tile, tile_faces_target)
        merge_vertices()

    # unwrap the uv
    if unwrap_uv:
        try:
            bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.select_all(action = 'SELECT')
            bpy.ops.uv.smart_project()
            bpy.ops.object.editmode_toggle()
        except:
            logger.error(f'Skip: bpy.ops.uv.smart_project failing for {name}')
            return

    if bake_img and bake_mat:
        logger.info(f"Baking texture for tile {name}")
        bake_img.select = True
        mat = tile.material_slots[0].material
        mat.node_tree.nodes.active = bake_img

        # bake texture to texture
        if target_model:
            target_model.hide_render = False
            target_model.select_set(True)
            bpy.context.scene.cycles.bake_type = 'DIFFUSE'
            bpy.context.scene.render.bake.use_selected_to_active = True
            bpy.context.scene.render.bake.cage_extrusion = cage_extrusion # (m) to avoid black pixels
            bpy.ops.object.bake(type='DIFFUSE',use_clear=False)
            target_model.select_set(False)
            target_model.hide_render = True

        # remove all material from tile copy
        tile.data.materials.clear()

        texture_node = bake_mat.node_tree.nodes.get('TileImageNode')
        texture_node.image = bake_img.image
        # apply the bake material
        tile.data.materials.append(bake_mat)

    tile.name = name

    if apply_transform:
        # bounding volume from the tile's actual local AABB (incl. margin overlap),
        # computed before the ENU rotation/location move it into ECEF
        tcount = len(tile.data.vertices)
        tcoords = np.empty(tcount * 3, dtype=np.float64)
        tile.data.vertices.foreach_get('co', tcoords)
        tcoords = tcoords.reshape(tcount, 3)
        tmin = tcoords.min(axis=0)
        tmax = tcoords.max(axis=0)
        tile_info = {
            'center': [
                float((tmin[0] + tmax[0]) / 2),
                float((tmin[1] + tmax[1]) / 2),
                float((tmin[2] + tmax[2]) / 2),
            ],
            'transform': transform,
            'size': [
                float(tmax[0] - tmin[0]),
                float(tmax[1] - tmin[1]),
                float(tmax[2] - tmin[2]),
            ],
        }
        with open(filepath.replace('.glb', '.json'), 'w') as f:
            json.dump(tile_info, f)

        rotation = location_and_rotation.get('rotation')
        if rotation is not None:
            from mathutils import Matrix
            if not isinstance(rotation, Matrix):
                rotation = Matrix(rotation)
            tile.data.transform(rotation)
        tile.data.update()

        location = location_and_rotation.get('location')
        tile.location.x = location[0]
        tile.location.y = location[1]
        tile.location.z = location[2]

    export_asset(filepath)

    remove_obj(tile)
    return

def cut_mesh(left, top, w_unit, h_unit, size):
    bpy.ops.object.mode_set(mode='EDIT')

    bm = bmesh.from_edit_mesh(bpy.context.object.data)

    for x in range(0, size):
        i = left + (x * w_unit)
        ret = bmesh.ops.bisect_plane(bm, geom=bm.verts[:]+bm.edges[:]+bm.faces[:], plane_co=(i,0,0), plane_no=(-1,0,0))
        bmesh.ops.split_edges(bm, edges=[e for e in ret['geom_cut'] if isinstance(e, bmesh.types.BMEdge)])

    for y in range(0, size):
        i = top - (y * h_unit)
        ret = bmesh.ops.bisect_plane(bm, geom=bm.verts[:]+bm.edges[:]+bm.faces[:], plane_co=(0,i,0), plane_no=(0,1,0))
        bmesh.ops.split_edges(bm, edges=[e for e in ret['geom_cut'] if isinstance(e, bmesh.types.BMEdge)])
        
    bmesh.update_edit_mesh(bpy.context.object.data)
    bm.free()

def crop_mesh(input_file,bbox):
    if not bbox:
        logger.info("Skip mesh cropping")
        return
    
    bpy.ops.wm.read_factory_settings(use_empty=True)
    clean_up()
    merged, info = import_mesh(input_file)
    left = bbox[0] 
    top = bbox[3] 
    width = bbox[2] - bbox[0]  # maxx - minx
    height = bbox[3] - bbox[1]  # maxy - miny

    cut_mesh(left, top, width, height, 1)

    # Back to select mode
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action = 'DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    split_params = {
        'bbox': (bbox[0], bbox[1], bbox[2], bbox[3]), 
        'margin': 0,  
        'filepath': input_file, 
        'name': 'clipped_mesh',
        'target':merged,
        'should_decimate':False,
        'apply_transform': False,
        'export_asset': export_obj,
        'bake_img': None,
        'target_model': None,
        'bake_mat': None,
        'unwrap_uv': False
    }
    split_tile(split_params)
    remove_obj(merged)
    clean_up()
    bpy.ops.wm.read_factory_settings(use_empty=True)

def run(params):

    input_file = params.get('input_file', '')
    texture_image_size = params.get('texture_image_size', 512)
    tile_faces_target = params.get('tile_faces_target', 10000)
    depth = params.get('depth', 4)
    output_dir = params.get('output_dir', '')
    latitude = params.get('latitude', 0)
    longitude = params.get('longitude', 0)
    altitude = params.get('altitude', 0)
    apply_transform = params.get('apply_transform', True)
    decimate_last_depth_level = params.get('decimate_last_depth_level', False)
    start_x = params.get('start_x', 0)
    start_y = params.get('start_y', 0)
    start_z = params.get('start_z', 0)
    forward_axis = params.get('forward_axis', 'Y')
    up_axis = params.get('up_axis', 'Z')

    bpy.ops.wm.read_factory_settings(use_empty=True)
    start_time = time.time()
    logger.info(f"Starting from level {start_z} - x {start_x} - y {start_y}")
    clean_up()

    bake_mat = create_bake_material()

    merged, info = import_mesh(input_file, forward_axis, up_axis)
    merged.hide_render = True

    merged.select_set(True)
    bpy.context.view_layer.objects.active = merged
    bpy.ops.object.duplicate()
    target_model = bpy.context.active_object
    target_model.name = 'target_model'
    target_model.hide_render = True

    for obj in bpy.context.scene.objects:
        obj.select_set(False)

    merged.select_set(True)
    bpy.context.view_layer.objects.active = merged

    mat = apply_default_material(merged)

    setup_bake_setting()

    # setup bake material
    bake_img = create_image(mat, texture_image_size)
 
    merged.name = 'merged'

    width = merged.dimensions[0]
    height = merged.dimensions[1]

    transform = None
    location_and_rotation = None

    if apply_transform:
        location_and_rotation = get_location_and_rotation({
            'scale': 1,
            'latitude':  latitude,
            'longitude': longitude,
            'altitude': altitude
        })

        transform =  get_transform({
            'scale': 1,
            'latitude':  latitude,
            'longitude': longitude,
            'altitude': altitude
        })

    left = info.get('left')
    top = info.get('top')

    for z in range(start_z, depth + 1):
        level_size = pow(2, z)
        w_unit = width / level_size
        h_unit = height / level_size

        merged.select_set(True)
        bpy.context.view_layer.objects.active = merged
        bpy.ops.object.duplicate()
        cloned_merged = bpy.context.active_object
        cloned_merged.name = 'cloned_merged'
        cloned_merged.hide_render = True
        
        cut_mesh(left, top, w_unit, h_unit, level_size)

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action = 'DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        logger.info(f"Meshes: {len(bpy.data.meshes)}")
        logger.info(f"Materials: {len(bpy.data.materials)}")
        logger.info(f"Textures: {len(bpy.data.textures)}")
        logger.info(f"Images: {len(bpy.data.images)}")

        for y in range(start_y, level_size):
            for x in range(start_x, level_size):
                tile_start_time = time.time()

                minx = left + x * w_unit
                miny = top - ( (y + 1) * h_unit)
                maxx = left + ((x + 1) * w_unit)
                maxy = top - (y * h_unit)
                tile_name = f"{z}_{y}_{x}"
                logger.info(f"tile {tile_name} extent ({minx}, {miny}, {maxx}, {maxy})")
                filepath = os.path.join(output_dir, f"{tile_name}.glb")

                cage_extrusion = 20 / pow(2, z)

                should_decimate = True
                if z == depth and not decimate_last_depth_level:
                    cage_extrusion = 0.001
                    should_decimate = False

                split_tile({
                    'target': cloned_merged,
                    'bbox': (minx, miny, maxx, maxy),
                    'margin': 4,
                    'filepath': filepath,
                    'name': tile_name,
                    'bake_img': bake_img,
                    'bake_mat': bake_mat,
                    'default_mat': mat,
                    'unwrap_uv': True,
                    'target_model': target_model,
                    'tile_faces_target': tile_faces_target,
                    'should_decimate': should_decimate,
                    'apply_transform': apply_transform,
                    'cage_extrusion': cage_extrusion,
                    'location_and_rotation': location_and_rotation,
                    'transform': transform,
                    'export_asset': export_gltf,
                    'factor_force_decimation': 5 / (2 ** z)
                })
                elapsed_time = (time.time() - tile_start_time)
                logger.info(f"tile {tile_name} completed in {elapsed_time} seconds")

        remove_obj(cloned_merged)

    # Save mesh info for the finalize step (runs in the parent process).
    with open(os.path.join(output_dir, 'info.json'), 'w') as f:
        json.dump(info, f)

    elapsed_time = (time.time() - start_time)
    logger.info(f"tiling completed in {elapsed_time} seconds")
    return info
