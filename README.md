# Railway Coverboard Segmentation

This project extracts frames from a railway video, uses a prompted SAM2 video
predictor to follow a coverboard, and saves segmented images. Anomaly detection
is outside the current scope.

## Scope and pipeline

```text
video -> sampled JPEG frames -> SAM2 video propagation -> masked RGBA PNGs
```

The pipeline currently supports:

- Video upload through the Gradio interface.
- OpenCV frame extraction at a configurable interval.
- SAM 2.1 Hiera Large video segmentation.
- Masked coverboard PNG output and a JSON run manifest.

It does not automatically detect coverboards and does not implement anomaly
detection.

## SAM2 model

The project pins the official SAM2 repository to commit
`2b90b9f5ceec907a1c18123530e92e794ad901a4` and uses the **SAM 2.1 Hiera Large**
variant:

```text
SAM2_CONFIG=configs/sam2.1/sam2.1_hiera_l.yaml
```

Download the matching official checkpoint:

<https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt>

Store it locally at `models/sam2.1_hiera_large.pt`. The `models/` directory is
ignored by Git.

## Setup and run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mkdir -p models
curl -L \
	-o models/sam2.1_hiera_large.pt \
	https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt

export SAM2_CHECKPOINT="$PWD/models/sam2.1_hiera_large.pt"
export SAM2_CONFIG="configs/sam2.1/sam2.1_hiera_l.yaml"
export SAM2_DEVICE="mps"
venv/bin/python main.py
```

Use `cpu` instead of `mps` when Apple Metal is unavailable. If
`SAM2_DEVICE` is omitted, the pipeline selects `mps` when available and falls
back to `cpu`.

The application stops with an error when the video, checkpoint, or prompt is
missing. It does not create placeholder segmentation outputs.

## Coverboard selection

SAM2 is a promptable segmentation model; it does not know that a particular
object is a railway coverboard without a prompt. The UI first extracts the
frames, displays the first extracted frame, and lets the user drag a bounding
box around the coverboard. The selected coordinates are normalized to the
range `0` to `1`:

```text
x1 = left / frame_width       y1 = top / frame_height
x2 = right / frame_width      y2 = bottom / frame_height
```

The box must satisfy `x1 < x2` and `y1 < y2`. The pipeline converts the box to
pixel coordinates, adds it as object `1` on frame `0`, and propagates it with
SAM2 through the extracted frame sequence. This allows a coverboard to move
from the right side of the track to the left side without reusing a fixed
screen location. Severe occlusion or tracking loss is reported in the
manifest rather than repaired automatically.

## Outputs

Each run receives a short ID:

```text
data/frames/<run_id>/000000.jpg
data/segmented/<run_id>/frame_000000.png
artifacts/manifests/<run_id>.json
```

Segmented outputs are masked images, not crops. They are RGBA PNGs: pixels
inside the SAM2 mask retain their original color and alpha `255`; pixels
outside the mask are transparent. Filenames preserve the source frame index,
including when every Nth frame is selected. This keeps spatial context for
later anomaly-detection preprocessing.

The manifest records the source video, extraction settings, prompt, model
configuration, checkpoint path, device, output directory, saved image count,
and source frame indices for which no usable mask was returned.

## Checks

Run the local tests with:

```bash
venv/bin/python -m unittest discover -s tests -v
```

The tests cover prompt validation and masked-image persistence. Full inference
requires a real video and downloaded checkpoint and is not part of the unit
test suite.

## Repository layout

```text
main.py                         Gradio application entry point
app/ui.py                       User interface and prompt inputs
src/ingestion/frame_extractor.py  Video decoding and frame manifests
src/segmentation/sam2_segmenter.py SAM2 propagation and PNG writing
data/frames/<run_id>/           Extracted JPEG frames
data/segmented/<run_id>/        Segmented RGBA PNGs
artifacts/manifests/<run_id>.json  Run metadata
tests/                          Focused unit tests
```

Future work can add an interactive re-prompt workflow or a dedicated coverboard
detector. Anomaly detection should consume the saved segmented images only
after segmentation quality has been evaluated.