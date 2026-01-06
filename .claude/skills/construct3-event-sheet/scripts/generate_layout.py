#!/usr/bin/env python3
"""
Generate complete C3 Layout JSON (includes object-types + instances + positions)

Usage:
    # Simple platformer layout
    python generate_layout.py --preset platformer --width 640 --height 480

    # Breakout game layout
    python generate_layout.py --preset breakout --width 640 --height 480
"""

import argparse
import json
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGEDATA_SCRIPT = os.path.join(SCRIPT_DIR, "generate_imagedata.py")


def gen_imagedata(args):
    """Generate imageData using generate_imagedata.py"""
    result = subprocess.run(
        ["python3", IMAGEDATA_SCRIPT] + args,
        capture_output=True, text=True
    )
    return result.stdout.strip()


def make_sprite_object(name, width, height, image_index, behaviors=None):
    """Create a Sprite object type definition"""
    obj = {
        "name": name,
        "plugin-id": "Sprite",
        "isGlobal": False,
        "editorNewInstanceIsReplica": True,
        "instanceVariables": [],
        "behaviorTypes": behaviors or [],
        "effectTypes": [],
        "animations": {
            "items": [{
                "frames": [{
                    "width": width,
                    "height": height,
                    "originX": 0.5,
                    "originY": 0.5,
                    "originalSource": "",
                    "exportFormat": "lossless",
                    "exportQuality": 0.8,
                    "fileType": "image/png",
                    "imageDataIndex": image_index,
                    "useCollisionPoly": True,
                    "duration": 1,
                    "tag": ""
                }],
                "name": "Default",
                "isLooping": False,
                "isPingPong": False,
                "repeatCount": 1,
                "repeatTo": 0,
                "speed": 5
            }],
            "subfolders": [],
            "name": "Animations"
        },
        "ui-state": None
    }
    return obj


def make_tiledbg_object(name, width, height, image_index, behaviors=None):
    """Create a TiledBackground object type definition"""
    obj = {
        "name": name,
        "plugin-id": "TiledBg",
        "isGlobal": False,
        "editorNewInstanceIsReplica": True,
        "instanceVariables": [],
        "behaviorTypes": behaviors or [],
        "effectTypes": [],
        "image": {
            "width": width,
            "height": height,
            "originX": 0.5,
            "originY": 0.5,
            "originalSource": "",
            "exportFormat": "lossless",
            "exportQuality": 0.8,
            "fileType": "image/png",
            "imageDataIndex": image_index,
            "useCollisionPoly": True,
            "tag": ""
        },
        "ui-state": None
    }
    return obj


def make_text_object(name):
    """Create a Text object type definition"""
    return {
        "name": name,
        "plugin-id": "Text",
        "isGlobal": False,
        "editorNewInstanceIsReplica": True,
        "instanceVariables": [],
        "behaviorTypes": [],
        "effectTypes": [],
        "ui-state": None
    }


def make_keyboard_object():
    """Create Keyboard object"""
    return {
        "name": "Keyboard",
        "plugin-id": "Keyboard",
        "singleglobal-inst": {"type": "Keyboard", "properties": {}, "tags": ""}
    }


def make_mouse_object():
    """Create Mouse object"""
    return {
        "name": "Mouse",
        "plugin-id": "Mouse",
        "singleglobal-inst": {"type": "Mouse", "properties": {}, "tags": ""}
    }


def make_sprite_instance(obj_type, x, y, width, height, behaviors_props=None):
    """Create a Sprite instance"""
    inst = {
        "type": obj_type,
        "properties": {
            "initially-visible": True,
            "initial-animation": "Default",
            "initial-frame": 0,
            "enable-collisions": True,
            "live-preview": False
        },
        "tags": "",
        "instanceVariables": {},
        "behaviors": behaviors_props or {},
        "showing": True,
        "locked": False,
        "world": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "originX": 0.5,
            "originY": 0.5,
            "color": [1, 1, 1, 1],
            "angle": 0,
            "zElevation": 0
        }
    }
    return inst


