# -*- coding: utf-8 -*-
"""
Logica compartida de muestras-rgb: la usan el script de consola
(exportar_muestras_rgb.py) y la interfaz grafica (muestras_gui.py).

Flujo por archivo (ver README para el porque de cada paso):
  1. Lee el JPG/TIFF y toma su perfil ICC INCRUSTADO como origen. Un CMYK sin
     perfil se SALTA con aviso: sin origen no hay forma honesta de convertir.
  2. REDIMENSIONA primero (LANCZOS, lado mayor = lado). La conversion ICC es por
     pixel, asi que reducir antes da el mismo color mucho mas rapido.
  3. Convierte a sRGB con littlecms (Relative Colorimetric + punto negro).
  4. Guarda JPEG progresivo y optimizado con sRGB incrustado y el dpi pedido.

Los originales NO se tocan: solo se escribe en la carpeta de salida.
"""
import os
import re
from dataclasses import dataclass

from PIL import Image, ImageCms

# Las piezas de impresion superan el limite anti-"image bomb" de Pillow.
Image.MAX_IMAGE_PIXELS = None

EXTENSIONES = (".jpg", ".jpeg", ".tif", ".tiff")

perfil_srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
SRGB_BYTES = perfil_srgb.tobytes()
BPC = ImageCms.Flags.BLACKPOINTCOMPENSATION

# Que hacer si el archivo de salida ya existe en disco.
SI_EXISTE = ("numerar", "sobrescribir", "saltar")


@dataclass
class Opciones:
    lado: int = 2000
    calidad: int = 92
    dpi: int = 72
    prefijo: str = ""
    sufijo: str = ""
    nombre_nuevo: str = ""      # si no esta vacio, reemplaza el nombre original
    numerar: bool = False       # agrega _001, _002... (siempre si hay nombre_nuevo)
    digitos: int = 3
    inicio: int = 1
    si_existe: str = "numerar"


@dataclass
class Resultado:
    origen: str
    salida: str = ""
    estado: str = "ok"          # ok | saltado | error
    motivo: str = ""
    modo_origen: str = ""
    perfil_origen: str = ""
    ancho: int = 0
    alto: int = 0
    peso: int = 0


def listar_archivos(carpeta, recursivo=False):
    """Archivos JPG/TIFF de la carpeta, en orden alfabetico sin importar mayusculas."""
    encontrados = []
    if recursivo:
        for raiz, _, nombres in os.walk(carpeta):
            encontrados += [os.path.join(raiz, n) for n in nombres
                            if n.lower().endswith(EXTENSIONES)]
    else:
        encontrados = [os.path.join(carpeta, n) for n in os.listdir(carpeta)
                       if n.lower().endswith(EXTENSIONES)
                       and os.path.isfile(os.path.join(carpeta, n))]
    return sorted(encontrados, key=str.lower)


_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def limpiar_nombre(texto):
    """Quita caracteres que Windows o macOS no aceptan en un nombre de archivo."""
    return _INVALIDOS.sub("", texto).strip()


def nombre_salida(ruta, opciones, indice):
    """Nombre final (con .jpg) para el archivo numero `indice` (0 = primero) del lote."""
    base = limpiar_nombre(opciones.nombre_nuevo) or os.path.splitext(os.path.basename(ruta))[0]
    if opciones.numerar or opciones.nombre_nuevo.strip():
        base += f"_{opciones.inicio + indice:0{opciones.digitos}d}"
    return f"{limpiar_nombre(opciones.prefijo)}{base}{limpiar_nombre(opciones.sufijo)}.jpg"


