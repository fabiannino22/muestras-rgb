<p align="center"><img src="recursos/icono.png" width="96" alt=""></p>

# Muestras RGB

**Turn print-ready CMYK JPG/TIFF files into light, color-accurate RGB samples for client approval — in batches, without opening Photoshop.**

[Leer en español](README.es.md) · [User guide](docs/guide.md) · [Download](#download)

![Muestras RGB](docs/img/app-en.png)

Free and open source (MIT), by [Estudio Veintidós Lab](https://estudioveintidoslab.com) (e22lab). Interface in English and Spanish.

## What it does

Drop a folder of print files and get, in a few seconds:

- **sRGB JPEG samples** sized by their longest side, at 72 dpi (or whatever you choose), light enough to email.
- **Correct color:** each file is converted from **its own embedded ICC profile** (FOGRA39, GRACoL, SWOP…) with relative colorimetric intent and black point compensation — not with a naive conversion that turns everything greenish and dull.
- **Honest warnings** instead of silent surprises:
  - a CMYK file with **no embedded profile** is skipped (or converted with the profile you choose, and flagged);
  - a TIFF with a **spot color** is converted and flagged, because the spot ink can't appear in an RGB sample.
- **Renaming:** prefix, suffix, a new name for the whole batch, numbering, and what to do if a file already exists.
- **Watermark** (text or your logo; centered, tiled or in a corner).
- **Contact sheet PDF** with every sample, its name and its print size, ready to send to the client.

![Contact sheet](docs/img/sheet-en.png)

Your original files are never modified.

## Download

| System | File |
|---|---|
| Windows 10/11 (64-bit) | [MuestrasRGB-windows-x64.zip](https://github.com/fabiannino22/muestras-rgb/releases/latest/download/MuestrasRGB-windows-x64.zip) |
| Mac with Apple chip (M1 and later) | [MuestrasRGB-macos-arm64.zip](https://github.com/fabiannino22/muestras-rgb/releases/latest/download/MuestrasRGB-macos-arm64.zip) |
| Mac with Intel processor | [MuestrasRGB-macos-x64.zip](https://github.com/fabiannino22/muestras-rgb/releases/latest/download/MuestrasRGB-macos-x64.zip) |

Nothing to install: unzip and open. The app isn't code-signed yet, so the first time:

- **Windows:** "Windows protected your PC" → *More info* → *Run anyway*.
- **macOS:** open it once, close the warning, then go to *System Settings → Privacy & Security* and click *Open Anyway*. If macOS says the app "is damaged", run `xattr -dr com.apple.quarantine "/Applications/Muestras RGB.app"` in Terminal.

The Mac versions are a **beta**: they're built and tested automatically, but haven't had much real-world use yet. Reports are welcome.

## Quick start

1. Drag your folder of print files onto the window (or click *Browse…*).
2. Set the longest side, and optionally a prefix/suffix, watermark or contact sheet.
3. Click **Convert**, then **Open output folder**.

By default the samples go to a `samples` subfolder inside your input folder. See the [user guide](docs/guide.md) for every option and an FAQ.

## Supported files

| Input | Result |
|---|---|
| CMYK JPG/TIFF with an embedded profile (8 or 16-bit; uncompressed, LZW, ZIP or JPEG-compressed TIFF; layered TIFF) | Converted from its profile to sRGB |
| TIFF with a spot color channel | Converted, with a note naming the spot color |
| TIFF with a saved alpha channel | Converted (the alpha channel is ignored) |
| CMYK with no embedded profile | Skipped with a note — or converted with a profile you choose |
| RGB / grayscale with a profile (e.g. Adobe RGB) | Converted from its profile to sRGB |
| RGB / grayscale with no profile | Assumed sRGB and resized |
| Transparent images | Flattened on white |

## Command line

The same engine is available from the terminal (requires Python 3.10+):

```
pip install -r requirements.txt
python exportar_muestras_rgb.py "path/to/folder" --lado 2000 --idioma en --hoja-contactos "Fall catalog"
python exportar_muestras_rgb.py --help
```

## Run from source / build

```
pip install -r requirements.txt
python muestras_gui.py                      # the app
python -m unittest discover tests           # tests (uses the TIFF fixtures in fixtures/)
pip install pyinstaller && python empaquetar.py   # build a package in dist/
```

Every push builds and smoke-tests the packaged app on Windows, macOS (Apple Silicon) and macOS (Intel) with GitHub Actions. Technical notes (color pipeline, verified gotchas, packaging and releases) are in [docs/tecnico.md](docs/tecnico.md) (Spanish).

## Feedback

Found a problem or have an idea? [Open an issue](https://github.com/fabiannino22/muestras-rgb/issues/new/choose) — a screenshot of the results table helps a lot.

## License

MIT © Estudio Veintidós Lab (e22lab). The packages include third-party components (Qt/PySide6 under LGPL v3, Pillow, Python, the Inter typeface under OFL); see `THIRD-PARTY-NOTICES.txt` in the download.
