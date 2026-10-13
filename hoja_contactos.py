# -*- coding: utf-8 -*-
"""
Hoja de contactos en PDF: todas las muestras de un lote en paginas Carta/A4, con
nombre, pixeles, medida de impresion del original y los avisos, lista para mandar
al cliente junto con (o en lugar de) los JPG.

Solo usa Pillow: cada pagina se dibuja como imagen RGB a 200 dpi y Pillow las junta
en un PDF. Asi no hay dependencias nuevas que empaquetar.
"""
import datetime
import os

from PIL import Image, ImageDraw

import muestras_core as core

DPI = 200
PAGINAS = {"carta": (8.5, 11.0), "a4": (8.27, 11.69)}   # pulgadas, vertical
COLUMNAS, FILAS = 2, 3
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")
TINTA = (25, 25, 25)
GRIS = (120, 120, 120)
AVISO = (196, 98, 0)


def _px(pulgadas):
    return int(round(pulgadas * DPI))


def medida_impresion(r):
    """'30 × 20 cm a 300 dpi' a partir del original, o '' si no traia dpi."""
    if not r.dpi_origen or r.dpi_origen < 2:
        return ""
    cm = lambda px: px / r.dpi_origen * 2.54
    return f"{cm(r.ancho_origen):.1f} × {cm(r.alto_origen):.1f} cm a {r.dpi_origen:.0f} dpi"


def _ajustar(draw, texto, f, ancho):
    """Recorta con '…' para que el texto quepa en `ancho` px."""
    if draw.textlength(texto, font=f) <= ancho:
        return texto
    while texto and draw.textlength(texto + "…", font=f) > ancho:
        texto = texto[:-1]
    return texto + "…"


def _lineas(draw, texto, f, ancho, maximo):
    """Parte `texto` en hasta `maximo` lineas que quepan en `ancho`."""
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if draw.textlength(prueba, font=f) <= ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    lineas.append(actual)
    if len(lineas) > maximo:
        lineas = lineas[:maximo]
        lineas[-1] = _ajustar(draw, lineas[-1] + " …", f, ancho)
    return lineas


def crear(resultados, ruta_pdf, titulo, pagina="carta", fecha=None):
    """
    Escribe el PDF con los Resultado convertidos (ok/aviso) en el orden dado.
    Devuelve el numero de paginas.
    """
    muestras = [r for r in resultados if r.estado in ("ok", "aviso") and os.path.isfile(r.salida)]
    if not muestras:
        raise ValueError("no hay muestras convertidas para la hoja de contactos")
    fecha = fecha or datetime.date.today()
    fecha_txt = f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"

    ancho, alto = (_px(x) for x in PAGINAS[pagina])
    margen = _px(0.5)
    cab = _px(0.85)
    pie = _px(0.45)
    celda_w = (ancho - 2 * margen - _px(0.3) * (COLUMNAS - 1)) // COLUMNAS
    celda_h = (alto - 2 * margen - cab - pie - _px(0.25) * (FILAS - 1)) // FILAS
    texto_h = _px(0.62)
    img_h = celda_h - texto_h

    f_titulo = core.fuente(_px(0.22), negrita=True)
    f_sub = core.fuente(_px(0.11))
    f_nombre = core.fuente(_px(0.12), negrita=True)
    f_dato = core.fuente(_px(0.1))
    f_pie = core.fuente(_px(0.085))

    por_pagina = COLUMNAS * FILAS
    total_paginas = (len(muestras) + por_pagina - 1) // por_pagina
    paginas = []
    for n in range(total_paginas):
        hoja = Image.new("RGB", (ancho, alto), "white")
        d = ImageDraw.Draw(hoja)
        d.text((margen, margen), _ajustar(d, titulo, f_titulo, ancho - 2 * margen),
               font=f_titulo, fill=TINTA)
        d.text((margen, margen + _px(0.34)),
               f"{len(muestras)} muestras · {fecha_txt}", font=f_sub, fill=GRIS)
        d.line((margen, margen + cab - _px(0.15), ancho - margen, margen + cab - _px(0.15)),
               fill=(220, 220, 220), width=2)

        for i, r in enumerate(muestras[n * por_pagina:(n + 1) * por_pagina]):
            fila, col = divmod(i, COLUMNAS)
            x = margen + col * (celda_w + _px(0.3))
            y = margen + cab + fila * (celda_h + _px(0.25))
            with Image.open(r.salida) as im:
                im = im.convert("RGB")
                im.thumbnail((celda_w, img_h), Image.LANCZOS)
                # Alineada abajo dentro de su espacio, centrada en horizontal.
                ix = x + (celda_w - im.width) // 2
                iy = y + img_h - im.height
                hoja.paste(im, (ix, iy))
                d.rectangle((ix - 1, iy - 1, ix + im.width, iy + im.height), outline=(210, 210, 210))
            # El pie arranca en el borde izquierdo de la imagen, no de la celda.
            x, celda_txt = ix, celda_w - (ix - x)
            ty = y + img_h + _px(0.08)
            d.text((x, ty), _ajustar(d, os.path.basename(r.salida), f_nombre, celda_txt),
                   font=f_nombre, fill=TINTA)
            datos = f"{r.ancho} × {r.alto} px"
            medida = medida_impresion(r)
            if medida:
                datos += f"  ·  impresión {medida}"
            d.text((x, ty + _px(0.17)), _ajustar(d, datos, f_dato, celda_txt), font=f_dato, fill=GRIS)
            # Solo notas para el cliente; los avisos tecnicos (perfil asumido...) se quedan
            # en la app.
            if r.nota_cliente:
                for k, linea in enumerate(_lineas(d, "⚠ " + r.nota_cliente, f_dato, celda_txt, 2)):
                    d.text((x, ty + _px(0.31) + k * _px(0.13)), linea, font=f_dato, fill=AVISO)

        d.text((margen, alto - margen - _px(0.1)),
               "Colores simulados en pantalla (sRGB) a partir del archivo de impresión; "
               "el impreso puede variar según papel y prensa.", font=f_pie, fill=GRIS)
        num = f"{n + 1} / {total_paginas}"
        d.text((ancho - margen - d.textlength(num, font=f_pie), alto - margen - _px(0.1)),
               num, font=f_pie, fill=GRIS)
        paginas.append(hoja)

    os.makedirs(os.path.dirname(os.path.abspath(ruta_pdf)), exist_ok=True)
    paginas[0].save(ruta_pdf, "PDF", resolution=DPI, save_all=True, append_images=paginas[1:],
                    title=titulo, author="Muestras RGB · e22lab", quality=88)
    return total_paginas
