import contextlib
import time
import warnings
from pathlib import Path

import cv2
import gradio as gr
import gradio.routes
from gradio.route_utils import move_uploaded_files_to_cache as _move_to_cache

FRAMES_DIR = Path(__file__).parent / "data" / "frames"


def ensure_dirs():
    """Create the data/frames folder if it's missing (e.g. on a fresh clone)."""
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)


ensure_dirs()


def _move_to_cache_skip_existing(files, destinations):
    """Gradio's upload-to-cache step, but skip files already in the cache.

    If a destination already exists (e.g. the same video uploaded again), the
    new temp upload is deleted and the cached copy is reused instead of being
    overwritten. Everything else is passed through to Gradio's original function.

    This only matters on Windows, where renaming onto an existing file fails and
    Gradio falls back to this function. On macOS/Linux the rename just replaces
    the cached file before this runs.
    """
    pending = []
    for src, dest in zip(files, destinations):
        if Path(dest).exists():
            # A locked temp file shouldn't stop the rest of the batch from moving.
            with contextlib.suppress(OSError):
                Path(src).unlink(missing_ok=True)
        else:
            pending.append((src, dest))
    if pending:
        _move_to_cache(*map(list, zip(*pending)))


# _move_to_cache comes from route_utils, which is never patched, so re-running this
# file (e.g. Gradio's reload mode) can't make the wrapper call itself.
if hasattr(gradio.routes, "move_uploaded_files_to_cache"):
    gradio.routes.move_uploaded_files_to_cache = _move_to_cache_skip_existing
else:
    warnings.warn(
        "gradio.routes.move_uploaded_files_to_cache not found, so the upload patch is "
        "off; re-uploading the same video may fail on Windows. Check the Gradio version."
    )


def _save_frame(path, frame):
    """Save a frame as a JPEG, recreating its folder if it was deleted mid-run.

    Encodes with OpenCV and writes the bytes with Python, because cv2.imwrite
    can't write to paths with non-ASCII characters (e.g. café.mp4) on Windows.
    """
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

    Args:
        video_path: Path to the uploaded video.
        every_n: Save one frame out of every N (1 saves every frame).
        progress: Gradio progress tracker, injected by Gradio.

    Yields:
        (status, position) pairs. While running, status is skipped and position
        is the current timestamp in seconds so the player can follow along; the
        final yield carries the summary message.
    """
    if not video_path:
        raise gr.Error("Upload a video first.")

    # Open the video before touching old frames, so a bad file doesn't wipe them.
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise gr.Error("Could not open the video.")
    try:
        # One subfolder per video so runs don't mix. Gradio keeps each upload in a
        # folder named by a hash of its contents; adding part of that keeps two
        # different videos both called clip.mp4 apart.
        video = Path(video_path)
        out_dir = FRAMES_DIR / f"{video.stem}_{video.parent.name[:8]}"
        out_dir.mkdir(parents=True, exist_ok=True)
        # Clear old frames from a re-run of the same video.
        for old in out_dir.glob("frame_*.jpg"):
            try:
                old.unlink()
            except PermissionError as e:
                raise gr.Error(
                    f"Could not delete {old}. Close any program using it and try again."
                ) from e

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            total = None  # some formats don't report a frame count
        every_n = int(every_n)

        index = saved = 0
        position = 0.0
        last_update = time.monotonic()
        # grab() moves to the next frame; retrieve() turns it into an image. Only
        # retrieve the frames being saved, since that's the expensive part.
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
            # Report the current timestamp a few times a second so the player can follow.
            if time.monotonic() - last_update >= 0.2:
                last_update = time.monotonic()
                yield gr.skip(), position
    finally:
        cap.release()

    status = f"Saved {saved} of {index} frames to {out_dir}"
    # The file's frame count is an estimate, so allow 1% slack before warning.
    if total and index < total * 0.99:
        status += (
            f". Warning: the video says it has {total} frames, so it may be"
            " truncated or corrupt."
        )
    yield status, position


with gr.Blocks(title="Frame Extractor") as demo:
    gr.Markdown("# Frame Extractor")
    video = gr.Video(label="Video", sources=["upload"], elem_id="input-video")
    every_n = gr.Slider(1, 60, value=1, step=1, label="Save every Nth frame (1 = every frame)")
    analyze_btn = gr.Button("Analyze", variant="primary")
    status = gr.Textbox(label="Status", interactive=False)
    position = gr.Number(visible="hidden")  # timestamp (s) extraction has reached

    # window.frameSync is an object while a run is going and null otherwise.
    # Rewind the player; it starts moving once extraction reports a position.
    analyze_btn.click(
        None,
        js="""() => {
            // Gradio ignores Analyze clicks during a run, so leave the player alone too.
            if (window.frameSync) return;
            const v = document.querySelector('#input-video video');
            if (v) { v.pause(); v.currentTime = 0; v.playbackRate = 1; }
            window.frameSync = {};
        }""",
    )
    # Once the run ends, stop following it and park the player where it stopped.
    analyze_btn.click(analyze, inputs=[video, every_n], outputs=[status, position]).then(
        None,
        inputs=position,
        js="""(t) => {
            const s = window.frameSync;
            window.frameSync = null;
            const v = document.querySelector('#input-video video');
            if (!v) return;
            v.pause(); v.playbackRate = 1;
            // Only seek if this run reported a position; otherwise t is from an old run.
            if (s && s.t != null && t != null) v.currentTime = t;
        }""",
    )

    # Keep the player at the same timestamp as the extraction: set its speed to
    # the extraction speed, plus a nudge to close any gap.
    position.change(
        None,
        inputs=position,
        js="""(t) => {
            const s = window.frameSync;
            const v = document.querySelector('#input-video video');
            // Ignore updates when no run is going, e.g. one arriving after the run ended.
            if (!s || !v || t == null) return;
            const now = performance.now();
            if (s.t == null || t <= s.t) {
                Object.assign(s, { t, now });
                v.currentTime = t; v.play(); return;
            }
            const speed = (t - s.t) / ((now - s.now) / 1000);
            Object.assign(s, { t, now });
            let drift = t - v.currentTime;
            // Too far off: jump there, and the gap is closed so drop the nudge.
            if (Math.abs(drift) > 2) { v.currentTime = t; drift = 0; }
            v.playbackRate = Math.min(16, Math.max(0.0625, speed + drift));
            if (v.paused) v.play();
        }""",
    )


if __name__ == "__main__":
    demo.launch(max_file_size=None)
