"""Procedural modern-downtown city generator for Blender 5.x.

Run headless:
    blender --background --python city_generator.py

Optional flags (after a bare ``--``):
    --render day|night   lighting/time of day (default: day)
    --animate            render an orbiting fly-through animation
    --export             export the scene to glTF (.glb) and FBX

Examples:
    blender --background --python city_generator.py -- --render night --export
    blender --background --python city_generator.py -- --animate

Outputs (next to this script):
    city.blend                 editable scene
    city_preview.png           still render (day)
    city_night.png             still render (night)
    renders/anim/####.png      fly-through frames (with --animate)
    exports/city.glb / .fbx    game-engine exports (with --export)
"""

import argparse
import bpy
import bmesh
import math
import os
import random
import sys
from mathutils import Vector

# ----------------------------------------------------------------------------
# CONFIG -- tweak these to generate different cities
# ----------------------------------------------------------------------------
SEED = 42                 # fixed seed => reproducible city
GRID = 9                  # blocks per side (GRID x GRID city)
BLOCK = 8.0               # block footprint size (Blender units)
ROAD = 3.0                # road width between blocks
MAX_HEIGHT = 60.0         # tallest possible building (city center)
MIN_HEIGHT = 6.0          # shortest building (city edge)
HEIGHT_JITTER = 0.35      # +/- random variation applied to height
FOOTPRINT_MARGIN = 0.85   # building footprint as fraction of block (gaps = sidewalks)
EMPTY_LOT_CHANCE = 0.08   # chance a block is a park/empty lot instead of a building

ANIM_FRAMES = 120         # frames for the orbiting fly-through

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND_PATH = os.path.join(HERE, "city.blend")
EXPORT_DIR = os.path.join(HERE, "exports")
ANIM_DIR = os.path.join(HERE, "renders", "anim")

CELL = BLOCK + ROAD       # full grid stride per block


# ----------------------------------------------------------------------------
# CLI parsing -- Blender passes script args after a bare "--"
# ----------------------------------------------------------------------------
def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(prog="city_generator")
    p.add_argument("--render", choices=["day", "night"], default="day")
    p.add_argument("--animate", action="store_true")
    p.add_argument("--export", action="store_true")
    return p.parse_args(argv)


# ----------------------------------------------------------------------------
# Scene setup
# ----------------------------------------------------------------------------
def clear_scene():
    """Remove everything so re-runs start from an empty scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.outliner.orphans_purge(do_recursive=True)


def make_material(name, color, *, metallic=0.0, roughness=0.5, emission=None):
    """Create a Principled BSDF material. emission=(rgb, strength) adds glow."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        rgb, strength = emission
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    return mat


