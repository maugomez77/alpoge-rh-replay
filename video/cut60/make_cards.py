from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import os

OUT = "video/cut60"
os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080
FONT_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_R = "/System/Library/Fonts/Supplemental/Arial.ttf"
ACCENT = (179, 136, 255)
CYAN = (103, 232, 249)
FG = (238, 234, 255)
MUTED = (154, 165, 177)


def bg():
    im = Image.new("RGB", (W, H), (5, 3, 10))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(5 + 8 * t), int(3 + 2 * t), int(10 + 14 * t)))
    # faint vignette
    return im


def font(path, size):
    return ImageFont.truetype(path, size)


def center(d, y, text, f, fill):
    w = d.textbbox((0, 0), text, font=f)[2]
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


def card(name, kicker, big, sub, foot):
    im = bg()
    d = ImageDraw.Draw(im)
    center(d, 330, kicker, font(FONT_R, 26), MUTED)
    center(d, 400, big, font(FONT_B, 150), FG)
    center(d, 590, sub, font(FONT_R, 38), MUTED)
    d.rectangle([(W // 2 - 60, 690), (W // 2 + 60, 694)], fill=ACCENT)
    center(d, 730, foot, font(FONT_R, 24), ACCENT)
    im.save(os.path.join(OUT, name))


def overlay(src, name, kicker, big, sub):
    base = Image.open(src).convert("RGB")
    base = ImageOps.fit(base, (W, H), Image.LANCZOS)
    # darken slightly for text
    base = Image.blend(base, Image.new("RGB", (W, H), (5, 3, 10)), 0.18)
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle([(90, 770), (1180, 1010)], radius=24,
                         fill=(5, 3, 10, 178), outline=(60, 40, 90, 200), width=2)
    d = ImageDraw.Draw(panel)
    d.text((130, 800), kicker, font=font(FONT_R, 24), fill=CYAN)
    d.text((130, 838), big, font=font(FONT_B, 54), fill=FG)
    d.text((130, 912), sub, font=font(FONT_R, 27), fill=MUTED)
    out = Image.alpha_composite(base.convert("RGBA"), panel).convert("RGB")
    out.save(os.path.join(OUT, name))


card("card_intro.png", "THE RIEMANN HYPOTHESIS",
     "17,374,215", "lines of Lean · 175,187 files", "one proof, replayed on Apple silicon")
card("card_build.png", "THE CLEAN BUILD",
     "114,019", "jobs · 9 h 07 m · 0 errors", "e497a6603e · Main + Challenge")
card("card_bridge.png", "OLLIVIER–RICCI CURVATURE",
     "90.9%", "of import edges are bridges", "494,947 edges · mean κ −0.266")
card("card_close.png", "STATUS",
     "Build green.", "Certification in progress.", "114,019 jobs · exit 0 · 0 errors")

overlay("dashboard/rh-module-graph-density.png", "overlay_graph.png",
        "THE PROOF GRAPH", "47,885 modules",
        "494,947 imports · every filament is a real import")
overlay("dashboard/rh-module-timeline-build.png", "overlay_build.png",
        "WHERE THE TIME GOES", "9 h 05 m",
        "46,347 modules · 114,019 jobs · 0 errors")
overlay("dashboard/rh-module-buildtime.png", "overlay_cost.png",
        "COMPILE COST IS SPREAD OUT", "Top 1% = 9.7%",
        "no small set of modules dominates the build")
overlay("dashboard/rh-module-ricci.png", "overlay_ricci.png",
        "THE FRAGILE BRIDGES", "90.9% negative",
        "cross-namespace imports are the weak links")
overlay("dashboard/rh-module-instances.png", "overlay_debt.png",
        "INSTANCE DEBT", "18,815 disables",
        "10,344 modules · 21.6% of the tree")
print("cards written", sorted(os.listdir(OUT)))
