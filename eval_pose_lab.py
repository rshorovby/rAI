"""Лабораторный прогон pose_lab по папке роликов. В базу и в Gemini ничего не уходит.

    .venv/bin/python eval_pose_lab.py --dir videos/fps-lab
    .venv/bin/python eval_pose_lab.py --dir videos/fps-lab --model heavy

На каждый ролик в eval_out/pose-lab/<модель>/<ролик>/: events.json, timeline.png
и contact_N.jpg (кадры за 0,15 с до контакта, контакт, через 0,15 с, со скелетом).

Разметка, если есть, — <dir>/labels.json: {"serve_rus.mov": [2.43], ...},
секунды контактов. Тогда в сводке — совпадение числа ударов и ошибка контакта.
С ключом "_timeline_fps": 30 значения — таймкод монтажки «секунды.кадры»:
5.04 — это 5 с и 4 кадра, 5,133 с.

Поза кэшируется в track.npz рядом с картинками. --fresh считает её заново.
"""

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("GLOG_minloglevel", "2")

import numpy as np  # noqa: E402

import pose_lab  # noqa: E402

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v"}
OUT_DIR = Path(__file__).resolve().parent / "eval_out" / "pose-lab"
SHEET_OFFSETS = (-0.15, 0.0, 0.15)
MATCH_SEC = 0.3
BONES = (
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (11, 23),
    (12, 24),
    (23, 24),
    (23, 25),
    (25, 27),
    (24, 26),
    (26, 28),
)


def stroke_of(path: Path) -> str:
    return "serve" if path.stem.lower().startswith("serve") else ""


def load_labels(path: Path) -> dict:
    """Секунды контактов по имени файла. Таймкод «секунды.кадры» переводится в секунды."""
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    fps = raw.pop("_timeline_fps", None)
    if not fps:
        return raw
    labels = {}
    for name, values in raw.items():
        labels[name] = [
            round(int(v) + round((v - int(v)) * 100) / fps, 3) for v in values
        ]
    return labels


def match_contacts(found: list, labels: list) -> dict:
    """Жадное сопоставление в пределах MATCH_SEC. Ошибка — по совпавшим."""
    free = list(found)
    errors = []
    for target in labels:
        if not free:
            break
        nearest = min(free, key=lambda t: abs(t - target))
        if abs(nearest - target) <= MATCH_SEC:
            errors.append(abs(nearest - target))
            free.remove(nearest)
    return {
        "labeled": len(labels),
        "found": len(found),
        "matched": len(errors),
        "within_0_1": sum(e <= 0.1 for e in errors),
        "mean_error_sec": round(float(np.mean(errors)), 3) if errors else None,
        "max_error_sec": round(float(np.max(errors)), 3) if errors else None,
    }


def draw_skeleton(cv2, frame, points: np.ndarray, dominant: str):
    out = frame.copy()
    for a, b in BONES:
        pa, pb = points[a], points[b]
        if np.isnan(pa[0]) or np.isnan(pb[0]):
            continue
        cv2.line(out, _pt(pa), _pt(pb), (0, 255, 0), 2)
    wrist = points[pose_lab.WRIST[dominant]]
    if not np.isnan(wrist[0]):
        cv2.circle(out, _pt(wrist), 7, (0, 0, 255), -1)
    return out


def contact_sheet(cv2, path: Path, report: dict, contact: dict, dest: Path) -> None:
    track = report["track"]
    times = [contact["t"] + offset for offset in SHEET_OFFSETS]
    tiles = []
    for (frame_t, frame), target in zip(pose_lab.grab_frames(path, times), times):
        if frame is None:
            continue
        index = int(np.argmin(np.abs(track.times - frame_t)))
        tile = draw_skeleton(cv2, frame, track.points[index], report["dominant"])
        label = f"{frame_t:.3f}s"
        if abs(target - contact["t"]) < 1e-6:
            label += f" CONTACT ({contact['source']})"
        cv2.putText(
            tile, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2
        )
        tiles.append(tile)
    if tiles:
        height = min(tile.shape[0] for tile in tiles)
        tiles = [tile[:height] for tile in tiles]
        cv2.imwrite(str(dest), np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 80])


