"""Positioned OCR evidence for the desktop chat layout.

This module only reads image files. It never clicks, types, or changes windows.
The layout detector is deliberately a narrow chat-composer profile: unrecognized
layouts return missing evidence instead of guessing an action position.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import unicodedata
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class OcrLine:
    text: str
    rect: tuple[float, float, float, float]


@dataclasses.dataclass(frozen=True)
class OcrFrame:
    width: int
    height: int
    lines: tuple[OcrLine, ...] = ()
    source: str = "python-winrt-positioned-ocr"


def _normalize(text: str) -> str:
    return "".join(unicodedata.normalize("NFC", text).casefold().split())


def _target_alias(text: str) -> str:
    normalized = _normalize(text)
    return "文件传输助手" if normalized in {"filetransferassistant", "filehelper"} else normalized


def find_chat_header(frame: OcrFrame, target_name: str) -> dict:
    """Require an exact title next to the top search field, not anywhere in OCR."""
    result = {"verified": False, "header_rect": [], "method": "positioned-chat-header"}
    if not target_name.strip() or frame.width <= 0 or frame.height <= 0:
        return {**result, "error": "invalid_target_or_frame"}
    searches = [
        item for item in frame.lines
        if ("搜索" in _normalize(item.text) or _normalize(item.text) == "search")
        and item.rect[0] < frame.width * 0.45
        and item.rect[1] < min(frame.height * 0.18, 180)
    ]
    matches = []
    for item in frame.lines:
        if _target_alias(item.text) != _target_alias(target_name):
            continue
        left, top, right, bottom = item.rect
        if right <= left or bottom <= top:
            continue
        for search in searches:
            sl, st, sr, sb = search.rect
            tolerance = max(18, (sb - st) * 1.5)
            if left > max(sr + 30, frame.width * 0.25) and abs(
                (top + bottom) / 2 - (st + sb) / 2
            ) <= tolerance:
                matches.append(item)
                break
    if len(matches) != 1:
        return {**result, "error": "chat_header_not_uniquely_verified"}
    return {
        **result, "verified": True, "header_rect": list(matches[0].rect),
        "error": "",
    }


def _composer_rectangle(path: Path, frame: OcrFrame, header: dict) -> list[int]:
    from PIL import Image

    sends = [
        item for item in frame.lines
        if _normalize(item.text) in {"发送", "send"}
        and item.rect[0] > frame.width * 0.5
        and item.rect[1] > frame.height * 0.60
    ]
    if len(sends) != 1:
        return []
    left = max(0, int(header["header_rect"][0]) - 24)
    right = frame.width - 16
    start_y = max(int(frame.height * 0.5), int(header["header_rect"][3]) + 50)
    end_y = min(frame.height - 4, int(sends[0].rect[1]) - 25)
    if left >= right or start_y >= end_y:
        return []
    with Image.open(path) as original:
        if original.size != (frame.width, frame.height):
            return []
        image = original.convert("RGB")
        pixels = image.load()
        sample_x = range(left, right, 3)
        width = len(sample_x)
        border_rows = []
        for y in range(start_y, end_y):
            count = 0
            for x in sample_x:
                rgb = pixels[x, y]
                level = sum(rgb) / 3
                if max(rgb) - min(rgb) > 12 or not 100 <= level <= 249:
                    continue
                above = sum(pixels[x, y - 3]) / 3
                below = sum(pixels[x, y + 3]) / 3
                if max(abs(level - above), abs(level - below)) >= 4:
                    count += 1
            if width and count / width >= 0.65:
                border_rows.append(y)
    if not border_rows:
        return []
    top = max(border_rows)
    return [left, top, right, frame.height - 8]


def verify_chat_send(
    image_path: str | Path,
    frame: OcrFrame,
    *,
    target_name: str,
    message: str,
) -> dict:
    """Require a verified header and a marker above the visible composer border."""
    header = find_chat_header(frame, target_name)
    result = {
        "verified": False, "target_verified": header["verified"],
        "method": "positioned-chat-history-readback",
        "ocr_method": frame.source, "layout_verified": False,
        "header_rect": header["header_rect"], "composer_rect": [],
        "normalized_marker_matched": False,
        "message_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
    }
    if not header["verified"]:
        return {**result, "error": header["error"]}
    path = Path(image_path)
    if not path.is_file():
        return {**result, "error": "screenshot_missing"}
    composer = _composer_rectangle(path, frame, header)
    if not composer:
        return {**result, "error": "composer_boundary_not_verified"}
    left = composer[0]
    top = header["header_rect"][3] + 10
    bottom = composer[1]
    history = sorted(
        (item for item in frame.lines if item.rect[0] >= left
         and item.rect[1] >= top and item.rect[3] < bottom),
        key=lambda item: (item.rect[1], item.rect[0]),
    )
    observed = "".join(_normalize(item.text) for item in history)
    marker = _normalize(message)
    if message.startswith(("OPENWUKONG_", "TEST_")):
        marker = "".join(c for c in marker if c.isalnum())
        observed = "".join(c for c in observed if c.isalnum())
    matched = bool(marker and marker in observed)
    return {
        **result, "verified": matched, "layout_verified": True,
        "composer_rect": composer, "normalized_marker_matched": matched,
        "error": "" if matched else "message_not_in_chat_history",
    }


async def recognize_frame_async(image_path: str | Path) -> OcrFrame:
    """Read WinRT line/word rectangles while retaining their source coordinates."""
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    bitmap = None
    try:
        writer.write_bytes(Path(image_path).read_bytes())
        await writer.store_async()
        await writer.flush_async()
        writer.detach_stream()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("ocr_engine_unavailable")
        recognized = await engine.recognize_async(bitmap)
        lines = []
        for item in recognized.lines:
            rects = [word.bounding_rect for word in item.words]
            if rects:
                lines.append(OcrLine(str(item.text), (
                    min(r.x for r in rects), min(r.y for r in rects),
                    max(r.x + r.width for r in rects),
                    max(r.y + r.height for r in rects),
                )))
        return OcrFrame(bitmap.pixel_width, bitmap.pixel_height, tuple(lines))
    finally:
        for resource in (bitmap, writer, stream):
            close = getattr(resource, "close", None)
            if callable(close):
                close()


def recognize_frame(image_path: str | Path, *, timeout: float = 20) -> OcrFrame:
    """Synchronous entry point; async callers use recognize_frame_async directly."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(asyncio.wait_for(recognize_frame_async(image_path), timeout))
    raise RuntimeError("use_recognize_frame_async_inside_event_loop")
