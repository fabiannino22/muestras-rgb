# -*- coding: utf-8 -*-
"""
Genera el icono de la app en recursos/: icono.png (1024), icono.ico (Windows) e
icono.icns (macOS). Idea: un cuadro partido en diagonal; arriba a la izquierda
semitono CMY (la imprenta), abajo a la derecha degradado RGB liso (la pantalla).

    python recursos/generar_icono.py
"""
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
S = 1024                      # tamano final
X = 4                         # sobremuestreo para bordes suaves
N = S * X


def mascara_cuadro():
    """Cuadro redondeado estilo macOS (~80 % del lienzo, con aire para la sombra)."""
    m = Image.new("L", (N, N), 0)
    lado = int(N * 0.80)
    o = (N - lado) // 2
    ImageDraw.Draw(m).rounded_rectangle((o, o, o + lado, o + lado), radius=int(lado * 0.225), fill=255)
    return m, o, lado


def semitono(o, lado):
    """
    Semitono de imprenta sobre papel: una rejilla a 45 grados (paralela al corte), filas
    alternadas de cian, magenta y amarillo, y puntos que crecen hacia la diagonal, donde
    la imprenta "se vuelve" el degradado continuo de la pantalla.
    """
    capa = Image.new("RGB", (N, N), (255, 255, 255))
    d = ImageDraw.Draw(capa)
    tintas = ((0, 174, 239), (236, 0, 140), (255, 222, 0))
    paso = lado / 5.0                      # separacion entre puntos a lo largo de una fila
    fila = paso * 0.5                      # separacion entre filas (en u = x + y)
    cy = N / 2
    n = 0
    u = 2 * o + fila * 0.7
    while u < N:                           # u = x + y: filas paralelas a la diagonal
        t = min(1.0, max(0.0, (u - 2 * o) / lado))
        r = paso * (0.06 + 0.2 * t)
        color = tintas[n % 3]
        # Solo puntos completos: ninguno cortado por la franja blanca del corte.
        if (N - u) / math.sqrt(2) < r + lado * 0.045:
            u += fila
            n += 1
            continue
        desfase = (paso / 2) * (n % 2)
        v = -N + desfase
        while v < N:                       # v = x - y: posicion a lo largo de la fila
            x, y = (u + v) / 2, (u - v) / 2
            d.ellipse((x - r, y - r, x + r, y + r), fill=color)
            v += paso
        u += fila
        n += 1
    return capa


def degradado(o, lado):
    """Degradado RGB vivo en diagonal (rojo -> verde -> azul), como luz de pantalla."""
    pequeno = Image.new("RGB", (256, 256))
    px = pequeno.load()
    for y in range(256):
        for x in range(256):
            # Solo se ve la mitad de abajo a la derecha: la rampa completa va ahi.
            t = (x - y + 255) / 510        # a lo largo del corte: rojo, verde, azul
            r = max(0, 1 - abs(t - 0.15) * 2.4)
            g = max(0, 1 - abs(t - 0.5) * 2.4)
            b = max(0, 1 - abs(t - 0.85) * 2.4)
            m = max(r, g, b)
            px[x, y] = tuple(int(255 * (0.15 + 0.85 * c / m)) for c in (r, g, b))
    return pequeno.resize((N, N), Image.BICUBIC)


def main():
    m, o, lado = mascara_cuadro()
    # Diagonal con una franja blanca entre las dos mitades.
    arriba = Image.new("L", (N, N), 0)
    ImageDraw.Draw(arriba).polygon([(0, 0), (N, 0), (0, N)], fill=255)
    franja = Image.new("L", (N, N), 0)
    ImageDraw.Draw(franja).line([(N, 0), (0, N)], fill=255, width=int(lado * 0.045))
    icono = Image.composite(semitono(o, lado), degradado(o, lado), arriba)
    icono = Image.composite(Image.new("RGB", (N, N), "white"), icono, franja)

    # Sombra suave y borde fino para que se despegue sobre fondos claros.
    sombra = m.filter(ImageFilter.GaussianBlur(N * 0.015)).point(lambda v: v * 0.35)
    fondo = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    fondo.putalpha(ImageChops.offset(sombra, 0, int(N * 0.01)))
    final = Image.alpha_composite(fondo, Image.merge("RGBA", (*icono.split(), m)))
    borde = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(borde).rounded_rectangle((o, o, o + lado, o + lado), radius=int(lado * 0.225),
                                            outline=(0, 0, 0, 40), width=X * 4)
    final = Image.alpha_composite(final, borde).resize((S, S), Image.LANCZOS)

    final.save(os.path.join(AQUI, "icono.png"))
    final.save(os.path.join(AQUI, "icono.ico"),
               sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    final.save(os.path.join(AQUI, "icono.icns"))
    print("OK icono.png / icono.ico / icono.icns")


if __name__ == "__main__":
    main()