def make_tiledbg_instance(obj_type, x, y, width, height, behaviors_props=None):
    """Create a TiledBackground instance"""
    inst = {
        "type": obj_type,
        "properties": {
            "initially-visible": True,
            "origin": "top-left",
            "wrap-horizontal": "repeat",
            "wrap-vertical": "repeat",
            "image-offset-x": 0,
            "image-offset-y": 0,
            "image-scale-x": 1,
            "image-scale-y": 1,
            "image-angle": 0,
            "enable-tile-randomization": False,
            "x-random": 1,
            "y-random": 1,
            "angle-random": 1,
            "blend-margin-x": 0.1,
            "blend-margin-y": 0.1
        },
        "tags": "",
        "instanceVariables": {},
        "behaviors": behaviors_props or {},
        "showing": True,
        "locked": False,
        "world": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "originX": 0,
            "originY": 0,
            "color": [1, 1, 1, 1],
            "angle": 0,
            "zElevation": 0
        }
    }
    return inst


def make_text_instance(obj_type, x, y, width, height, text):
    """Create a Text instance"""
    return {
        "type": obj_type,
        "properties": {
            "text": text,
            "enable-bbcode": False,
            "font": "Arial",
            "size": 16,
            "line-height": 0,
            "bold": False,
            "italic": False,
            "color": [0, 0, 0, 1],
            "horizontal-alignment": "left",
            "vertical-alignment": "top",
            "wrapping": "word",
            "text-direction": "ltr",
            "icon-set": -1,
            "initially-visible": True,
            "origin": "top-left",
            "read-aloud": False
        },
        "tags": "",
        "instanceVariables": {},
        "behaviors": {},
        "showing": True,
        "locked": False,
        "world": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "originX": 0,
            "originY": 0,
            "color": [1, 1, 1, 1],
            "angle": 0,
            "zElevation": 0
        }
    }


def make_layer(name, instances, parallax_x=1, parallax_y=1, is_transparent=True):
    """Create a layer"""
    return {
        "name": name,
        "overriden": 0,
        "subLayers": [],
        "instances": instances,
        "effectTypes": [],
        "isInitiallyVisible": True,
        "isInitiallyInteractive": True,
        "isHTMLElementsLayer": False,
        "color": [1, 1, 1, 1],
        "backgroundColor": [1, 1, 1, 1],
        "isTransparent": is_transparent,
        "parallaxX": parallax_x,
        "parallaxY": parallax_y,
        "scaleRate": 1,
        "forceOwnTexture": False,
        "renderingMode": "3d",
        "drawOrder": "z-order",
        "useRenderCells": False,
        "blendMode": "normal",
        "zElevation": 0,
        "global": False
    }


def make_layout(name, layers, width, height, event_sheet="Event sheet 1"):
    """Create a layout item"""
    return {
        "name": name,
        "layers": layers,
        "scene-graphs-folder-root": {"items": [], "subfolders": [], "name": "INSTANCES"},
        "effectTypes": [],
        "width": width,
        "height": height,
        "unboundedScrolling": False,
        "vpX": 0.5,
        "vpY": 0.5,
        "projection": "perspective",
        "eventSheet": event_sheet
    }