# ----------------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------------
def add_box(name, center, size, material):
    """Add a box mesh. center=(x,y,z) is the base-center; size=(sx,sy,sz)."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()

    obj.scale = (size[0], size[1], size[2])
    obj.location = (center[0], center[1], center[2] + size[2] / 2.0)
    obj.data.materials.append(material)
    return obj


def height_for(ix, iy, half):
    """Distance-from-center falloff: tall core, short edges, plus jitter."""
    cx, cy = ix - half, iy - half
    dist = math.sqrt(cx * cx + cy * cy) / (half * math.sqrt(2))  # 0 center -> 1 corner
    falloff = (1.0 - dist) ** 1.8                                # ease toward edges
    base = MIN_HEIGHT + (MAX_HEIGHT - MIN_HEIGHT) * falloff
    jitter = 1.0 + random.uniform(-HEIGHT_JITTER, HEIGHT_JITTER)
    return max(MIN_HEIGHT, base * jitter)


def build_roads(span, night):
    """Flat asphalt grid with painted center lane markings between blocks."""
    road_mat = make_material("Road", (0.03, 0.03, 0.04), roughness=0.85)
    # lane paint glows faintly at night so streets stay readable
    paint_em = ((1.0, 0.85, 0.4), 2.0) if night else None
    paint_mat = make_material("LanePaint", (0.85, 0.78, 0.45),
                              roughness=0.6, emission=paint_em)

    half = (GRID - 1) / 2.0
    # one continuous road strip per gridline, both axes
    for i in range(GRID + 1):
        offset = (i - half - 0.5) * CELL
        # road running along Y (vertical), centered on x=offset
        add_box(f"RoadV_{i}", (offset, 0, 0.01), (ROAD / 2, span / 2, 0.02), road_mat)
        # road running along X (horizontal)
        add_box(f"RoadH_{i}", (0, offset, 0.01), (span / 2, ROAD / 2, 0.02), road_mat)
        # dashed center line along Y
        for d in range(GRID * 2):
            y = (-span / 2) + (d + 0.5) * (span / (GRID * 2))
            add_box(f"PaintV_{i}_{d}", (offset, y, 0.03),
                    (0.06, span / (GRID * 4), 0.01), paint_mat)
            add_box(f"PaintH_{i}_{d}", (y, offset, 0.03),
                    (span / (GRID * 4), 0.06, 0.01), paint_mat)


# ----------------------------------------------------------------------------
# Build the city
# ----------------------------------------------------------------------------
def build_city(night):
    random.seed(SEED)
    half = (GRID - 1) / 2.0
    span = GRID * CELL

    asphalt = make_material("Asphalt", (0.04, 0.04, 0.05), roughness=0.9)
    add_box("Ground", (0, 0, -0.5), (span * 0.65, span * 0.65, 0.5), asphalt)

    build_roads(span * 1.0, night)

    glass_palette = [
        make_material("Glass_Blue", (0.12, 0.22, 0.32), metallic=0.7, roughness=0.15),
        make_material("Glass_Teal", (0.10, 0.28, 0.28), metallic=0.7, roughness=0.15),
        make_material("Glass_Steel", (0.30, 0.32, 0.36), metallic=0.85, roughness=0.2),
        make_material("Glass_Warm", (0.34, 0.30, 0.26), metallic=0.6, roughness=0.25),
    ]
    # windows blaze brighter at night
    win_strength = 6.0 if night else 1.2
    window = make_material(
        "Windows", (0.9, 0.85, 0.6),
        emission=((1.0, 0.9, 0.6), win_strength), roughness=0.3,
    )
    park = make_material("Park", (0.06, 0.22, 0.07), roughness=0.8)

    for ix in range(GRID):
        for iy in range(GRID):
            x = (ix - half) * CELL
            y = (iy - half) * CELL

            if random.random() < EMPTY_LOT_CHANCE:
                add_box(f"Park_{ix}_{iy}", (x, y, 0.0),
                        (BLOCK * 0.5, BLOCK * 0.5, 0.15), park)
                continue

            h = height_for(ix, iy, half)
            fp = BLOCK * FOOTPRINT_MARGIN * (1.0 - 0.25 * (h / MAX_HEIGHT))
            mat = random.choice(glass_palette)
            tower = add_box(f"Bldg_{ix}_{iy}", (x, y, 0.0), (fp / 2, fp / 2, h), mat)

            # stack a few glowing window bands up the tower
            n_bands = max(2, int(h // 12))
            for b in range(n_bands):
                bz = (b + 1) * h / (n_bands + 1)
                band = add_box(f"Win_{ix}_{iy}_{b}", (x, y, bz - 0.3),
                               (fp / 2 * 1.01, fp / 2 * 1.01, 0.6), window)
                band.parent = tower


# ----------------------------------------------------------------------------
# Lighting, camera, render
# ----------------------------------------------------------------------------
def setup_world(night):
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    if night:
        bg.inputs["Color"].default_value = (0.01, 0.012, 0.03, 1.0)
        bg.inputs["Strength"].default_value = 0.15
    else:
        bg.inputs["Color"].default_value = (0.55, 0.70, 0.95, 1.0)
        bg.inputs["Strength"].default_value = 1.0


def setup_sun(night):
    light = bpy.data.lights.new("Sun", type="SUN")
    if night:
        # cool, dim moonlight
        light.energy = 0.4
        light.color = (0.5, 0.6, 0.9)
    else:
        light.energy = 4.0
        light.color = (1.0, 0.97, 0.92)
    light.angle = math.radians(2.0)
    obj = bpy.data.objects.new("Sun", light)
    bpy.context.collection.objects.link(obj)
    obj.rotation_euler = (math.radians(55), math.radians(15), math.radians(40))


def setup_camera():
    """Camera parented to a center pivot Empty so it can orbit easily.

    Everything is built in the pivot's LOCAL space: the pivot sits at the orbit
    center, the camera is offset from it, and aims back at the local origin.
    This avoids any dependency on a (possibly stale) matrix_world.
    """
    pivot_z = MAX_HEIGHT * 0.35
    pivot = bpy.data.objects.new("CamPivot", None)
    pivot.location = (0, 0, pivot_z)
    bpy.context.collection.objects.link(pivot)

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 35
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.parent = pivot

    reach = GRID * CELL
    # local offset from the pivot (which is the orbit center / aim target)
    cam.location = (reach * 0.95, -reach * 0.95, reach * 0.7 - pivot_z)
    direction = Vector((0, 0, 0)) - cam.location  # aim at pivot (local origin)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    bpy.context.scene.camera = cam
    return pivot


def _action_fcurves(action):
    """Yield an action's F-Curves across legacy and 5.x slotted-action APIs."""
    if hasattr(action, "fcurves") and len(action.fcurves):
        yield from action.fcurves
        return
    for layer in getattr(action, "layers", []):       # Blender 4.4+ slotted actions
        for strip in layer.strips:
            for cbag in getattr(strip, "channelbags", []):
                yield from cbag.fcurves


