import bpy
sysp = bpy.context.preferences.system
print("SYS PREFS:", [a for a in dir(sysp) if 'shader' in a or 'compil' in a or 'subprocess' in a or 'gpu' in a])
for a in dir(sysp):
    if 'shader' in a or 'compil' in a or 'subprocess' in a:
        try:
            p = sysp.bl_rna.properties[a]
            print("  ", a, "=", getattr(sysp, a), "enum:", [e.identifier for e in p.enum_items] if p.type == 'ENUM' else p.type)
        except Exception as e:
            print("  ", a, "err", e)