def generate_platformer_layout(width, height):
    """Generate a simple platformer layout"""
    image_data = []
    object_types = []

    # Sky background (TiledBg)
    sky_img = gen_imagedata(["--pattern", "gradient", "--color", "#87CEEB", "--color2", "#1E90FF", "-W", "32", "-H", "32"])
    image_data.append(sky_img)
    object_types.append(make_tiledbg_object("Sky", 32, 32, 0))

    # Ground (TiledBg with Solid)
    ground_img = gen_imagedata(["--kenney", "platform", "--color", "#8B4513", "-W", "32", "-H", "32"])
    image_data.append(ground_img)
    object_types.append(make_tiledbg_object("Ground", 32, 32, 1, [{"behaviorId": "solid", "name": "Solid"}]))

    # Player (Sprite with Platform + ScrollTo)
    player_img = gen_imagedata(["--kenney", "player", "--color", "#4169E1", "-W", "32", "-H", "32"])
    image_data.append(player_img)
    object_types.append(make_sprite_object("Player", 32, 32, 2, [
        {"behaviorId": "Platform", "name": "Platform"},
        {"behaviorId": "scrollto", "name": "ScrollTo"}
    ]))

    # Coin (Sprite)
    coin_img = gen_imagedata(["--kenney", "coin", "--color", "gold", "-W", "24", "-H", "24"])
    image_data.append(coin_img)
    object_types.append(make_sprite_object("Coin", 24, 24, 3))

    # Enemy (Sprite)
    enemy_img = gen_imagedata(["--kenney", "enemy", "--color", "#32CD32", "-W", "32", "-H", "32"])
    image_data.append(enemy_img)
    object_types.append(make_sprite_object("Enemy", 32, 32, 4))

    # ScoreText
    object_types.append(make_text_object("ScoreText"))

    # Keyboard
    object_types.append(make_keyboard_object())

    # Create instances
    bg_instances = [
        make_tiledbg_instance("Sky", 0, 0, width, height)
    ]

    game_instances = [
        # Ground
        make_tiledbg_instance("Ground", 0, height - 64, width, 64, {"Solid": {"properties": {"enabled": True, "use-instance-tags": False, "tags": ""}}}),
        # Platforms
        make_tiledbg_instance("Ground", 100, height - 160, 128, 32, {"Solid": {"properties": {"enabled": True, "use-instance-tags": False, "tags": ""}}}),
        make_tiledbg_instance("Ground", 300, height - 240, 128, 32, {"Solid": {"properties": {"enabled": True, "use-instance-tags": False, "tags": ""}}}),
        make_tiledbg_instance("Ground", 500, height - 180, 96, 32, {"Solid": {"properties": {"enabled": True, "use-instance-tags": False, "tags": ""}}}),
        # Player
        make_sprite_instance("Player", 64, height - 96, 32, 32, {
            "Platform": {"properties": {"max-speed": 300, "acceleration": 1500, "deceleration": 1500, "jump-strength": 600, "gravity": 1500, "max-fall-speed": 1000, "double-jump": False, "jump-sustain": 0, "default-controls": True, "enabled": True}},
            "ScrollTo": {"properties": {"enabled": True}}
        }),
        # Coins
        make_sprite_instance("Coin", 164, height - 200, 24, 24),
        make_sprite_instance("Coin", 364, height - 280, 24, 24),
        make_sprite_instance("Coin", 548, height - 220, 24, 24),
        # Enemy
        make_sprite_instance("Enemy", 450, height - 96, 32, 32),
    ]

    ui_instances = [
        make_text_instance("ScoreText", 16, 16, 200, 32, "Score: 0")
    ]

    layers = [
        make_layer("Background", bg_instances, 0.5, 0.5, False),
        make_layer("Game", game_instances),
        make_layer("UI", ui_instances)
    ]

    layout = make_layout("Level1", layers, width, height)

    return {
        "is-c3-clipboard-data": True,
        "type": "layouts",
        "families": [],
        "object-types": object_types,
        "items": [layout],
        "folders": [],
        "imageData": image_data
    }


