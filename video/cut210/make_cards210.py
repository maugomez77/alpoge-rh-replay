from PIL import Image, ImageDraw, ImageFont, ImageOps
import os

OUT = "video/cut210"
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
        d.line([(0, y), (W, y)],
               fill=(int(5 + 8 * t), int(3 + 2 * t), int(10 + 14 * t)))
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
    center(d, 400, big, font(FONT_B, 140), FG)
    center(d, 590, sub, font(FONT_R, 36), MUTED)
    d.rectangle([(W // 2 - 60, 690), (W // 2 + 60, 694)], fill=ACCENT)
    center(d, 730, foot, font(FONT_R, 24), ACCENT)
    im.save(os.path.join(OUT, name))


def overlay(src, name, kicker, big, sub):
    base = Image.open(src).convert("RGB")
    base = ImageOps.fit(base, (W, H), Image.LANCZOS)
    base = Image.blend(base, Image.new("RGB", (W, H), (5, 3, 10)), 0.16)
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle([(90, 770), (1240, 1010)], radius=24,
                         fill=(5, 3, 10, 185), outline=(60, 40, 90, 200), width=2)
    d = ImageDraw.Draw(panel)
    d.text((130, 800), kicker, font=font(FONT_R, 24), fill=CYAN)
    d.text((130, 838), big, font=font(FONT_B, 52), fill=FG)
    d.text((130, 910), sub, font=font(FONT_R, 26), fill=MUTED)
    Image.alpha_composite(base.convert("RGBA"), panel).convert("RGB").save(
        os.path.join(OUT, name))


card("card_archive.png", "THE WORKING TREE",
     "47,885", "modules · 14,583,569 lines", "494,947 parsed imports")
card("card_verify.png", "STATUS",
     "Build green.", "Certification in progress.", "comparator · con-leche · leanchecker pending")
card("card_credits.png", "SOURCES",
     "Proof: Alpöge et al.", "leanprover-community / rohanarun / maugomez77", "built from real source and receipts")

overlay("dashboard/rh-module-kcore.png", "overlay_kcore.png",
        "THE CORE", "k-core = 46",
        "only 21 modules in the deepest core")
overlay("dashboard/rh-module-critical-path.png", "overlay_critical.png",
        "THE LONGEST CHAIN", "156 modules",
        "~24 min measured cost vs 6.25 h total work")
print("cards written", sorted(f for f in os.listdir(OUT) if f.endswith(".png")))
