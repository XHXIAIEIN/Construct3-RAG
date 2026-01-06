#!/usr/bin/env python3
"""
Generate valid C3 imageData (base64 PNG) for sprites.

Usage:
    # Basic shapes
    python generate_imagedata.py --color red --width 32 --height 32
    python generate_imagedata.py --color blue --width 16 --height 16 --shape circle

    # With border
    python generate_imagedata.py --color yellow --width 32 --height 32 --border black --border-width 2

    # Patterns
    python generate_imagedata.py --width 32 --height 32 --pattern checkerboard --color white --color2 gray
    python generate_imagedata.py --width 32 --height 32 --pattern stripes --color red --color2 white
    python generate_imagedata.py --width 32 --height 32 --pattern gradient --color blue --color2 cyan

    # Icons
    python generate_imagedata.py --width 32 --height 32 --icon arrow --color white
    python generate_imagedata.py --width 32 --height 32 --icon star --color yellow
    python generate_imagedata.py --width 32 --height 32 --icon heart --color red

    # Convert existing image
    python generate_imagedata.py --file sprite.png
"""

import argparse
import base64
import io
import sys
import math

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

# Predefined colors
COLORS = {
    "red": (255, 0, 0, 255),
    "green": (0, 255, 0, 255),
    "blue": (0, 0, 255, 255),
    "yellow": (255, 255, 0, 255),
    "cyan": (0, 255, 255, 255),
    "magenta": (255, 0, 255, 255),
    "white": (255, 255, 255, 255),
    "black": (0, 0, 0, 255),
    "gray": (128, 128, 128, 255),
    "orange": (255, 165, 0, 255),
    "purple": (128, 0, 128, 255),
    "brown": (139, 69, 19, 255),
    "pink": (255, 192, 203, 255),
    "lime": (50, 205, 50, 255),
    "navy": (0, 0, 128, 255),
    "teal": (0, 128, 128, 255),
    "gold": (255, 215, 0, 255),
    "silver": (192, 192, 192, 255),
    "transparent": (0, 0, 0, 0),
}


def parse_color(color_str: str) -> tuple:
    """Parse color string to RGBA tuple"""
    if color_str.lower() in COLORS:
        return COLORS[color_str.lower()]

    if color_str.startswith("#"):
        hex_color = color_str[1:]
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b, 255)
        elif len(hex_color) == 8:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            a = int(hex_color[6:8], 16)
            return (r, g, b, a)

    raise ValueError(f"Invalid color: {color_str}. Use color name or #RRGGBB format.")


def generate_rectangle(width: int, height: int, color: tuple) -> Image.Image:
    """Generate a solid colored rectangle"""
    img = Image.new("RGBA", (width, height), color)
    return img


def generate_circle(width: int, height: int, color: tuple) -> Image.Image:
    """Generate a circle (ellipse if width != height)"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, width - 1, height - 1], fill=color)
    return img


def generate_rounded_rect(width: int, height: int, color: tuple, radius: int = 4) -> Image.Image:
    """Generate a rounded rectangle"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=color)
    return img


def generate_triangle(width: int, height: int, color: tuple, direction: str = "up") -> Image.Image:
    """Generate a triangle"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if direction == "up":
        points = [(width // 2, 0), (0, height - 1), (width - 1, height - 1)]
    elif direction == "down":
        points = [(0, 0), (width - 1, 0), (width // 2, height - 1)]
    elif direction == "left":
        points = [(width - 1, 0), (0, height // 2), (width - 1, height - 1)]
    else:  # right
        points = [(0, 0), (width - 1, height // 2), (0, height - 1)]

    draw.polygon(points, fill=color)
    return img


def generate_diamond(width: int, height: int, color: tuple) -> Image.Image:
    """Generate a diamond shape"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    points = [(width // 2, 0), (width - 1, height // 2), (width // 2, height - 1), (0, height // 2)]
    draw.polygon(points, fill=color)
    return img


def generate_ring(width: int, height: int, color: tuple, thickness: int = 3) -> Image.Image:
    """Generate a ring (hollow circle)"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, width - 1, height - 1], fill=color)
    inner = thickness
    draw.ellipse([inner, inner, width - 1 - inner, height - 1 - inner], fill=(0, 0, 0, 0))
    return img


def add_border(img: Image.Image, border_color: tuple, border_width: int) -> Image.Image:
    """Add border to existing image"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for i in range(border_width):
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=border_color)
    return img


