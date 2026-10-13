# Notas técnicas

Para quien mantenga o modifique el código. La guía para usuarios está en [guia.md](guia.md).

## Estructura

| Archivo | Qué hace |
|---|---|
| `muestras_core.py` | Conversión de color, marca de agua, nombres de salida, detección de tintas directas y perfiles. Nunca escribe fuera de la carpeta de salida. |
| `hoja_contactos.py` | PDF con todas las muestras (solo Pillow: páginas dibujadas a 200 dpi). |
| `textos.py` | Todos los textos visibles en español e inglés (`t("clave")`). |
| `muestras_gui.py` | Interfaz PySide6. `--autoprueba ENTRADA SALIDA` es la prueba de humo del ejecutable. |
| `exportar_muestras_rgb.py` | Versión de consola (`--help`). |
| `empaquetar.py` | PyInstaller → `dist/MuestrasRGB-<plataforma>.zip`, con licencias. |
| `recursos/` | Ícono (`generar_icono.py` lo dibuja), fuente Inter y textos de licencia. |
| `fixtures/tiff/` | TIFF CMYK reales exportados desde Photoshop (ver `fixtures/README.md`). |
| `tests/` | `python -m unittest discover tests`. |

## Flujo de color

1. Toma el **perfil ICC incrustado** de cada archivo como origen. No hay perfil fijo en el código.
2. **Reduce primero** (LANCZOS al lado mayor) y convierte después. La conversión ICC es por píxel, así que el color sale igual pero ~30× más rápido que convertir los ~60 MP originales.
3. Convierte a **sRGB** con littlecms (incluido en Pillow): intento colorimétrico relativo + compensación de punto negro.
4. Aplica la marca de agua, si hay.
5. Guarda JPEG progresivo y optimizado con sRGB incrustado y el dpi pedido.

## Reglas

- **Nunca tocar los originales.**
- **Un CMYK sin perfil no se convierte en silencio.** Photoshop no tiene un perfil fijo para estos casos: usa el espacio de trabajo CMYK de *Ajustes de color*, que depende de la región de instalación (Norteamérica: U.S. Web Coated SWOP v2; Europa: Coated FOGRA39; Japón: Japan Color 2001 Coated). Por eso aquí se salta, o se asume el perfil que elija el usuario y la muestra queda marcada. La app no trae perfiles de Adobe: los busca en el sistema (`Common Files/Adobe/Color/Profiles` en Windows, `/Library/Application Support/Adobe/Color/Profiles` y ColorSync en Mac).
- **Una tinta directa no se puede simular.** Pillow lee solo los 4 canales CMYK y descarta los extra sin avisar. Por etiquetas TIFF un alfa y una tinta directa son indistinguibles (`ExtraSamples = 0`), pero el recurso DisplayInfo (`0x0435`) que Photoshop guarda en la etiqueta 34377 marca cada canal extra como alfa (tipo 0/1) o tinta directa (tipo 2), y el recurso `0x0415` trae los nombres. Con eso se avisa nombrando la tinta.
- **La hoja de contactos solo lleva notas para el cliente** (`Resultado.nota_cliente`); los avisos técnicos (`Resultado.motivo`) se quedan en la app.

## Problemas de color ya verificados (no volver a descubrirlos)

- El JPEG CMYK de Photoshop viene con `adobe_transform=2` (YCCK con canales invertidos). Pillow lo decodifica bien solo: **no invertir los canales a mano**.
- Con FOGRA39, colorimétrico relativo y perceptual dan resultado **idéntico** (diferencia media 0.0/255).
- `img.convert("RGB")` **sin ICC** sale visiblemente más verde y apagado.
- `Image.MAX_IMAGE_PIXELS = None` es obligatorio: las piezas de impresión (~60 MP) superan el límite anti-"image bomb" de Pillow.
- **sRGB es el destino correcto para aprobar en pantalla.** Adobe RGB sin gestión de color se ve saturado en el monitor del cliente.
- El **dpi no cambia los píxeles**; solo la etiqueta.
- Una muestra CMYK→RGB es una **simulación del impreso**, no el RGB original del diseño: en tonos muy saturados se nota el gamut de la imprenta.
- Valores de referencia FOGRA39 → sRGB (relativo + BPC): C100 = `0,159,227`, M100 = `230,0,126`, K100 = `29,29,27`.

