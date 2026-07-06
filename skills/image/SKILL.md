---
name: image
description: Convert, resize, crop, rotate, flip, optimize, read EXIF, strip metadata, and OCR images using ImageMagick, exiftool, and Tesseract. Use when you need to transform still images, reduce file size, inspect camera metadata, remove sensitive EXIF before sharing, or extract text from screenshots and scans.
license: MIT
compatibility: Requires ImageMagick (`convert`), exiftool, and tesseract on PATH. Scripts are Python 3.11+, run via `uv run`.
metadata:
  mediaskills-category: transform
  mediaskills-binaries: convert, exiftool, tesseract
---

# Image

Still-image processing with ImageMagick, exiftool, and Tesseract. Use this skill when you need to **modify or inspect raster images** (PNG, JPEG, WebP, TIFF, etc.).

## When to use

- **This skill** — format conversion, geometry edits (resize/crop/rotate/flip), compression, EXIF read/strip, OCR.
- **`inspect`** — probe video/audio/image containers with ffprobe without changing files. Run first if you are unsure of dimensions or format.
- **`download`** — fetch remote media before local image processing.

## Gotchas

- **ImageMagick v7** — some systems expose `magick` instead of `convert`. These scripts call `convert`; install the `imagemagick` package or symlink `convert` → `magick` if needed.
- **Resize without height** — `--width 800` with no `--height` preserves aspect ratio (`800x` geometry). Specifying both forces exact dimensions (may distort).
- **Crop geometry** — `width x height + x + y` is in pixels from the top-left. Values outside the image bounds fail or return partial crops depending on ImageMagick policy.
- **Optimize outputs JPEG** — `optimize.py` always writes JPEG at quality 85 with metadata stripped. Use `convert.py` for lossless PNG/WebP output.
- **EXIF on PNG/WebP** — `read_exif.py` returns whatever exiftool finds; synthetic or ffmpeg-generated images often have minimal metadata.
- **OCR quality** — Tesseract works best on high-contrast, deskewed text. Preprocess with `convert` (grayscale, threshold) for noisy scans. Use `--lang` for non-English (e.g. `deu`, `fra`).
- **Policy restrictions** — ImageMagick `policy.xml` may block PDF/PS reads on some Linux installs. Error mentions "not authorized".

## Recipes

### Convert PNG to JPEG

```bash
uv run scripts/convert.py --input photo.png --format jpg
```

### Resize for web (max width 1200, keep aspect)

```bash
uv run scripts/resize.py --input hero.png --width 1200
```

### Crop a thumbnail from coordinates

```bash
uv run scripts/crop.py --input photo.jpg --width 400 --height 400 --x 100 --y 50
```

### Rotate 90° clockwise

```bash
uv run scripts/rotate.py --input scan.png --degrees 90
```

### Mirror horizontally

```bash
uv run scripts/flip.py --input photo.png --direction horizontal
```

### Shrink file size for sharing

```bash
uv run scripts/optimize.py --input large.png
```

### Read camera metadata before editing

```bash
uv run scripts/read_exif.py --input IMG_1234.jpg
```

### Strip GPS and camera info before upload

```bash
uv run scripts/strip_metadata.py --input IMG_1234.jpg
```

### OCR text from a screenshot

```bash
uv run scripts/ocr.py --input screenshot.png
```

## Troubleshooting

| Error / symptom | Likely cause | Action |
| --- | --- | --- |
| `convert not found` | ImageMagick not installed | Run `install-media-tools` or `brew install imagemagick` |
| `exiftool not found` | exiftool missing | `brew install exiftool` / `apt install libimage-exiftool-perl` |
| `tesseract not found` | OCR binary missing | `brew install tesseract` / `apt install tesseract-ocr` |
| `not authorized` | ImageMagick policy block | Edit `/etc/ImageMagick-*/policy.xml` or use a different input format |
| Empty OCR text | Low contrast or wrong language | Preprocess image; try `--lang` |
| Distorted resize | Both width and height set | Omit `--height` to preserve aspect ratio |

## Available scripts

| Script | Purpose |
| --- | --- |
| `scripts/convert.py` | Change image format |
| `scripts/resize.py` | Scale to width/height |
| `scripts/crop.py` | Extract rectangular region |
| `scripts/rotate.py` | Rotate by degrees |
| `scripts/flip.py` | Mirror horizontal or vertical |
| `scripts/optimize.py` | Compress to JPEG, strip metadata |
| `scripts/read_exif.py` | Read metadata as JSON |
| `scripts/strip_metadata.py` | Remove metadata, write clean copy |
| `scripts/ocr.py` | Extract text with Tesseract |

## Do not use for

- Video timeline edits (use `video-transformation`)
- PDF or vector graphics
- RAW/developed photo workflows (develop first, then `convert.py`)

## Related skills

- `inspect` — probe dimensions and format before editing
- `download` — fetch images from URLs
- `install-media-tools` — install ImageMagick, exiftool, tesseract
