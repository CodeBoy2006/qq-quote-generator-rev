# anim.py
import io
import os
import math
import base64
import re
import shutil
import tempfile
import subprocess
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from fractions import Fraction

import requests
from PIL import Image, ImageSequence, ImageDraw, ImageChops
from apngasm_python.apngasm import APNGAsmBinder  # 使用 apngasm-python 组装 APNG

from utils import Config

DATA_URL_RE = re.compile(r'^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.+)$', re.I)


@dataclass
class AnimatedAsset:
    placeholder_id: str
    display_size: Tuple[int, int]          # (w, h) 渲染尺寸（已受 CSS max 限制）
    frames_rgba: List[Image.Image]         # 逐帧 RGBA（已缩放+圆角）
    durations_frac: List[Fraction]         # 每帧时长（单位：秒，Fraction）
    # 供事件时间线使用（基于全局分母 G 计算）
    cum_ticks: List[int]                   # 单轮内累计 ticks（整数）
    period_ticks: int                      # 单轮总 ticks（整数）


# ----------------- 基础工具 -----------------

def _is_data_url(s: str) -> Optional[re.Match]:
    if not isinstance(s, str):
        return None
    return DATA_URL_RE.match(s)


def _fetch_bytes_and_mime(src: str) -> Tuple[bytes, Optional[str]]:
    m = _is_data_url(src)
    if m:
        return base64.b64decode(m.group('data')), m.group('mime')
    resp = requests.get(src, timeout=15, stream=True)
    resp.raise_for_status()
    return resp.content, resp.headers.get('Content-Type')


def _load_pillow_image(content: bytes) -> Image.Image:
    return Image.open(io.BytesIO(content))


def _extract_frames(im: Image.Image) -> Tuple[List[Image.Image], List[int]]:
    """
    通用动图解析：GIF / APNG / WebP / ...
    返回：RGBA 帧列表 + 每帧时长（毫秒）
    """
    frames: List[Image.Image] = []
    durs_ms: List[int] = []
    if getattr(im, "is_animated", False):
        for f in ImageSequence.Iterator(im):
            fr = f.convert("RGBA")
            dur = int(f.info.get("duration", 100))
            if dur < 10:
                dur = 10
            frames.append(fr)
            durs_ms.append(dur)
        # 有些动图的最后一帧 dur 可能为 0，已在上面兜底
    else:
        frames = [im.convert("RGBA")]
        durs_ms = [1000]
    return frames, durs_ms


def _cap_size_to_css(orig_w: int, orig_h: int) -> Tuple[int, int]:
    """按模板 .image/.single-image 的 max 限制等比缩放到渲染尺寸"""
    max_w, max_h = Config.MAX_IMAGE_RENDER_W, Config.MAX_IMAGE_RENDER_H
    scale = min(max_w / orig_w if orig_w else 1, max_h / orig_h if orig_h else 1, 1)
    w = max(1, int(round(orig_w * scale)))
    h = max(1, int(round(orig_h * scale)))
    return w, h


def _round_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    w, h = size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    return mask


def _lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b)


def _lcm_list(vals: List[int]) -> int:
    r = vals[0]
    for v in vals[1:]:
        r = _lcm(r, v)
    return r


# ----------------- 资产准备 -----------------

def prepare_animated_asset(src: str, placeholder_id: str, border_radius_px: int) -> AnimatedAsset:
    """
    下载并解析图片（GIF/APNG/WebP/静态）：
    - 统一用 Pillow 提取帧与时长
    - 缩放 + 圆角一次性完成，减少合成时开销
    - 时长以 Fraction(秒) 表示，先做适度分母约束，后续再用“全局分母 G”统一量化
    """
    content, _ = _fetch_bytes_and_mime(src)
    im = _load_pillow_image(content)
    frames, durs_ms = _extract_frames(im)

    # 渲染尺寸
    ow, oh = frames[0].size
    dw, dh = _cap_size_to_css(ow, oh)
    mask = _round_mask((dw, dh), border_radius_px)

    # 缩放+圆角
    scaled: List[Image.Image] = []
    for fr in frames:
        if fr.size != (dw, dh):
            fr = fr.resize((dw, dh), resample=Image.LANCZOS)
        rounded = Image.new("RGBA", (dw, dh))
        rounded.paste(fr, (0, 0), mask)
        scaled.append(rounded)

    # 转 Fraction 秒，并限制分母（防止分母爆炸）
    durs_frac = [Fraction(ms, 1000).limit_denominator(Config.APNG_MAX_DEN) for ms in durs_ms]

    # cum_ticks & period_ticks 先占位，稍后由全局 G 统一计算（此处用空值）
    return AnimatedAsset(
        placeholder_id=placeholder_id,
        display_size=(dw, dh),
        frames_rgba=scaled,
        durations_frac=durs_frac,
        cum_ticks=[],
        period_ticks=0
    )


