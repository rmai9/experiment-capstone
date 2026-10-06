"""SAM2 video propagation and masked-image persistence."""

import os
from pathlib import Path

import cv2
import numpy as np


def _settings() -> tuple[str, str, str]:
	checkpoint = os.environ.get("SAM2_CHECKPOINT", "")
	model_config = os.environ.get(
		"SAM2_CONFIG", "configs/sam2.1/sam2.1_hiera_l.yaml"
	)
	device = os.environ.get("SAM2_DEVICE", "")
	if not checkpoint:
		raise ValueError(
			"SAM2_CHECKPOINT must point to a downloaded SAM2 checkpoint."
		)
	if not Path(checkpoint).is_file():
		raise ValueError(f"SAM2 checkpoint was not found: {checkpoint}")
	if not device:
		import torch

		device = "mps" if torch.backends.mps.is_available() else "cpu"
	return model_config, checkpoint, device


def _normalize_box(box) -> tuple[float, float, float, float]:
	try:
		values = tuple(float(value) for value in box)
	except (TypeError, ValueError) as exc:
		raise ValueError("The coverboard box must contain four numbers.") from exc
	if len(values) != 4:
		raise ValueError("The coverboard box must contain four numbers.")
	x1, y1, x2, y2 = values
	if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
		raise ValueError(
			"Box coordinates must satisfy 0 <= x1 < x2 <= 1 and "
			"0 <= y1 < y2 <= 1."
		)
	return values


def _save_masked_image(source: Path, destination: Path, mask: np.ndarray) -> None:
	frame = cv2.imread(str(source), cv2.IMREAD_COLOR)
	if frame is None:
		raise OSError(f"Could not read extracted frame: {source}")
	if mask.shape != frame.shape[:2]:
		raise RuntimeError(f"SAM2 mask size does not match frame: {source.name}")

	masked = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
	masked[~mask, :3] = 0
	masked[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
	destination.parent.mkdir(parents=True, exist_ok=True)
	if not cv2.imwrite(str(destination), masked):
		raise OSError(f"Could not write segmented image: {destination}")


def segment_frames(frames_dir: Path, output_dir: Path, box) -> dict:
	"""Propagate a first-frame box through extracted frames and save masked PNGs."""
	model_config, checkpoint, device = _settings()
	normalized_box = _normalize_box(box)
	frame_paths = sorted(frames_dir.glob("frame_*.jpg"))
	if not frame_paths:
		raise ValueError(f"No extracted frames found in {frames_dir}")

	try:
		from sam2.build_sam import build_sam2_video_predictor
	except ImportError as exc:
		raise RuntimeError(
			"SAM2 is not installed. Install the SAM2 package before running segmentation."
		) from exc

	first = cv2.imread(str(frame_paths[0]), cv2.IMREAD_COLOR)
	if first is None:
		raise OSError(f"Could not read first extracted frame: {frame_paths[0]}")
	height, width = first.shape[:2]
	pixel_box = np.array(
		[
			normalized_box[0] * width,
			normalized_box[1] * height,
			normalized_box[2] * width,
			normalized_box[3] * height,
		],
		dtype=np.float32,
	)

	predictor = build_sam2_video_predictor(model_config, checkpoint, device=device)
	state = predictor.init_state(video_path=str(frames_dir))
	predictor.reset_state(state)
	predictor.add_new_points_or_box(
		inference_state=state,
		frame_idx=0,
		obj_id=1,
		box=pixel_box,
	)

	saved = 0
	failed_frames = []
	for frame_index, object_ids, mask_logits in predictor.propagate_in_video(state):
		source_path = frame_paths[frame_index]
		source_frame_index = int(source_path.stem.removeprefix("frame_"))
		mask_index = list(object_ids).index(1) if 1 in object_ids else None
		if mask_index is None:
			failed_frames.append(source_frame_index)
			continue
		mask = (mask_logits[mask_index] > 0).detach().cpu().numpy()
		if mask.ndim == 3:
			mask = mask[0]
		if not np.any(mask):
			failed_frames.append(source_frame_index)
			continue
		_save_masked_image(
			source_path,
			output_dir / f"{source_path.stem}.png",
			mask,
		)
		saved += 1

	return {
		"method": "sam2_video_box_propagation",
		"model_config": model_config,
		"checkpoint": checkpoint,
		"device": device,
		"prompt": {"type": "normalized_box", "coordinates": list(normalized_box)},
		"format": "RGBA PNG with transparent pixels outside the coverboard mask",
		"output_directory": str(output_dir),
		"images_saved": saved,
		"failed_frame_indices": failed_frames,
	}