import io
import requests
from PIL import Image, ImageSequence

def _is_animated(img: Image.Image) -> bool:
    return getattr(img, "is_animated", False) and getattr(img, "n_frames", 1) > 1

def _dl(url: str, timeout=15) -> bytes:
    # 按要求：不做安全加固（无白名单/内网过滤）
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content

def compose_png(background_png_bytes: bytes, layout: dict) -> bytes:
    """动图取首帧，叠到背景上，输出静态 PNG"""
    bg = Image.open(io.BytesIO(background_png_bytes)).convert("RGBA")
    canvas = bg.copy()

    for it in layout.get("items", []):
        src = it.get("src")
        if not src: continue
        x, y, w, h = map(int, (it["x"], it["y"], it["w"], it["h"]))
        raw = _dl(src)
        img = Image.open(io.BytesIO(raw))
        if _is_animated(img):
            img.seek(0)  # 取第一帧
        frame = img.convert("RGBA").resize((w, h), Image.LANCZOS)
        canvas.alpha_composite(frame, (x, y))

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()

def compose_apng(background_png_bytes: bytes, layout: dict) -> bytes:
    """把多动图叠加，导出 APNG"""
    bg = Image.open(io.BytesIO(background_png_bytes)).convert("RGBA")

    # 预加载资源
    items = []
    for it in layout.get("items", []):
        if not it.get("src"): continue
        raw = _dl(it["src"])
        img = Image.open(io.BytesIO(raw))
        items.append({
            "geom": (int(it["x"]), int(it["y"]), int(it["w"]), int(it["h"])),
            "img": img
        })

    # 全静态 → 退化为 PNG
    if all(not _is_animated(it["img"]) for it in items):
        return compose_png(background_png_bytes, layout)

    # 组装时间轴
    anims = []
    for it in items:
        img = it["img"]
        if _is_animated(img):
            frames, durations = [], []
            for f in ImageSequence.Iterator(img):
                frames.append(f.convert("RGBA"))
                durations.append(max(10, int(f.info.get("duration", img.info.get("duration", 100)))))
            anims.append({"geom": it["geom"], "frames": frames, "durations": durations, "total": sum(durations)})
        else:
            anims.append({"geom": it["geom"], "frames": [img.convert("RGBA")], "durations": [10**9], "total": 10**9})

    # 时间基
    from math import gcd
    def gcd_list(ns):
        g = ns[0]
        for n in ns[1:]:
            g = gcd(g, n)
        return max(10, g)

    base = gcd_list([d for a in anims for d in a["durations"]])
    total_ms = min(max(a["total"] if a["total"] < 10**8 else 4000 for a in anims), 15000)

    frames_out, durations_out = [], []
    t = 0
    while t < total_ms:
        canvas = bg.copy()
        for a in anims:
            x, y, w, h = a["geom"]
            if len(a["frames"]) == 1:
                f = a["frames"][0]
            else:
                tt = t % a["total"]
                acc = 0
                idx = 0
                for i, d in enumerate(a["durations"]):
                    acc += d
                    if tt < acc:
                        idx = i
                        break
                f = a["frames"][idx]
            frame = f.resize((w, h), Image.LANCZOS)
            canvas.alpha_composite(frame, (x, y))
        frames_out.append(canvas)
        durations_out.append(base)
        t += base

    out = io.BytesIO()
    frames_out[0].save(out, format="PNG", save_all=True, append_images=frames_out[1:], duration=durations_out, loop=0, optimize=False)
    return out.getvalue()