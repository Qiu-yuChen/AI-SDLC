"""Poster Generator — SDXL text-to-image for project delivery poster.

Called via subprocess from the trellis2 conda env (torch + CUDA + diffusers).

Usage:
  /home/cqy/envs/trellis2/bin/python poster_generator.py \
      --prompt "A modern web dashboard..." \
      --output /path/to/poster.png
"""

import argparse
import sys
from pathlib import Path

SDXL_SNAPSHOT = "462165984030d82259a11f4367a4eed129e94a7b"
SDXL_PATH = str(
    Path.home()
    / ".cache/huggingface/hub/models--stabilityai--stable-diffusion-xl-base-1.0/snapshots"
    / SDXL_SNAPSHOT
)


def generate_poster(prompt: str, output_path: str) -> bool:
    """Generate a 1024x768 poster using SDXL"""
    import torch
    from diffusers import StableDiffusionXLPipeline

    pipe = StableDiffusionXLPipeline.from_pretrained(
        SDXL_PATH,
        torch_dtype=torch.float16,
        use_safetensors=True,
        local_files_only=True,
        variant="fp16",
        add_watermarker=False,
    ).to("cuda")

    pipe.enable_attention_slicing()

    poster_prompt = (
        f"{prompt}, engineering delivery poster, professional tech design, "
        f"dark theme, clean layout, blueprint style, circuit lines, "
        f"modern UI mockup background, high quality, 8k"
    )

    negative = (
        "text, letters, numbers, words, watermark, signature, label, title, "
        "subtitle, font, typography, calligraphy, ugly, blurry, low quality, "
        "distorted, messy, cartoon, anime, sketch, 2D, flat, jpeg artifacts"
    )

    image = pipe(
        prompt=poster_prompt,
        negative_prompt=negative,
        width=1024,
        height=768,
        num_inference_steps=30,
        guidance_scale=8.0,
    ).images[0]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="Poster description prompt")
    parser.add_argument("--output", required=True, help="Output PNG path")
    args = parser.parse_args()

    success = generate_poster(args.prompt, args.output)
    sys.exit(0 if success else 1)
