"""
Genera fixtures/_base_cmyk.tif: carta de prueba CMYK 8 bits, 2000x2000 px, sin perfil.

Es solo la base de pixeles. exportar_tiffs.jsx la abre en Photoshop, le asigna
FOGRA39, le agrega capas y exporta las variantes de fixtures/tiff/. Sin contenido
de clientes: degradados y parches de tinta deterministas.

    python fixtures/generar_base.py
"""

from pathlib import Path

import numpy as np
from PIL import Image

LADO = 2000
SALIDA = Path(__file__).with_name("_base_cmyk.tif")


def pct(*tintas):
    """Porcentajes de tinta C, M, Y, K (0-100) -> valores 0-255 de Pillow."""
    return [round(t * 255 / 100) for t in tintas]


def main():
    img = np.zeros((LADO, LADO, 4), dtype=np.uint8)  # 0 = papel blanco

    # Franja superior: un degradado 0->100 % por tinta, 200 px de alto cada uno
    rampa = np.linspace(0, 255, LADO).round().astype(np.uint8)
    for canal in range(4):
        img[canal * 200:(canal + 1) * 200, :, canal] = rampa

    # Rejilla de parches de 250x250 px (8 columnas x 3 filas), y = 900..1650
    parches = [
        pct(100, 0, 0, 0), pct(0, 100, 0, 0), pct(0, 0, 100, 0), pct(0, 0, 0, 100),
        pct(100, 100, 0, 0), pct(0, 100, 100, 0), pct(100, 0, 100, 0), pct(100, 100, 100, 0),
        pct(50, 0, 0, 0), pct(0, 50, 0, 0), pct(0, 0, 50, 0), pct(0, 0, 0, 50),
        pct(60, 40, 40, 100), pct(100, 100, 100, 100), pct(5, 25, 35, 0), pct(70, 15, 0, 0),
        pct(25, 25, 25, 0), pct(0, 0, 0, 25), pct(10, 10, 10, 10), pct(2, 2, 2, 0),
        pct(40, 0, 100, 0), pct(0, 60, 100, 0), pct(90, 70, 0, 10), pct(0, 0, 0, 0),
    ]
    for i, color in enumerate(parches):
        fila, col = divmod(i, 8)
        y, x = 900 + fila * 250, col * 250
        img[y:y + 250, x:x + 250] = color

    # Franja inferior: degradado mixto C+M de izquierda a derecha, Y+K de arriba a abajo
    yy = np.linspace(0, 255, LADO - 1700).round().astype(np.uint8)[:, None]
    img[1700:, :, 0] = rampa
    img[1700:, :, 1] = rampa[::-1]
    img[1700:, :, 2] = yy
    img[1700:, :, 3] = yy // 3

    Image.fromarray(img, "CMYK").save(SALIDA, compression="tiff_lzw", dpi=(300, 300))
    print(f"OK {SALIDA}")


if __name__ == "__main__":
    main()
