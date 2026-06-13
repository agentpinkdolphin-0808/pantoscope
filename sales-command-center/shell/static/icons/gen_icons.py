"""
Generate 500x500 PNG glyph icons on colored rounded tiles.
Requires: pip install cairosvg  (or pillow+svglib as fallback)
Run from the icons/ directory: python3 gen_icons.py
"""
import os

ICONS = {
    "account-overview": {
        "bg": "#1e3a5f",
        "color": "#3b82f6",
        "path": '<path d="M250 170a80 80 0 110 160 80 80 0 010-160zm0 180c-66 0-120 32-120 72v8h240v-8c0-40-54-72-120-72z" fill="{color}"/>',
    },
    "sales-history": {
        "bg": "#2d1b5e",
        "color": "#8b5cf6",
        "path": '<polyline points="110,340 180,240 250,280 320,160 390,200" fill="none" stroke="{color}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>',
    },
    "pipeline-management": {
        "bg": "#1e2060",
        "color": "#6366f1",
        "path": '<polygon points="250,130 370,197 370,303 250,370 130,303 130,197" fill="none" stroke="{color}" stroke-width="20"/><circle cx="250" cy="250" r="40" fill="{color}"/>',
    },
    "reports-analytics": {
        "bg": "#0d2d45",
        "color": "#0ea5e9",
        "path": '<rect x="120" y="290" width="50" height="80" rx="6" fill="{color}"/><rect x="195" y="230" width="50" height="140" rx="6" fill="{color}"/><rect x="270" y="180" width="50" height="190" rx="6" fill="{color}"/><rect x="345" y="140" width="50" height="230" rx="6" fill="{color}"/>',
    },
    "team-performance": {
        "bg": "#0d3535",
        "color": "#14b8a6",
        "path": '<circle cx="185" cy="210" r="50" fill="none" stroke="{color}" stroke-width="18"/><path d="M95 390v-20c0-44 40-80 90-80" fill="none" stroke="{color}" stroke-width="18" stroke-linecap="round"/><circle cx="315" cy="200" r="40" fill="none" stroke="{color}" stroke-width="16"/><path d="M275 380v-16c0-38 34-68 80-68h30" fill="none" stroke="{color}" stroke-width="16" stroke-linecap="round"/><path d="M175 390h140" stroke="{color}" stroke-width="18" stroke-linecap="round"/>',
    },
    "route-planner": {
        "bg": "#0d3520",
        "color": "#22c55e",
        "path": '<path d="M160 160q0 80 90 180q90-100 90-180a90 90 0 00-180 0z" fill="none" stroke="{color}" stroke-width="20"/><circle cx="250" cy="165" r="28" fill="{color}"/><path d="M220 360q60 20 80-20" fill="none" stroke="{color}" stroke-width="14" stroke-linecap="round"/>',
    },
    "visit-accounts": {
        "bg": "#0d2d45",
        "color": "#0ea5e9",
        "path": '<path d="M250 120q-90 0-90 100 0 80 90 160 90-80 90-160 0-100-90-100z" fill="none" stroke="{color}" stroke-width="20"/><circle cx="250" cy="222" r="32" fill="{color}"/><path d="M140 390h220" stroke="{color}" stroke-width="14" stroke-linecap="round"/>',
    },
    "merchandising": {
        "bg": "#3d2000",
        "color": "#f59e0b",
        "path": '<rect x="120" y="130" width="260" height="50" rx="10" fill="{color}"/><path d="M120 180v160h260V180" fill="none" stroke="{color}" stroke-width="20"/><line x1="160" y1="245" x2="340" y2="245" stroke="{color}" stroke-width="14" stroke-linecap="round"/><line x1="160" y1="295" x2="340" y2="295" stroke="{color}" stroke-width="14" stroke-linecap="round"/>',
    },
    "surveys-feedback": {
        "bg": "#1e2028",
        "color": "#9ca3af",
        "path": '<path d="M150 130h200a20 20 0 0120 20v140a20 20 0 01-20 20h-130l-70 60v-60h0a20 20 0 01-20-20V150a20 20 0 0120-20z" fill="none" stroke="{color}" stroke-width="20"/><line x1="190" y1="195" x2="310" y2="195" stroke="{color}" stroke-width="14" stroke-linecap="round"/><line x1="190" y1="240" x2="310" y2="240" stroke="{color}" stroke-width="14" stroke-linecap="round"/>',
    },
    "orders-invoices": {
        "bg": "#0d1a45",
        "color": "#3b82f6",
        "path": '<path d="M170 110h100l80 80v200a20 20 0 01-20 20H170a20 20 0 01-20-20V130a20 20 0 0120-20z" fill="none" stroke="{color}" stroke-width="20"/><path d="M270 110v80h80" fill="none" stroke="{color}" stroke-width="16"/><line x1="190" y1="255" x2="310" y2="255" stroke="{color}" stroke-width="14" stroke-linecap="round"/><line x1="190" y1="300" x2="310" y2="300" stroke="{color}" stroke-width="14" stroke-linecap="round"/><line x1="190" y1="210" x2="250" y2="210" stroke="{color}" stroke-width="14" stroke-linecap="round"/>',
    },
}

SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500">
  <rect width="500" height="500" rx="80" fill="{bg}"/>
  {shape}
</svg>"""

out_dir = os.path.dirname(os.path.abspath(__file__))

for name, cfg in ICONS.items():
    shape = cfg["path"].replace("{color}", cfg["color"])
    svg = SVG_TEMPLATE.format(bg=cfg["bg"], shape=shape)
    svg_path = os.path.join(out_dir, f"{name}.svg")
    with open(svg_path, "w") as f:
        f.write(svg)
    print(f"  wrote {name}.svg")

print(f"\nGenerated {len(ICONS)} SVG icons in {out_dir}/")
print("To convert to PNG: brew install librsvg && for f in *.svg; do rsvg-convert -w 500 -h 500 $f -o ${f%.svg}.png; done")
