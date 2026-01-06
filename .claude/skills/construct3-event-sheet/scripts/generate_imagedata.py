#!/usr/bin/env python3
"""
Generate valid C3 imageData (base64 PNG) for sprites.

Usage:
    # Generate colored rectangle
    python generate_imagedata.py --color red --width 32 --height 32
    python generate_imagedata.py --color "#00FF00" --width 64 --height 16

    # Convert existing image file
    python generate_imagedata.py --file sprite.png

    # Generate with specific shape
    python generate_imagedata.py --color blue --width 16 --height 16 --shape circle
"""

import argparse
import base64
import io
import sys

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
}


def parse_color(color_str: str) -> tuple:
    """Parse color string to RGBA tuple"""
    if color_str.lower() in COLORS:
        return COLORS[color_str.lower()]

    # Parse hex color
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
    parser = argparse.ArgumentParser(
        description="Generate C3-compatible imageData (base64 PNG)"
    )
    parser.add_argument("--file", "-f", help="Input image file to convert")
    parser.add_argument("--color", "-c", default="white", help="Color name or #RRGGBB")
    parser.add_argument("--width", "-W", type=int, default=32, help="Width in pixels")
    parser.add_argument("--height", "-H", type=int, default=32, help="Height in pixels")
    parser.add_argument(
        "--shape", "-s",
        choices=["rect", "circle", "rounded"],
        default="rect",
        help="Shape type"
    )
    parser.add_argument("--radius", "-r", type=int, default=4, help="Corner radius for rounded rect")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON array element")

    args = parser.parse_args()

    if args.file:
        img = load_image_file(args.file)
    else:
        color = parse_color(args.color)
        if args.shape == "circle":
            img = generate_circle(args.width, args.height, color)
        elif args.shape == "rounded":
            img = generate_rounded_rect(args.width, args.height, color, args.radius)
        else:
            img = generate_rectangle(args.width, args.height, color)

    base64_data = image_to_base64(img)

    if args.json:
        print(f'["{base64_data}"]')
    else:
        print(base64_data)

    # Print image info to stderr
    print(f"\n// Size: {img.width}x{img.height}", file=sys.stderr)


if __name__ == "__main__":
    main()
