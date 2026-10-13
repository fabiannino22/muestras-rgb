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
import hoja_contactos  # noqa: E402
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


class TestCmykSinPerfil(unittest.TestCase):
    """Asumir FOGRA39 para 08bit_sinperfil_lzw debe dar lo mismo que 08bit_lzw (mismos pixeles)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        with Image.open(os.path.join(FIXTURES, "08bit_lzw.tif")) as im:
            cls.fogra = os.path.join(cls.tmp.name, "perfiles", "fogra39.icc")
            os.makedirs(os.path.dirname(cls.fogra))
            with open(cls.fogra, "wb") as f:
                f.write(im.info["icc_profile"])
        with open(os.path.join(cls.tmp.name, "perfiles", "srgb.icc"), "wb") as f:
            f.write(core.SRGB_BYTES)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _procesar(self, nombre, perfil):
        salida = os.path.join(self.tmp.name, nombre + ".jpg")
        opciones = core.Opciones(lado=500, perfil_cmyk=perfil)
        return core.procesar(os.path.join(FIXTURES, nombre + ".tif"), salida, opciones)

    def test_sin_opcion_se_salta(self):
        self.assertEqual(self._procesar("08bit_sinperfil_lzw", "").estado, "saltado")

    def test_perfil_asumido(self):
        r = self._procesar("08bit_sinperfil_lzw", self.fogra)
        self.assertEqual(r.estado, "aviso")
        self.assertIn("se asumió «Coated FOGRA39", r.motivo)
        ref = self._procesar("08bit_lzw", self.fogra)
        self.assertEqual(ref.estado, "ok")      # el perfil incrustado manda sobre el asumido
        with Image.open(r.salida) as a, Image.open(ref.salida) as b:
            self.assertEqual(max(ImageStat.Stat(ImageChops.difference(a, b)).mean), 0)

    def test_buscar_perfiles_cmyk(self):
        encontrados = core.buscar_perfiles_cmyk([os.path.dirname(self.fogra)])
        self.assertEqual([d for d, _ in encontrados], ["Coated FOGRA39 (ISO 12647-2:2004)"])


class TestEntrega(unittest.TestCase):
    """Marca de agua y hoja de contactos."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.origen = os.path.join(FIXTURES, "08bit_lzw.tif")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _muestra(self, nombre, **marca):
        r = core.procesar(self.origen, os.path.join(self.tmp.name, nombre + ".jpg"),
                          core.Opciones(lado=400, **marca))
        self.assertEqual(r.estado, "ok", r.motivo)
        return r

    def test_marca_cambia_pixeles_no_tamano(self):
        limpia = self._muestra("limpia")
        with Image.open(limpia.salida) as ref:
            ref.load()
        logo = os.path.join(RAIZ, "recursos", "icono.png")
        for pos in core.POSICIONES_MARCA:
            for clave, marca in (("texto", {"marca_texto": "MUESTRA · Ñ"}), ("logo", {"marca_logo": logo})):
                with self.subTest(pos=pos, tipo=clave):
                    r = self._muestra(f"{clave}_{pos}", marca_posicion=pos, **marca)
                    with Image.open(r.salida) as im:
                        self.assertEqual(im.size, ref.size)
                        self.assertGreater(max(ImageStat.Stat(ImageChops.difference(im, ref)).mean), 0.05)

    def test_hoja_de_contactos(self):
        res = [self._muestra(f"h{i}") for i in range(7)]
        res.append(core.Resultado(origen="x.tif", estado="saltado"))   # se ignora
        pdf = os.path.join(self.tmp.name, "hoja.pdf")
        self.assertEqual(hoja_contactos.crear(res, pdf, "Catálogo ñ", "a4"), 2)   # 6 por página
        with open(pdf, "rb") as f:
            self.assertTrue(f.read(5) == b"%PDF-")
        self.assertEqual(hoja_contactos.medida_impresion(res[0]), "16.9 × 16.9 cm a 300 dpi")

    def test_nota_cliente_solo_tinta_directa(self):
        r = core.procesar(os.path.join(FIXTURES, "08bit_tintadirecta_lzw.tif"),
                          os.path.join(self.tmp.name, "td.jpg"), core.Opciones(lado=300))
        self.assertIn("Tinta directa prueba", r.nota_cliente)
        self.assertEqual(self._muestra("sin_nota").nota_cliente, "")


if __name__ == "__main__":
    unittest.main()
