"""Photo and illustration processing. No Firebase."""

import os

from PIL import Image, ImageFile, ExifTags

ImageFile.LOAD_TRUNCATED_IMAGES = True
RESAMPLE = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)

PHOTO_SIZE = 512
THUMB_SIZE = 128
ILLUSTRATION_MAX = 1024


def _orientation_tag():
    for key, name in ExifTags.TAGS.items():
        if name == "Orientation":
            return key
    return None


def apply_exif(image):
    tag = _orientation_tag()
    if tag is None:
        return image
    try:
        exif = image._getexif() or {}
        orientation = exif.get(tag)
    except Exception:
        return image
    if orientation == 3:
        return image.rotate(180, expand=True)
    if orientation == 6:
        return image.rotate(270, expand=True)
    if orientation == 8:
        return image.rotate(90, expand=True)
    return image


def crop_center_square(image):
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def save_webp(image, path, size=None):
    work = image
    if size:
        work = work.resize((size, size), RESAMPLE)
    if work.mode not in ("RGB", "RGBA"):
        work = work.convert("RGB")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    work.save(path, "WEBP", quality=90, method=6)
    return path


def process_photo(src, dest_512, dest_128):
    image = apply_exif(Image.open(src))
    square = crop_center_square(image)
    save_webp(square, dest_512, PHOTO_SIZE)
    save_webp(square, dest_128, THUMB_SIZE)
    return dest_512


def _paper_color(image, sample=12):
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = []
    for x, y in (
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
        (width // 2, 0),
        (width // 2, height - 1),
    ):
        region = rgb.crop(
            (
                max(0, x - sample),
                max(0, y - sample),
                min(width, x + sample),
                min(height, y + sample),
            )
        )
        stat = region.resize((1, 1))
        pixels.append(stat.getpixel((0, 0)))
    return tuple(sum(channel) // len(pixels) for channel in zip(*pixels))


def flatten_paper(image, threshold=28):
    rgb = image.convert("RGB")
    paper = _paper_color(rgb)
    cutoff = max(0, min(paper) - 8)
    cutoff = min(cutoff, 255 - threshold)
    gray = rgb.convert("L")
    mask = gray.point(lambda value: 255 if value >= cutoff else 0)
    white = Image.new("RGB", rgb.size, (255, 255, 255))
    return Image.composite(white, rgb, mask)


def _content_bbox(image, margin=8):
    gray = image.convert("L")
    mask = gray.point(lambda value: 0 if value > 248 else 255)
    box = mask.getbbox()
    if not box:
        return (0, 0, image.size[0], image.size[1])
    left, top, right, bottom = box
    left = max(0, left - margin)
    top = max(0, top - margin)
    right = min(image.size[0], right + margin)
    bottom = min(image.size[1], bottom + margin)
    return (left, top, right, bottom)


def drop_caption_band(image, fraction=0.08):
    """Crop a low-ink bottom strip that is usually the plate caption."""
    width, height = image.size
    band = int(height * fraction)
    if band < 8:
        return image
    bottom = image.crop((0, height - band, width, height))
    # mostly white / pale after flatten → treat as caption
    extrema = bottom.convert("L").getextrema()
    if extrema[0] > 200:
        return image.crop((0, 0, width, height - band))
    gray = bottom.convert("L")
    hist = gray.histogram()
    pale = sum(hist[200:])
    if pale / float(width * band) > 0.92:
        return image.crop((0, 0, width, height - band))
    return image


def resize_longest(image, longest=ILLUSTRATION_MAX):
    width, height = image.size
    current = max(width, height)
    if current <= longest:
        return image
    scale = longest / float(current)
    size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(size, RESAMPLE)


IMAGINE_CLEAN_PROMPT = "Clean up, make background white, remove all labels"


def finish_illustration(image, dest):
    """Shared export: flatten leftover paper, crop, resize, WebP."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    flat = flatten_paper(image, threshold=22)
    boxed = flat.crop(_content_bbox(flat))
    out = resize_longest(boxed)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    out.save(dest, "WEBP", quality=92, method=6)
    return dest


def clean_illustration(src, dest):
    """PIL fallback: paper flatten + caption crop. Prefer Imagine when available."""
    image = apply_exif(Image.open(src))
    flat = flatten_paper(image)
    trimmed = drop_caption_band(flat)
    return finish_illustration(trimmed, dest)


def import_imagine_result(src, dest):
    """Install a Grok Imagine edit as the catalog illustration WebP."""
    image = apply_exif(Image.open(src))
    return finish_illustration(image, dest)


def write_imagine_prompt(path, latin_name=""):
    del latin_name  # kept for callers; the short prompt is used as-is
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(IMAGINE_CLEAN_PROMPT.strip() + "\n")
    return path
