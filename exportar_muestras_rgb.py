# -*- coding: utf-8 -*-
"""
Exporta los JPG/TIFF de impresion de una carpeta como muestras RGB reducidas para
aprobacion del cliente. La logica de color vive en muestras_core.py (compartida con
la interfaz grafica muestras_gui.py); este archivo es solo la version de consola.

Uso:
    python exportar_muestras_rgb.py                          (carpeta actual)
    python exportar_muestras_rgb.py "G:\\ruta\\del\\cliente"
    python exportar_muestras_rgb.py "G:\\ruta" --lado 1600 --calidad 85 --dpi 72
    python exportar_muestras_rgb.py "G:\\ruta" --salida "D:\\envios" --prefijo e22_ --sufijo _muestra
"""
import argparse
import os
import time

import hoja_contactos
import muestras_core as core
import textos
from textos import t


def parse_args():
    p = argparse.ArgumentParser(
        description="JPG/TIFF de impresion (CMYK) -> muestras RGB reducidas para aprobacion del cliente.",
        epilog="Ejemplo: python exportar_muestras_rgb.py \"G:\\ruta\\del\\cliente\" --lado 2000 --calidad 92 --dpi 72",
    )
    p.add_argument("carpeta", nargs="?", default=".",
                   help="Carpeta con los JPG/TIFF de impresion (default: la carpeta actual)")
    p.add_argument("--subcarpeta", default="muestras",
                   help="Nombre de la subcarpeta de salida dentro de carpeta (default: muestras)")
    p.add_argument("--salida", default=None,
                   help="Carpeta de salida completa; si se da, ignora --subcarpeta")
    p.add_argument("--lado", type=int, default=2000,
                   help="Pixeles del lado mas largo de la muestra (default: 2000)")
    p.add_argument("--calidad", type=int, default=92,
                   help="Calidad JPEG de la muestra (default: 92)")
    p.add_argument("--dpi", type=int, default=72,
                   help="DPI escrito en los metadatos (default: 72)")
    p.add_argument("--prefijo", default="", help="Texto antes del nombre de cada muestra")
    p.add_argument("--sufijo", default="", help="Texto despues del nombre de cada muestra")
    p.add_argument("--perfil-cmyk", default="",
                   help="Perfil .icc a asumir en los CMYK sin perfil incrustado (default: saltarlos)")
    p.add_argument("--marca-texto", default="",
                   help='Marca de agua de texto, p. ej. "MUESTRA · NO IMPRIMIR"')
    p.add_argument("--marca-logo", default="", help="Marca de agua con un logo PNG (manda sobre el texto)")
    p.add_argument("--marca-posicion", choices=core.POSICIONES_MARCA, default="centro")
    p.add_argument("--marca-opacidad", type=int, default=35, help="Opacidad de la marca en %% (default: 35)")
    p.add_argument("--hoja-contactos", metavar="TITULO", default=None,
                   help="Crea un PDF con todas las muestras y este titulo en la carpeta de salida")
    p.add_argument("--pagina", choices=tuple(hoja_contactos.PAGINAS), default="carta",
                   help="Tamano de pagina de la hoja de contactos (default: carta)")
    p.add_argument("--idioma", choices=textos.IDIOMAS, default="es",
                   help="Idioma de los avisos y de la hoja de contactos (default: es)")
    p.add_argument("--si-existe", choices=core.SI_EXISTE, default="numerar",
                   help="Si la muestra ya existe: numerar (default), sobrescribir o saltar")
    return p.parse_args()


def main():
    args = parse_args()
    carpeta = os.path.abspath(args.carpeta)
    destino = os.path.abspath(args.salida) if args.salida else os.path.join(carpeta, args.subcarpeta)
    opciones = core.Opciones(lado=args.lado, calidad=args.calidad, dpi=args.dpi,
                             prefijo=args.prefijo, sufijo=args.sufijo, si_existe=args.si_existe,
                             perfil_cmyk=args.perfil_cmyk, marca_texto=args.marca_texto,
                             marca_logo=args.marca_logo, marca_posicion=args.marca_posicion,
                             marca_opacidad=args.marca_opacidad, idioma=args.idioma)
    textos.usar(args.idioma)

    if args.perfil_cmyk and not core.es_perfil_cmyk(args.perfil_cmyk):
        raise SystemExit(f"--perfil-cmyk: {args.perfil_cmyk} no es un perfil ICC CMYK")
    archivos = core.listar_archivos(carpeta)
    plan = core.planear_salidas(archivos, destino, opciones)
    print(f"{len(archivos)} JPG/TIFF en {carpeta}")
    print(f"Destino: {destino}  |  lado mayor {args.lado}px, q{args.calidad}, {args.dpi} dpi, sRGB\n")
    print(f"{'ARCHIVO':<28}{'SALIDA':>12}  {'PESO':>9}  PERFIL DE ORIGEN")
    print("-" * 100)

    total = 0
    saltados = []
    avisos = []
    resultados = []
    t0 = time.time()
    for ruta, salida in zip(archivos, plan):
        r = core.procesar(ruta, salida, opciones)
        resultados.append(r)
        nombre = os.path.basename(ruta)
        if r.estado in ("saltado", "error"):
            saltados.append((nombre, r.motivo))
            continue
        if r.estado == "aviso":
            avisos.append((nombre, r.motivo))
        total += r.peso
        print(f"{nombre:<28}{f'{r.ancho}x{r.alto}':>12}  {r.peso/1024:>7.0f}KB  {r.perfil_origen}")

    print("-" * 100)
    print(f"Total: {total/1024/1024:.1f} MB en {len(archivos)-len(saltados)} archivos, "
          f"{time.time()-t0:.0f}s")
    if args.hoja_contactos is not None and any(r.estado in ("ok", "aviso") for r in resultados):
        titulo = args.hoja_contactos or os.path.basename(carpeta)
        pdf = os.path.join(destino, t("hoja_archivo",
                                      titulo=core.limpiar_nombre(titulo) or t("hoja_titulo_defecto")))
        paginas = hoja_contactos.crear(resultados, pdf, titulo, args.pagina)
        print(f"Hoja de contactos: {pdf} ({paginas} pag.)")
    for nombre, motivo in avisos:
        print(f"OJO: {nombre}: {motivo}")
    for nombre, motivo in saltados:
        print(f"AVISO: {nombre} no se proceso ({motivo})")


if __name__ == "__main__":
    main()
