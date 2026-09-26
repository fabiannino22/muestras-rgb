# muestras-rgb

Convierte los **JPG de impresión (CMYK)** de una carpeta de cliente en **muestras RGB
reducidas** listas para mandar al cliente a aprobación final, dentro de una subcarpeta
(`muestras/` por defecto). Usa el perfil ICC incrustado de cada pieza como origen, así
que sirve con cualquier perfil de imprenta (FOGRA39, GRACoL, etc.), no solo con uno.

Probado el 2026-09-26 con Python 3.14 y Pillow 12.3.0 en Windows, sobre 15 fondos de
pared de impresión de un cliente (CMYK `Coated FOGRA39 (ISO 12647-2:2004)`,
11221×5315 px @ 150 dpi): 15/15 muestras RGB correctas en 20 s, 7.1 MB en total.

## Qué hay aquí

| Archivo | Qué hace |
|---|---|
| `exportar_muestras_rgb.py` | Lee los `.jpg` de una carpeta, los reduce y los convierte a sRGB, y escribe las muestras en la subcarpeta de salida. Solo lectura sobre los originales. |

## Cómo se usa

```
python exportar_muestras_rgb.py                              (sobre la carpeta actual)
python exportar_muestras_rgb.py "G:\ruta\del\cliente"
python exportar_muestras_rgb.py "G:\ruta" --lado 1600 --calidad 85 --dpi 72 --subcarpeta pruebas
```

| Opción | Default | Significado |
|---|---|---|
| `carpeta` (posicional) | `.` | Carpeta que contiene los JPG de impresión. |
| `--subcarpeta` | `muestras` | Nombre de la subcarpeta de salida, dentro de `carpeta`. |
| `--lado` | `2000` | Píxeles del lado **más largo** de la muestra (respeta la proporción). |
| `--calidad` | `92` | Calidad JPEG. 92 ≈ 500-700 KB/pieza a 2000 px; 85 aligera para envío. |
| `--dpi` | `72` | DPI escrito en los metadatos. No cambia los píxeles, solo la etiqueta. |

**Dependencia:** `pip install pillow` (littlecms ya viene dentro de Pillow).

Al terminar imprime una tabla de verificación (dimensiones, modo, dpi, peso y perfil
de cada salida) y avisa de cualquier archivo que no procesó.

## Qué hace por dentro

1. Toma el **perfil ICC incrustado** de cada JPG como origen de color. No hay perfil
   hardcodeado: cada pieza aporta el suyo.
2. **Reduce primero** (LANCZOS al lado mayor pedido) y convierte el perfil después.
   La conversión ICC es por píxel independiente, así que el color sale igual pero
   ~30× más rápido que convertir los ~60 MP originales.
3. Convierte a **sRGB** con littlecms, intento *Relative Colorimetric* + compensación
   de punto negro.
4. Guarda JPEG progresivo y optimizado con el perfil sRGB incrustado y el dpi pedido.

## Reglas de seguridad

- **Nunca toca los originales:** solo escribe dentro de la subcarpeta de salida.
- Un **CMYK sin perfil incrustado se salta con aviso**, porque sin origen no hay forma
   honesta de convertir el color. Mejor un aviso que un color inventado.
- Un JPG que ya es RGB se reconvierte desde su perfil a sRGB (o solo se reduce si no
   trae perfil).

## Gotchas de color verificados (no volver a descubrirlos)

- El JPEG CMYK de Photoshop viene con `adobe_transform=2` (YCCK con canales invertidos).
  Pillow lo decodifica bien solo: **no invertir los canales a mano**.
- Con FOGRA39, *Relative Colorimetric* y *Perceptual* dan resultado **idéntico**
  (diferencia media 0.0/255): la elección de intento no importa con este perfil.
- `img.convert("RGB")` **sin ICC** sale visiblemente más verde y apagado. Nunca omitir
  el perfil incrustado.
- `Image.MAX_IMAGE_PIXELS = None` es obligatorio: las piezas de impresión (~60 MP)
  superan el límite anti-"image bomb" de Pillow y sin eso abre con excepción.
- **sRGB es el destino correcto para aprobar en pantalla.** Adobe RGB sin gestión de
  color se ve saturado y engañoso en el monitor del cliente.
- El **dpi de los metadatos no cambia los píxeles**: 2000 px son 2000 px en pantalla.
  Solo afecta a cómo lo interpreta un programa que mida en cm/pulgadas.
- Una muestra CMYK→RGB es una **simulación de cómo se verá impreso**, no el RGB
  original del diseño. Si el cliente compara contra un PNG RGB anterior, notará
  ligeras diferencias en los tonos más saturados: es el gamut de la imprenta, no un bug.

## Dónde vive y por qué

- El código vive aquí, en OneDrive, porque es una herramienta **transversal del
  estudio**, no de un cliente: cualquier carpeta de impresión de cualquier cliente se
  procesa apuntándola por argumento.
- Las **muestras salen dentro de la carpeta del cliente** (subcarpeta `muestras/`),
  porque son el entregable que se envía; no se acumulan aquí.

## A futuro: e22labs (apuntado 2026-09-26, sin fecha)

La visión es convertir esto en una **herramienta gratuita de distribución pública**
bajo el sello **e22labs**, para que cualquier diseñador que imprima se salte el tener
que programar un lote de acciones en Photoshop o convertir a mano.

Orden previsto (cada paso desbloquea el siguiente):

1. **Repo versionado** (este): semilla y backup. Hoy privado/interno.
2. **Ejecutable drag & drop** (PyInstaller + una GUI mínima): es el paso que de verdad
   la vuelve usable para quien no abre una consola. Sin esto, la adopción externa es
   cercana a cero.
3. **Video demo + landing de e22labs**: rinden después del ejecutable, no antes; un
   video de "suelta tu carpeta de CMYK, recibe tus muestras RGB" es lo que convierte.
4. **Más repos de e22labs**: irán saliendo de `studio-lab` (QC de entregas, PSD→spec)
   cuando cada uno tenga readme y ejemplo propios.

**Mientras no exista el ejecutable, esto NO se publica:** queda privado como el resto
de herramientas del estudio. Antes de cualquier publicación: licencia elegida (MIT si
se mantiene gratuita), readme sin nombres de clientes, y cero rutas locales.
