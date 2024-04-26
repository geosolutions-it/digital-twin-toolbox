import bpy
import os
import bmesh
from bpy import context as C
import math
import json
import time
import sys
argv = sys.argv
if '--' in argv:
    argv = argv[argv.index("--") + 1:] 
else:
    argv = []

input_file = argv[0]
output_dir = argv[1]

depth = argv[2]
if not depth:
    depth = 3
else:
    depth = int(depth)

mesh_faces_target = argv[3]
if not mesh_faces_target:
    mesh_faces_target = 500000
else:
    mesh_faces_target = int(mesh_faces_target)

tile_faces_target = argv[4]
if not tile_faces_target:
    tile_faces_target = 40000
else:
    tile_faces_target = int(tile_faces_target)

remove_doubles_factor = argv[5]
if not remove_doubles_factor:
    remove_doubles_factor = 0.025
else:
    remove_doubles_factor = float(remove_doubles_factor)

input_image = argv[6]
if not input_image:
    input_image = None

if __name__ == '__main__':

    bpy.ops.wm.read_factory_settings(use_empty=True)
    start_time = time.time()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    scene = bpy.context.scene

    # clean up
    def clean_up():

        if bpy.context.active_object:
            bpy.ops.object.mode_set(mode='OBJECT')
                
        for obj in scene.objects:
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
            bsdf.inputs['Specular'].default_value = 0
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

    def setup(bake_mat):

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

        # setup bake material
        bake_img_1024 = create_image(bake_mat, 1024)
        bake_img_512 = create_image(bake_mat, 512)
        return [bake_img_1024, bake_img_512]

    # merge parts
    def merge_parts(filepath, output_path):

        if bpy.context.active_object:
            bpy.ops.object.mode_set(mode='OBJECT')
            
        for obj in scene.objects:
            obj.select_set(False)
            obj.hide_set(False)

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(True)

        # this import is slower
        # bpy.ops.import_mesh.ply(filepath=filepath)
        # the experimental import needs the make single user operation
        bpy.ops.wm.ply_import(filepath=filepath)
        bpy.ops.object.make_single_user(object=True, obdata=True, material=True, animation=False, obdata_animation=False)

        mesh_objects = [obj for obj in scene.objects if obj.type == 'MESH']

        for obj in mesh_objects:
            obj.select_set(True)

        bpy.context.view_layer.objects.active = mesh_objects[0]

        obj = bpy.context.object
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        loc = obj.location.copy()

        x = loc[0]
        y = loc[1]
        z = loc[2]

        obj.location.x = 0
        obj.location.y = 0
        obj.location.z = 0
        
        width = obj.dimensions[0]
        height = obj.dimensions[1]
        
        info = {
            'size': [obj.dimensions[0], obj.dimensions[1], obj.dimensions[2]],
            'depth': depth,
            'center': [x, y, z]
        }

        info_path =  os.path.join(output_path, 'info.json')

        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=4)

        mat = bpy.data.materials.new(name='EmissionMaterial')
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs['Base Color'].default_value = (0, 0, 0, 1)
        bsdf.inputs['Specular'].default_value = 0
        bsdf.inputs['Roughness'].default_value = 1

        vertex_color_node = mat.node_tree.nodes.new('ShaderNodeVertexColor')
        vertex_color_node.name = 'VertexColorNode'
        vertex_color_node.select = True
        mat.node_tree.links.new( vertex_color_node.outputs[0], bsdf.inputs['Emission'] )

        obj.data.materials.append(mat)

        return [obj, mat]

    def export_gltf(filepath, export_jpeg_quality):
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_image_format='JPEG',
            export_jpeg_quality=export_jpeg_quality,
            
            use_selection=True,
            export_format="GLB",
            export_draco_mesh_compression_enable=True,

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
            export_colors=False,
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

    def decimate_obj(obj, _faces_target):
        ratio = _faces_target / len(obj.data.polygons)
        print('faces', len(obj.data.polygons))
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        if ratio < 1:
            print('ratio', ratio)
            decimate = obj.modifiers.new(type="DECIMATE", name="decimate")
            decimate.ratio = ratio
            decimate.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier="decimate")

    def get_image_plane(dimensions):

        bpy.ops.mesh.primitive_plane_add(
            size=1,
            enter_editmode=False,
            align='WORLD',
            location=(0, 0, dimensions[2]),
            scale=(1, 1, 1)
        )
        
        plane = bpy.context.object
        plane.scale.x = dimensions[0]
        plane.scale.y = dimensions[1]
        
        bpy.ops.object.transform_apply()
        
        mat = bpy.data.materials.new(name='PlaneMaterial')
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs['Specular'].default_value = 0
        bsdf.inputs['Roughness'].default_value = 1
        texture_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        texture_node.name = 'BaseImageNode'
        texture_node.select = True
        texture_node.image = bpy.data.images.load(filepath=input_image, check_existing=False)
        mat.node_tree.links.new(bsdf.inputs['Base Color'], texture_node.outputs['Color'])
        mat.node_tree.nodes.active = texture_node
        
        plane.data.materials.append(mat)
        
        bpy.ops.object.vertex_group_add()
        
        bpy.ops.object.mode_set(mode='EDIT')

        for subdivide_count in range(0, 10):
            bpy.ops.mesh.subdivide()

        bpy.ops.object.vertex_group_assign()
        bpy.ops.object.mode_set(mode='OBJECT')
        
        shrinkwrap = plane.modifiers.new(type="SHRINKWRAP", name="shrinkwrap")
        shrinkwrap.wrap_method = 'PROJECT'
        shrinkwrap.use_positive_direction = True
        shrinkwrap.use_negative_direction = True
        shrinkwrap.target = merged
        bpy.ops.object.modifier_apply(modifier="shrinkwrap")
        
        vertex_weight_proximity = plane.modifiers.new(type="VERTEX_WEIGHT_PROXIMITY", name="vertex_weight_proximity")
        vertex_weight_proximity.target = merged
        vertex_weight_proximity.vertex_group = 'Group'
        vertex_weight_proximity.max_dist = 0.0001
        vertex_weight_proximity.min_dist = 0.0002
        vertex_weight_proximity.proximity_mode = 'GEOMETRY'
        vertex_weight_proximity.proximity_geometry = {'FACE'}
        vertex_weight_proximity.normalize = True
        bpy.ops.object.modifier_apply(modifier="vertex_weight_proximity")

        mask = plane.modifiers.new(type="MASK", name="mask")
        mask.vertex_group = 'Group'
        bpy.ops.object.modifier_apply(modifier="mask")
        
        bpy.ops.object.select_all(action="DESELECT")

        return plane

    def split_tile(target, bbox, margin, filepath, name, bake_img, remove_doubles_threshold, bake_mat, plane):

        for obj in scene.objects:
            obj.select_set(False)
            obj.hide_set(False)
        
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.duplicate()
        full = bpy.context.active_object
        full.name = 'full'

        nothing_selected = True
        for vertex in full.data.vertices:
            x = vertex.co[0]
            y = vertex.co[1]
            minx = bbox[0] - margin
            miny = bbox[1] - margin
            maxx = bbox[2] + margin
            maxy = bbox[3] + margin
            if x >= minx and x <= maxx and y >= miny and y <= maxy:
                vertex.select = True
                nothing_selected = False

        if nothing_selected:
            # if nothing is selected we skip and proceed with next tile
            remove_obj(full)
            return

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')
        tile = bpy.data.objects['full.001']
        tile.name = 'tile'
        bpy.ops.object.select_all(action="DESELECT")

        remove_obj(full)

        tile.select_set(True)
        bpy.context.view_layer.objects.active = tile

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action = 'SELECT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.mesh.dissolve_degenerate()
        bpy.ops.object.editmode_toggle()
        # unwrap the uv
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action = 'SELECT')
        bpy.ops.uv.smart_project()
        bpy.ops.object.editmode_toggle()

        bake_img.select = True
        mat = tile.material_slots[0].material
        mat.node_tree.nodes.active = bake_img

        # bake
        if plane:
            plane.select_set(True)
            bpy.context.scene.cycles.bake_type = 'DIFFUSE'
            bpy.context.scene.render.bake.use_selected_to_active = True
            bpy.context.scene.render.bake.cage_extrusion = 0.001 # (m) to avoid black pixels
            bpy.ops.object.bake(type='DIFFUSE',use_clear=True)
            plane.select_set(False)
        else:
            bpy.context.scene.cycles.bake_type = 'EMIT'
            bpy.context.scene.render.bake.use_selected_to_active = False
            bpy.context.scene.render.bake.cage_extrusion = 0
            bpy.ops.object.bake(type='EMIT',use_clear=True)

        # remove all material from tile copy
        tile.data.materials.clear()

        texture_node = bake_mat.node_tree.nodes.get('TileImageNode')
        texture_node.image = bake_img.image
        # apply the bake material
        tile.data.materials.append(bake_mat)

        tile.name = name

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.remove_doubles()
        bpy.ops.object.editmode_toggle()

        decimate_obj(tile, tile_faces_target)

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.remove_doubles(threshold=remove_doubles_threshold)
        bpy.ops.object.editmode_toggle()

        bpy.ops.object.shade_smooth()

        export_gltf(filepath, 60)

        remove_obj(tile)
        return


    clean_up()
    bake_mat = create_bake_material()

    merged, mat = merge_parts(input_file, output_dir)

    # initial decimation to keep mesh under 500000 faces
    decimate_obj(merged, mesh_faces_target)

    bake_imgs = setup(mat)
    merged.name = 'merged'

    width = merged.dimensions[0]
    height = merged.dimensions[1]

    plane = None

    if input_image:

        # remove edge from merged
        '''
        if mesh_faces_target <= 500000:
            bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.select_all(action = 'SELECT')
            bpy.ops.mesh.dissolve_limited()
            bpy.ops.object.editmode_toggle()
        '''

        plane = get_image_plane(merged.dimensions)

    for z in range(0, depth + 1):

        for img in bake_imgs:
            img.select = False

        bake_img = bake_imgs[1] # 512

        if z == depth:
            bake_img = bake_imgs[0] # 1024

        size = pow(2, z)
        w_unit = width / size
        h_unit = height / size

        remove_doubles_threshold = (width * remove_doubles_factor) / size
        if z == depth:
            remove_doubles_threshold = 0.0001

        # decimate merged
        merged.select_set(True)
        bpy.context.view_layer.objects.active = merged
        bpy.ops.object.duplicate()
        clonded_merged = bpy.context.active_object
        clonded_merged.name = 'clonded_merged'

        bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(C.object.data)

        for x in range(0, size):
            i = (x * w_unit) - width / 2
            ret = bmesh.ops.bisect_plane(bm, geom=bm.verts[:]+bm.edges[:]+bm.faces[:], plane_co=(i,0,0), plane_no=(-1,0,0))
            bmesh.ops.split_edges(bm, edges=[e for e in ret['geom_cut'] if isinstance(e, bmesh.types.BMEdge)])

        for y in range(0, size):
            i = (height / 2) - (y * h_unit)
            ret = bmesh.ops.bisect_plane(bm, geom=bm.verts[:]+bm.edges[:]+bm.faces[:], plane_co=(0,i,0), plane_no=(0,1,0))
            bmesh.ops.split_edges(bm, edges=[e for e in ret['geom_cut'] if isinstance(e, bmesh.types.BMEdge)])
            
        bmesh.update_edit_mesh(C.object.data)
        bm.free()

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action = 'DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        for y in range(0, size):
            for x in range(0, size):

                print('Meshes', len(bpy.data.meshes))
                print('Materials', len(bpy.data.materials))
                print('Textures', len(bpy.data.textures))
                print('Images', len(bpy.data.images))

                tile_start_time = time.time()

                minx = x * w_unit - width / 2
                miny = (height / 2) - (y + 1) * h_unit
                maxx = (x + 1) * w_unit - width / 2
                maxy = (height / 2) - y * h_unit

                print(minx, miny, maxx, maxy)
                tile_name = f"{z}_{y}_{x}"
                filepath = os.path.join(output_dir, f"{tile_name}.glb")
                split_tile(clonded_merged, (minx, miny, maxx, maxy), 4, filepath, tile_name, bake_img, remove_doubles_threshold, bake_mat, plane)
                print(f"done {tile_name} in")
                print("--- %s seconds ---" % ((time.time() - tile_start_time)))

        remove_obj(clonded_merged)

    remove_obj(merged)

    print("--- %s minutes ---" % ((time.time() - start_time) / 60))
