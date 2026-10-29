"""Hidden-test-style designs: 12 archetypes that exercise every schema feature.

Product promo, event poster, sale banner, quote card, product grid, text-heavy,
collage, testimonial, app ad, minimal, intentional layering, and an adversarial
case (off-canvas pieces, zero-size and invisible elements, unbreakable words,
non-Latin text). Seeded, so `design(seed)` is reproducible.

Assets: the 3 brand-kit files plus names the engine has never seen, since the
judges' kit may hold more real assets. For rendering, `mock_judge_kit()` aliases
the unknown names to real files so renders look the way a judge would see them.

    python -m evaluation.stress --suite hidden --designs 240
    python -m evaluation.contact_sheet out.png 1 2 3
"""
import random

FMT = {  # real platform formats (source canvases and targets)
    "ig_post": (1080, 1080), "ig_portrait": (1080, 1350), "ig_story": (1080, 1920),
    "fb_post": (1200, 630), "yt_thumb": (1280, 720), "x_post": (1600, 900),
    "linkedin_banner": (1584, 396), "fb_cover": (820, 312), "pinterest": (1000, 1500),
    "leaderboard": (728, 90), "med_rect": (300, 250), "skyscraper": (160, 600),
    "half_page": (300, 600), "mobile_banner": (320, 50), "x_header": (1500, 500),
    "billboard": (970, 250), "large_rect": (336, 280), "mobile_large": (320, 100),
    "hd": (1920, 1080), "a4ish": (1240, 1754), "square_small": (250, 250),
}
SOURCES = ["ig_post", "ig_portrait", "ig_story", "fb_post", "yt_thumb", "hd", "pinterest", "x_post"]

# name -> real file it renders as in the mock judge kit
UNKNOWN_ASSETS = {
    "solstice_product_peach.png": "solstice_bottle.png",
    "solstice_product_lime.png": "solstice_bottle.png",
    "solstice_lifestyle_photo.jpg": "solstice_bg_gradient.png",
    "solstice_avatar.png": "solstice_bottle.png",
    "solstice_pattern.png": "solstice_bg_gradient.png",
    "solstice_icon_star.png": "solstice_logo_lockup.png",
}
PRODUCTS = ["solstice_bottle.png", "solstice_product_peach.png", "solstice_product_lime.png"]

WHITE, DARK = "rgba(255,255,255,1)", "rgba(33,22,40,1)"
ORANGE, GOLD, PLUM = "rgba(232,106,58,1)", "rgba(240,178,66,1)", "rgba(60,30,70,1)"
HEADLINES = ["Chase the Light", "Golden Hour, Bottled", "Summer Starts Here",
             "Introducing the Limited-Batch Botanical Collection",
             "Sparkling infusions crafted slowly for long evenings with friends",
             "NEW", "Taste the Season — Only While It Lasts", "Pre-order Now"]
BODY = ["Botanical sparkling infusions, crafted for golden hour.",
        "Small-batch blends of wild honey, blood orange and smoked rosemary, bottled at the peak of the season.",
        "Available at selected retailers from June 1st. Limited quantities.",
        "Light. Bright. Zero compromise.",
        "Join us for an evening of tastings, live music and sunset views on the rooftop terrace."]
CTAS = ["Shop now", "Shop the Summer Line", "Learn more", "Get tickets", "Order today →", "Download the app"]
LEGAL = ["Please drink responsibly. Solstice Sparkling Co., 2026. Void where prohibited. See solstice.com/terms for details.",
         "Offer valid until 31/08 while stocks last. T&Cs apply.", "© 2026 Solstice"]


