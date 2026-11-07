"""Generates the app icon (ico + png), tray variants and the glass backdrop.

    python tools/make_assets.py
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "audio_balancer" / "assets"
S = 2048  # supersampled canvas, downscaled at the end


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def diagonal_gradient(size, c1, c2):
    """Top-left to bottom-right gradient."""
    grad = Image.linear_gradient("L").resize((size, size))  # top black -> bottom white
    diag = Image.linear_gradient("L").rotate(90).resize((size, size))
    mix = ImageChops.add(grad, diag, scale=2)
    return Image.composite(
        Image.new("RGB", (size, size), c2), Image.new("RGB", (size, size), c1), mix
    )


def squircle_mask(size, radius_frac=0.225):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * radius_frac), fill=255
    )
    return m


def vertical_fade(size, top_alpha, bottom_alpha):
    g = Image.linear_gradient("L").resize((size, size))
    lut = [int(top_alpha + (bottom_alpha - top_alpha) * i / 255) for i in range(256)]
    return g.point(lut)


def render_icon(c1, c2, glow):
    mask = squircle_mask(S)
    base = diagonal_gradient(S, c1, c2).convert("RGBA")

    # soft colored glow in the lower right, like light refracting through glass
    glow_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow_layer).ellipse(
        (S * 0.35, S * 0.45, S * 1.1, S * 1.2), fill=glow + (150,)
    )
    base = Image.alpha_composite(base, glow_layer.filter(ImageFilter.GaussianBlur(S * 0.12)))

    # equalizer bars: left and right high, middle "ducked" low
    bar_w, gap = S * 0.135, S * 0.075
    heights = [S * 0.36, S * 0.56, S * 0.26]
    total = bar_w * 3 + gap * 2
    x0 = (S - total) / 2
    cy = S * 0.52

    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bars = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd, bd = ImageDraw.Draw(shadow), ImageDraw.Draw(bars)
    for i, h in enumerate(heights):
        x = x0 + i * (bar_w + gap)
        box = (x, cy - h / 2, x + bar_w, cy + h / 2)
        sd.rounded_rectangle(
            (box[0], box[1] + S * 0.025, box[2], box[3] + S * 0.025),
            radius=bar_w / 2, fill=(10, 10, 60, 110),
        )
        bd.rounded_rectangle(box, radius=bar_w / 2, fill=(255, 255, 255, 235))
    base = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(S * 0.02)))

    # glass look on the bars: fade to translucent at the bottom + bright top edge
    fade = vertical_fade(S, 255, 185)
    bar_alpha = ImageChops.multiply(bars.getchannel("A"), fade)
    bars.putalpha(bar_alpha)
    base = Image.alpha_composite(base, bars)

    edge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge)
    for i, h in enumerate(heights):
        x = x0 + i * (bar_w + gap)
        ed.rounded_rectangle(
            (x, cy - h / 2, x + bar_w, cy + h / 2),
            radius=bar_w / 2, outline=(255, 255, 255, 120), width=int(S * 0.005),
        )
    base = Image.alpha_composite(base, edge)

    # top sheen across the whole tile
    sheen = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    sheen.putalpha(vertical_fade(S, 95, 0).point(lambda v: v if v > 0 else 0))
    sheen_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sheen_mask).ellipse((-S * 0.15, -S * 0.55, S * 1.15, S * 0.62), fill=255)
    sheen_mask = sheen_mask.filter(ImageFilter.GaussianBlur(S * 0.035))
    sheen.putalpha(ImageChops.multiply(sheen.getchannel("A"), sheen_mask))
    base = Image.alpha_composite(base, sheen)

    # glass rim
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle(
        (S * 0.004, S * 0.004, S * 0.996, S * 0.996),
        radius=int(S * 0.225), outline=(255, 255, 255, 90), width=int(S * 0.008),
    )
    base = Image.alpha_composite(base, rim)

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    return out.resize((1024, 1024), Image.LANCZOS)


def make_backdrop():
    w, h = 900, 1200
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    blobs = [
        ((-120, -80, 520, 560), (122, 92, 255, 150)),
        ((420, 380, 1050, 1000), (25, 211, 197, 120)),
        ((-160, 760, 420, 1320), (255, 107, 214, 80)),
        ((380, -60, 980, 420), (47, 123, 255, 95)),
    ]
    for box, color in blobs:
        d.ellipse(box, fill=color)
    return layer.filter(ImageFilter.GaussianBlur(110))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idle = render_icon((78, 70, 255), (0, 200, 185), (90, 255, 225))
    talk = render_icon((255, 140, 66), (255, 80, 120), (255, 214, 120))
    idle.save(OUT / "icon.png")
    idle.save(
        OUT / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    idle.resize((64, 64), Image.LANCZOS).save(OUT / "tray_idle.png")
    talk.resize((64, 64), Image.LANCZOS).save(OUT / "tray_talk.png")
    make_backdrop().save(OUT / "backdrop.png")
    print("assets written to", OUT)


if __name__ == "__main__":
    main()
