"""Procedural modern-downtown city generator for Blender 5.x.

Run headless:
    blender --background --python city_generator.py

Outputs (next to this script):
    city.blend          editable scene
    city_preview.png     rendered preview

All tunable parameters live in the CONFIG block below.
"""

import bpy
import bmesh
import math
import os
import random
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

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND_PATH = os.path.join(HERE, "city.blend")
RENDER_PATH = os.path.join(HERE, "city_preview.png")

CELL = BLOCK + ROAD       # full grid stride per block


# ----------------------------------------------------------------------------
# Scene setup
# ----------------------------------------------------------------------------
def clear_scene():
    """Remove everything so re-runs start from an empty scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # purge orphaned datablocks (meshes/materials) left behind
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
    # cube is centered on origin; lift so it sits on z=0 then move to base center
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


# ----------------------------------------------------------------------------
# Build the city
# ----------------------------------------------------------------------------
def build_city():
    random.seed(SEED)
    half = (GRID - 1) / 2.0
    span = GRID * CELL

    # ground / asphalt
    asphalt = make_material("Asphalt", (0.04, 0.04, 0.05), roughness=0.9)
    add_box("Ground", (0, 0, -0.5), (span * 0.65, span * 0.65, 0.5), asphalt)

    # reusable palette of glass tints for buildings
    glass_palette = [
        make_material("Glass_Blue", (0.12, 0.22, 0.32), metallic=0.7, roughness=0.15),
        make_material("Glass_Teal", (0.10, 0.28, 0.28), metallic=0.7, roughness=0.15),
        make_material("Glass_Steel", (0.30, 0.32, 0.36), metallic=0.85, roughness=0.2),
        make_material("Glass_Warm", (0.34, 0.30, 0.26), metallic=0.6, roughness=0.25),
    ]
    window = make_material(
        "Windows", (0.9, 0.85, 0.6), emission=((1.0, 0.9, 0.6), 1.2), roughness=0.3
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
            # narrower footprint for taller towers => slender skyline
            fp = BLOCK * FOOTPRINT_MARGIN * (1.0 - 0.25 * (h / MAX_HEIGHT))
            mat = random.choice(glass_palette)
            tower = add_box(f"Bldg_{ix}_{iy}", (x, y, 0.0), (fp / 2, fp / 2, h), mat)

            # a thin glowing "crown" band near the top for window-light flavor
            band = add_box(f"Crown_{ix}_{iy}", (x, y, h - 1.2),
                           (fp / 2 * 1.01, fp / 2 * 1.01, 0.6), window)
            band.parent = tower


# ----------------------------------------------------------------------------
# Lighting, camera, render
# ----------------------------------------------------------------------------
def setup_world():
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.55, 0.70, 0.95, 1.0)  # daytime sky
    bg.inputs["Strength"].default_value = 1.0


def setup_sun():
    light = bpy.data.lights.new("Sun", type="SUN")
    light.energy = 4.0
    light.angle = math.radians(2.0)
    obj = bpy.data.objects.new("Sun", light)
    bpy.context.collection.objects.link(obj)
    obj.rotation_euler = (math.radians(55), math.radians(15), math.radians(40))


def setup_camera():
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 35
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)

    reach = GRID * CELL
    cam.location = (reach * 0.95, -reach * 0.95, reach * 0.7)
    # aim camera at the city core
    direction = Vector((0, 0, MAX_HEIGHT * 0.35)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam


def render(scene):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.filepath = RENDER_PATH
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)


def main():
    clear_scene()
    build_city()
    setup_world()
    setup_sun()
    setup_camera()
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    render(bpy.context.scene)
    print(f"Saved scene  -> {BLEND_PATH}")
    print(f"Saved render -> {RENDER_PATH}")


if __name__ == "__main__":
    main()