class D:
    def __init__(self, rng, fmt):
        self.r = rng
        self.W, self.H = FMT[fmt]
        self.els, self.n, self.z = [], 0, 0

    def id(self, p):
        self.n += 1
        return f"{p}_{self.n}"

    def add(self, **e):
        e.setdefault("z_index", self.z)
        self.z += 1
        e["id"] = e.get("id") or self.id(e["type"])
        self.els.append(e)
        return e

    def text(self, x, y, w, h, content, size, **kw):
        e = dict(type="text", x=x, y=y, width=w, height=h, content=content, font_size=size,
                 font_family=kw.pop("family", self.r.choice(["Solstice Sans", "Solstice Serif"])),
                 color=kw.pop("color", WHITE))
        e.update(kw)
        return self.add(**e)

    def image(self, x, y, w, h, asset, fit="contain", **kw):
        return self.add(type="image", x=x, y=y, width=w, height=h, asset_id=asset, fit=fit, **kw)

    def shape(self, x, y, w, h, kind="rectangle", fill=ORANGE, **kw):
        return self.add(type="shape", x=x, y=y, width=w, height=h, shape_type=kind, fill_color=fill, **kw)

    def button(self, x, y, w, h, label, fill=ORANGE, color=WHITE, radius=None):
        g = self.id("grp")
        self.shape(x, y, w, h, fill=fill, group_id=g, corner_radius=h / 2 if radius is None else radius)
        self.text(x, y + h * 0.25, w, h * 0.5, label, max(10, round(h * 0.36)), family="Solstice Sans",
                  font_weight="bold", text_align="center", color=color, group_id=g)

    def background(self):
        k = self.r.random()
        if k < 0.4:
            self.image(0, 0, self.W, self.H, "solstice_bg_gradient.png", fit="cover")
        elif k < 0.6:
            self.image(0, 0, self.W, self.H, "solstice_lifestyle_photo.jpg", fit="cover")
        elif k < 0.9:
            self.shape(0, 0, self.W, self.H, fill=self.r.choice([PLUM, DARK, "rgba(250,240,228,1)"]))
        # else: no background element at all

    def decor(self, k=None):
        for _ in range(self.r.randint(0, 3) if k is None else k):
            s = self.r.uniform(0.1, 0.5) * min(self.W, self.H)
            self.shape(self.r.uniform(-0.2, 0.9) * self.W, self.r.uniform(-0.2, 0.9) * self.H, s, s,
                       kind="ellipse", fill="rgba(255,255,255,1)", opacity=self.r.choice([0.08, 0.15, 0.25]))

    def done(self):
        return {"canvas": {"width": self.W, "height": self.H}, "elements": self.els}


def product_promo(d):
    W, H, r = d.W, d.H, d.r
    d.background(); d.decor()
    portrait = H >= W
    d.image(W * 0.36, H * 0.04, W * 0.28, H * 0.08, "solstice_logo_lockup.png")
    if portrait:
        d.image(W * 0.25, H * 0.15, W * 0.5, H * 0.38, r.choice(PRODUCTS))
        hl = r.choice(HEADLINES)
        d.text(W * 0.08, H * 0.56, W * 0.84, H * 0.12, hl, round(H * 0.05), font_weight="bold", text_align="center",
               style_runs=[{"start": 0, "end": min(5, len(hl)), "color": GOLD}] if r.random() < 0.5 else [])
        d.text(W * 0.12, H * 0.69, W * 0.76, H * 0.08, r.choice(BODY), round(H * 0.022), text_align="center")
        d.button(W * 0.3, H * 0.8, W * 0.4, H * 0.065, r.choice(CTAS))
    else:
        d.image(W * 0.06, H * 0.18, W * 0.34, H * 0.7, r.choice(PRODUCTS))
        d.text(W * 0.45, H * 0.22, W * 0.5, H * 0.25, r.choice(HEADLINES), round(H * 0.08), font_weight="bold")
        d.text(W * 0.45, H * 0.5, W * 0.48, H * 0.15, r.choice(BODY), round(H * 0.03))
        d.button(W * 0.45, H * 0.72, W * 0.28, H * 0.11, r.choice(CTAS))
    if r.random() < 0.6:
        d.text(W * 0.05, H * 0.94, W * 0.9, H * 0.03, r.choice(LEGAL), max(9, round(min(W, H) * 0.012)),
               family="Solstice Sans", text_align="center", color="rgba(255,255,255,0.7)")