# ----------------- 事件驱动时间线（全局分母 G） -----------------

def _build_global_denominator(assets: List[AnimatedAsset]) -> int:
    """G = lcm(所有帧时长分母)"""
    dens = []
    for a in assets:
        for f in a.durations_frac:
            dens.append(f.denominator)
    if not dens:
        return 1000
    return _lcm_list(dens) if len(dens) > 1 else dens[0]


def _fill_ticks_with_G(assets: List[AnimatedAsset], G: int) -> None:
    """
    用全局分母 G 将每个资产的帧时长（秒）映射为整数 ticks，
    并计算 cum_ticks 与 period_ticks（单轮）。
    """
    for a in assets:
        cum = []
        acc = 0
        for f in a.durations_frac:
            # f = p/q (秒)，ticks = f * G = p * (G/q)（一定是整数，因为 G 是所有分母的 lcm）
            inc = f.numerator * (G // f.denominator)
            if inc <= 0:
                inc = 1
            acc += inc
            cum.append(acc)
        a.cum_ticks = cum
        a.period_ticks = cum[-1] if cum else 0


def _build_event_ticks(assets: List[AnimatedAsset], T_ticks: int) -> List[int]:
    """收集 [0, T_ticks] 内所有资产换帧时刻（tick）并集 + 排序 + 去重 + 限幅"""
    events = set([0, T_ticks])
    for a in assets:
        if a.period_ticks <= 0:
            continue
        single = [0] + a.cum_ticks
        rep = max(1, T_ticks // a.period_ticks)
        for r in range(rep):
            base = r * a.period_ticks
            for e in single:
                t = base + e
                if 0 < t < T_ticks:
                    events.add(t)
    out = sorted(events)
    if len(out) > Config.TIMELINE_MAX_EVENTS:
        keep = set([0, T_ticks])
        step = max(1, len(out) // (Config.TIMELINE_MAX_EVENTS - 2))
        for i in range(1, len(out) - 1, step):
            keep.add(out[i])
        out = sorted(keep)
    return out


def _images_equal(a: Image.Image, b: Image.Image) -> bool:
    if a.size != b.size:
        return False
    diff = ImageChops.difference(a, b)
    return diff.getbbox() is None


def _rationalize_delay(frac_sec: Fraction) -> Tuple[int, int]:
    """
    将时长（秒，Fraction）转换为 (num, den)：
    - 先 limit_denominator(APNG_MAX_DEN)
    - 误差容忍 APNG_DELAY_TOL_MS
    - 兜底到 1/1000 s
    """
    approx = frac_sec.limit_denominator(Config.APNG_MAX_DEN)
    tol = Fraction(int(Config.APNG_DELAY_TOL_MS), 1000)  # 容忍误差（秒）
    if abs(approx - frac_sec) <= tol:
        return approx.numerator, approx.denominator
    # 兜底（ms 精度）
    num = int(round(float(frac_sec) * 1000))
    den = 1000
    return num, den


def _gif_quantize_delays_ms(durations: List[Fraction]) -> List[int]:
    """GIF：最小 20ms，四舍五入到 10ms 网格"""
    out = []
    for d in durations:
        ms = float(d) * 1000.0
        ms = max(ms, Config.GIF_MIN_DELAY_MS)
        ms = round(ms / Config.GIF_ROUND_TO_MS) * Config.GIF_ROUND_TO_MS
        out.append(int(ms))
    return out


# ----------------- 合成（事件驱动 & 面向格式） -----------------

def compose_animation_event_driven(
    base_png: bytes,
    placements: Dict[str, Tuple[int, int, int, int]],   # id -> (x, y, w, h)
    assets: List[AnimatedAsset],
    fmt: str = "APNG"
) -> bytes:
    """
    事件驱动合成：
    - 全局分母 G 统一时间刻度；T_ticks = lcm(各资源的 period_ticks)
    - 事件点为所有换帧刻度的并集（最小必要帧）
    - 区间时长 = Δticks / G （单位：秒）
    """
    base = Image.open(io.BytesIO(base_png)).convert("RGBA")

    # 无动图：单帧输出
    if not assets:
        if fmt.upper() == "GIF":
            bio = io.BytesIO()
            base.convert("P", palette=Image.ADAPTIVE, colors=Config.GIF_COLORS).save(
                bio, format="GIF", save_all=True, loop=0, duration=1000, disposal=2
            )
            return bio.getvalue()
        # APNG（单帧）
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "one.apng")
        ap = APNGAsmBinder()
        buf = io.BytesIO()
        base.convert("RGBA").save(buf, format="PNG")
        ap.add_frame_from_png(buf.getvalue(), delay_num=100, delay_den=1000)
        ap.set_loops(0)
        ap.assemble(tmp)
        return open(tmp, "rb").read()
    # 统一刻度：全局分母 G
    G = _build_global_denominator(assets)
    _fill_ticks_with_G(assets, G)

    # 合成周期（ticks）
    periods = [max(1, a.period_ticks) for a in assets]
    T_ticks = periods[0]
    for v in periods[1:]:
        T_ticks = _lcm(T_ticks, v)

    # 周期秒数（用于护栏）
    T_sec = T_ticks / float(G)
    if T_sec > Config.TIMELINE_MAX_SECONDS:
        T_ticks = int(Config.TIMELINE_MAX_SECONDS * G)
        T_sec = T_ticks / float(G)

    # 事件集
    events = _build_event_ticks(assets, T_ticks)
    if len(events) < 2:
        events = [0, T_ticks]

    frames: List[Image.Image] = []
    durations_frac: List[Fraction] = []

    prev_img: Optional[Image.Image] = None
    for i in range(len(events) - 1):
        t0 = events[i]
        t1 = events[i + 1]
        dt_ticks = t1 - t0
        if dt_ticks <= 0:
            continue

        # 区间起点画面
        canvas = base.copy()
        for a in assets:
            pid = a.placeholder_id
            if pid not in placements:
                continue
            x, y, w, h = placements[pid]
            # 找到 t0 对应的帧索引（单轮）
            mod = a.period_ticks if a.period_ticks > 0 else 1
            t_mod = t0 % mod
            idx = 0
            for j, c in enumerate(a.cum_ticks):
                if t_mod < c:
                    idx = j
                    break
            fr = a.frames_rgba[idx]
            if fr.size != (w, h):
                fr = fr.resize((w, h), resample=Image.LANCZOS)
            canvas.alpha_composite(fr, (x, y))

        # 去重：像素一致则累加时长
        dur_sec = Fraction(dt_ticks, G)
        if prev_img is not None and _images_equal(prev_img, canvas):
            durations_frac[-1] += dur_sec
        else:
            frames.append(canvas)
            durations_frac.append(dur_sec)
            prev_img = canvas

    # 输出
    if fmt.upper() == "GIF":
        durs_ms = _gif_quantize_delays_ms(durations_frac)
        first = frames[0].convert("P", palette=Image.ADAPTIVE, colors=Config.GIF_COLORS)
        rest = [f.convert("P", palette=Image.ADAPTIVE, colors=Config.GIF_COLORS) for f in frames[1:]]
        bio = io.BytesIO()
        first.save(
            bio,
            format="GIF",
            save_all=True,
            append_images=rest,
            duration=durs_ms,
            loop=0,
            disposal=2,
        )
        gif_bytes = bio.getvalue()

        # 可选：gifsicle 二次优化（若可用）
        if Config.USE_GIFSICLE and shutil.which("gifsicle"):
            try:
                p = subprocess.Popen(["gifsicle", "-O3"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, _ = p.communicate(gif_bytes, timeout=30)
                if p.returncode == 0 and out:
                    gif_bytes = out
            except Exception:
                pass
        return gif_bytes

    # APNG（apngasm-python 组装，自动帧优化/压缩）
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "out.apng")
        ap = APNGAsmBinder()
        ap.set_loops(0)  # 0 = infinite loop
        for img, d in zip(frames, durations_frac):
            num, den = _rationalize_delay(d)  # 分数延时
            ap.add_frame_from_pillow(img.convert("RGBA"), delay_num=num, delay_den=den)
        ap.assemble(tmp)
        return open(tmp, "rb").read()