"""SIEGE / Astra procedural cinematic. No assets, add-ons or network required.

Blender 5.2:
  Blender -b -P blender/siege_scene_astra.py -- --out blender/astra_preview --res 1280 720 --start 24 --end 24
  Blender -b -P blender/siege_scene_astra.py -- --out blender/astra_frames --res 1280 720 --start 1 --end 180
  Blender -b -P blender/siege_scene_astra.py -- --out blender/astra_hero --res 3200 1800 --start 28 --end 28 --samples 48

The animation is exactly periodic over 180 frames (frame 181 == frame 1).
Frame handlers are registered on each scripted invocation; the optional .blend
is a portable scene snapshot. Re-run this source to render the animation.
"""

import argparse
import math
import os
import random
import sys
import time

import bpy
import bmesh
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument('--out', default='blender/astra_frames')
ap.add_argument('--res', nargs=2, type=int, default=[1280, 720])
ap.add_argument('--start', type=int, default=1)
ap.add_argument('--end', type=int, default=180)
ap.add_argument('--samples', type=int, default=24)
ap.add_argument('--engine', choices=['EEVEE', 'CYCLES'], default='EEVEE')
ap.add_argument('--device', choices=['CPU', 'GPU'], default='CPU')
ap.add_argument('--save-blend', action='store_true')
ap.add_argument('--title', action='store_true')
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
os.makedirs(args.out, exist_ok=True)
rng = random.Random(410)
TAU = math.tau
CENTER = Vector((0.6, 0, 3.15))
CORE = Vector((4.7, 0, 3.15))

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES' if args.engine == 'CYCLES' else 'BLENDER_EEVEE'
if args.engine == 'CYCLES':
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.device = args.device
    if args.device == 'GPU':
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for backend in ['OPTIX', 'CUDA', 'METAL', 'HIP', 'ONEAPI']:
            try:
                prefs.compute_device_type = backend
                prefs.get_devices()
                devices = [d for d in prefs.devices if d.type != 'CPU']
                if devices:
                    for device in prefs.devices:
                        device.use = device.type != 'CPU'
                    print(f'ASTRA_CYCLES_GPU {backend}', flush=True)
                    break
            except Exception:
                continue
        else:
            raise RuntimeError('No supported Cycles GPU detected; choose --device CPU.')
scene.render.resolution_x, scene.render.resolution_y = args.res
scene.render.resolution_percentage = 100
scene.render.fps = 30
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.render.film_transparent = False
scene.frame_start = 1
scene.frame_end = 180
scene.eevee.taa_render_samples = args.samples
scene.eevee.use_raytracing = False
scene.eevee.volumetric_samples = 16
scene.eevee.volumetric_tile_size = '8'
scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass
scene.view_settings.exposure = .2

world = bpy.data.worlds.new('SIEGE / midnight')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.009, .015, .023, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = .24
scene.world = world

def material(name, color, emission=0, metallic=0, rough=.36):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = rough
    p.inputs['Emission Color'].default_value = (*color, 1)
    p.inputs['Emission Strength'].default_value = emission
    return m

emerald = material('Gate / energized emerald', (.018, .78, .285), 3.4)
dim_green = material('Gate / dark teal tracery', (.014, .12, .09), 1.2, .6)
bright = material('Gate / luminous edge', (.31, 1, .63), 9)
amber = material('Attack / amber', (1, .255, .025), 6)
red = material('Breach / signal red', (1, .014, .07), 8)
violet = material('Defender / violet', (.38, .18, 1), 6)
blue = material('Observability / ice', (.055, .25, .51), 1.4)
metal = material('Blackened titanium', (.022, .031, .037), .02, .82, .22)
coremat = material('Agent / smoked ceramic', (.035, .09, .067), .30, .8, .19)
groundmat = material('Obsidian stage', (.005, .01, .013), 0, .55, .39)
floorline = material('Stage / barely visible inlay', (.009, .025, .019), .24, .35)
white = material('Typography / ivory', (.8, .92, .89), .32, .45, .24)

def assign(obj, mat):
    obj.data.materials.append(mat)
    return obj

def curve(name, coords, mat, bevel=.009, cyclic=False):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 1
    data.bevel_depth = bevel
    data.bevel_resolution = 1
    spline = data.splines.new('POLY')
    spline.points.add(len(coords)-1)
    for p, co in zip(spline.points, coords):
        p.co = (*co, 1)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    return assign(obj, mat)

def ring(name, radius, x, mat, bevel=.014, arc=TAU, start=0):
    n = max(8, int(150*arc/TAU))
    pts = [(x, radius*math.cos(start+arc*i/n), radius*math.sin(start+arc*i/n)) for i in range(n+1)]
    obj = curve(name, pts, mat, bevel, arc >= TAU)
    obj.location = CENTER
    return obj