def event_poster(d):
    W, H, r = d.W, d.H, d.r
    d.shape(0, 0, W, H, fill=r.choice([PLUM, DARK]))
    d.shape(W * 0.08, H * 0.1, W * 0.84, 4, kind="line", fill=GOLD, stroke_color=GOLD, stroke_width=4)
    d.text(W * 0.08, H * 0.14, W * 0.84, H * 0.3, r.choice(HEADLINES).upper(), round(min(W, H) * 0.11),
           family="Solstice Serif", font_weight="bold", line_height=1.0, letter_spacing=2)
    d.text(W * 0.08, H * 0.48, W * 0.84, H * 0.06, "FRIDAY 21 JUNE · 7 PM\nThe Rooftop, 12 Harbour St", round(min(W, H) * 0.035),
           family="Solstice Sans", color=GOLD, line_height=1.4)
    d.text(W * 0.08, H * 0.6, W * 0.84, H * 0.15, r.choice(BODY), round(min(W, H) * 0.028), family="Solstice Sans")
    d.shape(W * 0.08, H * 0.78, W * 0.84, 4, kind="line", fill=GOLD, stroke_color=GOLD, stroke_width=4)
    d.button(W * 0.08, H * 0.83, W * 0.38, H * 0.08, "Get tickets", fill=GOLD, color=DARK, radius=0)
    d.image(W * 0.62, H * 0.83, W * 0.3, H * 0.08, "solstice_logo_lockup.png")
    d.decor(2)


def sale_banner(d):
    W, H, r = d.W, d.H, d.r
    d.background()
    d.text(W * 0.05, H * 0.08, W * 0.5, H * 0.35, r.choice(["50% OFF", "SALE", "2 FOR 1"]), round(min(W, H) * 0.2),
           family="Solstice Sans", font_weight="bold", color=GOLD)
    g = d.id("ribbon")
    d.shape(W * 0.68, H * 0.06, W * 0.3, H * 0.08, fill="rgba(210,40,40,1)", group_id=g, rotation=12)
    d.text(W * 0.68, H * 0.075, W * 0.3, H * 0.05, "THIS WEEKEND", round(H * 0.03), family="Solstice Sans",
           font_weight="bold", text_align="center", group_id=g, rotation=12)
    n = r.randint(2, 4)
    for i in range(n):
        d.image(W * (0.08 + i * 0.84 / n), H * 0.48, W * 0.8 / n, H * 0.3, r.choice(PRODUCTS))
    d.button(W * 0.35, H * 0.84, W * 0.3, H * 0.08, r.choice(CTAS))
    d.text(W * 0.05, H * 0.95, W * 0.9, H * 0.03, r.choice(LEGAL), max(8, round(min(W, H) * 0.011)),
           family="Solstice Sans", text_align="center")


def quote_card(d):
    W, H, r = d.W, d.H, d.r
    d.shape(0, 0, W, H, fill="rgba(250,240,228,1)")
    d.text(W * 0.08, H * 0.05, W * 0.2, H * 0.2, "“", round(min(W, H) * 0.25), family="Solstice Serif", color=ORANGE)
    d.text(W * 0.1, H * 0.25, W * 0.8, H * 0.4,
           r.choice(["The best things are made slowly.", "Every sunset is an invitation to slow down and share something good with someone you love."]),
           round(min(W, H) * 0.06), family="Solstice Serif", font_style="italic", color=DARK)
    d.text(W * 0.1, H * 0.7, W * 0.8, H * 0.05, "— Maya R., head blender", round(min(W, H) * 0.03),
           family="Solstice Sans", color=DARK, text_align="right")
    d.image(W * 0.4, H * 0.84, W * 0.2, H * 0.08, "solstice_logo_lockup.png")


