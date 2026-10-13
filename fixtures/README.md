# Fixtures TIFF CMYK

Carta de prueba sintética (2000×2000 px, 300 dpi, sin contenido de clientes) exportada
desde Photoshop 2026 en las variantes de TIFF que puede recibir el script. Sirve para
probar la lectura de TIFF: qué se convierte, qué se salta con aviso y qué rompe.

| Archivo | Qué es | Qué se espera |
|---|---|---|
| `tiff/08bit_lzw.tif` | CMYK 8 bits, FOGRA39 incrustado, LZW | Caso típico: se convierte |
| `tiff/08bit_zip.tif` | Igual, compresión ZIP | Se convierte |
| `tiff/08bit_jpeg.tif` | Igual, compresión JPEG dentro del TIFF | Se convierte |
| `tiff/16bit_lzw.tif` | CMYK 16 bits, FOGRA39, LZW | Hoy se salta con aviso; ¿se puede leer? |
| `tiff/08bit_capas_lzw.tif` | Con capas ("Guardar capas"): fondo, texto, capa al 60 % | Puede fallar |
| `tiff/08bit_alfa_lzw.tif` | Con un canal alfa guardado ("Alfa 1") | Puede fallar |
| `tiff/08bit_tintadirecta_lzw.tif` | Con una tinta directa ("Tinta directa prueba") | Puede fallar |
| `tiff/08bit_sinperfil_lzw.tif` | Sin perfil incrustado | Se salta con aviso |
| `tiff/08bit_gracol2006_lzw.tif` | Convertido a Coated GRACoL 2006 | Se convierte con su perfil |

## Qué trae cada archivo por dentro (verificado con Pillow)

- **Capas:** el TIFF trae el compuesto aplanado normal (4 canales) y las capas en la
  etiqueta Photoshop 37724. Un lector que solo lea la imagen principal la ve bien.
- **Alfa y tinta directa:** 5 muestras por píxel con `ExtraSamples = 0` (sin
  especificar). Por las etiquetas TIFF son indistinguibles: el nombre de la tinta
  directa no queda en ninguna etiqueta estándar.
- **16 bits:** `BitsPerSample = (16, 16, 16, 16)`.
- **Sin perfil:** pesa ~650 KB menos que `08bit_lzw.tif`, que es el tamaño del ICC de
  FOGRA39.

## Resultado con muestras_core (2026-10-13, Pillow 12.3)

Los 9 abren sin error. Las de 16 bits, capas, alfa, tinta directa y ZIP dan
**exactamente** los mismos píxeles CMYK que `08bit_lzw.tif` (y la misma muestra RGB);
la de JPEG difiere <1/255 de media por la compresión y la de GRACoL ~1-2/255.

| Archivo | Resultado |
|---|---|
| `08bit_lzw`, `08bit_zip`, `08bit_jpeg`, `08bit_gracol2006_lzw` | Se convierten |
| `16bit_lzw` | Se convierte (Pillow lo lee reducido a 8 bits) |
| `08bit_capas_lzw` | Se convierte (usa el compuesto) |
| `08bit_alfa_lzw` | Se convierte (el alfa se ignora) |
| `08bit_tintadirecta_lzw` | Se convierte **con aviso** nombrando la tinta directa, que no sale en la muestra |
| `08bit_sinperfil_lzw` | Se salta con aviso |

`python -m unittest discover tests` lo verifica.

## Regenerarlas

```
python fixtures/generar_base.py          (escribe fixtures/_base_cmyk.tif, no va al repo)
```
Después, en Photoshop, desde PowerShell:
```
$ps = New-Object -ComObject Photoshop.Application
$ps.DoJavaScriptFile("<ruta del repo>\fixtures\exportar_tiffs.jsx")
```
El registro queda en `fixtures/tiff/_export_log.txt`.