def planear_salidas(archivos, destino, opciones):
    """
    Ruta de salida para cada archivo, o None si se salta porque ya existe.
    Evita que dos archivos del lote (p. ej. pieza.jpg y pieza.tif) se pisen entre si
    y aplica `si_existe` contra lo que ya hay en disco.
    """
    usados = set()
    plan = []
    for i, ruta in enumerate(archivos):
        nombre = nombre_salida(ruta, opciones, i)
        salida = os.path.join(destino, nombre)
        existe = os.path.exists(salida)
        if existe and opciones.si_existe == "saltar":
            plan.append(None)
            continue
        if salida.lower() in usados or (existe and opciones.si_existe == "numerar"):
            raiz, ext = os.path.splitext(salida)
            n = 2
            while (f"{raiz} ({n}){ext}".lower() in usados
                   or os.path.exists(f"{raiz} ({n}){ext}")):
                n += 1
            salida = f"{raiz} ({n}){ext}"
        usados.add(salida.lower())
        plan.append(salida)
    return plan


def descripcion_perfil(icc):
    if not icc:
        return "(sin perfil)"
    try:
        return ImageCms.getProfileDescription(
            ImageCms.ImageCmsProfile(ImageCms.core.profile_frombytes(icc))).strip()
    except Exception:
        return "(perfil ilegible)"


def _convertir(img, icc, modo_entrada):
    origen = ImageCms.ImageCmsProfile(ImageCms.core.profile_frombytes(icc))
    tr = ImageCms.buildTransform(origen, perfil_srgb, modo_entrada, "RGB",
                                 renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                                 flags=BPC)
    return ImageCms.applyTransform(img, tr)


def _aplanar(img):
    """Quita la transparencia componiendo sobre blanco (JPEG no tiene alfa)."""
    fondo = Image.new(img.mode[:-1], img.size, 255)
    fondo.paste(img.convert(img.mode[:-1]), mask=img.getchannel("A"))
    return fondo


def a_rgb(img):
    """Imagen en sRGB usando su perfil incrustado como origen."""
    icc = img.info.get("icc_profile")
    if img.mode in ("RGBA", "LA"):
        img = _aplanar(img)
    if icc and img.mode in ("CMYK", "RGB", "L"):
        try:
            return _convertir(img, icc, img.mode)
        except ImageCms.PyCMSError:
            # Perfil que no corresponde al modo (p. ej. RGB con perfil CMYK).
            raise ValueError("el perfil incrustado no corresponde al modo de color")
    # Sin perfil (RGB o gris) no hay como adivinar el origen: se asume sRGB.
    return img if img.mode == "RGB" else img.convert("RGB")


MODOS_SOPORTADOS = ("CMYK", "RGB", "RGBA", "L", "LA")


def procesar(ruta, salida, opciones):
    """Convierte un archivo. Nunca lanza excepcion: el error queda en el Resultado."""
    r = Resultado(origen=ruta, salida=salida or "")
    if salida is None:
        r.estado, r.motivo = "saltado", "ya existe en la carpeta de salida"
        return r
    try:
        with Image.open(ruta) as img:
            r.modo_origen = img.mode
            icc = img.info.get("icc_profile")
            r.perfil_origen = descripcion_perfil(icc)
            if img.mode not in MODOS_SOPORTADOS:
                r.estado = "saltado"
                r.motivo = f"modo {img.mode} no soportado"
                if img.mode.startswith("I;16") or img.mode in ("I", "F"):
                    r.motivo += " (16/32 bits: guardalo en 8 bits)"
                return r
            if img.mode == "CMYK" and not icc:
                r.estado = "saltado"
                r.motivo = "CMYK sin perfil incrustado: no se adivina el origen"
                return r
            img.thumbnail((opciones.lado, opciones.lado), Image.LANCZOS)
            img.info["icc_profile"] = icc
            rgb = a_rgb(img)
            os.makedirs(os.path.dirname(salida), exist_ok=True)
            rgb.save(salida, "JPEG", quality=opciones.calidad, optimize=True,
                     progressive=True, icc_profile=SRGB_BYTES,
                     dpi=(opciones.dpi, opciones.dpi))
            r.ancho, r.alto = rgb.size
        r.peso = os.path.getsize(salida)
    except Image.UnidentifiedImageError:
        r.estado, r.motivo = "error", "no se pudo leer (archivo dañado o no es imagen)"
    except Exception as e:
        r.estado, r.motivo = "error", f"{type(e).__name__}: {e}"
    return r
