import bpy
import json
import os
import sys

import numpy as np

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
STILL = "--still" in ARGS
ANIM = "--anim" in ARGS

GRAPH = "/tmp/current-graph"
NPZ = os.path.join(GRAPH, "layout.npz")
META = os.path.join(GRAPH, "layout.json")
OUT = "/Volumes/Storage/Riemmann/alpoge-rh-replay/video/blender"
os.makedirs(OUT, exist_ok=True)

d = np.load(NPZ)
xy = d["xy"].astype(np.float32)
edges = d["edges"].astype(np.int32)
meta = json.load(open(META))
roots = np.array([c.split(".")[0] for c in meta["clusters"]])
uniq = sorted(set(roots.tolist()))

PALETTE = [
    (0.70, 0.35, 1.00), (0.45, 0.30, 1.00), (0.90, 0.25, 0.95),
    (0.30, 0.45, 1.00), (0.10, 0.90, 0.95), (1.00, 0.45, 0.65),
    (0.85, 0.35, 0.95), (0.55, 0.60, 1.00), (0.80, 0.20, 1.00),
    (0.35, 0.75, 1.00), (1.00, 0.55, 0.75), (0.65, 1.00, 0.45),
]
color_of = {r: PALETTE[i % len(PALETTE)] for i, r in enumerate(uniq)}
rng = np.random.default_rng(42)
if len(edges) > 120000:
    deg = np.bincount(edges.ravel(), minlength=len(xy))
    w = 1.0 / np.sqrt(deg[edges[:, 0]] + 1.0)
    keep = rng.choice(len(edges), size=120000, replace=False, p=w / w.sum())
    edges = edges[keep]
edge_colors = np.array([color_of[r] for r in roots[edges[:, 0]]], dtype=np.float32)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.eevee.taa_render_samples = 32
scene.view_settings.view_transform = "Standard"

scale = 1.6
zvals = (np.array([uniq.index(r) for r in roots], dtype=np.float32)
         - (len(uniq) - 1) / 2.0) * 0.22
p0 = np.column_stack([xy[edges[:, 0], 0] * scale, xy[edges[:, 0], 1] * scale,
                      zvals[edges[:, 0]]])
p1 = np.column_stack([xy[edges[:, 1], 0] * scale, xy[edges[:, 1], 1] * scale,
                      zvals[edges[:, 1]]])
dvec = p1 - p0
length = np.linalg.norm(dvec[:, :2], axis=1)
length[length == 0] = 1.0
perp = np.column_stack([-dvec[:, 1] / length, dvec[:, 0] / length,
                        np.zeros(len(edges))]) * 0.0022
V = np.empty((len(edges) * 4, 3), dtype=np.float32)
V[0::4] = p0 + perp
V[1::4] = p0 - perp
V[2::4] = p1 - perp
V[3::4] = p1 + perp
F = np.arange(len(edges) * 4, dtype=np.int32).reshape(-1, 4)

mesh = bpy.data.meshes.new("import_graph")
mesh.vertices.add(len(V))
mesh.vertices.foreach_set("co", V.ravel())
mesh.loops.add(len(F.ravel()))
mesh.loops.foreach_set("vertex_index", F.ravel())
mesh.polygons.add(len(F))
mesh.polygons.foreach_set("loop_start", np.arange(0, len(F.ravel()), 4,
                                                  dtype=np.int32))
mesh.polygons.foreach_set("loop_total", np.full(len(F), 4, dtype=np.int32))
mesh.update()

col = np.repeat(edge_colors, 4, axis=0)
attr = mesh.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
attr.data.foreach_set("color", np.hstack([col, np.ones((len(col), 1),
                                                      dtype=np.float32)]).ravel())

obj = bpy.data.objects.new("import_graph", mesh)
bpy.context.collection.objects.link(obj)

mat = bpy.data.materials.new("graph_glow")
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
em = nt.nodes.new("ShaderNodeEmission")
vc = nt.nodes.new("ShaderNodeVertexColor")
vc.layer_name = "Col"
em.inputs["Strength"].default_value = 0.55
nt.links.new(vc.outputs["Color"], em.inputs["Color"])
nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
mesh.materials.append(mat)

world = bpy.data.worlds.new("space")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.002, 0.001, 0.006, 1.0)
bg.inputs["Strength"].default_value = 0.2
scene.world = world

target = bpy.data.objects.new("target", None)
bpy.context.collection.objects.link(target)
target.location = (0.0, 0.0, 0.0)

cam_data = bpy.data.cameras.new("camera")
cam = bpy.data.objects.new("camera", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam
con = cam.constraints.new("TRACK_TO")
con.target = target
con.track_axis = "TRACK_NEGATIVE_Z"
con.up_axis = "UP_Y"

cam.location = (0.0, -5.2, 3.4)
cam.keyframe_insert("location", frame=1)
cam.location = (1.1, -4.0, 2.3)
cam.keyframe_insert("location", frame=120)

scene.frame_start = 1
scene.frame_end = 120
scene.render.fps = 24

if STILL:
    scene.frame_set(60)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.join(OUT, "still.png")
    bpy.ops.render.render(write_still=True)
    print("STILL", scene.render.filepath)

if ANIM:
    os.makedirs(os.path.join(OUT, "frames"), exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.join(OUT, "frames", "frame_")
    bpy.ops.render.render(animation=True)
    print("ANIM", os.path.join(OUT, "frames"))
