# anim.py
import io
import math
import base64
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from fractions import Fraction

import requests
from PIL import Image, ImageSequence, ImageDraw, ImageChops
from apng import APNG

from utils import Config

DATA_URL_RE = re.compile(r'^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.+)$', re.I)


@dataclass
class AnimatedAsset:
    placeholder_id: str
    display_size: Tuple[int, int]          # (w, h) 按 CSS max 限制后的渲染尺寸
    frames_rgba: List[Image.Image]         # 帧图（已缩放+圆角）
    durations_frac: List[Fraction]         # 每帧时长（Fraction 秒）
    period_frac: Fraction                  # 一轮总时长（秒）
    cum_ticks: List[int]                   # 单轮内的累计“ticks”（基于公共分母）
    ticks_per_period: int                  # 单轮总 ticks


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


def _extract_frames_pillow(im: Image.Image) -> Tuple[List[Image.Image], List[int]]:
    """适配 GIF / WebP 等：返回 RGBA 帧 + 时长（ms）"""
    frames: List[Image.Image] = []
    durations: List[int] = []
    if getattr(im, "is_animated", False):
        for f in ImageSequence.Iterator(im):
            fr = f.convert("RGBA")
            dur = int(f.info.get("duration", 100))
            if dur < 10:
                dur = 10
            frames.append(fr)
            durations.append(dur)
        return frames, durations
    # 静态图
    frames = [im.convert("RGBA")]
    durations = [1000]
    return frames, durations


def _extract_apng_frames(content: bytes) -> Tuple[List[Image.Image], List[int]]:
    """使用 apng 包解析 APNG，返回 RGBA 帧 + 时长（ms）"""
    frames: List[Image.Image] = []
    durs: List[int] = []
    ap = APNG.from_bytes(content)
    for png, control in ap.frames:
        bio = io.BytesIO()
        png.save(bio)
        fr = Image.open(io.BytesIO(bio.getvalue())).convert("RGBA")
        num = control.delay_num or 1
        den = control.delay_den or 100
        ms = int(round(1000 * num / den))
        if ms < 10:
            ms = 10
        frames.append(fr)
        durs.append(ms)
    if not frames:
        # 兜底：单帧
        fr = Image.open(io.BytesIO(content)).convert("RGBA")
        frames = [fr]
        durs = [1000]
    return frames, durs


def _cap_size_to_css(orig_w: int, orig_h: int) -> Tuple[int, int]:
    """按模板 .image/.single-image max 限制等比缩放"""
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


def _limit_fraction(f: Fraction, max_den: int) -> Fraction:
    return f.limit_denominator(max_den)


def _lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b)


def _lcm_list(vals: List[int]) -> int:
    r = vals[0]
    for v in vals[1:]:
        r = _lcm(r, v)
    return r


# ----------------- 资产准备 -----------------

