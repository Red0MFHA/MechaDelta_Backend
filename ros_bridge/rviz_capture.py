"""Capture only the RViz 3D/map viewport (not the Displays side panel).

Uses X11 window get_image so OpenGL content is included.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from io import BytesIO

from PIL import Image

logger = logging.getLogger("ros_bridge.rviz_capture")

_miss_logged = False


def _display() -> str:
    return os.environ.get("DISPLAY") or ":1"


def find_rviz_viewport_id() -> int | None:
    """Return the large untitled rviz2 child that is the 3D/map viewport."""
    global _miss_logged
    try:
        out = subprocess.check_output(
            ["xwininfo", "-root", "-tree"],
            text=True,
            env={**os.environ, "DISPLAY": _display()},
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        if not _miss_logged:
            logger.warning("xwininfo failed on DISPLAY=%s: %s", _display(), exc)
            _miss_logged = True
        return None

    best: tuple[int, int] | None = None  # (score, id)
    for line in out.splitlines():
        # Skip the outer chrome / titled frame that includes the side panel.
        if " - RViz" in line or ".rviz" in line:
            continue
        if '"rviz2"' not in line and "'rviz2'" not in line:
            # xwininfo prints: 0x… "rviz2": ("rviz2" "rviz2") WxH+…
            if ' "rviz2":' not in line and " rviz2" not in line.lower():
                continue
        m_id = re.search(r"0x([0-9a-fA-F]+)", line)
        m_geom = re.search(r"(\d+)x(\d+)\+", line)
        if not m_id or not m_geom:
            continue
        wid = int(m_id.group(1), 16)
        w, h = int(m_geom.group(1)), int(m_geom.group(2))
        area = w * h
        # 3D view is typically large; ignore tiny dock widgets.
        if area < 500_000:
            continue
        # Prefer wider panes (map view) over tall side stacks.
        score = area + (w - h) * 200
        if best is None or score > best[0]:
            best = (score, wid)

    if best is None:
        if not _miss_logged:
            logger.warning(
                "No RViz 3D viewport found on DISPLAY=%s (is rviz2 running?)",
                _display(),
            )
            _miss_logged = True
        return None

    _miss_logged = False
    return best[1]


def _crop_map_content(img: Image.Image, pad: float = 0.18) -> Image.Image:
    """Trim empty RViz chrome, but keep wide context so walls stay in frame."""
    small = img.resize((max(32, img.width // 4), max(32, img.height // 4)), Image.BILINEAR)
    px = small.load()
    w, h = small.size
    ys: list[int] = []
    xs: list[int] = []
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            # Prefer structure (walls/scans/robot), not the whole free-space wash.
            structured = (r < 90 and g < 90 and b < 90) or (r > 160 and g < 120 and b < 120) or (
                40 < r < 120 and 80 < g < 180 and 80 < b < 180
            )
            if structured:
                xs.append(x)
                ys.append(y)
    if len(xs) < 20:
        return img
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    sx = img.width / w
    sy = img.height / h
    # Minimum crop span ~55% of the viewport so we do not over-zoom into white floor.
    min_w = int(w * 0.55)
    min_h = int(h * 0.55)
    if x1 - x0 < min_w:
        mid = (x0 + x1) // 2
        x0, x1 = max(0, mid - min_w // 2), min(w - 1, mid + min_w // 2)
    if y1 - y0 < min_h:
        mid = (y0 + y1) // 2
        y0, y1 = max(0, mid - min_h // 2), min(h - 1, mid + min_h // 2)
    fx0 = max(0, int((x0 - (x1 - x0) * pad) * sx))
    fy0 = max(0, int((y0 - (y1 - y0) * pad) * sy))
    fx1 = min(img.width, int((x1 + (x1 - x0) * pad) * sx) + 1)
    fy1 = min(img.height, int((y1 + (y1 - y0) * pad) * sy) + 1)
    if fx1 - fx0 < 64 or fy1 - fy0 < 64:
        return img
    return img.crop((fx0, fy0, fx1, fy1))


def capture_rviz_jpeg(max_width: int = 960, quality: int = 78) -> bytes | None:
    # Import threaded Xlib before Display — required for capture from a worker thread.
    try:
        import Xlib.threaded  # noqa: F401
        from Xlib import X, display
    except ImportError:
        logger.warning("python-xlib missing; cannot capture RViz")
        return None

    wid = find_rviz_viewport_id()
    if wid is None:
        return None

    try:
        d = display.Display(_display())
        try:
            w = d.create_resource_object("window", wid)
            geom = w.get_geometry()
            if geom.width < 64 or geom.height < 64:
                return None
            raw = w.get_image(0, 0, geom.width, geom.height, X.ZPixmap, 0xFFFFFFFF)
            img = Image.frombytes("RGB", (geom.width, geom.height), raw.data, "raw", "BGRX")
            img = _crop_map_content(img)
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, max(1, int(img.height * ratio))), Image.BILINEAR)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            return buf.getvalue()
        finally:
            d.close()
    except Exception as exc:
        logger.debug("RViz capture failed: %s", exc)
        return None
