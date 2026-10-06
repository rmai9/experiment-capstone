import contextlib
import time
import warnings
from pathlib import Path

import json
from datetime import datetime, timezone
from uuid import uuid4

import cv2
import gradio as gr
import gradio.routes
from gradio.route_utils import move_uploaded_files_to_cache as _move_to_cache

from src.segmentation.sam2_segmenter import segment_frames

PROJECT_ROOT = Path(__file__).parents[2]
FRAMES_DIR = PROJECT_ROOT / "data" / "frames"
MANIFESTS_DIR = PROJECT_ROOT / "artifacts" / "manifests"

def ensure_dirs():
	"""Create the data/frames folder if it's missing (e.g. on a fresh clone)."""
	FRAMES_DIR.mkdir(parents=True, exist_ok=True)
	MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

ensure_dirs()


def _move_to_cache_skip_existing(files, destinations):
	"""Move uploads to Gradio's cache without replacing existing files."""
	pending = []
	for src, dest in zip(files, destinations):
		if Path(dest).exists():
			with contextlib.suppress(OSError):
				Path(src).unlink(missing_ok=True)
		else:
			pending.append((src, dest))
	if pending:
		_move_to_cache(*map(list, zip(*pending)))


if hasattr(gradio.routes, "move_uploaded_files_to_cache"):
	gradio.routes.move_uploaded_files_to_cache = _move_to_cache_skip_existing
else:
	warnings.warn(
		"gradio.routes.move_uploaded_files_to_cache not found, so the upload patch is "
		"off; re-uploading the same video may fail on Windows. Check the Gradio version."
	)


def _save_frame(path, frame):
	"""Save an OpenCV frame as a JPEG."""
	ok, jpg = cv2.imencode(".jpg", frame)
	if not ok:
		raise gr.Error(f"Could not encode {path.name}")
	path.parent.mkdir(parents=True, exist_ok=True)
	try:
		path.write_bytes(jpg)
	except OSError as e:
		raise gr.Error(f"Could not write {path}: {e}") from e

def _write_manifest(run_id: str, manifest: dict) -> Path:
    """Write extraction metadata to artifacts/manifests/<run_id>.json."""
    manifest_path = MANIFESTS_DIR / f"{run_id}.json"

    try:
        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise gr.Error(f"Could not write extraction manifest: {exc}") from exc

    return manifest_path

def _validate_every_n(every_n) -> int:
    """Validate and normalize the frame-sampling interval."""
    try:
        every_n = int(every_n)
    except (TypeError, ValueError) as exc:
        raise gr.Error("Save every Nth frame must be a whole number.") from exc

    if every_n < 1:
        raise gr.Error("Save every Nth frame must be at least 1.")

    return every_n

def analyze(video_path, every_n, x1, y1, x2, y2, progress=gr.Progress()):
	"""Extract frames from a video into data/frames/<video name>_<id>/.

	Yields status and timestamp pairs while extraction is running.
	"""
	if not video_path:
		raise gr.Error("Upload a video first.")

	if not Path(video_path).is_file():
		raise gr.Error("The uploaded video file could not be found.")

	cap = cv2.VideoCapture(video_path)
	if not cap.isOpened():
		raise gr.Error("Could not open the video.")
	try:
		video = Path(video_path)
		print(f"Gradio input path: {video}")
		print(f"Gradio input size: {video.stat().st_size:,} bytes")
		run_id = uuid4().hex[:12]
		out_dir = FRAMES_DIR / run_id
		out_dir.mkdir(parents=True, exist_ok=False)

		total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
		fps = cap.get(cv2.CAP_PROP_FPS)
		if total <= 0:
			total = None
		every_n = _validate_every_n(every_n)

		index = saved = 0
		position = 0.0
		frames = []
		last_update = time.monotonic()
		while True:
			ok, frame = cap.read()

			if not ok:
				break

			position = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000

			if index % every_n == 0:
				filename = f"frame_{index:06d}.jpg"
				_save_frame(out_dir / filename, frame)

				frames.append(
					{
						"frame_index": index,
						"timestamp_seconds": round(position, 3),
						"filename": filename,
					}
				)

				saved += 1

			index += 1
			if index % 30 == 0:
				done = min(index, total) if total else index
				progress((done, total), desc="Extracting frames", unit="frames")
			if time.monotonic() - last_update >= 0.2:
				last_update = time.monotonic()
				yield gr.skip(), position
	finally:
		cap.release()

	manifest = {
    	"run_id": run_id,
    	"source_filename": video.name,
    	"created_at": datetime.now(timezone.utc).isoformat(),
    	"every_n_frames": every_n,
    	"fps": fps,
    	"reported_total_frames": total,
    	"frames_read": index,
    	"frames_saved": saved,
    	"output_directory": str(out_dir.relative_to(PROJECT_ROOT)),
    	"frames": frames,
	}

	manifest_path = _write_manifest(run_id, manifest)

	segmented_dir = PROJECT_ROOT / "data" / "segmented" / run_id
	try:
		segmentation = segment_frames(
			frames_dir=out_dir,
			output_dir=segmented_dir,
			box=(x1, y1, x2, y2),
		)
	except (OSError, ValueError, RuntimeError) as exc:
		raise gr.Error(str(exc)) from exc
	segmentation["output_directory"] = str(segmented_dir.relative_to(PROJECT_ROOT))
	manifest["segmentation"] = segmentation
	manifest_path = _write_manifest(run_id, manifest)

	status = (
	    	f"Run {run_id}: saved {segmentation['images_saved']} segmented images from "
	    	f"{saved} extracted frames to "
    	f"{out_dir.relative_to(PROJECT_ROOT)}. "
    	f"Manifest: {manifest_path.relative_to(PROJECT_ROOT)}"
	)
	if total and index < total * 0.99:
		status += (
			f". Warning: the video says it has {total} frames, so it may be"
			" truncated or corrupt."
		)
	yield status, position
