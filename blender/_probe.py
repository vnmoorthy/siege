import bpy, sys
print("ENGINES:", [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items])
s = bpy.context.scene
print("scene attrs with comp:", [a for a in dir(s) if 'comp' in a.lower()])
print("has node_tree:", hasattr(s, 'node_tree'), "use_nodes:", hasattr(s, 'use_nodes'))
print("eevee attrs:", [a for a in dir(s.eevee) if not a.startswith('_')])
print("render.compositor attrs:", [a for a in dir(s.render) if 'comp' in a.lower()])
print("world attrs:", [a for a in dir(bpy.data.worlds[0]) if not a.startswith('_')] if bpy.data.worlds else None)
try:
    prefs = bpy.context.preferences
    print("gpu_backend:", prefs.system.gpu_backend)
except Exception as e:
    print("gpu_backend err", e)
try:
    import gpu
    print("GPU backend:", gpu.platform.backend_type_get(), gpu.platform.device_type_get(), gpu.platform.renderer_get())
except Exception as e:
    print("gpu err", e)
# Glare node types
print("Glare node:", hasattr(bpy.types, 'CompositorNodeGlare'))
try:
    gl = bpy.types.CompositorNodeGlare
    print("glare props:", [p.identifier for p in gl.bl_rna.properties])
    print("glare types:", [e.identifier for e in gl.bl_rna.properties['glare_type'].enum_items])
except Exception as e:
    print("glare err", e)
print("image_settings formats:", [e.identifier for e in bpy.types.ImageFormatSettings.bl_rna.properties['file_format'].enum_items])
print("view transforms:", [e.identifier for e in s.view_settings.bl_rna.properties['view_transform'].enum_items])
print("look:", [e.identifier for e in s.view_settings.bl_rna.properties['look'].enum_items][:20])
print("cam attrs:", [a for a in dir(bpy.data.cameras[0]) if 'dof' in a.lower()] if bpy.data.cameras else None)
print("eevee taa:", s.eevee.taa_render_samples)
print("light probe / shadow:", [a for a in dir(s.eevee) if 'shadow' in a.lower() or 'volum' in a.lower() or 'ray' in a.lower()])
