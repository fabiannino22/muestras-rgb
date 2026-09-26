# -*- coding: utf-8 -*-
"""
Exporta los JPG de impresion de una carpeta como muestras RGB reducidas para
aprobacion del cliente, dentro de una subcarpeta (default: "muestras").

Flujo por archivo:
  1. Lee el JPG y toma su perfil ICC INCRUSTADO como origen (tipicamente Coated
     FOGRA39 en piezas de imprenta). No se hardcodea el perfil: cada pieza aporta
     el suyo. Un CMYK sin perfil incrustado se SALTA con aviso, porque sin origen
     no hay forma honesta de convertir el color.
  2. REDIMENSIONA primero (LANCZOS, lado mayor = --lado). La conversion ICC es una
     operacion por pixel independiente, asi que reducir antes da el mismo color
     pero ~30x mas rapido que convertir los ~60 MP originales.
  3. Convierte el perfil a sRGB con littlecms (Relative Colorimetric + compensacion
     de punto negro). sRGB es el destino correcto para aprobar en pantalla: Adobe
     RGB sin gestion de color se ve saturado y enganoso para el cliente.
  4. Guarda JPEG progresivo y optimizado con el perfil sRGB incrustado y --dpi en
     los metadatos (el DPI no cambia los pixeles, solo la etiqueta).

Los originales NO se tocan: solo se escribe dentro de la subcarpeta de salida.

Uso:
    python exportar_muestras_rgb.py                          (carpeta actual)
    python exportar_muestras_rgb.py "G:\\ruta\\del\\cliente"
    python exportar_muestras_rgb.py "G:\\ruta" --lado 1600 --calidad 85 --dpi 72
"""
import argparse
import os
import time

from PIL import Image, ImageCms

# Las piezas de impresion superan el limite anti-"image bomb" de Pillow.
Image.MAX_IMAGE_PIXELS = None

perfil_srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
SRGB_BYTES = perfil_srgb.tobytes()
BPC = ImageCms.Flags.BLACKPOINTCOMPENSATION


def parse_args():
    p = argparse.ArgumentParser(
        description="JPG de impresion (CMYK) -> muestras RGB reducidas para aprobacion del cliente.",
        epilog="Ejemplo: python exportar_muestras_rgb.py \"G:\\ruta\\del\\cliente\" --lado 2000 --calidad 92 --dpi 72",
    )
    p.add_argument("carpeta", nargs="?", default=".",
                   help="Carpeta con los JPG de impresion (default: la carpeta actual)")
    p.add_argument("--subcarpeta", default="muestras",
                   help="Nombre de la subcarpeta de salida (default: muestras)")
    p.add_argument("--lado", type=int, default=2000,
                   help="Pixeles del lado mas largo de la muestra (default: 2000)")
    p.add_argument("--calidad", type=int, default=92,
                   help="Calidad JPEG de la muestra (default: 92)")
    p.add_argument("--dpi", type=int, default=72,
                   help="DPI escrito en los metadatos (default: 72)")
    return p.parse_args()


def a_rgb(img):
    """Devuelve la imagen en RGB usando su perfil incrustado como origen."""
    icc = img.info.get("icc_profile")
    if img.mode == "CMYK" and icc:
        origen = ImageCms.ImageCmsProfile(ImageCms.core.profile_frombytes(icc))
        tr = ImageCms.buildTransform(origen, perfil_srgb, "CMYK", "RGB",
                                     renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                                     flags=BPC)
        return ImageCms.applyTransform(img, tr)
    if img.mode == "RGB" and icc:
        origen = ImageCms.ImageCmsProfile(ImageCms.core.profile_frombytes(icc))
        tr = ImageCms.buildTransform(origen, perfil_srgb, "RGB", "RGB",
                                     renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                                     flags=BPC)
        return ImageCms.applyTransform(img, tr)
    # Sin perfil incrustado no hay como adivinar el origen: se asume sRGB y solo se reduce.
    return img if img.mode == "RGB" else img.convert("RGB")


def main():
    args = parse_args()
    carpeta = os.path.abspath(args.carpeta)
    destino = os.path.join(carpeta, args.subcarpeta)
    os.makedirs(destino, exist_ok=True)

    archivos = sorted(
        (os.path.join(carpeta, n) for n in os.listdir(carpeta)
         if n.lower().endswith(".jpg") and os.path.isfile(os.path.join(carpeta, n))),
        key=str.lower,
    )
    print(f"{len(archivos)} JPG en {carpeta}")
    print(f"Destino: {destino}  |  lado mayor {args.lado}px, q{args.calidad}, {args.dpi} dpi, sRGB\n")
    print(f"{'ARCHIVO':<28}{'SALIDA':>12}{'MODO':>6}  {'DPI':>7}  {'PESO':>9}  PERFIL")
    print("-" * 100)

    total = 0
    saltados = []
    t0 = time.time()
    for ruta in archivos:
        nombre = os.path.basename(ruta)
        salida = os.path.join(destino, nombre)
        with Image.open(ruta) as img:
            if img.mode not in ("RGB", "CMYK"):
                saltados.append((nombre, f"modo {img.mode} no soportado"))
                continue
            if img.mode == "CMYK" and not img.info.get("icc_profile"):
                saltados.append((nombre, "CMYK sin perfil incrustado: no se adivina el origen"))
                continue
            img.thumbnail((args.lado, args.lado), Image.LANCZOS)
            rgb = a_rgb(img)
            rgb.save(salida, "JPEG", quality=args.calidad, optimize=True, progressive=True,
                     icc_profile=SRGB_BYTES, dpi=(args.dpi, args.dpi))

        peso = os.path.getsize(salida)
        total += peso
        with Image.open(salida) as chk:
            desc = ImageCms.getProfileDescription(
                ImageCms.ImageCmsProfile(ImageCms.core.profile_frombytes(chk.info["icc_profile"]))
            ).strip() if chk.info.get("icc_profile") else "(sin perfil)"
            dpi = chk.info.get("dpi")
            dpi_txt = f"{float(dpi[0]):.0f}x{float(dpi[1]):.0f}" if dpi else "n/d"
            print(f"{nombre:<28}{f'{chk.size[0]}x{chk.size[1]}':>12}{chk.mode:>6}  "
                  f"{dpi_txt:>7}  {peso/1024:>7.0f}KB  {desc}")

    print("-" * 100)
    print(f"Total: {total/1024/1024:.1f} MB en {len(archivos)-len(saltados)} archivos, "
          f"{time.time()-t0:.0f}s")
    for nombre, motivo in saltados:
        print(f"AVISO: {nombre} no se proceso ({motivo})")


if __name__ == "__main__":
    main()
