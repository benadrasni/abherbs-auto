"""Photo and illustration processing. No Firebase."""

import os

from PIL import Image, ImageChops, ImageFile, ExifTags

ImageFile.LOAD_TRUNCATED_IMAGES = True
RESAMPLE = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)

PHOTO_SIZE = 512
THUMB_SIZE = 128

PLATE_SIZE = (1600, 2400)
GRID_SIZE = (400, 600)
WEBP_QUALITY = 90
CREAM = (244, 239, 228)  # #f4efe4
CREAM_EDGE = (214, 200, 176)

PAGE_TREATMENT = (
    "Set the field to an aged cream 19th-century book page: warm ivory about "
    "#f4efe4, soft vignette so edges and corners are a little darker and oxidized, "
    "faint even paper tooth. Remove foxing, stains, dust specks, and scan noise; "
    "do not leave blotches. No frame, no rule, no mount, no laid-line grid, no plate-mark. "
    "Portrait 2:3. Remove all labels, captions, plate numbers, and titles. "
    "Keep the original composition; do not rearrange or restack parts."
)


def _site_author_clause(author):
    name = (author or "").strip()
    ignore = (
        " Ignore any signature or inscription printed on the original plate."
    )
    if name:
        return (
            ignore
            + " Bottom right, small brown ink, period hand, write the "
            "botanicalillustrations.org author exactly as: %s." % name
        )
    return (
        ignore
        + " No botanicalillustrations.org author is known; leave the plate unsigned."
    )


def imagine_prompt(kind="clean", author=""):
    if kind == "colorize":
        return (
            "Colour this botanical plate from the photographs. Keep the engraving’s "
            "line work and composition. Take flower and foliage colour only from the "
            "photographs; do not invent colour. Do not paste photo parts onto the drawing. "
            + PAGE_TREATMENT
            + _site_author_clause(author)
            + " Next to that author mark, add a second discreet script signature that "
            "reads exactly colored by Grok Imagine. If there is no author mark, still "
            "add colored by Grok Imagine bottom right."
        )
    if kind == "generate":
        return (
            "Paint a 19th-century colour botanical plate from the photographs. "
            "Match habit, flower, and leaf to the photos. "
            + PAGE_TREATMENT
            + " This plate is generated entirely by Imagine. Add only one signature, "
            "bottom right, small brown ink, stylish script, discreet, not a logo, "
            "that reads exactly Grok Imagine. Do not invent a historic artist mark."
        )
    return (
        "Clean up this botanical plate. "
        + PAGE_TREATMENT
        + " Cleaning is not a meaningful change of authorship. Do not add a Grok "
        "signature."
        + _site_author_clause(author)
    )


IMAGINE_CLEAN_PROMPT = imagine_prompt("clean")
IMAGINE_COLORIZE_PROMPT = imagine_prompt("colorize")
IMAGINE_GENERATE_PROMPT = imagine_prompt("generate")
IMAGINE_PROMPTS = {
    "clean": IMAGINE_CLEAN_PROMPT,
    "colorize": IMAGINE_COLORIZE_PROMPT,
    "generate": IMAGINE_GENERATE_PROMPT,
}


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
    work.save(path, "WEBP", quality=WEBP_QUALITY, method=6)
    return path


def process_photo(src, dest_512, dest_128):
    image = apply_exif(Image.open(src))
    square = crop_center_square(image)
    save_webp(square, dest_512, PHOTO_SIZE)
    save_webp(square, dest_128, THUMB_SIZE)
    return dest_512


def plate_stem(name):
    stem, ext = os.path.splitext(os.path.basename(name).split("?")[0])
    for suffix in ("@1600", "@400"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem, ext or ".webp"


def distribution_map_name(illustration_url, latin_name=None):
    """WebP basename the website derives from illustrationUrl (`distributionRel`)."""
    base = os.path.basename(illustration_url or "").split("?")[0]
    if not base and latin_name:
        base = latin_name.replace(" ", "_") + ".webp"
    stem, ext = plate_stem(base)
    if not stem:
        return ""
    return stem + "_distribution" + ext


def distribution_map_path(job_dir, illustration_url, latin_name=None):
    name = distribution_map_name(illustration_url, latin_name)
    if not job_dir or not name:
        return ""
    return os.path.join(job_dir, "media", name)


def official_plate_paths(dest):
    """Return master (@1600), grid (@400), and optional unsuffixed alias."""
    directory, name = os.path.split(dest)
    stem, ext = plate_stem(name)
    alias = None
    if "@1600" not in name and "@400" not in name:
        alias = dest
    return {
        "stem": stem,
        "master": os.path.join(directory, stem + "@1600" + ext),
        "grid": os.path.join(directory, stem + "@400" + ext),
        "alias": alias,
    }


def plate_master_name(latin_name):
    return latin_name.replace(" ", "_") + "@1600.webp"


def plate_legacy_name(latin_name):
    return latin_name.replace(" ", "_") + ".webp"


def plate_master_path(directory, latin_name):
    return os.path.join(directory, plate_master_name(latin_name))


def plate_legacy_path(directory, latin_name):
    return os.path.join(directory, plate_legacy_name(latin_name))


def sibling_plate_filenames(name):
    """@1600, @400, and unsuffixed names that are not `name` itself."""
    if not name:
        return []
    stem, ext = plate_stem(name)
    out = []
    for candidate in (stem + ext, stem + "@1600" + ext, stem + "@400" + ext):
        if candidate != os.path.basename(name):
            out.append(candidate)
    return out


def grid_filename(name):
    """Sibling @400 name, or None when the file is a legacy unsuffixed plate."""
    if not name or "@1600." not in name:
        return None
    return name.replace("@1600.", "@400.")


def grid_url(illustration_url):
    if not illustration_url or "@1600." not in illustration_url:
        return illustration_url
    return illustration_url.replace("@1600.", "@400.")


def as_rgb(image, paper=CREAM):
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, paper)
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


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


