import gradio as gr

from src.ingestion.frame_extractor import analyze


with gr.Blocks(title="Railway Coverboard Segmentation") as demo:
	gr.Markdown("# Railway Coverboard Segmentation")
	video = gr.Video(label="Video", sources=["upload"], format=None, elem_id="input-video",)
	every_n = gr.Slider(1, 60, value=1, step=1, label="Save every Nth frame (1 = every frame)")
	gr.Markdown("Coverboard box on the first frame, normalized from 0 to 1")
	with gr.Row():
		x1 = gr.Number(label="Left", minimum=0, maximum=1)
		y1 = gr.Number(label="Top", minimum=0, maximum=1)
		x2 = gr.Number(label="Right", minimum=0, maximum=1)
		y2 = gr.Number(label="Bottom", minimum=0, maximum=1)
	analyze_btn = gr.Button("Analyze", variant="primary")
	status = gr.Textbox(label="Status", interactive=False)
	position = gr.Number(visible="hidden")

	analyze_btn.click(
		None,
		js="""() => {
			if (window.frameSync) return;
			const v = document.querySelector('#input-video video');
			if (v) { v.pause(); v.currentTime = 0; v.playbackRate = 1; }
			window.frameSync = {};
		}""",
	)
	analyze_btn.click(
		analyze,
		inputs=[video, every_n, x1, y1, x2, y2],
		outputs=[status, position],
	).then(
		None,
		inputs=position,
		js="""(t) => {
			const s = window.frameSync;
			window.frameSync = null;
			const v = document.querySelector('#input-video video');
			if (!v) return;
			v.pause(); v.playbackRate = 1;
			if (s && s.t != null && t != null) v.currentTime = t;
		}""",
	)

	position.change(
		None,
		inputs=position,
		js="""(t) => {
			const s = window.frameSync;
			const v = document.querySelector('#input-video video');
			if (!s || !v || t == null) return;
			const now = performance.now();
			if (s.t == null || t <= s.t) {
				Object.assign(s, { t, now });
				v.currentTime = t; v.play(); return;
			}
			const speed = (t - s.t) / ((now - s.now) / 1000);
			Object.assign(s, { t, now });
			let drift = t - v.currentTime;
			if (Math.abs(drift) > 2) { v.currentTime = t; drift = 0; }
			v.playbackRate = Math.min(16, Math.max(0.0625, speed + drift));
			if (v.paused) v.play();
		}""",
	)
