from __future__ import annotations

from typing import Any, Sequence


def frame_index_records(decoded_timestamps_sec: Sequence[float]) -> list[dict[str, Any]]:
    if not decoded_timestamps_sec:
        raise ValueError("at least one decoded timestamp is required")
    values = [float(value) for value in decoded_timestamps_sec]
    if any(right <= left for left, right in zip(values, values[1:])):
        raise ValueError("decoded timestamps must be strictly increasing")
    width = max(3, len(str(len(values) - 1)))
    return [
        {
            "frame_index": index,
            "visible_frame_label": f"F{index:0{width}d}",
            "source_timestamp_sec": timestamp,
        }
        for index, timestamp in enumerate(values)
    ]


def annotate_frames(frames: Sequence[Any], decoded_timestamps_sec: Sequence[float]) -> list[Any]:
    """Burn auditable frame indices/timestamps into copies of PIL images."""
    if len(frames) != len(decoded_timestamps_sec):
        raise ValueError("frame and timestamp counts differ")
    records = frame_index_records(decoded_timestamps_sec)
    from PIL import ImageDraw

    output = []
    for frame, record in zip(frames, records):
        image = frame.convert("RGB").copy()
        draw = ImageDraw.Draw(image)
        label = f"{record['visible_frame_label']}  source_t={record['source_timestamp_sec']:.3f}s"
        box = draw.textbbox((0, 0), label)
        width, height = box[2] - box[0], box[3] - box[1]
        draw.rectangle((0, 0, width + 8, height + 8), fill=(0, 0, 0))
        draw.text((4, 4), label, fill=(255, 255, 255))
        output.append(image)
    return output

