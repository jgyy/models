# models

Procedural 3D models generated with Blender.

## City landscape

A procedural **modern-downtown** city generator for Blender 5.x. It builds a grid
of glass skyscrapers with a distance-based height falloff (tall core, shorter
edges), green park lots, daytime lighting, and an aerial camera.

![City preview](city_preview.png)

### Usage

```bash
blender --background --python city_generator.py
```

Outputs (next to the script):

| File | Purpose |
|------|---------|
| `city_generator.py` | The procedural source — edit & re-run to regenerate |
| `city.blend` | Editable scene (open in Blender GUI) |
| `city_preview.png` | 1280×720 preview render |

If `--render night` is passed, a `city_night.png` is produced instead, and
exports land in `exports/city.glb` / `exports/city.fbx` when `--export` is used
(see options below).

### Options (command-line flags after `--`)

```bash
# night scene with lit windows
blender --background --python city_generator.py -- --render night

# render an orbiting fly-through animation (frames -> renders/anim/)
blender --background --python city_generator.py -- --animate

# export the scene to glTF (.glb) and FBX for game engines
blender --background --python city_generator.py -- --export

# combine flags
blender --background --python city_generator.py -- --render night --export
```

### Customizing

All tunable parameters live in the `CONFIG` block at the top of
`city_generator.py`:

- **`SEED`** — change for a completely different city layout
- **`GRID`** — blocks per side (bigger/smaller city)
- **`MAX_HEIGHT`** — height of the city core
- **`EMPTY_LOT_CHANCE`** — frequency of parks/empty lots
- **`BLOCK` / `ROAD`** — block footprint vs. street width

Re-run the script, or open `city.blend` directly in Blender to edit by hand.
