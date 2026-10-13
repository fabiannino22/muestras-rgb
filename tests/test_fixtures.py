# -*- coding: utf-8 -*-
"""
Corre el nucleo sobre fixtures/tiff y verifica que cada variante de TIFF de
Photoshop se convierta, avise o se salte como se espera, y que el color salga
igual en todas las variantes FOGRA39 sin perdida.

    python -m unittest discover tests
"""
import os
import sys
import tempfile
import unittest

from PIL import Image, ImageChops, ImageStat

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import muestras_core as core  # noqa: E402

FIXTURES = os.path.join(RAIZ, "fixtures", "tiff")
ESPERADO = {
    "08bit_lzw.tif": "ok",
    "08bit_zip.tif": "ok",
    "08bit_jpeg.tif": "ok",
    "16bit_lzw.tif": "ok",
    "08bit_capas_lzw.tif": "ok",
    "08bit_alfa_lzw.tif": "ok",
    "08bit_tintadirecta_lzw.tif": "aviso",
    "08bit_sinperfil_lzw.tif": "saltado",
    "08bit_gracol2006_lzw.tif": "ok",
}
# Mismos pixeles CMYK y mismo perfil que 08bit_lzw: la muestra debe ser identica.
IDENTICOS = ("08bit_zip", "16bit_lzw", "08bit_capas_lzw", "08bit_alfa_lzw",
             "08bit_tintadirecta_lzw")


class TestFixturesTiff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.opciones = core.Opciones(lado=500)
        cls.res = {}
        for nombre in ESPERADO:
            salida = os.path.join(cls.tmp.name, os.path.splitext(nombre)[0] + ".jpg")
            cls.res[nombre] = core.procesar(os.path.join(FIXTURES, nombre), salida, cls.opciones)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_estados(self):
        for nombre, estado in ESPERADO.items():
            with self.subTest(nombre):
                self.assertEqual(self.res[nombre].estado, estado, self.res[nombre].motivo)

    def test_tinta_directa_nombrada(self):
        self.assertIn("Tinta directa prueba", self.res["08bit_tintadirecta_lzw.tif"].motivo)

    def test_salida_srgb_72dpi(self):
        with Image.open(self.res["08bit_lzw.tif"].salida) as im:
            self.assertEqual((im.mode, im.size), ("RGB", (500, 500)))
            self.assertEqual(tuple(round(float(d)) for d in im.info["dpi"]), (72, 72))
            self.assertEqual(core.descripcion_perfil(im.info["icc_profile"]), "sRGB built-in")

    def test_color_igual_entre_variantes(self):
        with Image.open(self.res["08bit_lzw.tif"].salida) as ref:
            ref.load()
            for base in IDENTICOS:
                with self.subTest(base), Image.open(self.res[base + ".tif"].salida) as im:
                    dif = ImageStat.Stat(ImageChops.difference(im, ref)).mean
                    self.assertEqual(max(dif), 0)
            for base, tolerancia in (("08bit_jpeg", 1.0), ("08bit_gracol2006_lzw", 2.5)):
                with self.subTest(base), Image.open(self.res[base + ".tif"].salida) as im:
                    dif = ImageStat.Stat(ImageChops.difference(im, ref)).mean
                    self.assertLess(max(dif), tolerancia)


if __name__ == "__main__":
    unittest.main()