def generate_checkerboard(width: int, height: int, color1: tuple, color2: tuple, cell_size: int = 8) -> Image.Image:
    """Generate checkerboard pattern"""
    img = Image.new("RGBA", (width, height), color1)
    draw = ImageDraw.Draw(img)
    for y in range(0, height, cell_size):
        for x in range(0, width, cell_size):
            if ((x // cell_size) + (y // cell_size)) % 2 == 1:
                draw.rectangle([x, y, x + cell_size - 1, y + cell_size - 1], fill=color2)
    return img


def generate_stripes(width: int, height: int, color1: tuple, color2: tuple, stripe_width: int = 4, horizontal: bool = False) -> Image.Image:
    """Generate stripe pattern"""
    img = Image.new("RGBA", (width, height), color1)
    draw = ImageDraw.Draw(img)
    if horizontal:
        for y in range(0, height, stripe_width * 2):
            draw.rectangle([0, y, width - 1, y + stripe_width - 1], fill=color2)
    else:
        for x in range(0, width, stripe_width * 2):
            draw.rectangle([x, 0, x + stripe_width - 1, height - 1], fill=color2)
    return img


def generate_gradient(width: int, height: int, color1: tuple, color2: tuple, horizontal: bool = False) -> Image.Image:
    """Generate gradient"""
    img = Image.new("RGBA", (width, height))
    for i in range(width if horizontal else height):
        ratio = i / (width if horizontal else height)
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        a = int(color1[3] + (color2[3] - color1[3]) * ratio)
        if horizontal:
            for y in range(height):
                img.putpixel((i, y), (r, g, b, a))
        else:
            for x in range(width):
                img.putpixel((x, i), (r, g, b, a))
    return img


def generate_dots(width: int, height: int, bg_color: tuple, dot_color: tuple, dot_size: int = 2, spacing: int = 6) -> Image.Image:
    """Generate dot pattern"""
    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    for y in range(spacing // 2, height, spacing):
        for x in range(spacing // 2, width, spacing):
            draw.ellipse([x - dot_size, y - dot_size, x + dot_size, y + dot_size], fill=dot_color)
    return img


def generate_brick(width: int, height: int, brick_color: tuple, mortar_color: tuple) -> Image.Image:
    """Generate brick pattern"""
    img = Image.new("RGBA", (width, height), mortar_color)
    draw = ImageDraw.Draw(img)
    brick_h = 8
    brick_w = 16
    mortar = 1

    for row, y in enumerate(range(0, height, brick_h)):
        offset = (brick_w // 2) if row % 2 == 1 else 0
        for x in range(-brick_w, width + brick_w, brick_w):
            bx = x + offset
            draw.rectangle([bx + mortar, y + mortar, bx + brick_w - mortar - 1, y + brick_h - mortar - 1], fill=brick_color)
    return img


def generate_icon_arrow(width: int, height: int, color: tuple, direction: str = "right") -> Image.Image:
    """Generate arrow icon"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = width // 2, height // 2
    size = min(width, height) // 2 - 2

    if direction == "right":
        points = [(cx - size // 2, cy - size // 2), (cx + size // 2, cy), (cx - size // 2, cy + size // 2)]
    elif direction == "left":
        points = [(cx + size // 2, cy - size // 2), (cx - size // 2, cy), (cx + size // 2, cy + size // 2)]
    elif direction == "up":
        points = [(cx - size // 2, cy + size // 2), (cx, cy - size // 2), (cx + size // 2, cy + size // 2)]
    else:  # down
        points = [(cx - size // 2, cy - size // 2), (cx, cy + size // 2), (cx + size // 2, cy - size // 2)]

    draw.polygon(points, fill=color)
    return img


def generate_icon_star(width: int, height: int, color: tuple, points: int = 5) -> Image.Image:
    """Generate star icon"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = width // 2, height // 2
    outer_r = min(width, height) // 2 - 1
    inner_r = outer_r // 2

    star_points = []
    for i in range(points * 2):
        angle = math.pi / 2 + i * math.pi / points
        r = outer_r if i % 2 == 0 else inner_r
        x = cx + r * math.cos(angle)
        y = cy - r * math.sin(angle)
        star_points.append((x, y))

    draw.polygon(star_points, fill=color)
    return img


def generate_icon_heart(width: int, height: int, color: tuple) -> Image.Image:
    """Generate heart icon"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw two circles for top of heart
    r = width // 4
    draw.ellipse([width // 4 - r, height // 4 - r, width // 4 + r, height // 4 + r], fill=color)
    draw.ellipse([3 * width // 4 - r, height // 4 - r, 3 * width // 4 + r, height // 4 + r], fill=color)

    # Draw triangle for bottom
    points = [(1, height // 3), (width // 2, height - 2), (width - 2, height // 3)]
    draw.polygon(points, fill=color)

    return img


def generate_icon_cross(width: int, height: int, color: tuple, thickness: int = None) -> Image.Image:
    """Generate cross/plus icon"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if thickness is None:
        thickness = max(2, min(width, height) // 4)

    cx, cy = width // 2, height // 2

    # Horizontal bar
    draw.rectangle([2, cy - thickness // 2, width - 3, cy + thickness // 2], fill=color)
    # Vertical bar
    draw.rectangle([cx - thickness // 2, 2, cx + thickness // 2, height - 3], fill=color)

    return img


def generate_icon_x(width: int, height: int, color: tuple, thickness: int = 3) -> Image.Image:
    """Generate X icon"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw two thick diagonal lines
    for i in range(-thickness // 2, thickness // 2 + 1):
        draw.line([(2 + i, 2), (width - 3 + i, height - 3)], fill=color, width=1)
        draw.line([(width - 3 + i, 2), (2 + i, height - 3)], fill=color, width=1)

    return img


# ============== Kenney Style ==============

def darken(color: tuple, factor: float = 0.7) -> tuple:
    """Darken a color"""
    return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor), color[3])


def lighten(color: tuple, factor: float = 0.3) -> tuple:
    """Lighten a color (add white)"""
    return (
        min(255, int(color[0] + (255 - color[0]) * factor)),
        min(255, int(color[1] + (255 - color[1]) * factor)),
        min(255, int(color[2] + (255 - color[2]) * factor)),
        color[3]
    )


def kenney_box(width: int, height: int, color: tuple, outline_width: int = 2) -> Image.Image:
    """Kenney-style box with rounded corners, outline and highlight"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = min(width, height) // 4
    outline = darken(color, 0.5)
    highlight = lighten(color, 0.4)
    shadow = darken(color, 0.8)

    # Shadow/outline layer
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=outline)

    # Main color
    m = outline_width
    draw.rounded_rectangle([m, m, width - 1 - m, height - 1 - m], radius=radius - m, fill=color)

    # Bottom shadow
    draw.rounded_rectangle([m, height // 2, width - 1 - m, height - 1 - m], radius=radius - m, fill=shadow)

    # Top highlight
    draw.rounded_rectangle([m, m, width - 1 - m, height // 3], radius=radius - m, fill=highlight)

    return img


def kenney_circle(width: int, height: int, color: tuple, outline_width: int = 2) -> Image.Image:
    """Kenney-style circle with outline and highlight"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    outline = darken(color, 0.5)
    highlight = lighten(color, 0.4)
    shadow = darken(color, 0.8)

    # Outline
    draw.ellipse([0, 0, width - 1, height - 1], fill=outline)

    # Main
    m = outline_width
    draw.ellipse([m, m, width - 1 - m, height - 1 - m], fill=color)

    # Shadow (bottom half)
    draw.chord([m, m, width - 1 - m, height - 1 - m], start=0, end=180, fill=shadow)

    # Highlight (top portion)
    hl_size = min(width, height) // 3
    draw.ellipse([width // 4, height // 6, width // 4 + hl_size, height // 6 + hl_size // 2], fill=highlight)

    return img


def kenney_player(width: int, height: int, color: tuple) -> Image.Image:
    """Kenney-style player character (simple humanoid)"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    outline = darken(color, 0.4)
    highlight = lighten(color, 0.3)
    eye_color = (255, 255, 255, 255)
    pupil = (40, 40, 40, 255)

    cx, cy = width // 2, height // 2

    # Body (rounded rect)
    body_w, body_h = width * 2 // 3, height // 2
    body_x = cx - body_w // 2
    body_y = cy

    draw.rounded_rectangle([body_x - 1, body_y - 1, body_x + body_w, body_y + body_h],
                          radius=body_w // 4, fill=outline)
    draw.rounded_rectangle([body_x + 1, body_y + 1, body_x + body_w - 2, body_y + body_h - 2],
                          radius=body_w // 4, fill=color)

    # Head (circle)
    head_r = width // 3
    head_x, head_y = cx, cy - head_r // 3

    draw.ellipse([head_x - head_r - 1, head_y - head_r - 1, head_x + head_r, head_y + head_r], fill=outline)
    draw.ellipse([head_x - head_r + 1, head_y - head_r + 1, head_x + head_r - 2, head_y + head_r - 2], fill=color)

    # Highlight on head
    draw.ellipse([head_x - head_r // 2, head_y - head_r + 2, head_x + head_r // 3, head_y - head_r // 3], fill=highlight)

    # Eyes
    eye_w = head_r // 2
    eye_h = head_r // 2
    left_eye_x = head_x - head_r // 2
    right_eye_x = head_x + head_r // 6
    eye_y = head_y - head_r // 4

    draw.ellipse([left_eye_x, eye_y, left_eye_x + eye_w, eye_y + eye_h], fill=eye_color)
    draw.ellipse([right_eye_x, eye_y, right_eye_x + eye_w, eye_y + eye_h], fill=eye_color)

    # Pupils
    p_size = eye_w // 2
    draw.ellipse([left_eye_x + eye_w // 3, eye_y + eye_h // 4, left_eye_x + eye_w // 3 + p_size, eye_y + eye_h // 4 + p_size], fill=pupil)
    draw.ellipse([right_eye_x + eye_w // 3, eye_y + eye_h // 4, right_eye_x + eye_w // 3 + p_size, eye_y + eye_h // 4 + p_size], fill=pupil)

    return img


def kenney_enemy(width: int, height: int, color: tuple) -> Image.Image:
    """Kenney-style enemy (angry slime/blob)"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    outline = darken(color, 0.4)
    highlight = lighten(color, 0.3)
    eye_color = (255, 255, 255, 255)
    pupil = (40, 40, 40, 255)

    cx, cy = width // 2, height // 2

    # Body (ellipse, wider than tall)
    body_w, body_h = width - 4, height * 2 // 3
    body_y = height - body_h - 1

    draw.ellipse([1, body_y, width - 2, height - 2], fill=outline)
    draw.ellipse([3, body_y + 2, width - 4, height - 4], fill=color)

    # Highlight
    draw.ellipse([width // 4, body_y + 4, width * 3 // 4, body_y + body_h // 3], fill=highlight)

    # Angry eyes
    eye_w = width // 4
    eye_h = height // 5
    left_x = cx - eye_w - 2
    right_x = cx + 2
    eye_y = body_y + body_h // 3

    # Eye whites
    draw.ellipse([left_x, eye_y, left_x + eye_w, eye_y + eye_h], fill=eye_color)
    draw.ellipse([right_x, eye_y, right_x + eye_w, eye_y + eye_h], fill=eye_color)

    # Angry eyebrows (triangles)
    draw.polygon([(left_x, eye_y - 2), (left_x + eye_w, eye_y + 2), (left_x + eye_w, eye_y - 2)], fill=outline)
    draw.polygon([(right_x, eye_y + 2), (right_x + eye_w, eye_y - 2), (right_x, eye_y - 2)], fill=outline)

    # Pupils
    p_size = eye_w // 2
    draw.ellipse([left_x + eye_w // 4, eye_y + eye_h // 4, left_x + eye_w // 4 + p_size, eye_y + eye_h // 4 + p_size], fill=pupil)
    draw.ellipse([right_x + eye_w // 4, eye_y + eye_h // 4, right_x + eye_w // 4 + p_size, eye_y + eye_h // 4 + p_size], fill=pupil)

    return img


def kenney_coin(width: int, height: int, color: tuple) -> Image.Image:
    """Kenney-style coin with shine"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    outline = darken(color, 0.5)
    highlight = lighten(color, 0.5)
    inner = darken(color, 0.85)

    # Outer circle (outline)
    draw.ellipse([0, 0, width - 1, height - 1], fill=outline)

    # Main coin
    m = 2
    draw.ellipse([m, m, width - 1 - m, height - 1 - m], fill=color)

    # Inner circle
    m2 = width // 6
    draw.ellipse([m2, m2, width - 1 - m2, height - 1 - m2], fill=inner)

    # Shine highlight
    shine_w = width // 3
    shine_h = height // 4
    draw.ellipse([width // 5, height // 6, width // 5 + shine_w, height // 6 + shine_h], fill=highlight)

    return img


def kenney_platform(width: int, height: int, color: tuple) -> Image.Image:
    """Kenney-style platform tile"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    outline = darken(color, 0.4)
    highlight = lighten(color, 0.3)
    shadow = darken(color, 0.75)

    # Base with outline
    draw.rectangle([0, 0, width - 1, height - 1], fill=outline)

    # Main fill
    m = 2
    draw.rectangle([m, m, width - 1 - m, height - 1 - m], fill=color)

    # Top highlight stripe
    draw.rectangle([m, m, width - 1 - m, height // 4], fill=highlight)

    # Bottom shadow stripe
    draw.rectangle([m, height * 3 // 4, width - 1 - m, height - 1 - m], fill=shadow)

    # Grass/detail on top (optional green tufts)
    grass = (100, 200, 80, 255)
    grass_dark = darken(grass, 0.7)
    for x in range(4, width - 4, 8):
        # Grass blade
        draw.polygon([(x, m), (x + 3, -4), (x + 6, m)], fill=grass)
        draw.line([(x + 3, -4), (x + 3, m)], fill=grass_dark, width=1)

    return img


def kenney_spike(width: int, height: int, color: tuple) -> Image.Image:
    """Kenney-style spike/hazard"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    outline = darken(color, 0.4)
    highlight = lighten(color, 0.3)

    # Triangle spike
    points = [(width // 2, 2), (2, height - 2), (width - 3, height - 2)]

    # Outline
    draw.polygon(points, fill=outline)

    # Inner fill
    inner_points = [(width // 2, 6), (6, height - 4), (width - 7, height - 4)]
    draw.polygon(inner_points, fill=color)

    # Highlight on left edge
    hl_points = [(width // 2, 6), (6, height - 4), (width // 4, height // 2)]
    draw.polygon(hl_points, fill=highlight)

    return img


# ============== Animations ==============

def anim_coin_spin(width: int, height: int, color: tuple, frames: int = 4) -> list:
    """Generate coin spin animation frames"""
    images = []
    outline = darken(color, 0.5)
    highlight = lighten(color, 0.5)
    inner = darken(color, 0.85)

    for i in range(frames):
        # Calculate width scaling for spin effect
        scale = abs(math.cos(i * math.pi / frames))
        scaled_w = max(4, int(width * scale))
        offset_x = (width - scaled_w) // 2

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Outer ellipse
        draw.ellipse([offset_x, 0, offset_x + scaled_w - 1, height - 1], fill=outline)

        if scaled_w > 6:
            m = 2
            draw.ellipse([offset_x + m, m, offset_x + scaled_w - 1 - m, height - 1 - m], fill=color)

            # Inner circle (if wide enough)
            if scaled_w > 12:
                m2 = scaled_w // 6
                draw.ellipse([offset_x + m2, height // 6, offset_x + scaled_w - 1 - m2, height - 1 - height // 6], fill=inner)

            # Highlight
            if scaled_w > 8:
                hl_w = scaled_w // 3
                draw.ellipse([offset_x + scaled_w // 5, height // 6, offset_x + scaled_w // 5 + hl_w, height // 3], fill=highlight)

        images.append(img)

    return images


def anim_player_walk(width: int, height: int, color: tuple, frames: int = 4) -> list:
    """Generate simple walk animation frames"""
    images = []
    outline = darken(color, 0.4)
    highlight = lighten(color, 0.3)
    eye_color = (255, 255, 255, 255)
    pupil = (40, 40, 40, 255)

    for i in range(frames):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx, cy = width // 2, height // 2

        # Body bounce
        bounce = int(2 * math.sin(i * math.pi * 2 / frames))

        # Body
        body_w, body_h = width * 2 // 3, height // 2
        body_x = cx - body_w // 2
        body_y = cy + bounce

        draw.rounded_rectangle([body_x - 1, body_y - 1, body_x + body_w, body_y + body_h],
                              radius=body_w // 4, fill=outline)
        draw.rounded_rectangle([body_x + 1, body_y + 1, body_x + body_w - 2, body_y + body_h - 2],
                              radius=body_w // 4, fill=color)

        # Legs (alternating)
        leg_w = body_w // 4
        leg_h = height // 6
        leg_offset = int(4 * math.sin(i * math.pi * 2 / frames))

        # Left leg
        left_leg_x = body_x + leg_w // 2 - leg_offset
        draw.rounded_rectangle([left_leg_x, body_y + body_h - 2, left_leg_x + leg_w, body_y + body_h + leg_h],
                              radius=2, fill=outline)

        # Right leg
        right_leg_x = body_x + body_w - leg_w - leg_w // 2 + leg_offset
        draw.rounded_rectangle([right_leg_x, body_y + body_h - 2, right_leg_x + leg_w, body_y + body_h + leg_h],
                              radius=2, fill=outline)

        # Head
        head_r = width // 3
        head_x, head_y = cx, cy - head_r // 3 + bounce

        draw.ellipse([head_x - head_r - 1, head_y - head_r - 1, head_x + head_r, head_y + head_r], fill=outline)
        draw.ellipse([head_x - head_r + 1, head_y - head_r + 1, head_x + head_r - 2, head_y + head_r - 2], fill=color)

        # Highlight
        draw.ellipse([head_x - head_r // 2, head_y - head_r + 2, head_x + head_r // 3, head_y - head_r // 3], fill=highlight)

        # Eyes
        eye_w = head_r // 2
        eye_h = head_r // 2
        left_eye_x = head_x - head_r // 2
        right_eye_x = head_x + head_r // 6
        eye_y = head_y - head_r // 4

        draw.ellipse([left_eye_x, eye_y, left_eye_x + eye_w, eye_y + eye_h], fill=eye_color)
        draw.ellipse([right_eye_x, eye_y, right_eye_x + eye_w, eye_y + eye_h], fill=eye_color)

        # Pupils
        p_size = eye_w // 2
        draw.ellipse([left_eye_x + eye_w // 3, eye_y + eye_h // 4, left_eye_x + eye_w // 3 + p_size, eye_y + eye_h // 4 + p_size], fill=pupil)
        draw.ellipse([right_eye_x + eye_w // 3, eye_y + eye_h // 4, right_eye_x + eye_w // 3 + p_size, eye_y + eye_h // 4 + p_size], fill=pupil)

        images.append(img)

    return images


def anim_enemy_idle(width: int, height: int, color: tuple, frames: int = 4) -> list:
    """Generate enemy idle/bounce animation"""
    images = []
    outline = darken(color, 0.4)
    highlight = lighten(color, 0.3)
    eye_color = (255, 255, 255, 255)
    pupil = (40, 40, 40, 255)

    for i in range(frames):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Squash and stretch
        stretch = 1 + 0.15 * math.sin(i * math.pi * 2 / frames)
        squash = 1 / stretch

        body_w = int((width - 4) * squash)
        body_h = int((height * 2 // 3) * stretch)
        body_x = (width - body_w) // 2
        body_y = height - body_h - 1

        draw.ellipse([body_x, body_y, body_x + body_w, height - 2], fill=outline)
        draw.ellipse([body_x + 2, body_y + 2, body_x + body_w - 2, height - 4], fill=color)

        # Highlight
        draw.ellipse([width // 4, body_y + 4, width * 3 // 4, body_y + body_h // 3], fill=highlight)

        # Eyes
        eye_w = width // 4
        eye_h = height // 5
        cx = width // 2
        left_x = cx - eye_w - 2
        right_x = cx + 2
        eye_y = body_y + body_h // 3

        draw.ellipse([left_x, eye_y, left_x + eye_w, eye_y + eye_h], fill=eye_color)
        draw.ellipse([right_x, eye_y, right_x + eye_w, eye_y + eye_h], fill=eye_color)

        # Angry eyebrows
        draw.polygon([(left_x, eye_y - 2), (left_x + eye_w, eye_y + 2), (left_x + eye_w, eye_y - 2)], fill=outline)
        draw.polygon([(right_x, eye_y + 2), (right_x + eye_w, eye_y - 2), (right_x, eye_y - 2)], fill=outline)

        # Pupils
        p_size = eye_w // 2
        draw.ellipse([left_x + eye_w // 4, eye_y + eye_h // 4, left_x + eye_w // 4 + p_size, eye_y + eye_h // 4 + p_size], fill=pupil)
        draw.ellipse([right_x + eye_w // 4, eye_y + eye_h // 4, right_x + eye_w // 4 + p_size, eye_y + eye_h // 4 + p_size], fill=pupil)

        images.append(img)

    return images


def anim_explosion(width: int, height: int, color: tuple, frames: int = 6) -> list:
    """Generate explosion animation"""
    images = []
    colors = [
        lighten(color, 0.6),  # Bright center
        color,
        darken(color, 0.7),
        darken(color, 0.5),
        (100, 100, 100, 200),  # Smoke
        (80, 80, 80, 100),
    ]

    for i in range(frames):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        progress = i / (frames - 1)
        cx, cy = width // 2, height // 2

        # Multiple circles expanding
        for j in range(3):
            radius = int((min(width, height) // 2) * (progress + j * 0.2))
            alpha = int(255 * (1 - progress) * (1 - j * 0.3))
            if alpha > 0 and radius > 0:
                c = colors[min(i, len(colors) - 1)]
                c_alpha = (c[0], c[1], c[2], min(alpha, c[3]))
                draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=c_alpha)

        images.append(img)

    return images


def anim_blink(width: int, height: int, color: tuple, frames: int = 2) -> list:
    """Generate simple blink/flash animation"""
    images = []
    for i in range(frames):
        if i % 2 == 0:
            img = kenney_box(width, height, color)
        else:
            img = kenney_box(width, height, lighten(color, 0.4))
        images.append(img)
    return images


def image_to_base64(img: Image.Image) -> str:
    """Convert PIL Image to base64 data URI"""
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    base64_data = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{base64_data}"


def load_image_file(filepath: str) -> Image.Image:
    """Load image from file"""
    img = Image.open(filepath)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img


def main():
    parser = argparse.ArgumentParser(description="Generate C3-compatible imageData (base64 PNG)")

    # Input
    parser.add_argument("--file", "-f", help="Input image file to convert")

    # Size
    parser.add_argument("--width", "-W", type=int, default=32, help="Width in pixels")
    parser.add_argument("--height", "-H", type=int, default=32, help="Height in pixels")

    # Colors
    parser.add_argument("--color", "-c", default="white", help="Primary color (name or #RRGGBB)")
    parser.add_argument("--color2", "-c2", help="Secondary color for patterns")

    # Shape
    parser.add_argument("--shape", "-s",
        choices=["rect", "circle", "rounded", "triangle", "diamond", "ring"],
        default="rect", help="Shape type")
    parser.add_argument("--radius", "-r", type=int, default=4, help="Corner radius for rounded rect")
    parser.add_argument("--direction", "-d", default="up", help="Direction for triangle/arrow (up/down/left/right)")
    parser.add_argument("--thickness", type=int, default=3, help="Thickness for ring/cross")

    # Style
    parser.add_argument("--flat", action="store_true", help="Use flat style (no outline/highlight)")

    # Border
    parser.add_argument("--border", "-b", help="Border color")
    parser.add_argument("--border-width", "-bw", type=int, default=1, help="Border width")

    # Patterns
    parser.add_argument("--pattern", "-p",
        choices=["checkerboard", "stripes", "stripes-h", "gradient", "gradient-h", "dots", "brick"],
        help="Pattern type")
    parser.add_argument("--cell-size", type=int, default=8, help="Cell size for checkerboard")
    parser.add_argument("--stripe-width", type=int, default=4, help="Stripe width")

    # Icons
    parser.add_argument("--icon", "-i",
        choices=["arrow", "arrow-up", "arrow-down", "arrow-left", "star", "heart", "cross", "x"],
        help="Icon type")

    # Kenney style
    parser.add_argument("--kenney", "-k",
        choices=["box", "circle", "player", "enemy", "coin", "platform", "spike"],
        help="Kenney-style preset")

    # Animation
    parser.add_argument("--anim", "-a",
        choices=["coin-spin", "player-walk", "enemy-idle", "explosion", "blink"],
        help="Animation preset")
    parser.add_argument("--frames", type=int, default=4, help="Number of animation frames")

    # Output
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON array element")
    parser.add_argument("--c3-object", action="store_true", help="Output complete C3 object-types JSON")

    args = parser.parse_args()

    # Handle animation
    if args.anim:
        color = parse_color(args.color)
        if args.anim == "coin-spin":
            images = anim_coin_spin(args.width, args.height, color, args.frames)
        elif args.anim == "player-walk":
            images = anim_player_walk(args.width, args.height, color, args.frames)
        elif args.anim == "enemy-idle":
            images = anim_enemy_idle(args.width, args.height, color, args.frames)
        elif args.anim == "explosion":
            images = anim_explosion(args.width, args.height, color, args.frames)
        elif args.anim == "blink":
            images = anim_blink(args.width, args.height, color, args.frames)
        else:
            images = [kenney_box(args.width, args.height, color)]

        # Convert all frames to base64
        image_data_list = [image_to_base64(img) for img in images]

        if args.c3_object:
            # Output complete C3 object-types JSON with animation
            obj_json = {
                "is-c3-clipboard-data": True,
                "type": "object-types",
                "families": [],
                "items": [{
                    "name": args.anim.replace("-", "").title(),
                    "plugin-id": "Sprite",
                    "isGlobal": False,
                    "editorNewInstanceIsReplica": True,
                    "instanceVariables": [],
                    "behaviorTypes": [],
                    "effectTypes": [],
                    "animations": {
                        "items": [{
                            "frames": [
                                {
                                    "width": args.width,
                                    "height": args.height,
                                    "originX": 0.5,
                                    "originY": 0.5,
                                    "originalSource": "",
                                    "exportFormat": "lossless",
                                    "exportQuality": 0.8,
                                    "fileType": "image/png",
                                    "imageDataIndex": i,
                                    "useCollisionPoly": True,
                                    "duration": 1,
                                    "tag": ""
                                }
                                for i in range(len(images))
                            ],
                            "name": "Default",
                            "isLooping": True,
                            "isPingPong": False,
                            "repeatCount": 1,
                            "repeatTo": 0,
                            "speed": 8
                        }],
                        "subfolders": [],
                        "name": "Animations"
                    }
                }],
                "folders": [],
                "imageData": image_data_list
            }
            import json
            print(json.dumps(obj_json, ensure_ascii=False))
        else:
            # Output just the imageData array
            print("[")
            for i, data in enumerate(image_data_list):
                comma = "," if i < len(image_data_list) - 1 else ""
                print(f'  "{data}"{comma}')
            print("]")

        print(f"\n// Animation: {args.anim}, {len(images)} frames, {args.width}x{args.height}", file=sys.stderr)
        sys.exit(0)

    # Generate single image
    if args.file:
        img = load_image_file(args.file)
    elif args.kenney:
        color = parse_color(args.color)
        if args.kenney == "box":
            img = kenney_box(args.width, args.height, color)
        elif args.kenney == "circle":
            img = kenney_circle(args.width, args.height, color)
        elif args.kenney == "player":
            img = kenney_player(args.width, args.height, color)
        elif args.kenney == "enemy":
            img = kenney_enemy(args.width, args.height, color)
        elif args.kenney == "coin":
            img = kenney_coin(args.width, args.height, color)
        elif args.kenney == "platform":
            img = kenney_platform(args.width, args.height, color)
        elif args.kenney == "spike":
            img = kenney_spike(args.width, args.height, color)
        else:
            img = kenney_box(args.width, args.height, color)
    elif args.icon:
        color = parse_color(args.color)
        if args.icon.startswith("arrow"):
            direction = args.icon.split("-")[1] if "-" in args.icon else "right"
            img = generate_icon_arrow(args.width, args.height, color, direction)
        elif args.icon == "star":
            img = generate_icon_star(args.width, args.height, color)
        elif args.icon == "heart":
            img = generate_icon_heart(args.width, args.height, color)
        elif args.icon == "cross":
            img = generate_icon_cross(args.width, args.height, color, args.thickness)
        elif args.icon == "x":
            img = generate_icon_x(args.width, args.height, color, args.thickness)
        else:
            img = generate_rectangle(args.width, args.height, color)
    elif args.pattern:
        color1 = parse_color(args.color)
        color2 = parse_color(args.color2) if args.color2 else parse_color("gray")
        if args.pattern == "checkerboard":
            img = generate_checkerboard(args.width, args.height, color1, color2, args.cell_size)
        elif args.pattern == "stripes":
            img = generate_stripes(args.width, args.height, color1, color2, args.stripe_width, horizontal=False)
        elif args.pattern == "stripes-h":
            img = generate_stripes(args.width, args.height, color1, color2, args.stripe_width, horizontal=True)
        elif args.pattern == "gradient":
            img = generate_gradient(args.width, args.height, color1, color2, horizontal=False)
        elif args.pattern == "gradient-h":
            img = generate_gradient(args.width, args.height, color1, color2, horizontal=True)
        elif args.pattern == "dots":
            img = generate_dots(args.width, args.height, color1, color2)
        elif args.pattern == "brick":
            img = generate_brick(args.width, args.height, color1, color2)
        else:
            img = generate_rectangle(args.width, args.height, color1)
    else:
        color = parse_color(args.color)
        if args.flat:
            # Flat style (original simple shapes)
            if args.shape == "circle":
                img = generate_circle(args.width, args.height, color)
            elif args.shape == "rounded":
                img = generate_rounded_rect(args.width, args.height, color, args.radius)
            elif args.shape == "triangle":
                img = generate_triangle(args.width, args.height, color, args.direction)
            elif args.shape == "diamond":
                img = generate_diamond(args.width, args.height, color)
            elif args.shape == "ring":
                img = generate_ring(args.width, args.height, color, args.thickness)
            else:
                img = generate_rectangle(args.width, args.height, color)
        else:
            # Kenney style (default)
            if args.shape == "circle":
                img = kenney_circle(args.width, args.height, color)
            elif args.shape == "rounded":
                img = kenney_box(args.width, args.height, color)
            elif args.shape == "triangle":
                img = kenney_spike(args.width, args.height, color)
            elif args.shape == "diamond":
                img = generate_diamond(args.width, args.height, color)  # Keep flat for diamond
                img = add_border(img, darken(color, 0.5), 2)
            elif args.shape == "ring":
                img = generate_ring(args.width, args.height, color, args.thickness)
            else:
                img = kenney_box(args.width, args.height, color)

    # Add border if specified
    if args.border:
        border_color = parse_color(args.border)
        img = add_border(img, border_color, args.border_width)

    base64_data = image_to_base64(img)

    if args.json:
        print(f'["{base64_data}"]')
    else:
        print(base64_data)

    print(f"\n// Size: {img.width}x{img.height}", file=sys.stderr)


if __name__ == "__main__":
    main()