def product_grid(d):
    W, H, r = d.W, d.H, d.r
    d.background()
    d.text(W * 0.05, H * 0.04, W * 0.9, H * 0.1, "Meet the range", round(min(W, H) * 0.07), font_weight="bold",
           text_align="center")
    cols, rows = (2, 2) if r.random() < 0.6 else (3, 1)
    cw, ch = W * 0.9 / cols, H * 0.7 / rows
    for i in range(cols * rows):
        x, y = W * 0.05 + (i % cols) * cw, H * 0.17 + (i // cols) * ch
        g = d.id("card")
        d.shape(x + 8, y + 8, cw - 16, ch - 16, fill="rgba(255,255,255,0.12)", group_id=g, corner_radius=18)
        d.image(x + cw * 0.2, y + ch * 0.08, cw * 0.6, ch * 0.55, r.choice(PRODUCTS), group_id=g)
        d.text(x + 16, y + ch * 0.66, cw - 32, ch * 0.12, r.choice(["Peach & Thyme", "Lime Leaf", "Blood Orange"]),
               round(ch * 0.07), family="Solstice Sans", font_weight="bold", text_align="center", group_id=g)
        d.text(x + 16, y + ch * 0.8, cw - 32, ch * 0.08, "$4.99", round(ch * 0.055), family="Solstice Sans",
               color=GOLD, text_align="center", group_id=g)
    d.button(W * 0.35, H * 0.9, W * 0.3, H * 0.065, "Shop all")


def text_heavy(d):
    W, H, r = d.W, d.H, d.r
    d.shape(0, 0, W, H, fill=DARK)
    d.text(W * 0.07, H * 0.06, W * 0.86, H * 0.14, r.choice(HEADLINES), round(min(W, H) * 0.06), font_weight="bold",
           max_lines=2)
    y = H * 0.24
    for _ in range(3):
        d.text(W * 0.07, y, W * 0.86, H * 0.15, " ".join(r.sample(BODY, 2)), round(min(W, H) * 0.026),
               family="Solstice Sans", line_height=1.5)
        y += H * 0.18
    d.text(W * 0.07, y, W * 0.86, H * 0.12, "• Small batch\n• No refined sugar\n• Recyclable glass",
           round(min(W, H) * 0.026), family="Solstice Sans", color=GOLD, line_height=1.5)
    d.text(W * 0.07, H * 0.93, W * 0.86, H * 0.03, "solstice.com/a-very-long-url-that-cannot-be-wrapped-anywhere-at-all",
           round(min(W, H) * 0.018), family="Solstice Sans", text_align="right")


def collage(d):
    W, H, r = d.W, d.H, d.r
    d.shape(0, 0, W, H, fill="rgba(250,240,228,1)")
    for i in range(r.randint(3, 6)):
        s = r.uniform(0.25, 0.45) * min(W, H)
        d.image(r.uniform(0, W - s), r.uniform(0, H * 0.7 - s / 2), s, s,
                r.choice(PRODUCTS + ["solstice_lifestyle_photo.jpg"]), fit=r.choice(["contain", "cover"]),
                rotation=r.uniform(-15, 15))
    d.text(W * 0.06, H * 0.78, W * 0.88, H * 0.14, "Moments worth sharing", round(min(W, H) * 0.07),
           family="Solstice Serif", font_weight="bold", color=DARK, text_align="center")


def testimonial(d):
    W, H, r = d.W, d.H, d.r
    d.background()
    g = d.id("card")
    d.shape(W * 0.08, H * 0.12, W * 0.84, H * 0.76, fill="rgba(255,255,255,1)", group_id=None, corner_radius=24,
            stroke_color="rgba(232,106,58,1)", stroke_width=3)
    d.image(W * 0.42, H * 0.17, W * 0.16, W * 0.16, "solstice_avatar.png", fit="cover")
    d.text(W * 0.14, H * 0.38, W * 0.72, H * 0.06, "★★★★★", round(min(W, H) * 0.05), family="Solstice Sans",
           color=GOLD, text_align="center")
    d.text(W * 0.14, H * 0.46, W * 0.72, H * 0.25, r.choice(BODY), round(min(W, H) * 0.035), family="Solstice Serif",
           font_style="italic", color=DARK, text_align="center")
    d.text(W * 0.14, H * 0.76, W * 0.72, H * 0.05, "Jordan P. · verified buyer", round(min(W, H) * 0.025),
           family="Solstice Sans", color=DARK, text_align="center")


def app_ad(d):
    W, H, r = d.W, d.H, d.r
    d.shape(0, 0, W, H, fill=PLUM)
    d.image(W * 0.55, H * 0.08, W * 0.4, H * 0.84, "solstice_lifestyle_photo.jpg", fit="cover")
    d.text(W * 0.06, H * 0.12, W * 0.45, H * 0.3, "Your table, reserved in two taps", round(min(W, H) * 0.07),
           font_weight="bold")
    d.text(W * 0.06, H * 0.45, W * 0.45, H * 0.12, "Rated 4.9 by 20k+ hosts", round(min(W, H) * 0.03),
           family="Solstice Sans", color=GOLD)
    d.button(W * 0.06, H * 0.62, W * 0.2, H * 0.09, "App Store", fill=WHITE, color=DARK, radius=12)
    d.button(W * 0.29, H * 0.62, W * 0.2, H * 0.09, "Google Play", fill=WHITE, color=DARK, radius=12)
    d.image(W * 0.06, H * 0.82, W * 0.18, H * 0.08, "solstice_icon_star.png")


def minimal(d):
    W, H, r = d.W, d.H, d.r
    d.background()
    d.image(W * 0.3, H * 0.35, W * 0.4, H * 0.18, "solstice_logo_lockup.png")
    if r.random() < 0.7:
        d.text(W * 0.15, H * 0.58, W * 0.7, H * 0.06, "Chase the Light", round(min(W, H) * 0.045), text_align="center")


def layered(d):
    """Intentional overlaps: text on an image card, translucent panels, rotated badge."""
    W, H, r = d.W, d.H, d.r
    d.image(0, 0, W, H, "solstice_lifestyle_photo.jpg", fit="cover")
    d.shape(W * 0.05, H * 0.55, W * 0.9, H * 0.38, fill="rgba(20,10,30,0.65)", corner_radius=20)
    d.text(W * 0.1, H * 0.6, W * 0.8, H * 0.14, r.choice(HEADLINES), round(min(W, H) * 0.06), font_weight="bold")
    d.text(W * 0.1, H * 0.75, W * 0.8, H * 0.1, r.choice(BODY), round(min(W, H) * 0.026), family="Solstice Sans")
    g = d.id("badge")
    d.shape(W * 0.72, H * 0.06, W * 0.22, W * 0.22, kind="ellipse", fill=ORANGE, group_id=g, rotation=-10)
    d.text(W * 0.74, H * 0.06 + W * 0.07, W * 0.18, W * 0.08, "NEW!", round(W * 0.045), family="Solstice Sans",
           font_weight="bold", text_align="center", group_id=g, rotation=-10)
    d.image(W * 0.05, H * 0.05, W * 0.25, H * 0.08, "solstice_logo_lockup.png")


def awkward(d):
    """Adversarial: off-canvas source pieces, zero-size, invisible, huge text, many tiny bits."""
    W, H, r = d.W, d.H, d.r
    d.background()
    d.shape(-W * 0.1, H * 0.85, W * 1.2, H * 0.3, fill=ORANGE, opacity=0.9)          # spills off canvas
    d.shape(W * 0.5, H * 0.5, 0, 0, fill=ORANGE)                                         # zero-size
    d.text(W * 0.1, H * 0.05, W * 0.8, H * 0.1, "hidden", 20, opacity=0)                 # invisible
    d.text(W * 0.05, H * 0.15, W * 0.9, H * 0.35, "Supercalifragilisticexpialidocious botanicals",
           round(min(W, H) * 0.09), font_weight="bold")
    for i in range(r.randint(6, 12)):
        d.text(r.uniform(0, W * 0.8), r.uniform(H * 0.5, H * 0.8), W * 0.18, H * 0.04,
               r.choice(["Peach", "Lime", "Thyme", "No sugar", "Vegan", "Glass", "Local"]),
               max(10, round(min(W, H) * 0.02)), family="Solstice Sans")
    d.image(W * 0.75, H * 0.02, W * 0.2, H * 0.08, "solstice_logo_lockup.png", opacity=0.8)
    d.text(W * 0.2, H * 0.9, W * 0.6, H * 0.05, "Ünïcödé · 日本語 · emoji 🍑", round(min(W, H) * 0.025),
           family="Solstice Sans", text_align="center", color=DARK)


ARCHETYPES = [product_promo, event_poster, sale_banner, quote_card, product_grid, text_heavy,
              collage, testimonial, app_ad, minimal, layered, awkward]


def design(seed):
    r = random.Random(seed)
    arch = ARCHETYPES[seed % len(ARCHETYPES)]
    fmt = r.choice(SOURCES)
    d = D(r, fmt)
    arch(d)
    out = d.done()
    if r.random() < 0.3:  # opaque ids, like a real export
        for i, e in enumerate(out["elements"]):
            e["id"] = f"el-{r.randint(1000, 9999)}-{i}"
    return arch.__name__, fmt, out


def mock_judge_kit(root="brand_kit"):
    """A temp copy of the brand kit with the unknown asset names filled in."""
    import shutil, tempfile
    from pathlib import Path
    kit = Path(tempfile.mkdtemp(prefix="judge-kit-")) / "kit"
    shutil.copytree(root, kit)
    for new, real in UNKNOWN_ASSETS.items():
        shutil.copy(kit / "assets" / real, kit / "assets" / new)
    return kit
