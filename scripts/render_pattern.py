# -*- coding: utf-8 -*-
"""
拼豆施工图渲染脚本
输入：一张图片（自动降采样 + 量化到 Hama 色板），或一份已做好的网格 JSON。
输出：施工图 PNG（坐标网格 + 色号标注 + 底部色卡 + 统计 + 采购清单），并在 stdout 打印文字清单。

用法：
  python render_pattern.py --image 输入图.png --cols 32 --rows 32 --out 图纸.png
  python render_pattern.py --grid grid.json --out 图纸.png
"""
import argparse, json, os, math, sys
from PIL import Image, ImageDraw, ImageFont

# ---------- Hama 5mm 色板（与 references/hama-color-chart.md 一致） ----------
PALETTE = [
    ("01", "White",   "白",   (255,255,255)),
    ("02", "Black",   "黑",   (28,28,28)),
    ("03", "Cream",   "奶油", (245,235,205)),
    ("04", "Yellow",  "黄",   (255,214,0)),
    ("05", "Orange",  "橙",   (245,130,30)),
    ("06", "Red",     "红",   (215,40,40)),
    ("07", "Pink",    "粉",   (245,150,175)),
    ("08", "Fuchsia", "紫红", (190,60,150)),
    ("09", "Purple",  "紫",   (120,80,175)),
    ("10", "Blue",    "蓝",   (55,110,200)),
    ("11", "LightBlue","浅蓝",(130,190,230)),
    ("12", "Green",   "绿",   (60,150,80)),
    ("13", "LightGreen","浅绿",(150,210,130)),
    ("14", "Brown",   "棕",   (120,75,45)),
    ("15", "Grey",    "灰",   (150,150,155)),
    ("16", "DarkGrey","深灰", (80,80,85)),
    ("17", "Beige",   "米色", (215,190,150)),
    ("18", "Apricot", "杏",   (245,190,140)),
    ("19", "Coral",   "珊瑚", (240,110,95)),
    ("20", "Rose",    "玫瑰", (200,90,110)),
    ("21", "Lilac",   "淡紫", (190,170,215)),
    ("22", "Turquoise","青",  (60,175,175)),
    ("23", "DarkBlue","深蓝", (35,55,120)),
    ("24", "DarkGreen","深绿",(35,90,55)),
    ("25", "Gold",    "金",   (205,160,60)),
    ("26", "Silver",  "银",   (190,190,195)),
    ("27", "RedBrown","红棕", (130,60,50)),
    ("28", "Sand",    "沙色", (200,175,130)),
    ("29", "Mint",    "薄荷", (170,225,200)),
    ("30", "Peach",   "桃色", (250,200,180)),
]
PAL = {c[0]: {"name": c[1], "cn": c[2], "rgb": c[3]} for c in PALETTE}
EMPTY = "--"

def nearest(rgb):
    r, g, b = rgb[:3]
    best, bd = None, 1e18
    for code, _, _, prgb in PALETTE:
        d = (r-prgb[0])**2 + (g-prgb[1])**2 + (b-prgb[2])**2
        if d < bd:
            bd, best = d, code
    return best

def load_font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def image_to_grid(path, cols, rows, bg_tolerance=28):
    im = Image.open(path).convert("RGBA")
    im = im.resize((cols, rows), Image.LANCZOS)
    grid = []
    for y in range(rows):
        row = []
        for x in range(cols):
            r, g, b, a = im.getpixel((x, y))
            if a < 40:  # 透明
                row.append(EMPTY); continue
            # 近白背景判定（可选透明背景）
            if min(r, g, b) > 245:
                row.append(EMPTY); continue
            row.append(nearest((r, g, b)))
        grid.append(row)
    return grid

def load_grid(path):
    data = json.load(open(path, encoding="utf-8"))
    return data.get("title", "拼豆施工图"), data["grid"]

def count_beads(grid):
    counts = {}
    total = 0
    for row in grid:
        for c in row:
            if c == EMPTY: continue
            counts[c] = counts.get(c, 0) + 1
            total += 1
    return counts, total

