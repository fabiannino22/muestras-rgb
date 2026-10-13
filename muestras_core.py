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
import functools
import os
import re
import struct
import sys
from dataclasses import dataclass

from PIL import Image, ImageCms

# Las piezas de impresion superan el limite anti-"image bomb" de Pillow.
Image.MAX_IMAGE_PIXELS = None

VERSION = "0.2.0"

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
    perfil_cmyk: str = ""       # .icc a asumir en CMYK sin perfil; vacio = saltarlos


@dataclass
class Resultado:
    origen: str
    salida: str = ""
    estado: str = "ok"          # ok | aviso (convertido, pero leer motivo) | saltado | error
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


# Donde suelen vivir los perfiles ICC (Adobe instala los suyos en las de Adobe).
def _carpetas_perfiles():
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        comunes = os.environ.get("COMMONPROGRAMFILES", r"C:\Program Files\Common Files")
        return [os.path.join(windir, "System32", "spool", "drivers", "color"),
                os.path.join(comunes, "Adobe", "Color", "Profiles")]
    if sys.platform == "darwin":
        return ["/Library/Application Support/Adobe/Color/Profiles",
                "/Library/ColorSync/Profiles",
                os.path.expanduser("~/Library/ColorSync/Profiles"),
                "/System/Library/ColorSync/Profiles"]
    return ["/usr/share/color/icc", "/usr/local/share/color/icc",
            os.path.expanduser("~/.local/share/icc"), os.path.expanduser("~/.color/icc")]


def es_perfil_cmyk(ruta):
    """True si el .icc/.icm describe un espacio CMYK (bytes 16-19 de la cabecera)."""
    try:
        with open(ruta, "rb") as f:
            cabecera = f.read(40)
        return len(cabecera) == 40 and cabecera[36:40] == b"acsp" and cabecera[16:20] == b"CMYK"
    except OSError:
        return False


def buscar_perfiles_cmyk(carpetas=None):
    """[(descripcion, ruta)] de los perfiles CMYK instalados, sin repetir descripcion."""
    vistos = {}
    for carpeta in carpetas or _carpetas_perfiles():
        for raiz, _, nombres in os.walk(carpeta):
            for n in nombres:
                ruta = os.path.join(raiz, n)
                if n.lower().endswith((".icc", ".icm")) and es_perfil_cmyk(ruta):
                    with open(ruta, "rb") as f:
                        desc = descripcion_perfil(f.read())
                    vistos.setdefault(desc, ruta)
    return sorted(vistos.items(), key=lambda par: par[0].lower())


@functools.lru_cache(maxsize=4)
def leer_perfil(ruta):
    with open(ruta, "rb") as f:
        return f.read()


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

TAG_PHOTOSHOP = 34377      # recursos de imagen de Photoshop dentro del TIFF


def _recursos_photoshop(datos):
    """Bloques '8BIM' de Photoshop -> {id: bytes}."""
    recursos, i = {}, 0
    while i + 12 <= len(datos) and datos[i:i + 4] == b"8BIM":
        rid = struct.unpack(">H", datos[i + 4:i + 6])[0]
        j = i + 6 + 1 + datos[i + 6]          # nombre Pascal...
        j += (j - i) % 2                      # ...rellenado a par
        largo = struct.unpack(">I", datos[j:j + 4])[0]
        recursos[rid] = datos[j + 4:j + 4 + largo]
        i = j + 4 + largo + largo % 2
    return recursos


def tintas_directas(img):
    """
    Nombres de las tintas directas de un TIFF de Photoshop. Pillow lee solo los 4
    canales CMYK y descarta los extra sin avisar; por etiquetas TIFF un alfa y una
    tinta directa son indistinguibles, pero el recurso DisplayInfo (0x0435) de
    Photoshop marca cada canal extra como alfa (0/1) o tinta directa (2).
    """
    try:
        datos = img.tag_v2.get(TAG_PHOTOSHOP) if img.format == "TIFF" else None
        if not datos:
            return []
        r = _recursos_photoshop(bytes(datos))
        info = r.get(0x0435, b"")[4:]          # salta la version
        tipos = [info[k + 12] for k in range(0, len(info) - 12, 13)]
        if 0x0415 in r:                        # nombres Unicode
            nombres = r[0x0415]
            lista, i = [], 0
            while i + 4 <= len(nombres):
                n = struct.unpack(">I", nombres[i:i + 4])[0]
                lista.append(nombres[i + 4:i + 4 + 2 * n].decode("utf-16-be").rstrip("\x00"))
                i += 4 + 2 * n
        else:                                  # nombres Pascal
            pas, lista, i = r.get(0x03EE, b""), [], 0
            while i < len(pas):
                lista.append(pas[i + 1:i + 1 + pas[i]].decode("latin-1"))
                i += 1 + pas[i]
        return [lista[k] if k < len(lista) else f"canal {k + 1}"
                for k, tipo in enumerate(tipos) if tipo == 2]
    except Exception:
        return []


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
                    r.motivo += " (gris de 16/32 bits: guárdalo en 8 bits)"
                return r
            if img.mode == "CMYK" and not icc:
                if not opciones.perfil_cmyk:
                    r.estado = "saltado"
                    r.motivo = "CMYK sin perfil incrustado: no se adivina el origen"
                    return r
                # Lo mismo que hace Photoshop con su espacio de trabajo CMYK, pero a la vista.
                icc = leer_perfil(opciones.perfil_cmyk)
                r.perfil_origen = descripcion_perfil(icc) + " (asumido)"
                r.estado = "aviso"
                r.motivo = f"sin perfil incrustado: se asumió «{descripcion_perfil(icc)}»"
            directas = tintas_directas(img)
            if directas:
                r.estado = "aviso"
                r.motivo = (r.motivo + "; " if r.motivo else "") + ("la muestra no incluye la tinta directa "
                            + ", ".join(f"«{n}»" for n in directas) + " (solo CMYK)")
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
