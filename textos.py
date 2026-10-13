# -*- coding: utf-8 -*-
"""
Textos de la app en espanol e ingles. Todo lo que ve el usuario (ventana, estados,
avisos, hoja de contactos, nombres de archivo por defecto) sale de aqui con t().

    textos.usar("en")
    textos.t("bt_convertir")                 -> "Convert"
    textos.t("resumen_archivos", n=3)        -> "3 JPG/TIFF files"

El idioma es global por proceso; los procesos de conversion lo reciben en
Opciones.idioma (muestras_core.procesar llama a usar()).
"""
IDIOMAS = ("es", "en")
_actual = "es"


def usar(idioma):
    global _actual
    _actual = idioma if idioma in IDIOMAS else "en"


def actual():
    return _actual


def resolver(preferencia, nombre_locale):
    """'auto' + 'es_MX' -> 'es'; cualquier idioma que no sea espanol -> 'en'."""
    if preferencia in IDIOMAS:
        return preferencia
    return "es" if (nombre_locale or "").lower().startswith(("es", "spanish")) else "en"


def t(clave, **datos):
    texto = TEXTOS[clave][_actual]
    return texto.format(**datos) if datos else texto


def todas(clave):
    """El texto en todos los idiomas (p. ej. para reconocer un valor por defecto)."""
    return set(TEXTOS[clave].values())


def fecha(d):
    if _actual == "es":
        return f"{d.day} de {MESES_ES[d.month - 1]} de {d.year}"
    return f"{MESES_EN[d.month - 1]} {d.day}, {d.year}"


MESES_ES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
            "septiembre", "octubre", "noviembre", "diciembre")
MESES_EN = ("January", "February", "March", "April", "May", "June", "July", "August",
            "September", "October", "November", "December")


def _(es, en):
    return {"es": es, "en": en}