def render(title, grid, out_path, cell=24):
    rows, cols = len(grid), len(grid[0])
    counts, total = count_beads(grid)
    used = sorted(counts.keys(), key=lambda c: -counts[c])

    # 画布尺寸
    pad = 24
    title_h = 44
    legend_h = 150
    grid_w = cols * cell
    grid_h = rows * cell
    W = pad*2 + grid_w
    H = pad + title_h + grid_h + legend_h + 60

    img = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(img)
    f_title = load_font(22, True)
    f_coord = load_font(10)
    f_cell = load_font(9)
    f_legend = load_font(11)
    f_stat = load_font(13, True)

    # 标题
    d.text((pad, 12), title, fill=(30,30,30), font=f_title)

    ox, oy = pad, pad + title_h
    # 网格
    for y in range(rows):
        for x in range(cols):
            code = grid[y][x]
            x0, y0 = ox + x*cell, oy + y*cell
            if code == EMPTY:
                d.rectangle([x0, y0, x0+cell-1, y0+cell-1], outline=(210,210,210), fill=(255,255,255))
            else:
                rgb = PAL[code]["rgb"]
                d.rectangle([x0, y0, x0+cell-1, y0+cell-1], fill=rgb, outline=(180,180,180))
                # 格内标色号（深色字用白，浅色字用黑）
                lum = 0.299*rgb[0]+0.587*rgb[1]+0.114*rgb[2]
                tc = (255,255,255) if lum < 130 else (30,30,30)
                d.text((x0+3, y0+cell//2-5), code, fill=tc, font=f_cell)
    # 外轮廓加粗
    d.rectangle([ox-1, oy-1, ox+grid_w, oy+grid_h], outline=(60,60,60), width=2)

    # 统计文字
    stat_y = oy + grid_h + 12
    stat = f"总豆数：{total}    尺寸：{cols}×{rows} 格    颜色数：{len(used)}"
    d.text((pad, stat_y), stat, fill=(30,30,30), font=f_stat)

    # 色卡图例
    ly = stat_y + 30
    col_w = (W - pad*2) // 3
    for i, code in enumerate(used):
        col = i % 3
        row_i = i // 3
        lx = pad + col*col_w
        yy = ly + row_i*34
        rgb = PAL[code]["rgb"]
        d.rectangle([lx, yy, lx+22, yy+22], fill=rgb, outline=(120,120,120))
        d.text((lx+30, yy+3), f"{code} {PAL[code]['cn']} {PAL[code]['name']} ×{counts[code]}",
                fill=(30,30,30), font=f_legend)

    img.save(out_path)

    # 文字清单 + 采购清单（stdout）
    print("="*40)
    print(f"标题：{title}")
    print(f"总豆数：{total}")
    print(f"尺寸：{cols}×{rows} 格")
    print(f"颜色总数：{len(used)}")
    print("="*40)
    print("【色卡统计表】")
    for code in used:
        print(f"  {code} | {PAL[code]['cn']} {PAL[code]['name']} | {counts[code]} 颗")
    print("="*40)
    print("【采购备货清单（多备 5%）】")
    for code in used:
        need = counts[code]
        backup = math.ceil(need * 1.05)
        print(f"  {code} | {PAL[code]['cn']} {PAL[code]['name']} | 实需 {need} | 备货 {backup}")
    print("="*40)
    print(f"施工图已保存：{out_path}")
    return {"total": total, "cols": cols, "rows": rows, "colors": len(used),
            "counts": {c: counts[c] for c in used}}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="输入图片路径")
    ap.add_argument("--grid", help="网格 JSON 路径")
    ap.add_argument("--cols", type=int, default=32)
    ap.add_argument("--rows", type=int, default=32)
    ap.add_argument("--title", default="拼豆施工图")
    ap.add_argument("--cell", type=int, default=24)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    if a.grid:
        title, grid = load_grid(a.grid)
    elif a.image:
        grid = image_to_grid(a.image, a.cols, a.rows)
        title = a.title
    else:
        print("错误：必须提供 --image 或 --grid", file=sys.stderr); sys.exit(1)

    render(title, grid, a.out, a.cell)

if __name__ == "__main__":
    main()
