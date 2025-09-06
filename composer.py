import io
import math
import hashlib
import requests
from typing import Dict, Tuple, List

from PIL import Image, ImageSequence, ImageDraw, ImageChops


# ------------- 基础工具 -------------
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

def _hash_rgba(img: Image.Image) -> bytes:
    """对 RGBA 图像做内容哈希，用于帧去重（无损）"""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    return hashlib.md5(img.tobytes()).digest()


# ------------- 输出：静态 PNG -------------
def compose_png(background_png_bytes: bytes, layout: Dict) -> bytes:
    """动图取首帧，叠到背景上，输出静态 PNG（支持圆角/圆形，contain/cover），无损压缩"""
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
    # 无损压缩：optimize + compress_level=9
    canvas.save(out, format='PNG', optimize=True, compress_level=9)
    return out.getvalue()


# ------------- 共享：合成帧序列（供 APNG / WebP 共用）-------------
def _compose_frames(background_png_bytes: bytes, layout: Dict) -> Tuple[List[Image.Image], List[int]]:
    """
    返回 (frames_out, durations_out)：
      - 若全静态：frames=[单帧]、durations=[1000]
      - 若存在动图：合成动画帧并按 GCD 采样；相邻相同帧去重并合并时长
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

    # 全静态 → 直接生成一帧
    if all(not _is_animated(it['img']) for it in items):
        canvas = bg.copy()
        for a in items:
            x, y, w, h = a['geom']
            slot = _prepare_slot(a['img'], (x, y, w, h), a['fit'], a['radius'], a['shape'])
            canvas.alpha_composite(slot, (x, y))
        return [canvas], [1000]  # 单帧：持续 1s（值对 PNG 无意义，对 WebP 动画判断安全）

    # 展开动画
    anims = []
    for it in items:
        img = it['img']
        if _is_animated(img):
            frames, durations = [], []
            for f in ImageSequence.Iterator(img):
                fr = f.convert('RGBA')
                frames.append(fr)
                durations.append(max(10, int(f.info.get('duration', img.info.get('duration', 100)))))
            total = sum(durations)
        else:
            frames = [it['img'].convert('RGBA')]
            durations = [10 ** 9]  # 近似“无限长”
            total = durations[0]

        anims.append({
            'geom': it['geom'], 'fit': it['fit'], 'radius': it['radius'], 'shape': it['shape'],
            'frames': frames, 'durations': durations, 'total': total
        })

    # 时间基（gcd）
    def gcd_list(ns: List[int]) -> int:
        g = ns[0]
        for n in ns[1:]:
            g = math.gcd(g, n)
        return max(10, g)

    base = gcd_list([d for a in anims for d in a['durations']])

    # 总时长上限（避免过大），无循环信息时默认 4s，上限 15s
    total_ms_candidates = []
    for a in anims:
        total_ms_candidates.append(a['total'] if a['total'] < 10 ** 8 else 4000)
    total_ms = min(max(total_ms_candidates or [4000]), 15000)

    frames_out, durations_out = [], []
    last_hash = None

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

        # 相邻帧去重：完全一致则合并时长
        hsh = _hash_rgba(canvas)
        if last_hash is not None and hsh == last_hash:
            durations_out[-1] += base
        else:
            frames_out.append(canvas)
            durations_out.append(base)
            last_hash = hsh

        t += base

    return frames_out, durations_out


# ------------- 输出：APNG -------------
def compose_apng(background_png_bytes: bytes, layout: Dict) -> bytes:
    """
    多动图叠加导出 APNG（无损），开启 PNG 优化与高压缩等级，并做帧去重。
    """
    frames_out, durations_out = _compose_frames(background_png_bytes, layout)

    # 单帧 → 退化为 PNG
    if len(frames_out) == 1:
        buf = io.BytesIO()
        frames_out[0].save(buf, format='PNG', optimize=True, compress_level=9)
        return buf.getvalue()

    out = io.BytesIO()
    frames_out[0].save(
        out,
        format='PNG',
        save_all=True,
        append_images=frames_out[1:],
        duration=durations_out,
        loop=0,
        optimize=True,          # 开启帧内优化
        compress_level=9        # 最高压缩（无损）
    )
    return out.getvalue()


# ------------- 输出：WebP（静态/动图，lossless）-------------
def compose_webp(background_png_bytes: bytes, layout: Dict) -> bytes:
    """
    生成 WebP（尽量无损）：
      - 静态：lossless=True, quality=100, method=6
      - 动图：同上，save_all=True 并携带帧时长
    """
    frames_out, durations_out = _compose_frames(background_png_bytes, layout)

    out = io.BytesIO()
    if len(frames_out) == 1:
        frames_out[0].save(
            out,
            format='WEBP',
            lossless=False,
            quality=85,
            method=6
        )
    else:
        frames_out[0].save(
            out,
            format='WEBP',
            save_all=True,
            append_images=frames_out[1:],
            duration=durations_out,
            loop=0,
            lossless=True,
            quality=100,
            method=6
        )
    return out.getvalue()