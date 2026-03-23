"""Generate a 1024x1024 Abacus brand icon."""
from PIL import Image, ImageDraw

SIZE = 1024
PAD = 120  # padding from edges

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background: rounded black square
r = 140  # corner radius
draw.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=r, fill="#0A0A0A")

# Frame of the abacus (outer rectangle with rounded corners)
frame_l, frame_r = PAD, SIZE - PAD
frame_t, frame_b = PAD + 40, SIZE - PAD - 40
bar_color = "#E0E0E0"
bar_w = 14

# Top bar
draw.rounded_rectangle([frame_l, frame_t, frame_r, frame_t + bar_w], radius=7, fill=bar_color)
# Bottom bar
draw.rounded_rectangle([frame_l, frame_b - bar_w, frame_r, frame_b], radius=7, fill=bar_color)
# Left post
draw.rounded_rectangle([frame_l, frame_t, frame_l + bar_w, frame_b], radius=7, fill=bar_color)
# Right post
draw.rounded_rectangle([frame_r - bar_w, frame_t, frame_r, frame_b], radius=7, fill=bar_color)

# Horizontal rods (5 rods across the frame)
rod_color = "#666666"
rod_h = 6
num_rods = 5
usable_h = frame_b - frame_t - bar_w * 2
spacing = usable_h / (num_rods + 1)

rod_y_positions = []
for i in range(num_rods):
    y = frame_t + bar_w + spacing * (i + 1)
    rod_y_positions.append(y)
    draw.rounded_rectangle(
        [frame_l + bar_w, y - rod_h // 2, frame_r - bar_w, y + rod_h // 2],
        radius=3, fill=rod_color,
    )

# Beads on rods — different positions for visual interest
# Each row: list of x-positions (as fractions 0-1 across the rod)
bead_configs = [
    [0.10, 0.20, 0.30, 0.75, 0.85],       # row 1: 3 left, 2 right
    [0.12, 0.22, 0.60, 0.70, 0.80, 0.90],  # row 2: 2 left, 4 right
    [0.08, 0.18, 0.28, 0.38],              # row 3: 4 left
    [0.15, 0.55, 0.65, 0.75, 0.85, 0.95],  # row 4: 1 left, 5 right
    [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70],  # row 5: 7 across
]

# Bead colors — accent palette
bead_colors = [
    "#4FC3F7",  # light blue
    "#81C784",  # green
    "#FFB74D",  # amber
    "#E57373",  # red
    "#BA68C8",  # purple
]

bead_radius = 28
rod_left = frame_l + bar_w + bead_radius + 10
rod_right = frame_r - bar_w - bead_radius - 10
rod_span = rod_right - rod_left

for row_idx, (rod_y, beads, color) in enumerate(zip(rod_y_positions, bead_configs, bead_colors)):
    for frac in beads:
        bx = rod_left + rod_span * frac
        draw.ellipse(
            [bx - bead_radius, rod_y - bead_radius, bx + bead_radius, rod_y + bead_radius],
            fill=color,
        )
        # Inner highlight for depth
        highlight_r = bead_radius * 0.55
        draw.ellipse(
            [bx - highlight_r, rod_y - highlight_r - 4,
             bx + highlight_r * 0.6, rod_y + highlight_r * 0.4 - 4],
            fill=color.replace("7", "9").replace("4", "6"),  # slightly lighter
        )

out_path = "J:/abacus-meatspace/abacus_icon.png"
img.save(out_path, "PNG")
print(f"Saved {out_path} ({img.size[0]}x{img.size[1]})")
