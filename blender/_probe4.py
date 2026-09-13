import bpy
s = bpy.context.scene
ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree"); s.compositing_node_group = ng
for t in ("CompositorNodeEllipseMask","CompositorNodeBlur","CompositorNodeColorBalance","CompositorNodeLensdist","CompositorNodeRLayers","CompositorNodeHueSat"):
    n = ng.nodes.new(t)
    print(t, "IN:", [(i.name, i.type, (i.default_value if i.type in ('VALUE','INT','BOOLEAN','MENU') else '...')) for i in n.inputs])
    print("   props:", [p.identifier for p in n.bl_rna.properties if p.identifier not in ('rna_type','location','location_absolute','width','height','dimensions','name','label','inputs','outputs','panel_states','internal_links','parent','warning_propagation','use_custom_color','color','color_tag','select','show_options','show_preview','hide','mute','show_texture','bl_idname','bl_label','bl_description','bl_icon','bl_static_type','bl_width_default','bl_width_min','bl_width_max','bl_height_default','bl_height_min','bl_height_max','type')])
print("cam fstop range:", bpy.types.CameraDOFSettings.bl_rna.properties['aperture_fstop'].hard_min)
print("vol tile:", [e.identifier for e in s.eevee.bl_rna.properties['volumetric_tile_size'].enum_items])
l = bpy.data.lights.new("L","POINT"); print("light props:", [a for a in dir(l) if a in ('use_shadow','diffuse_factor','specular_factor','volume_factor','shadow_soft_size','use_soft_falloff','exposure','normalize')])
print("pref interp:", bpy.context.preferences.edit.keyframe_new_interpolation_type)
m = bpy.data.materials.new("M"); m.use_nodes=True
print("blend_method items:", [e.identifier for e in m.bl_rna.properties['blend_method'].enum_items])
print("mesh shade_smooth:", hasattr(bpy.types.Mesh, 'shade_smooth'))
