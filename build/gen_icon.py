"""Generate Caret app icon — purple gradient diamond/layers on dark background."""
from PIL import Image, ImageDraw
import math, sys, os

SIZE = 1024
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background: dark rounded square
def rounded_rect(d, x0, y0, x1, y1, r, fill):
    d.rectangle([x0+r, y0, x1-r, y1], fill=fill)
    d.rectangle([x0, y0+r, x1, y1-r], fill=fill)
    d.ellipse([x0, y0, x0+2*r, y0+2*r], fill=fill)
    d.ellipse([x1-2*r, y0, x1, y0+2*r], fill=fill)
    d.ellipse([x0, y1-2*r, x0+2*r, y1], fill=fill)
    d.ellipse([x1-2*r, y1-2*r, x1, y1], fill=fill)

rounded_rect(draw, 0, 0, SIZE, SIZE, 160, (11, 11, 18, 255))

# Purple gradient overlay — draw horizontal bands
for y in range(SIZE):
    t = y / SIZE
    r = int(124 + (167 - 124) * t)
    g = int(106 + (139 - 106) * t)
    b = int(255)
    # just use for the logo shapes

# Logo: 3 chevron/diamond layers — matching sidebar SVG
cx, cy = SIZE // 2, SIZE // 2
scale = SIZE / 24

def pt(x, y):
    return (x * scale, y * scale)

# Colors: accent purple gradient
color1 = (124, 106, 255, 255)   # #7c6aff
color2 = (167, 139, 250, 255)   # #a78bfa

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(4))

def gradient_polygon(draw, pts, c1, c2):
    if not pts:
        return
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)
    from PIL import Image as Im, ImageDraw as ID
    layer = Im.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    ld = ID.Draw(layer)
    ld.polygon(pts, fill=c1)
    img.paste(layer, (0,0), layer)

# Top diamond (filled)
top_pts = [pt(12,2), pt(2,7), pt(12,12), pt(22,7)]
draw.polygon(top_pts, fill=color1)

# Middle chevron
def stroke_polyline(pts, width, color):
    for i in range(len(pts)-1):
        x0,y0 = pts[i]
        x1,y1 = pts[i+1]
        draw.line([(x0,y0),(x1,y1)], fill=color, width=width)
    # round caps
    r = width//2
    for x,y in pts:
        draw.ellipse([x-r,y-r,x+r,y+r], fill=color)

w = int(1.75 * scale)
stroke_polyline([pt(2,12), pt(12,17), pt(22,12)], w, color1)
stroke_polyline([pt(2,17), pt(12,22), pt(22,17)], w, color2)

out = sys.argv[1] if len(sys.argv) > 1 else "caret-source.png"
img.save(out)
print(f"Saved {out}")