def timeline(cv2, report: dict, dest: Path, labels: list) -> None:
    times = report["track"].times
    speed = report["speed"]
    width, height, pad = 1400, 320, 30
    canvas = np.full((height, width, 3), 255, np.uint8)
    span = max(float(times[-1]), 1e-3)
    top = max(float(speed.max()), 1e-3)

    def x_of(t: float) -> int:
        return int(pad + (width - 2 * pad) * t / span)

    def y_of(v: float) -> int:
        return int(height - pad - (height - 2 * pad) * v / top)

    threshold = max(pose_lab.MIN_SWING_SPEED, pose_lab.SWING_SHARE_OF_MAX * top)
    cv2.line(
        canvas, (pad, y_of(threshold)), (width - pad, y_of(threshold)), (0, 200, 255), 1
    )
    for t in report["audio_onsets"]:
        cv2.line(canvas, (x_of(t), pad), (x_of(t), height - pad), (255, 160, 0), 1)
    for t in labels:
        cv2.line(canvas, (x_of(t), pad), (x_of(t), height - pad), (0, 160, 0), 3)
    curve = np.array([[x_of(t), y_of(v)] for t, v in zip(times, speed)], np.int32)
    cv2.polylines(canvas, [curve], False, (60, 60, 60), 1)
    for contact in report["contacts"]:
        x = x_of(contact["t"])
        cv2.line(canvas, (x, pad), (x, height - pad), (0, 0, 255), 2)
    for second in range(int(span) + 1):
        cv2.putText(
            canvas,
            str(second),
            (x_of(second), height - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (0, 0, 0),
            1,
        )
    cv2.imwrite(str(dest), canvas)


def run(directory: Path, model: str, skip: list, fresh: bool = False) -> None:
    import cv2

    labels = load_labels(directory / "labels.json")
    out_root = OUT_DIR / model
    summary = {}
    errors = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in VIDEO_SUFFIXES or path.stem in skip:
            continue
        dest = out_root / path.stem
        dest.mkdir(parents=True, exist_ok=True)
        cached = None if fresh else pose_lab.load_track(dest / "track.npz")
        started = time.perf_counter()
        report = pose_lab.analyze(
            path, model=model, stroke=stroke_of(path), track=cached
        )
        elapsed = time.perf_counter() - started
        if cached is None and "track" in report:
            pose_lab.save_track(report["track"], dest / "track.npz")
        truth = labels.get(path.name, [])
        row = {
            "sec": round(elapsed, 1),
            "frames": report["frames"],
            "ms_per_frame": round(1000 * elapsed / max(report["frames"], 1), 1),
            "detected_share": report["detected_share"],
            "dominant": report.get("dominant"),
            "view": report.get("view"),
            "contacts": [c["t"] for c in report["contacts"]],
        }
        if path.name in labels:
            row["labels"] = truth
            row["vs_labels"] = match_contacts(row["contacts"], truth)
            errors.append(row["vs_labels"])
        summary[path.name] = row
        if "track" in report:
            for n, contact in enumerate(report["contacts"], 1):
                contact_sheet(cv2, path, report, contact, dest / f"contact_{n}.jpg")
            timeline(cv2, report, dest / "timeline.png", truth)
        plain = {k: v for k, v in report.items() if k not in ("track", "speed")}
        (dest / "events.json").write_text(
            json.dumps(plain, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(path.name, json.dumps(row, ensure_ascii=False))
    if errors:
        print("ИТОГО", json.dumps(_total(errors), ensure_ascii=False))
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _total(rows: list) -> dict:
    return {
        "labeled": sum(r["labeled"] for r in rows),
        "found": sum(r["found"] for r in rows),
        "matched": sum(r["matched"] for r in rows),
        "within_0_1": sum(r["within_0_1"] for r in rows),
    }


def _pt(point) -> tuple:
    return int(point[0]), int(point[1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=Path("videos/fps-lab"))
    parser.add_argument("--model", default="full", choices=("lite", "full", "heavy"))
    parser.add_argument(
        "--skip", nargs="*", default=[], help="имена роликов без расширения"
    )
    parser.add_argument("--fresh", action="store_true", help="не брать позу из кэша")
    args = parser.parse_args()
    run(args.dir, args.model, args.skip, fresh=args.fresh)


if __name__ == "__main__":
    main()
