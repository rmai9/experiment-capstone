import gradio as gr

from src.ingestion.frame_extractor import extract_frames, segment_run


BOX_SELECTOR = """
() => {
    const root = document.querySelector('#first-frame-selector');
    const image = root?.querySelector('img');
    if (!root || !image) return;

    const setup = () => {
        const host = image.parentElement;
        if (!host) return;
        host.style.position = 'relative';
        host.querySelector('canvas')?.remove();

        const canvas = document.createElement('canvas');
        const bounds = image.getBoundingClientRect();
        canvas.width = bounds.width;
        canvas.height = bounds.height;
        Object.assign(canvas.style, {
            position: 'absolute', left: '0', top: '0',
            width: `${bounds.width}px`, height: `${bounds.height}px`,
            cursor: 'crosshair'
        });
        host.appendChild(canvas);

        const context = canvas.getContext('2d');
        let start = null;

        const draw = (end) => {
            context.clearRect(0, 0, canvas.width, canvas.height);
            if (!start || !end) return;
            const left = Math.min(start.x, end.x);
            const top = Math.min(start.y, end.y);
            const width = Math.abs(end.x - start.x);
            const height = Math.abs(end.y - start.y);
            context.fillStyle = 'rgba(40, 130, 255, 0.18)';
            context.strokeStyle = '#2882ff';
            context.lineWidth = 2;
            context.fillRect(left, top, width, height);
            context.strokeRect(left, top, width, height);
        };

        const point = (event) => {
            const rect = canvas.getBoundingClientRect();
            return {
                x: Math.max(0, Math.min(rect.width, event.clientX - rect.left)),
                y: Math.max(0, Math.min(rect.height, event.clientY - rect.top))
            };
        };

        canvas.onpointerdown = (event) => {
            start = point(event);
            canvas.setPointerCapture(event.pointerId);
            draw(start);
        };
        canvas.onpointermove = (event) => {
            if (start) draw(point(event));
        };
        canvas.onpointerup = (event) => {
            if (!start) return;
            const end = point(event);
            const left = Math.min(start.x, end.x) / canvas.width;
            const top = Math.min(start.y, end.y) / canvas.height;
            const right = Math.max(start.x, end.x) / canvas.width;
            const bottom = Math.max(start.y, end.y) / canvas.height;
            const field = document.querySelector('#box-data textarea, #box-data input');
            if (field && right > left && bottom > top) {
                field.value = JSON.stringify([left, top, right, bottom]);
                field.dispatchEvent(new Event('input', { bubbles: true }));
                field.dispatchEvent(new Event('change', { bubbles: true }));
            }
            start = null;
            draw(null);
        };
    };

    if (image.complete) setup();
    else image.onload = setup;
}
"""


with gr.Blocks(title="Railway Coverboard Segmentation") as demo:
	gr.Markdown("# Railway Coverboard Segmentation")
	video = gr.Video(label="Video", sources=["upload"], format=None)
	every_n = gr.Slider(
		1, 60, value=1, step=1, label="Save every Nth frame (1 = every frame)"
	)
	extract_btn = gr.Button("Extract frames", variant="primary")
	status = gr.Textbox(label="Status", interactive=False)
	first_frame = gr.Image(
		label="First extracted frame: drag around the coverboard",
		type="filepath",
		interactive=False,
		elem_id="first-frame-selector",
	)
	box_data = gr.Textbox(visible="hidden", elem_id="box-data")
	run_id = gr.Textbox(visible="hidden")
	segment_btn = gr.Button("Segment coverboard", variant="primary")

	extract_btn.click(
		extract_frames,
		inputs=[video, every_n],
		outputs=[status, first_frame, run_id],
	)
	first_frame.change(None, inputs=first_frame, js=BOX_SELECTOR)
	segment_btn.click(
		segment_run,
		inputs=[run_id, box_data],
		outputs=status,
	)