TEXTOS = {
    # --- ventana: carpetas ---------------------------------------------------
    "grp_carpetas": _("Carpetas", "Folders"),
    "lbl_entrada": _("Entrada:", "Input:"),
    "lbl_salida": _("Salida:", "Output:"),
    "ph_entrada": _("Arrastra aquí una carpeta con JPG/TIFF de impresión",
                    "Drop a folder of print-ready JPG/TIFF files here"),
    "chk_sub": _("Incluir subcarpetas", "Include subfolders"),
    "bt_elegir": _("Elegir…", "Browse…"),
    "dlg_entrada": _("Carpeta con los archivos de impresión", "Folder with the print files"),
    "dlg_salida": _("Carpeta donde guardar las muestras", "Folder to save the samples in"),
    "subcarpeta": _("muestras", "samples"),

    # --- ventana: muestra ----------------------------------------------------
    "grp_muestra": _("Muestra", "Sample"),
    "lbl_lado": _("Lado más largo:", "Longest side:"),
    "tip_lado": _("Las imágenes más chicas que esto no se agrandan.",
                  "Smaller images are never enlarged."),
    "lbl_dpi": _("Resolución:", "Resolution:"),
    "lbl_calidad": _("Calidad JPEG:", "JPEG quality:"),
    "tip_calidad": _("92 ≈ 500-700 KB a 2000 px; 85 aligera para envío.",
                     "92 ≈ 500-700 KB at 2000 px; 85 is lighter for email."),
    "lbl_perfil": _("CMYK sin perfil:", "Untagged CMYK:"),
    "tip_perfil": _(
        "Qué hacer con un CMYK que no trae perfil incrustado. Photoshop usa su espacio\n"
        "de trabajo CMYK (en Norteamérica suele ser U.S. Web Coated SWOP v2; en Europa,\n"
        "Coated FOGRA39). Si asumes uno, la muestra queda marcada con aviso.",
        "What to do with a CMYK file that has no embedded profile. Photoshop uses its\n"
        "CMYK working space (usually U.S. Web Coated SWOP v2 in North America and\n"
        "Coated FOGRA39 in Europe). If you assume one, the sample gets a note."),
    "perfil_saltar": _("Saltarlos (recomendado)", "Skip them (recommended)"),
    "perfil_asumir": _("Asumir {desc}", "Assume {desc}"),
    "perfil_elegir": _("Elegir archivo .icc…", "Choose .icc file…"),
    "dlg_perfil": _("Perfil CMYK a asumir", "CMYK profile to assume"),
    "filtro_icc": _("Perfiles ICC (*.icc *.icm)", "ICC profiles (*.icc *.icm)"),
    "err_no_icc": _("Ese archivo no es un perfil ICC CMYK.", "That file is not a CMYK ICC profile."),

    # --- ventana: nombre -----------------------------------------------------
    "grp_nombre": _("Nombre de salida", "Output name"),
    "lbl_prefijo": _("Prefijo:", "Prefix:"),
    "lbl_sufijo": _("Sufijo:", "Suffix:"),
    "lbl_nuevo": _("Nombre nuevo:", "New name:"),
    "ph_nuevo": _("(vacío = conservar el nombre original)", "(empty = keep the original name)"),
    "chk_numerar": _("Numerar", "Number"),
    "suf_digitos": _(" dígitos", " digits"),
    "pre_desde": _("desde ", "from "),
    "lbl_existe": _("Si ya existe:", "If it exists:"),
    "existe_numerar": _("Agregar (2), (3)…", "Add (2), (3)…"),
    "existe_sobrescribir": _("Sobrescribir", "Overwrite"),
    "existe_saltar": _("Saltar", "Skip"),
    "lbl_ejemplo": _("Ejemplo:", "Example:"),
    "ejemplo_archivo": _("portada.tif", "cover.tif"),

    # --- ventana: entrega ----------------------------------------------------
    "grp_entrega": _("Entrega", "Delivery"),
    "lbl_marca": _("Marca de agua:", "Watermark:"),
    "marca_ninguna": _("Sin marca", "None"),
    "marca_texto": _("Texto", "Text"),
    "marca_logo": _("Logo (PNG)", "Logo (PNG)"),
    "marca_default": _("MUESTRA · NO IMPRIMIR", "PROOF · DO NOT PRINT"),
    "lbl_texto": _("Texto:", "Text:"),
    "lbl_logo": _("Logo:", "Logo:"),
    "ph_logo": _("PNG con fondo transparente", "PNG with a transparent background"),
    "dlg_logo": _("Logo para la marca de agua", "Logo for the watermark"),
    "filtro_png": _("Imágenes (*.png)", "Images (*.png)"),
    "lbl_posicion": _("Posición:", "Position:"),
    "pos_centro": _("Centro, en diagonal", "Center, diagonal"),
    "pos_mosaico": _("Mosaico", "Tiled"),
    "pos_esquina": _("Esquina", "Corner"),
    "lbl_opacidad": _("Opacidad:", "Opacity:"),
    "chk_hoja": _("Crear hoja de contactos (PDF) al terminar", "Create a contact sheet (PDF) when done"),
    "lbl_titulo": _("Título:", "Title:"),
    "ph_titulo": _("(vacío = nombre de la carpeta)", "(empty = folder name)"),
    "lbl_pagina": _("Página:", "Page:"),
    "pagina_carta": _("Carta", "Letter"),
    "pagina_a4": _("A4", "A4"),

    # --- ventana: tabla y pie ------------------------------------------------
    "col_archivo": _("Archivo", "File"),
    "col_salida": _("Salida", "Output"),
    "col_tamano": _("Tamaño", "Size"),
    "col_peso": _("Peso", "File size"),
    "col_perfil": _("Perfil de origen", "Source profile"),
    "col_estado": _("Estado", "Status"),
    "bt_abrir": _("Abrir carpeta de salida", "Open output folder"),
    "bt_convertir": _("Convertir", "Convert"),
    "bt_cancelar": _("Cancelar", "Cancel"),
    "bt_cancelando": _("Cancelando…", "Cancelling…"),
    "lbl_idioma": _("Idioma:", "Language:"),
    "idioma_auto": _("Automático", "Automatic"),
    "salida_existe": _("(ya existe: se salta)", "(exists: skipped)"),
    "resumen_archivos": _("{n} archivos JPG/TIFF", "{n} JPG/TIFF files"),
    "en_cola": _("en cola", "queued"),
    "estado_ok": _("✔ listo", "✔ done"),
    "estado_aviso": _("✔ listo, ojo", "✔ done, note"),
    "estado_saltado": _("⚠ saltado", "⚠ skipped"),
    "estado_error": _("✖ error", "✖ error"),
    "resumen_avance": _("{ok} listos · {avisos} con aviso · {mb:.1f} MB",
                        "{ok} done · {avisos} with notes · {mb:.1f} MB"),
    "resumen_cancelado": _(" · cancelado", " · cancelled"),
    "resumen_hoja": _(" · hoja de contactos: {n} pág.", " · contact sheet: {n} p."),
    "err_sin_archivos": _("No hay archivos JPG/TIFF en la carpeta de entrada.",
                          "There are no JPG/TIFF files in the input folder."),
    "err_sin_salida": _("Elige una carpeta de salida.", "Choose an output folder."),
    "err_logo": _("Elige un logo PNG válido para la marca de agua.",
                  "Choose a valid PNG logo for the watermark."),
    "confirma_sobrescribir": _("Se sobrescribirán {n} muestras existentes. ¿Continuar?",
                               "{n} existing samples will be overwritten. Continue?"),
    "err_hoja": _("No se pudo crear la hoja de contactos:\n{e}", "Couldn't create the contact sheet:\n{e}"),

    # --- nucleo: motivos de cada archivo ------------------------------------
    "ya_existe": _("ya existe en la carpeta de salida", "already exists in the output folder"),
    "modo_no_soportado": _("modo {modo} no soportado", "{modo} mode is not supported"),
    "gris_16": _(" (gris de 16/32 bits: guárdalo en 8 bits)", " (16/32-bit grayscale: save it as 8-bit)"),
    "cmyk_sin_perfil": _("CMYK sin perfil incrustado: no se adivina el origen",
                         "untagged CMYK: the source color can't be guessed"),
    "perfil_asumido": _("sin perfil incrustado: se asumió «{desc}»",
                        "no embedded profile: assumed “{desc}”"),
    "asumido": _(" (asumido)", " (assumed)"),
    "tinta_aviso": _("la muestra no incluye la tinta directa {nombres} (solo CMYK)",
                     "the sample doesn't include the spot color {nombres} (CMYK only)"),
    "tinta_cliente": _("Lleva la tinta directa {nombres}, que no se puede simular en esta muestra.",
                       "Uses the spot color {nombres}, which can't be simulated in this sample."),
    "comillas": _("«{n}»", "“{n}”"),
    "no_se_pudo_leer": _("no se pudo leer (archivo dañado o no es imagen)",
                         "couldn't read it (damaged file or not an image)"),
    "perfil_no_corresponde": _("el perfil incrustado no corresponde al modo de color",
                               "the embedded profile doesn't match the color mode"),
    "sin_perfil": _("(sin perfil)", "(no profile)"),
    "perfil_ilegible": _("(perfil ilegible)", "(unreadable profile)"),

    # --- hoja de contactos ---------------------------------------------------
    "hoja_archivo": _("{titulo} - hoja de contactos.pdf", "{titulo} - contact sheet.pdf"),
    "hoja_titulo_defecto": _("Muestras", "Samples"),
    "hoja_subtitulo": _("{n} muestras · {fecha}", "{n} samples · {fecha}"),
    "hoja_impresion": _("impresión {medida}", "print {medida}"),
    "hoja_medida": _("{w_cm:.1f} × {h_cm:.1f} cm a {dpi:.0f} dpi",
                     "{w_in:.2f} × {h_in:.2f} in at {dpi:.0f} dpi"),
    "hoja_pie": _("Colores simulados en pantalla (sRGB) a partir del archivo de impresión; "
                  "el impreso puede variar según papel y prensa.",
                  "On-screen color simulation (sRGB) from the print file; the printed piece "
                  "may vary with paper and press."),
}