def animate_orbit(pivot, scene):
    """Keyframe a full 360 turn of the pivot -> camera orbits the skyline."""
    scene.frame_start = 1
    scene.frame_end = ANIM_FRAMES
    pivot.rotation_euler = (0, 0, 0)
    pivot.keyframe_insert(data_path="rotation_euler", frame=1)
    pivot.rotation_euler = (0, 0, math.radians(360))
    pivot.keyframe_insert(data_path="rotation_euler", frame=ANIM_FRAMES)
    # constant-speed orbit (no ease in/out)
    for fc in _action_fcurves(pivot.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def configure_render(scene, night):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = "PNG"
    # a touch of bloom-like glow reads well for lit windows at night
    if hasattr(scene.eevee, "use_bloom"):
        scene.eevee.use_bloom = night


def render_still(scene, night):
    path = os.path.join(HERE, "city_night.png" if night else "city_preview.png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def render_animation(scene):
    os.makedirs(ANIM_DIR, exist_ok=True)
    scene.render.filepath = os.path.join(ANIM_DIR, "")
    bpy.ops.render.render(animation=True)
    return ANIM_DIR


# ----------------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------------
def export_scene():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    glb = os.path.join(EXPORT_DIR, "city.glb")
    fbx = os.path.join(EXPORT_DIR, "city.fbx")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB")
    bpy.ops.export_scene.fbx(filepath=fbx)
    return glb, fbx


def main():
    args = parse_args()
    night = args.render == "night"

    clear_scene()
    build_city(night)
    setup_world(night)
    setup_sun(night)
    pivot = setup_camera()

    scene = bpy.context.scene
    configure_render(scene, night)

    if args.animate:
        animate_orbit(pivot, scene)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print(f"Saved scene  -> {BLEND_PATH}")

    if args.animate:
        out = render_animation(scene)
        print(f"Saved frames -> {out}/####.png")
    else:
        out = render_still(scene, night)
        print(f"Saved render -> {out}")

    if args.export:
        glb, fbx = export_scene()
        print(f"Exported     -> {glb}")
        print(f"Exported     -> {fbx}")


if __name__ == "__main__":
    main()
