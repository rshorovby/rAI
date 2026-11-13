"""Углы на уже сохранённом треке. Руку задаём сами, MediaPipe её не выбирает.

    .venv/bin/python eval_pose_metrics.py
    .venv/bin/python eval_pose_metrics.py --hand left --only serve_rus

Контакты берутся из events.json прошлого прогона, поза заново не считается.
Картинки: eval_out/pose-metrics/<ролик>/contact_N.jpg. Красная точка — заданная кисть.
"""

import argparse
import json
from pathlib import Path
from typing import Optional

import numpy as np

import pose_lab
from eval_pose_lab import VIDEO_SUFFIXES, _pt, draw_skeleton

TRACK_ROOT = Path("eval_out/pose-lab/full")
VIDEO_DIR = Path("videos/fps-lab")
OUT_DIR = Path("eval_out/pose-metrics")
HAND_RU = {"right": "правая", "left": "левая"}


def find_video(stem: str) -> Optional[Path]:
    for path in VIDEO_DIR.iterdir():
        if path.stem == stem and path.suffix.lower() in VIDEO_SUFFIXES:
            return path
    return None


def annotate(cv2, frame, points, hand: str, row: dict):
    out = draw_skeleton(cv2, frame, points, hand)
    other = points[pose_lab.WRIST[pose_lab.other_side(hand)]]
    if not np.isnan(other[0]):
        cv2.circle(out, _pt(other), 8, (255, 80, 0), 2)
    _near(cv2, out, points[pose_lab.ELBOW[hand]], row.get("elbow"))
    _near(cv2, out, points[pose_lab.KNEE["left"]], row.get("knee_left"))
    _near(cv2, out, points[pose_lab.KNEE["right"]], row.get("knee_right"))
    lines = [f"hand {hand} (profile)"]
    lines.append(_pair("elbow", row.get("elbow"), row.get("elbow_other")))
    lines.append(
        f"knees L {_num(row.get('knee_left'))}  R {_num(row.get('knee_right'))}"
    )
    lines.append(f"stance {_num(row.get('stance'))} torso")
    lines.append(f"contact {_signed(row.get('contact_above_head'))} torso")
    if "toss_above_head" in row:
        lines.append(f"toss {_signed(row.get('toss_above_head'))} torso")
        lines.append(f"knee load {_num(row.get('knee_load'))}")
    _panel(cv2, out, [line for line in lines if line])
    return out


def _near(cv2, frame, point, value) -> None:
    if value is None or np.isnan(point[0]):
        return
    x, y = _pt(point)
    cv2.putText(
        frame,
        f"{value:.0f}",
        (x + 8, y - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        3,
    )
    cv2.putText(
        frame,
        f"{value:.0f}",
        (x + 8, y - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        1,
    )


def _panel(cv2, frame, lines: list) -> None:
    cv2.rectangle(frame, (0, 0), (460, 24 + 26 * len(lines)), (0, 0, 0), -1)
    for i, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (10, 22 + 26 * i),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
        )


def _num(value) -> str:
    if value is None:
        return "-"
    if abs(value) >= 10:
        return f"{value:.0f}"
    return f"{value:.2f}"


def _signed(value) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}"


def _pair(name: str, own, other) -> str:
    if own is None and other is None:
        return ""
    return f"{name} {_num(own)}  other {_num(other)}"


def render(cv2, frame, frame_t, track, row: dict, hand: str, dest: Path) -> None:
    if frame is None:
        return
    index = int(np.argmin(np.abs(track.times - frame_t)))
    image = annotate(cv2, frame, track.points[index], hand, row)
    cv2.imwrite(str(dest), image, [cv2.IMWRITE_JPEG_QUALITY, 85])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hand", default="right", choices=("right", "left"))
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    import cv2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"рука из профиля: {HAND_RU[args.hand]}")
    for events_path in sorted(TRACK_ROOT.glob("*/events.json")):
        stem = events_path.parent.name
        if args.only and stem != args.only:
            continue
        video = find_video(stem)
        track = pose_lab.load_track(events_path.parent / "track.npz")
        if video is None or track is None:
            print(f"{stem}: нет видео или трека, пропуск")
            continue
        events = json.loads(events_path.read_text(encoding="utf-8"))
        times = [contact["t"] for contact in events["contacts"]]
        scale = pose_lab.body_scale(track)
        stroke = "serve" if stem.startswith("serve") else ""
        measured = pose_lab.measure_contacts(
            track, times, args.hand, scale or 0, stroke
        )
        dest = OUT_DIR / stem
        dest.mkdir(parents=True, exist_ok=True)
        grabbed = pose_lab.grab_frames(video, times)
        for number, (row, (frame_t, frame)) in enumerate(
            zip(measured["contacts"], grabbed), start=1
        ):
            render(
                cv2,
                frame,
                frame_t,
                track,
                row,
                args.hand,
                dest / f"contact_{number}.jpg",
            )
        (dest / "metrics.json").write_text(
            json.dumps(measured, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{stem}: {len(times)} контакт(ов), разброс {measured['spread'] or '—'}")


if __name__ == "__main__":
    main()
