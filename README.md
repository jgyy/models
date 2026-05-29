# models

3D models built and maintained in Blender.

## Dungeon map

A **grid-based dungeon** game map for Blender 5.x: rooms connected by corridors
on a tile grid, fully enclosed by auto-generated stone walls, lit with a warm sun
and atmospheric torch lights.

### What's in the scene

- **Layout** — built from a 20×15 tile map (4 m tiles) where each cell is either
  floor or void. Several rooms are linked by corridors.
- **Floor** (`DungeonFloor`) — one tile per walkable cell, textured with the
  PolyHaven `brick_floor_003` PBR material.
- **Walls** (`DungeonWalls`) — generated on every edge where a floor tile borders
  void, so the walkable space is always fully enclosed (ready for collision /
  navmesh baking). Textured with PolyHaven `brick_wall_006`.
- **Lighting** — a warm directional sun, a dark ambient world, and three point
  "torch" lights placed inside rooms for atmosphere.
- **Camera** — an overhead 3/4 view framing the whole dungeon.

### Files

| File | Purpose |
|------|---------|
| `dungeon.blend` | The editable scene — open in Blender to view or edit by hand (textures packed) |

### Working with the scene

Open `dungeon.blend` in Blender and edit directly. Objects are organized by name:

| Object | Contents |
|--------|----------|
| `DungeonFloor` | floor tiles (one quad per walkable cell) |
| `DungeonWalls` | enclosing walls (box per floor↔void edge) |
| `Sun` | warm directional key light |
| `Torch0` / `Torch1` / `Torch2` | point lights inside rooms |
| `Camera` | overhead 3/4 framing camera |

The layout is defined by a 2D ASCII tile map (`.` = floor, `#` = void) in the
generation script. To reshape the dungeon, edit the map and regenerate the floor
and wall meshes.