## Formatos verificados con `fixtures/tiff/`

| Entrada | Resultado |
|---|---|
| CMYK 8 bits con perfil: TIFF sin comprimir / LZW / ZIP / JPEG, JPG | Se convierte. |
| CMYK 16 bits | Pillow lo lee reducido a 8 bits: muestra idéntica a la de 8 bits. |
| TIFF con capas | Se usa el compuesto aplanado; idéntico. |
| TIFF con alfa guardado | El alfa se ignora; idéntico. |
| TIFF con tinta directa | Se convierte con aviso nombrando la tinta. |
| CMYK sin perfil | Se salta, o se convierte con el perfil elegido y aviso. |
| RGB / gris con o sin perfil, RGBA | Se convierte / se asume sRGB / se aplana sobre blanco. |
| Gris de 16 bits, archivo dañado | Se salta con aviso / error. |

## Idiomas

Todo texto visible sale de `textos.py`. Para agregar uno: una clave nueva con `_(es, en)` y `t("clave")` en el código. La prueba `TestIdiomas` falla si una clave no tiene los dos idiomas. Los procesos de conversión reciben el idioma en `Opciones.idioma`. La app elige el idioma con *Automático* (español si el sistema está en español; si no, inglés) o el que fije el usuario, y lo cambia en vivo reabriendo la ventana.

El código (variables, comentarios) y la consola están en español.

## Empaquetado y publicación

- `python empaquetar.py` arma `dist/MuestrasRGB-<plataforma>.zip` en modo carpeta (no un solo `.exe`: arranca más rápido y los antivirus lo marcan menos). Incluye `LICENSE.txt`, `THIRD-PARTY-NOTICES.txt` y `licenses/` (LGPL/GPL de Qt, Pillow y sus librerías, Python, Inter). En Mac re-firma *ad-hoc* el `.app`, porque tocarlo después de PyInstaller invalida la firma y en Apple Silicon no abriría.
- Se instala `PySide6-Essentials`, no `PySide6` completo, para no meter WebEngine, QML y compañía al paquete.
- Los zip **no llevan versión en el nombre**, para que `releases/latest/download/MuestrasRGB-windows-x64.zip` siempre baje la última.
- La Action `.github/workflows/empaquetar.yml` corre las pruebas, empaqueta y **ejecuta el programa ya empaquetado** (`--autoprueba`, que usa marca de agua y hoja de contactos) en Windows, macOS arm64 y macOS Intel.

Para publicar una versión:

1. Sube `VERSION` en `muestras_core.py` y haz commit en `main`.
2. `git tag vX.Y.Z && git push origin vX.Y.Z`
3. La Action crea un **release en borrador** con los tres zip; revísalo y publícalo. Si la etiqueta no coincide con `VERSION`, falla a propósito.

## Consola

```
python exportar_muestras_rgb.py "ruta" --salida "destino" --lado 1600 --calidad 85 --prefijo e22_ \
    --marca-texto "MUESTRA" --marca-posicion esquina --hoja-contactos "Título" --pagina a4 --idioma es
```

| Opción | Default | Significado |
|---|---|---|
| `carpeta` | `.` | Carpeta con los JPG/TIFF. |
| `--subcarpeta` / `--salida` | `muestras` | Subcarpeta de salida, o carpeta de salida completa. |
| `--lado` / `--calidad` / `--dpi` | `2000` / `92` / `72` | Tamaño, calidad JPEG y dpi. |
| `--prefijo` / `--sufijo` | — | Texto antes / después del nombre. |
| `--si-existe` | `numerar` | `numerar`, `sobrescribir` o `saltar`. |
| `--perfil-cmyk` | — | `.icc` a asumir en CMYK sin perfil. |
| `--marca-texto` / `--marca-logo` | — | Marca de agua. |
| `--marca-posicion` / `--marca-opacidad` | `centro` / `35` | Posición y opacidad de la marca. |
| `--hoja-contactos TITULO` / `--pagina` | — / `carta` | Hoja de contactos en PDF. |
| `--idioma` | `es` | Idioma de los avisos y de la hoja de contactos. |
