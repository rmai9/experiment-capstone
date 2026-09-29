import contextlib
import time
import warnings
from pathlib import Path

import cv2
import gradio as gr
import gradio.routes
from gradio.route_utils import move_uploaded_files_to_cache as _move_to_cache

FRAMES_DIR = Path(__file__).parents[2] / "data" / "frames"


def ensure_dirs():
	"""Create the data/frames folder if it's missing (e.g. on a fresh clone)."""
	FRAMES_DIR.mkdir(parents=True, exist_ok=True)


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


def analyze(video_path, every_n, progress=gr.Progress()):
	"""Extract frames from a video into data/frames/<video name>_<id>/.

	Yields status and timestamp pairs while extraction is running.
	"""
	if not video_path:
		raise gr.Error("Upload a video first.")

	cap = cv2.VideoCapture(video_path)
	if not cap.isOpened():
		raise gr.Error("Could not open the video.")
	try:
		video = Path(video_path)
		out_dir = FRAMES_DIR / f"{video.stem}_{video.parent.name[:8]}"
		out_dir.mkdir(parents=True, exist_ok=True)
		for old in out_dir.glob("frame_*.jpg"):
			try:
				old.unlink()
			except PermissionError as e:
				raise gr.Error(
					f"Could not delete {old}. Close any program using it and try again."
				) from e

		total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
		if total <= 0:
			total = None
		every_n = int(every_n)

		index = saved = 0
		position = 0.0
		last_update = time.monotonic()
		while cap.grab():
			position = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
			if index % every_n == 0:
				ok, frame = cap.retrieve()
				if not ok:
					break
				_save_frame(out_dir / f"frame_{index:06d}.jpg", frame)
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

	status = f"Saved {saved} of {index} frames to {out_dir}"
	if total and index < total * 0.99:
		status += (
			f". Warning: the video says it has {total} frames, so it may be"
			" truncated or corrupt."
		)
	yield status, position