def prepare_animated_asset(src: str, placeholder_id: str, border_radius_px: int) -> AnimatedAsset:
    """下载并解析图片（GIF/APNG/WebP/静态），输出已缩放+圆角+时序（Fraction 秒）。"""
    content, mime = _fetch_bytes_and_mime(src)

    # 判断是否 APNG（MIME 或 PNG 头 + acTL）
    is_apng = (mime and "apng" in mime.lower()) or (content.startswith(b"\x89PNG\r\n\x1a\n") and b"acTL" in content[:512])

    if is_apng:
        frames, durs_ms = _extract_apng_frames(content)
    else:
        im = _load_pillow_image(content)
        frames, durs_ms = _extract_frames_pillow(im)

    # 渲染尺寸
    ow, oh = frames[0].size
    dw, dh = _cap_size_to_css(ow, oh)
    mask = _round_mask((dw, dh), border_radius_px)

    # 统一缩放 + 圆角
    scaled = []
    for fr in frames:
        if fr.size != (dw, dh):
            fr = fr.resize((dw, dh), resample=Image.LANCZOS)
        rounded = Image.new("RGBA", (dw, dh))
        rounded.paste(fr, (0, 0), mask)
        scaled.append(rounded)

    # 转 Fraction 秒，并限制分母，减少 LCM 爆炸
    durs_frac = [_limit_fraction(Fraction(ms, 1000), Config.APNG_MAX_DEN) for ms in durs_ms]
    period = sum(durs_frac, Fraction(0, 1))

    # 公共分母下的 ticks（单轮）
    denoms = [f.denominator for f in durs_frac]
    D = _lcm_list(denoms) if len(denoms) > 1 else denoms[0]
    # 避免过大
    if D > 65535:
        # 再次收敛分母
        durs_frac = [f.limit_denominator(65535) for f in durs_frac]
        denoms = [f.denominator for f in durs_frac]
        D = _lcm_list(denoms) if len(denoms) > 1 else denoms[0]

    cum = []
    acc = 0
    for f in durs_frac:
        acc += (f.numerator * (D // f.denominator))
        cum.append(acc)
    ticks_per_period = cum[-1] if cum else int(period * D)

    return AnimatedAsset(
        placeholder_id=placeholder_id,
        display_size=(dw, dh),
        frames_rgba=scaled,
        durations_frac=durs_frac,
        period_frac=period,
        cum_ticks=cum,
        ticks_per_period=ticks_per_period
    )


# ----------------- 事件驱动合成 -----------------

def _frame_index_at_tick(asset: AnimatedAsset, t_tick: int) -> int:
    """给定时间 tick（mod 单轮），返回当前帧索引。"""
    if asset.ticks_per_period <= 0:
        return 0
    mod_t = t_tick % asset.ticks_per_period
    # 等价查找 cum_ticks 中第一个 > mod_t 的索引
    # 线性即可（帧数不会太大），需要可改成 bisect
    for i, c in enumerate(asset.cum_ticks):
        if mod_t < c:
            return i
    return len(asset.cum_ticks) - 1


def _build_event_ticks(assets: List[AnimatedAsset], T_ticks: int) -> List[int]:
    """收集 [0, T] 内所有资产的换帧时刻（tick），并集 + 排序 + 去重。"""
    events = set([0, T_ticks])
    for a in assets:
        if a.ticks_per_period <= 0:
            continue
        # 单轮事件
        single = [0] + a.cum_ticks
        # 复制到整个周期
        rep = max(1, T_ticks // a.ticks_per_period)
        for r in range(rep):
            base = r * a.ticks_per_period
            for e in single:
                t = base + e
                if 0 < t < T_ticks:
                    events.add(t)
    out = sorted(events)
    # 护栏：最多事件数
    if len(out) > Config.TIMELINE_MAX_EVENTS:
        # 采样稀疏（均匀抽稀），但保证首尾
        keep = set([0, T_ticks])
        step = max(1, len(out) // (Config.TIMELINE_MAX_EVENTS - 2))
        for i in range(1, len(out) - 1, step):
            keep.add(out[i])
        out = sorted(keep)
    return out


def _rationalize_delay(frac_sec: Fraction) -> Tuple[int, int]:
    """将时间（秒）变为 (num, den)，误差 <= APNG_DELAY_TOL_MS；优先小分母。"""
    approx = frac_sec.limit_denominator(Config.APNG_MAX_DEN)
    # 误差阈值（秒）
    tol = Fraction(int(Config.APNG_DELAY_TOL_MS), 1000)
    if abs(approx - frac_sec) <= tol:
        return approx.numerator, approx.denominator
    # 兜底到 1/1000 s
    num = int(round(float(frac_sec) * 1000))
    den = 1000
    return num, den


def _gif_quantize_delays_ms(durations: List[Fraction]) -> List[int]:
    """将 Fraction 秒量化为 GIF 友好的毫秒：最小 20ms、10ms 对齐。"""
    out = []
    for d in durations:
        ms = float(d) * 1000.0
        ms = max(ms, Config.GIF_MIN_DELAY_MS)
        # 10ms 对齐（GIF 1/100s）
        ms = round(ms / Config.GIF_ROUND_TO_MS) * Config.GIF_ROUND_TO_MS
        out.append(int(ms))
    return out


def _images_equal(a: Image.Image, b: Image.Image) -> bool:
    """像素级相等判定。"""
    if a.size != b.size:
        return False
    diff = ImageChops.difference(a, b)
    return diff.getbbox() is None


def compose_animation_event_driven(
    base_png: bytes,
    placements: Dict[str, Tuple[int, int, int, int]],   # id -> (x, y, w, h)
    assets: List[AnimatedAsset],
    fmt: str = "APNG"
) -> bytes:
    """
    事件驱动合成：
    - 时间轴 = 所有资产换帧时刻的并集（最小必要帧）
    - 单资产总时长 = period_frac；多资产总时长 = 各 period 的 LCM（基于 ticks 实现）
    - 护栏：总时长与事件数上限，必要时做稀疏/截断
    """
    base = Image.open(io.BytesIO(base_png)).convert("RGBA")

    if not assets:
        # 无动图：输出单帧
        if fmt.upper() == "GIF":
            bio = io.BytesIO()
            base.convert("P", palette=Image.ADAPTIVE, colors=Config.GIF_COLORS).save(
                bio, format="GIF", save_all=True, loop=0, duration=1000, disposal=2
            )
            return bio.getvalue()
        else:
            a = APNG()
            b = io.BytesIO()
            base.save(b, format="PNG")
            a.append(b.getvalue(), delay=(100, 1000))
            out = io.BytesIO()
            a.save(out)
            return out.getvalue()

    # ---- 计算整个合成周期（ticks）----
    ticks_list = [max(1, a.ticks_per_period) for a in assets]
    T_ticks = ticks_list[0]
    for v in ticks_list[1:]:
        T_ticks = _lcm(T_ticks, v)

    # 护栏：总时长上限（秒）
    # 估算 tick 时长：以 period_frac / ticks_per_period
    avg_tick_sec = min(float(a.period_frac) / max(1, a.ticks_per_period) for a in assets)
    T_sec = T_ticks * avg_tick_sec
    if T_sec > Config.TIMELINE_MAX_SECONDS:
        # 截断到指定秒数（非严格 LCM，但更实用）
        T_ticks = int(Config.TIMELINE_MAX_SECONDS / avg_tick_sec)
        T_sec = T_ticks * avg_tick_sec

    # 事件集合
    events = _build_event_ticks(assets, T_ticks)
    if len(events) < 2:
        events = [0, T_ticks]

    # ---- 按事件区间合成帧 ----
    frames: List[Image.Image] = []
    durations_frac: List[Fraction] = []

    prev_img: Optional[Image.Image] = None
    for i in range(len(events) - 1):
        t0 = events[i]
        t1 = events[i + 1]
        dt_ticks = t1 - t0
        if dt_ticks <= 0:
            continue
        # 构造这一帧画面（取区间起点）
        canvas = base.copy()
        for a in assets:
            pid = a.placeholder_id
            if pid not in placements:
                continue
            x, y, w, h = placements[pid]
            idx = _frame_index_at_tick(a, t0)
            fr = a.frames_rgba[idx]
            if fr.size != (w, h):
                fr = fr.resize((w, h), resample=Image.LANCZOS)
            canvas.alpha_composite(fr, (x, y))

        # 去重：若像素一致则只累加时长
        if prev_img is not None and _images_equal(prev_img, canvas):
            durations_frac[-1] += Fraction(dt_ticks, 1) * Fraction(a.period_frac, a.ticks_per_period) / a.period_frac
            # 上式等价于 dt_ticks * avg_tick_sec；为避免浮动，改用代表性资产 a 的 tick→sec 比例
            # 更严谨：直接用 avg_tick_sec
            last = durations_frac[-1]
            durations_frac[-1] = last + Fraction(0, 1)  # 保持 Fraction 类型
        else:
            frames.append(canvas)
            # 用 avg_tick_sec 映射到秒
            dur_sec = Fraction(dt_ticks, 1) * Fraction.from_float(avg_tick_sec)
            durations_frac.append(dur_sec)
            prev_img = canvas

    # 兜底：至少 1 帧
    if not frames:
        frames = [base]
        durations_frac = [Fraction(1, 1)]

    # ---- 输出 ----
    if fmt.upper() == "GIF":
        # 时间量化（浏览器友好）
        durs_ms = _gif_quantize_delays_ms(durations_frac)

        # Pillow 写 GIF（单一调色板自适应）
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

        # 可选：gifsicle 二次优化（若存在）
        if Config.USE_GIFSICLE and shutil.which("gifsicle"):
            try:
                p = subprocess.Popen(
                    ["gifsicle", "-O3"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                out, _ = p.communicate(gif_bytes, timeout=30)
                if p.returncode == 0 and out:
                    gif_bytes = out
            except Exception:
                pass
        return gif_bytes

    # APNG：逐帧写入，精确（num/den）延时
    ap = APNG()
    for img, d in zip(frames, durations_frac):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        num, den = _rationalize_delay(d)
        ap.append(buf.getvalue(), delay=(num, den))
    out = io.BytesIO()
    ap.save(out)
    return out.getvalue()