def generate_breakout_layout(width, height):
    """Generate a breakout game layout"""
    image_data = []
    object_types = []

    # Paddle (Sprite)
    paddle_img = gen_imagedata(["--color", "green", "-W", "80", "-H", "16", "--shape", "rounded"])
    image_data.append(paddle_img)
    object_types.append(make_sprite_object("Paddle", 80, 16, 0))

    # Ball (Sprite with Bullet)
    ball_img = gen_imagedata(["--shape", "circle", "--color", "white", "-W", "16", "-H", "16"])
    image_data.append(ball_img)
    object_types.append(make_sprite_object("Ball", 16, 16, 1, [{"behaviorId": "Bullet", "name": "Bullet"}]))

    # Brick (Sprite with Solid)
    brick_img = gen_imagedata(["--color", "red", "-W", "48", "-H", "24"])
    image_data.append(brick_img)
    object_types.append(make_sprite_object("Brick", 48, 24, 2, [{"behaviorId": "solid", "name": "Solid"}]))

    # Wall (TiledBg with Solid)
    wall_img = gen_imagedata(["--color", "gray", "-W", "16", "-H", "16", "--flat"])
    image_data.append(wall_img)
    object_types.append(make_tiledbg_object("Wall", 16, 16, 3, [{"behaviorId": "solid", "name": "Solid"}]))

    # ScoreText
    object_types.append(make_text_object("ScoreText"))

    # Mouse
    object_types.append(make_mouse_object())

    # Create instances
    game_instances = []

    # Walls (left, right, top)
    game_instances.append(make_tiledbg_instance("Wall", 0, 0, 16, height, {"Solid": {"properties": {"enabled": True, "use-instance-tags": False, "tags": ""}}}))
    game_instances.append(make_tiledbg_instance("Wall", width - 16, 0, 16, height, {"Solid": {"properties": {"enabled": True, "use-instance-tags": False, "tags": ""}}}))
    game_instances.append(make_tiledbg_instance("Wall", 0, 0, width, 16, {"Solid": {"properties": {"enabled": True, "use-instance-tags": False, "tags": ""}}}))

    # Paddle
    game_instances.append(make_sprite_instance("Paddle", width // 2, height - 40, 80, 16))

    # Ball (set angle in world properties for initial direction)
    ball_inst = make_sprite_instance("Ball", width // 2, height - 80, 16, 16, {
        "Bullet": {"properties": {"speed": 300, "acceleration": 0, "gravity": 0, "bounce-off-solids": False, "set-angle": False, "enabled": True}}
    })
    ball_inst["world"]["angle"] = -60  # Initial angle of motion (up-right)
    game_instances.append(ball_inst)

    # Bricks (grid)
    brick_w = 48
    brick_h = 24
    brick_margin = 4
    start_x = 32
    start_y = 60
    cols = (width - 64) // (brick_w + brick_margin)
    rows = 5
    colors = ["red", "orange", "yellow", "green", "blue"]

    for row in range(rows):
        # Generate different colored bricks for each row
        color = colors[row % len(colors)]
        brick_img = gen_imagedata(["--color", color, "-W", str(brick_w), "-H", str(brick_h)])
        # Note: In a real implementation, we'd need separate object types for different colored bricks
        # For simplicity, all bricks use the same object type (red)

        for col in range(cols):
            x = start_x + col * (brick_w + brick_margin) + brick_w // 2
            y = start_y + row * (brick_h + brick_margin) + brick_h // 2
            game_instances.append(make_sprite_instance("Brick", x, y, brick_w, brick_h))

    ui_instances = [
        make_text_instance("ScoreText", 20, height - 30, 200, 24, "Score: 0")
    ]

    layers = [
        make_layer("Game", game_instances),
        make_layer("UI", ui_instances)
    ]

    layout = make_layout("Game", layers, width, height)

    return {
        "is-c3-clipboard-data": True,
        "type": "layouts",
        "families": [],
        "object-types": object_types,
        "items": [layout],
        "folders": [],
        "imageData": image_data
    }


def main():
    parser = argparse.ArgumentParser(description="Generate C3 Layout JSON")
    parser.add_argument("--preset", "-p", choices=["platformer", "breakout"], default="platformer", help="Layout preset")
    parser.add_argument("--width", "-W", type=int, default=640, help="Layout width")
    parser.add_argument("--height", "-H", type=int, default=480, help="Layout height")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")

    args = parser.parse_args()

    if args.preset == "platformer":
        layout = generate_platformer_layout(args.width, args.height)
    elif args.preset == "breakout":
        layout = generate_breakout_layout(args.width, args.height)
    else:
        layout = generate_platformer_layout(args.width, args.height)

    json_str = json.dumps(layout, ensure_ascii=False)

    if args.output:
        with open(args.output, "w") as f:
            f.write(json_str)
        print(f"✅ Generated: {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
