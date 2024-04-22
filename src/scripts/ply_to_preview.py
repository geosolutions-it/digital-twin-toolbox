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
output_file = argv[1]

mesh_faces_target = argv[2]
if not mesh_faces_target:
    mesh_faces_target = 500000
else:
    mesh_faces_target = int(mesh_faces_target)

if __name__ == '__main__':

    bpy.ops.wm.read_factory_settings(use_empty=True)
    start_time = time.time()

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

    # merge parts
    def import_ply(filepath):

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

        obj.location.x = 0
        obj.location.y = 0
        obj.location.z = 0

        return obj

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

    clean_up()

    merged = import_ply(input_file)

    # initial decimation to keep mesh under 500000 faces
    decimate_obj(merged, mesh_faces_target)

    merged.name = 'merged'

    bpy.ops.export_scene.gltf(
        filepath=output_file,
        use_selection=True,
        export_format="GLB",
        export_draco_mesh_compression_enable=False,

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
        export_colors=True,
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

    remove_obj(merged)

    print("--- %s minutes ---" % ((time.time() - start_time) / 60))