ico_meshes = {}
def ico(name, pos, scale, mat, subdivisions=1):
    key = (subdivisions, mat.name)
    if key not in ico_meshes:
        mesh = bpy.data.meshes.new('Shared icosphere / ' + str(key))
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=1)
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(mat)
        ico_meshes[key] = mesh
    obj = bpy.data.objects.new(name, ico_meshes[key])
    scene.collection.objects.link(obj)
    obj.location = pos
    obj.scale = (scale,)*3 if isinstance(scale, (int,float)) else scale
    return obj

cube_meshes = {}
def cube(name, pos, scale, mat, bevel=0):
    if mat.name not in cube_meshes:
        mesh = bpy.data.meshes.new('Shared cube / ' + mat.name)
        verts = [(-.5,-.5,-.5),(-.5,-.5,.5),(-.5,.5,-.5),(-.5,.5,.5),(.5,-.5,-.5),(.5,-.5,.5),(.5,.5,-.5),(.5,.5,.5)]
        mesh.from_pydata(verts, [], [(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)])
        mesh.materials.append(mat)
        cube_meshes[mat.name] = mesh
    obj = bpy.data.objects.new(name, cube_meshes[mat.name])
    scene.collection.objects.link(obj)
    obj.location = pos
    obj.scale = scale
    if bevel:
        mod = obj.modifiers.new('Machined corners', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
    return obj

def pointlight(name, pos, color, energy, radius):
    data = bpy.data.lights.new(name, 'POINT')
    data.energy = energy
    data.color = color
    data.shadow_soft_size = radius
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = pos
    return obj

def aim(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z', 'Y').to_euler()

# A machined object with a live perimeter: thin lines stay legible at thumbnail scale.
ring('Gate / titanium outer wall', 2.45, 0, metal, .14)
ring('Gate / titanium inner wall', 2.24, 0, metal, .067)
ring('Gate / rear rim', 2.45, .23, dim_green, .03)
ring('Gate / forward emitter', 2.43, -.15, bright, .018)
ring('Gate / inner green emitter', 2.28, -.10, emerald, .024)
ring('Gate / outer halo', 2.72, 0, dim_green, .009)
ring('Gate / second fine halo', 2.84, .07, dim_green, .005)
gate_arcs = []
for i in range(12):
    a = i*TAU/12
    gate_arcs.append(ring('Gate / twelve indexed emitters %02d'%i, 2.59, -.04, emerald, .024, .29, a))
    for x in [-.18, .18]:
        coords = [(x, r*math.cos(a), r*math.sin(a)) for r in [2.34,2.54]]
        o = curve('Gate / radial key', coords, metal, .035)
        o.location = CENTER

# A counter-rotating helix makes the checkpoint feel intelligent and dimensional.
lattice = []
for j in range(3):
    pts = []
    for i in range(361):
        t = TAU*i/360
        r = 2.05 + .10*math.cos(t*9 + j*TAU/3)
        pts.append((.12*math.sin(t*9+j*TAU/3), r*math.cos(t), r*math.sin(t)))
    ob = curve('Gate / adaptive helical lattice %d'%j, pts, dim_green if j else emerald, .010, True)
    ob.location = CENTER
    lattice.append(ob)

# A sparsely etched membrane suggests an inspection plane without obscuring the core.
for y in [-1.5,-1,-.5,0,.5,1,1.5]:
    z = math.sqrt(1.95**2-y*y)
    ob = curve('Gate / inspection grid', [(0,y,-z),(0,y,z)], dim_green, .0025)
    ob.location=CENTER
for z in [-1.5,-1,-.5,0,.5,1,1.5]:
    y = math.sqrt(1.95**2-z*z)
    ob = curve('Gate / inspection grid', [(0,-y,z),(0,y,z)], dim_green, .0025)
    ob.location=CENTER

# The protected agent: dark faceted heart suspended in an orbital containment cage.
core = ico('Protected agent / faceted heart', CORE, .69, coremat, 3)
cage = ico('Protected agent / topology', CORE, .76, dim_green, 2)
wire = cage.modifiers.new('Agent topology', 'WIREFRAME')
wire.thickness=.006
core_orbits=[]
for j in range(3):
    ob=curve('Protected agent / orbit %d'%j, [(0,1.03*math.cos(i*TAU/160),1.03*math.sin(i*TAU/160)) for i in range(160)], emerald if j==0 else dim_green, .009, True)
    ob.location=CORE
    ob.rotation_euler=(j*.9,j*.66,j*.56)
    core_orbits.append(ob)
ico('Protected agent / central light', CORE+Vector((.4,-.48,.23)), .12, bright, 2)

# Controlled architectural floor lines establish scale; no arcade backdrop.
cube('Obsidian horizon', (0,0,-.08), (200,200,.1), groundmat)
for i in range(-5,6):
    curve('Stage / long line', [(-23,i*4,-.016),(19,i*4,-.016)], floorline, .002)
for i in range(-5,6):
    curve('Stage / cross line', [(i*4,-24,-.016),(i*4,24,-.016)], floorline, .002)
floor_ring=curve('Gate / floor projection', [(CENTER.x+2.95*math.cos(i*TAU/180),2.95*math.sin(i*TAU/180),.008) for i in range(180)], dim_green,.008,True)
for j in range(5):
    theta = j*TAU/5
    ico('Stage / calibration beacon', (CENTER.x+3.1*math.cos(theta),3.1*math.sin(theta),.015), .025, emerald)

# Low frequency dust with deliberately varied depth for lens parallax.
for i in range(95):
    p=(rng.uniform(-16,12),rng.uniform(-5,11),rng.uniform(.3,12))
    ico('Atmosphere / mote %03d'%i,p,rng.uniform(.007,.018),dim_green if i%4 else blue)

pointlight('Gate / spill', CENTER+Vector((-1.1,-.3,0)), (.03,1,.31), 700, 2.2)
pointlight('Agent / teal rim', CORE+Vector((1,1,1)), (.12,.6,.51), 450, 1.7)
pointlight('Stage / amber bounce', (-5,-1,2), (1,.3,.03), 130, 3)
area_data=bpy.data.lights.new('Key / softbox','AREA')
area_data.energy=1700
area_data.color=(.32,.46,.6)
area_data.shape='DISK'
area_data.size=9
area=bpy.data.objects.new('Key / softbox',area_data)
scene.collection.objects.link(area)
area.location=(2,-3,11)
aim(area,CENTER)

# Geometric attack trails; all animate from periodic analytic expressions.
attack_template=ico('Attack / head template',(0,0,-50),1,amber)
fragment_template=ico('Attack / fragment template',(0,0,-50),1,amber)
attack_template.hide_render=True
fragment_template.hide_render=True

def instance(name, template, mat=None):
    ob=bpy.data.objects.new(name,template.data)
    scene.collection.objects.link(ob)
    if mat:
        ob.data=template.data.copy()
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    return ob

def streak(name, mat):
    ob=cube(name,(0,0,-50),(1,.012,.012),mat)
    return ob

attacks=[]
for wave,(phase,count) in enumerate([(.015,16),(.36,11),(.705,5)]):
    for i in range(count):
        a=rng.uniform(0,TAU)
        r=rng.uniform(.38,1.78)
        yz=Vector((0,math.cos(a)*r,math.sin(a)*r))
        breach=(wave==0 and i in (4,10)) or (wave==1 and i==5)
        mat=red if breach else amber
        head=instance('Attack / %d.%02d'%(wave+1,i),attack_template,mat)
        tail=streak('Attack / trajectory',mat)
        impact=ico('Attack / impact',CENTER+yz,.001,mat,2)
        fragments=[]
        for k in range(9 if not breach else 0):
            frag=instance('Block / fragment',fragment_template)
            direction=Vector((-rng.uniform(.3,1.5),rng.uniform(-1,1),rng.uniform(-1,1))).normalized()
            fragments.append((frag,direction,rng.uniform(.7,1.6),rng.uniform(.012,.04)))
        attacks.append(dict(start=phase+i/count*.095,head=head,tail=tail,impact=impact,fragments=fragments,yz=yz,breach=breach))

satellites=[]
for i in range(5):
    sat=ico('Defender / satellite %d'%i,(0,0,-40),.07,violet,2)
    satellites.append(sat)
defender_ring=ring('Defender / rewrite wave',2.43,-.17,violet,.032)
flash=pointlight('Breach / contained pulse',CORE,(1,.02,.08),0,1.8)

# Camera composition leaves space to the left for application overlays.
cam_data=bpy.data.cameras.new('Camera / slow orbital dolly')
cam=bpy.data.objects.new('Camera / slow orbital dolly',cam_data)
scene.collection.objects.link(cam)
scene.camera=cam
cam_data.lens=49
cam_data.dof.use_dof=True
cam_data.dof.focus_object=core
cam_data.dof.aperture_fstop=7.0
cam_data.lens=49

if args.title:
    data=bpy.data.curves.new('SIEGE / wordmark','FONT')
    data.body='SIEGE'
    data.align_x='CENTER'
    data.size=1.52
    data.space_character=1.16
    data.extrude=.017
    data.bevel_depth=.006
    data.bevel_resolution=2
    wordmark=bpy.data.objects.new('SIEGE / wordmark',data)
    scene.collection.objects.link(wordmark)
    assign(wordmark,white)
else:
    wordmark=None

# Blender 5.2 exposes compositing as a node group with an Image interface.
comp=bpy.data.node_groups.new('SIEGE / optical finish','CompositorNodeTree')
scene.compositing_node_group=comp
comp.interface.new_socket('Image',in_out='OUTPUT',socket_type='NodeSocketColor')
rl=comp.nodes.new('CompositorNodeRLayers')
gl=comp.nodes.new('CompositorNodeGlare')
gl.inputs['Type'].default_value='Fog Glow'
gl.inputs['Quality'].default_value='High'
if 'Threshold' in gl.inputs:
    gl.inputs['Threshold'].default_value=.9
if 'Strength' in gl.inputs:
    gl.inputs['Strength'].default_value=.55
out=comp.nodes.new('NodeGroupOutput')
comp.links.new(rl.outputs['Image'],gl.inputs['Image'])
comp.links.new(gl.outputs['Image'],out.inputs['Image'])

def hide(ob):
    ob.scale=(.00001,)*3

def update(scene):
    phase=((scene.frame_current-1)%180)/180
    theta=TAU*phase
    cam.location=(13.8+.3*math.sin(theta),-17.2+.2*math.cos(theta),7.1+.10*math.sin(theta))
    aim(cam,(-.7,0,3.15))
    for i,ob in enumerate(lattice):
        ob.rotation_euler.x=-theta
    for j,ob in enumerate(core_orbits):
        ob.rotation_euler=(j*.9+theta,j*.66,j*.56)
    core.rotation_euler=(theta,theta,0)
    cage.rotation_euler=(theta,theta,0)
    flash.data.energy=0
    for a in attacks:
        age=(phase-a['start'])%1
        travel=.145
        incoming=0<=age<travel
        after=age-travel
        if incoming:
            p=age/travel
            pos=CENTER+a['yz']+Vector((-13*(1-p),0,0))
            a['head'].location=pos
            a['head'].scale=(.083,.021,.021)
            a['tail'].location=pos-Vector((.68,0,0))
            a['tail'].scale=(1.25,.011,.011)
        elif a['breach'] and 0<=after<.10:
            p=after/.10
            pos=CENTER+a['yz']*(1-p)+Vector(((CORE.x-CENTER.x)*p,0,0))
            a['head'].location=pos
            a['head'].scale=(.1,.028,.028)
            a['tail'].location=pos-Vector((.85,0,0))
            a['tail'].scale=(1.6,.018,.018)
        else:
            hide(a['head']);hide(a['tail'])
        if 0<=after<.065:
            p=after/.065
            s=.13*(1-p)**2+.005
            a['impact'].scale=(s*.35,s,s)
        else:
            hide(a['impact'])
        for ob,direction,speed,size in a['fragments']:
            if 0<=after<.155:
                p=after/.155
                ob.location=CENTER+a['yz']+direction*(1-(1-p)**3)*speed
                ob.scale=(size*(1-p),)*3
                ob.rotation_euler=(p*8,p*13,p*5)
            else: hide(ob)
        if a['breach'] and .095<after<.155:
            flash.data.energy=max(flash.data.energy,650*math.sin((after-.095)/.06*math.pi))
    # Two revision intervals. The final attack wave is materially smaller.
    defense=max(math.exp(-((phase-.325)/.045)**2),math.exp(-((phase-.667)/.045)**2))
    for j,sat in enumerate(satellites):
        ang=theta*3+j*TAU/5
        radius=2.6+(1-defense)*.7
        sat.location=CENTER+Vector((-.15,radius*math.cos(ang),radius*math.sin(ang)))
        sat.scale=(.07*defense+.00001,)*3
    defender_ring.scale=(1,1,1) if defense>.05 else (.00001,)*3
    defender_ring.data.bevel_depth=.006+.022*defense
    if wordmark:
        # Camera-facing title with subtle depth, placed in reserved foreground.
        wordmark.rotation_euler=cam.rotation_euler
        wordmark.location=Vector((-4.2,-1.8,3.9))
        wordmark.scale=(1+.008*math.sin(theta),)*3

bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(update)
scene.frame_set(args.start)
update(scene)
if args.save_blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(args.out,'siege_astra.blend')))
timings=[]
print(f'ASTRA_SCENE_READY objects={len(scene.objects)}',flush=True)
for frame in range(args.start,args.end+1):
    scene.frame_set(frame)
    update(scene)
    scene.render.filepath=os.path.abspath(os.path.join(args.out,f'frame_{frame:04d}.png'))
    started=time.perf_counter()
    bpy.ops.render.render(write_still=True)
    timings.append(time.perf_counter()-started)
    print(f'ASTRA_FRAME {frame} {timings[-1]:.3f}s',flush=True)
print(f'ASTRA_DONE frames={len(timings)} mean={sum(timings)/len(timings):.3f}s',flush=True)
