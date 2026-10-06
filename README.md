<div align="center">

# Project Title

Project Description

</div>


## Overview

Project details

### Goals

List main objectives, problems you aim to solve.

### Features

- [x] Feature 1
- [x] Feature 2
- [ ] Feature 3

### Software Stack / Technologies Used

- Language: python, 
- Framework: ...
- Database: ...
- etc...

## Quickstart

Summary for developers with links to setup, build, test instructions in wiki or docs.

### Instructions

1. Click "Use this template" on GitHub to create your private repository.
2. Clone your repo locally.
3. Fill in the metadata table above.
4. Create an initial branch (e.g., `setup`), never commit directly to `main` (unless instructed).
5. Open an Issue for each lab / feature before starting work.
6. Use Pull Requests to merge changes (each PR should reference at least one Issue).



# Commands windows
`python -m venv venv`
`venv/scripts/activate`
`pip install -r requirements.txt`
`python main.py`

# Max os
`python3 -m venv venv`
# Railway Coverboard Segmentation

This project extracts frames from a railway video, uses a prompted SAM2 video
predictor to follow a coverboard through the frame sequence, and saves masked
coverboard images. Anomaly detection is intentionally outside the current
scope.

## Pipeline

```text
video -> sampled JPEG frames -> SAM2 box prompt + video propagation -> RGBA PNG masks
```

The prompt is a bounding box around the coverboard in the first extracted
frame. SAM2 propagates that object through subsequent frames, so the box is not
reused at a fixed screen location when the coverboard moves from one side of
the track to the other.

The current UI accepts normalized coordinates in the range `0` to `1`:

```text
x1 = left / frame_width       y1 = top / frame_height
x2 = right / frame_width      y2 = bottom / frame_height
```

The box must satisfy `x1 < x2` and `y1 < y2`.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Download a SAM2 checkpoint and keep it outside Git. Set its path before
starting the app:

```bash
export SAM2_CHECKPOINT=/absolute/path/to/sam2_checkpoint.pt
export SAM2_CONFIG=configs/sam2.1/sam2.1_hiera_l.yaml
export SAM2_DEVICE=mps
venv/bin/python main.py
```

The configuration must match the downloaded checkpoint. If the package,
checkpoint, or prompt is missing, the pipeline stops with an error and does
not claim segmentation succeeded.

## Outputs

Each run receives a short ID:

```text
data/frames/<run_id>/frame_000000.jpg
data/segmented/<run_id>/frame_000000.png
artifacts/manifests/<run_id>.json
```

Segmented outputs are **masked images**, not crops. They are RGBA PNG files:
coverboard pixels retain their original color and have alpha `255`; pixels
outside the SAM2 mask are transparent. The filename preserves the original
source frame index, including when every Nth frame is selected. This format
keeps spatial context for later anomaly-detection preprocessing.

The manifest records source video and extraction settings, prompt, SAM2
configuration/checkpoint, device, output directory, saved image count, and
frame indices for which propagation returned no usable mask.

## Checks

```bash
venv/bin/python -m unittest discover -s tests -v
```

The tests cover prompt validation and masked-image persistence. Full inference
requires the SAM2 package, a checkpoint, and a real video; it is not executed
in the unit test suite.

## Remaining limitation

The first-frame bounding box is still selected manually. SAM2 video
propagation handles normal motion and side changes, but severe occlusion or
tracking loss is reported in the manifest rather than repaired automatically.
Future work can add a re-prompt workflow or a coverboard detector before
considering anomaly detection.