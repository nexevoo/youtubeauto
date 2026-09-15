import os
import urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFont


def create_gradient_fallback(width: int = 1080, height: int = 1920) -> Image.Image:
    """Creates an aesthetic cinematic dark gradient if external image API is unavailable."""
    base = Image.new("RGB", (width, height), (15, 18, 28))
    draw = ImageDraw.Draw(base)
    for y in range(height):
        ratio = y / height
        r = int(18 + 45 * ratio)
        g = int(22 + 20 * ratio)
        b = int(45 + 55 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return base


def generate_thumbnail(title: str, save_path: str, add_text: bool = True) -> str:
    """
    Generates a premium 9:16 vertical thumbnail for YouTube Shorts.
    - Uses cinematic AI scenery from Pollinations AI (with instant offline fallback)
    - Strips all watermarks
    - Overlays bold, high-contrast, viral-optimized typography with 3D drop shadow
    """
    print(f"Generating professional thumbnail for: {title}")
    W, H = 1080, 1920
    img = None

    # 1. Fetch AI Background
    clean_title = title.replace(":", " ").replace("'", "").replace('"', '').strip()
    ai_prompt = (
        f"Cinematic dramatic 4K background scenery representing {clean_title}, "
        "atmospheric lighting, movie poster aesthetic, photorealistic, trending on artstation, "
        "ultra-detailed, no text, no words, no letters, no watermark."
    )
    encoded = urllib.parse.quote(ai_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={abs(hash(title)) % 99999}"

    try:
        resp = requests.get(url, timeout=35)
        if resp.status_code == 200 and len(resp.content) > 5000:
            import io
            downloaded = Image.open(io.BytesIO(resp.content)).convert("RGB")
            # Crop bottom 50px to eliminate any API watermark
            if downloaded.height > 60:
                downloaded = downloaded.crop((0, 0, downloaded.width, downloaded.height - 50))
            img = downloaded.resize((W, H), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"AI image provider notice ({e}). Generating aesthetic cinematic gradient background...")

    if img is None:
        img = create_gradient_fallback(W, H)
    else:
        img = img.resize((W, H), Image.Resampling.LANCZOS)

    if not add_text:
        img.convert("RGB").save(save_path, "JPEG", quality=95)
        return save_path

    # 2. Add top & center subtle gradient vignette for crisp text readability
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    for y in range(int(H * 0.55)):
        alpha = int(170 * (1.0 - (y / (H * 0.55)) ** 1.5))
        v_draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), vignette)

    # 3. Typography & Word Wrapping
    draw = ImageDraw.Draw(img)

    font_path = r"C:\Windows\Fonts\impact.ttf"
    if not os.path.exists(font_path):
        font_path = r"C:\Windows\Fonts\arialbd.ttf"

    raw_words = title.upper().replace("-", " ").split()
    clean_words = raw_words[:8]  # Keep first 8 words for punchy shorts thumbnail

    font_size = 110
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()

    # Word wrap lines
    lines = []
    curr = []
    max_text_width = W - 140

    for w in clean_words:
        test = " ".join(curr + [w])
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) > max_text_width and curr:
            lines.append(" ".join(curr))
            curr = [w]
        else:
            curr.append(w)
    if curr:
        lines.append(" ".join(curr))

    if len(lines) > 3:
        font_size = 90
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            font = ImageFont.load_default()
        lines = []
        curr = []
        for w in clean_words:
            test = " ".join(curr + [w])
            bbox = draw.textbbox((0, 0), test, font=font)
            if (bbox[2] - bbox[0]) > max_text_width and curr:
                lines.append(" ".join(curr))
                curr = [w]
            else:
                curr.append(w)
        if curr:
            lines.append(" ".join(curr))

    line_height = int(font_size * 1.22)
    start_y = int(H * 0.16)  # Top-third position
    stroke_w = 8

    # Render each line with 3D drop shadow, thick border, and alternating white/gold fill
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (W - line_w) // 2
        y = start_y + i * line_height

        # 3D Drop Shadow
        draw.text((x + 6, y + 8), line, font=font, fill=(0, 0, 0, 210), stroke_width=stroke_w + 2, stroke_fill=(0, 0, 0, 210))

        # Color: Alternate between White and Vibrant Golden Yellow
        fill_color = (255, 255, 255, 255) if i % 2 == 0 else (255, 220, 0, 255)

        # Thick black outline + solid fill
        draw.text((x, y), line, font=font, fill=fill_color, stroke_width=stroke_w, stroke_fill=(0, 0, 0, 255))

    # 4. Save clean final JPEG
    final_rgb = img.convert("RGB")
    final_rgb.save(save_path, "JPEG", quality=95)
    print(f"Thumbnail successfully saved to {save_path}")
    return save_path
