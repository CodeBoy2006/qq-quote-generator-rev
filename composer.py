import io
import math
import requests
from typing import Dict, Tuple, List

from PIL import Image, ImageSequence, ImageDraw, ImageChops

def _is_animated(img: Image.Image) -> bool:
    return getattr(img, "is_animated", False) and getattr(img, "n_frames", 1) > 1

def _dl(url: str, timeout=15) -> bytes:
    # 按要求：不做安全加固（无白名单/内网过滤）
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content

def _make_mask(size: Tuple[int, int], radius: int = 0, shape: str = 'rect') -> Image.Image:
    """生成圆角/圆形遮罩（L）"""
    w, h = size
    mask = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(mask)
    if shape == 'circle':
        draw.ellipse((0, 0, w - 1, h - 1), fill=255)
    elif radius and radius > 0:
        r = max(0, min(radius, min(w, h) // 2))
        draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    else:
        draw.rectangle((0, 0, w, h), fill=255)
    return mask

def _fit_frame(frame_rgba: Image.Image, box_w: int, box_h: int, fit: str) -> Image.Image:
    """
    返回一个 (box_w, box_h) 的 RGBA 画布，按 contain/cover 规则放置 frame_rgba。
    画布周围留透明“信箱边”或裁切到满。
    """
    W, H = frame_rgba.size
    if W == 0 or H == 0:
        return Image.new('RGBA', (box_w, box_h), (0, 0, 0, 0))

    if fit == 'cover':
        s = max(box_w / W, box_h / H)
    else:  # contain
        s = min(box_w / W, box_h / H)

    nw, nh = max(1, int(round(W * s))), max(1, int(round(H * s)))
    resized = frame_rgba.resize((nw, nh), Image.LANCZOS)

    # 居中放置
    canvas = Image.new('RGBA', (box_w, box_h), (0, 0, 0, 0))
    left = (box_w - nw) // 2
    top  = (box_h - nh) // 2
    canvas.alpha_composite(resized, (left, top))

    # 若 cover 尺寸超过盒子（理论上不会，因为我们放在更大画布），这里不再另行裁切
    return canvas

def _apply_mask_keep_alpha(rgba: Image.Image, mask: Image.Image) -> Image.Image:
    """将 mask 叠加到原 alpha（乘法），以保留源图透明度细节"""
    if rgba.mode != 'RGBA':
        rgba = rgba.convert('RGBA')
    src_a = rgba.getchannel('A')
    new_a = ImageChops.multiply(src_a, mask)
    out = rgba.copy()
    out.putalpha(new_a)
    return out

def _prepare_slot(frame: Image.Image, geom: Tuple[int, int, int, int], fit: str, radius: int, shape: str) -> Image.Image:
    """按布局准备单个图像的“槽位”图层：contain/cover + 圆角/圆形 mask"""
    x, y, w, h = geom
    fr = frame.convert('RGBA')
    slot = _fit_frame(fr, w, h, fit)
    mask = _make_mask((w, h), radius=radius, shape=shape)
    slot = _apply_mask_keep_alpha(slot, mask)
    return slot

def compose_png(background_png_bytes: bytes, layout: Dict) -> bytes:
    """动图取首帧，叠到背景上，输出静态 PNG（支持圆角/圆形，contain/cover）"""
    bg = Image.open(io.BytesIO(background_png_bytes)).convert('RGBA')
    canvas = bg.copy()

    for it in layout.get('items', []):
        src = it.get('src')
        if not src:
            continue
        x, y, w, h = map(int, (it['x'], it['y'], it['w'], it['h']))
        fit = it.get('fit', 'contain')
        radius = int(it.get('radius', 0) or 0)
        shape = it.get('shape', 'rect')

        raw = _dl(src)
        img = Image.open(io.BytesIO(raw))
        if _is_animated(img):
            img.seek(0)  # 取首帧
        slot = _prepare_slot(img, (x, y, w, h), fit, radius, shape)
        canvas.alpha_composite(slot, (x, y))

    out = io.BytesIO()
    canvas.save(out, format='PNG', optimize=True)
    return out.getvalue()

def compose_apng(background_png_bytes: bytes, layout: Dict) -> bytes:
    """
    多动图叠加导出 APNG。
    - 静态图：转为单帧（超长时长）；
    - 动图：逐帧展开，保留各自帧间隔；
    - 输出帧间隔为所有帧时长的 gcd，时轴齐步推进；
    - 圆角/圆形 + contain/cover 生效。
    """
    bg = Image.open(io.BytesIO(background_png_bytes)).convert('RGBA')

    # 预加载资源
    items = []
    for it in layout.get('items', []):
        src = it.get('src')
        if not src:
            continue
        raw = _dl(src)
        img = Image.open(io.BytesIO(raw))
        items.append({
            'geom': (int(it['x']), int(it['y']), int(it['w']), int(it['h'])),
            'fit': it.get('fit', 'contain'),
            'radius': int(it.get('radius', 0) or 0),
            'shape': it.get('shape', 'rect'),
            'img': img
        })

    # 全静态 → 退化为 PNG
    if all(not _is_animated(it['img']) for it in items):
        return compose_png(background_png_bytes, layout)

    # 展开动画
    anims = []
    for it in items:
        img = it['img']
        geom = it['geom']
        fit = it['fit']
        radius = it['radius']
        shape = it['shape']

        if _is_animated(img):
            frames, durations = [], []
            for f in ImageSequence.Iterator(img):
                fr = f.convert('RGBA')
                frames.append(fr)
                # Pillow 的 duration 单位是毫秒；兜底 100ms
                durations.append(max(10, int(f.info.get('duration', img.info.get('duration', 100)))))
            total = sum(durations)
        else:
            frames = [img.convert('RGBA')]
            durations = [10 ** 9]  # 近似“无限长”，只为对齐用
            total = durations[0]

        anims.append({
            'geom': geom, 'fit': fit, 'radius': radius, 'shape': shape,
            'frames': frames, 'durations': durations, 'total': total
        })

    # 时间基（gcd）
    def gcd_list(ns: List[int]) -> int:
        g = ns[0]
        for n in ns[1:]:
            g = math.gcd(g, n)
        return max(10, g)

    base = gcd_list([d for a in anims for d in a['durations']])

    # 总时长（避免失控：限制在 15s 内；没有循环信息就给个默认 4s）
    total_ms_candidates = []
    for a in anims:
        total_ms_candidates.append(a['total'] if a['total'] < 10 ** 8 else 4000)
    total_ms = min(max(total_ms_candidates or [4000]), 15000)

    frames_out, durations_out = [], []
    t = 0
    while t < total_ms:
        canvas = bg.copy()
        for a in anims:
            x, y, w, h = a['geom']
            fit, radius, shape = a['fit'], a['radius'], a['shape']

            if len(a['frames']) == 1:
                f = a['frames'][0]
            else:
                tt = t % a['total']
                acc = 0
                idx = 0
                for i, d in enumerate(a['durations']):
                    acc += d
                    if tt < acc:
                        idx = i
                        break
                f = a['frames'][idx]

            slot = _prepare_slot(f, (x, y, w, h), fit, radius, shape)
            canvas.alpha_composite(slot, (x, y))

        frames_out.append(canvas)
        durations_out.append(base)
        t += base

    out = io.BytesIO()
    # 用 PNG 编码 + save_all 形成 APNG（Pillow 支持）
    frames_out[0].save(
        out,
        format='PNG',
        save_all=True,
        append_images=frames_out[1:],
        duration=durations_out,
        loop=0,
        optimize=False
    )
    return out.getvalue()