def flatten_paper(image, threshold=28, paper=CREAM):
    rgb = as_rgb(image, paper)
    sampled = _paper_color(rgb)
    cutoff = max(0, min(sampled) - 8)
    cutoff = min(cutoff, 255 - threshold)
    gray = rgb.convert("L")
    mask = gray.point(lambda value: 255 if value >= cutoff else 0)
    field = Image.new("RGB", rgb.size, paper)
    return Image.composite(field, rgb, mask)


def _content_bbox(image, paper=CREAM, margin=8, tol=16):
    rgb = as_rgb(image, paper)
    solid = Image.new("RGB", rgb.size, paper)
    diff = ImageChops.difference(rgb, solid).convert("L")
    mask = diff.point(lambda value: 255 if value > tol else 0)
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
    extrema = bottom.convert("L").getextrema()
    if extrema[0] > 200:
        return image.crop((0, 0, width, height - band))
    gray = bottom.convert("L")
    hist = gray.histogram()
    pale = sum(hist[200:])
    if pale / float(width * band) > 0.92:
        return image.crop((0, 0, width, height - band))
    return image


def pad_to_plate(image, size=PLATE_SIZE, paper=CREAM):
    rgb = as_rgb(image, paper)
    target_w, target_h = size
    width, height = rgb.size
    scale = min(target_w / float(width), target_h / float(height))
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    fitted = rgb.resize((new_w, new_h), RESAMPLE)
    canvas = Image.new("RGB", size, paper)
    canvas.paste(fitted, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return canvas


def apply_vignette(image, paper=CREAM, edge=CREAM_EDGE):
    """Soft darker edges and corners. No frame."""
    width, height = image.size
    small = Image.new("L", (80, 120), 0)
    pixels = small.load()
    inset_x = 80 * 0.18
    inset_y = 120 * 0.16
    for y in range(120):
        for x in range(80):
            nx = min(x, 79 - x) / inset_x
            ny = min(y, 119 - y) / inset_y
            t = min(1.0, min(nx, ny))
            t = t * t * (3 - 2 * t)
            pixels[x, y] = int(210 * (1 - t))
    mask = small.resize((width, height), RESAMPLE)
    overlay = Image.new("RGB", (width, height), edge)
    return Image.composite(overlay, as_rgb(image, paper), mask)


def _save_plate_webp(image, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    image.save(path, "WEBP", quality=WEBP_QUALITY, method=6)
    return path


def finish_illustration(image, dest, vignette=False):
    """Fit to 2:3 cream and write @1600 plus @400 WebPs."""
    plate = pad_to_plate(image, PLATE_SIZE, CREAM)
    if vignette:
        plate = apply_vignette(plate)
    paths = official_plate_paths(dest)
    _save_plate_webp(plate, paths["master"])
    grid = plate.resize(GRID_SIZE, RESAMPLE)
    _save_plate_webp(grid, paths["grid"])
    if paths["alias"] and os.path.abspath(paths["alias"]) != os.path.abspath(paths["master"]):
        _save_plate_webp(plate, paths["alias"])
    return paths["master"]


def clean_illustration(src, dest):
    """PIL fallback: cream flatten + caption crop + vignette. Prefer Imagine."""
    image = apply_exif(Image.open(src))
    flat = flatten_paper(image)
    trimmed = drop_caption_band(flat)
    boxed = trimmed.crop(_content_bbox(trimmed))
    return finish_illustration(boxed, dest, vignette=True)


def import_imagine_result(src, dest):
    """Install a Grok Imagine page as the official 2:3 WebPs. Do not recrop."""
    image = apply_exif(Image.open(src))
    return finish_illustration(image, dest, vignette=False)


def write_imagine_prompt(path, latin_name="", kind="clean", author=""):
    del latin_name  # kept for callers; the short prompt is used as-is
    prompt = imagine_prompt(kind, author=author)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(prompt.strip() + "\n")
    return path
