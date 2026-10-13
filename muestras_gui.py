# -*- coding: utf-8 -*-
"""
Interfaz grafica de muestras-rgb: JPG/TIFF de impresion (CMYK) -> muestras RGB
ligeras para aprobacion del cliente. La conversion vive en muestras_core.py.

Uso:  python muestras_gui.py        (requiere: pip install pillow PySide6)
"""
import multiprocessing
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

from PySide6.QtCore import (
    QLibraryInfo, QLocale, QObject, QSettings, Qt, QThread, QTranslator, QUrl, Signal,
)
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

import hoja_contactos
import muestras_core as core
import textos
from textos import t

APP = "muestras-rgb"
ORG = "e22lab"
COL_ARCHIVO, COL_SALIDA, COL_TAMANO, COL_PESO, COL_PERFIL, COL_ESTADO = range(6)
ELEGIR_ICC = "<elegir>"
# clave interna -> clave de textos.py
MARCAS = {"": "marca_ninguna", "texto": "marca_texto", "logo": "marca_logo"}
POSICIONES = {"centro": "pos_centro", "mosaico": "pos_mosaico", "esquina": "pos_esquina"}
SI_EXISTE = {"numerar": "existe_numerar", "sobrescribir": "existe_sobrescribir",
             "saltar": "existe_saltar"}
IDIOMAS = {"auto": None, "es": "Español", "en": "English"}   # nombres en su propio idioma
_ventanas = []          # mantiene vivas las ventanas al cambiar de idioma
_traductor_qt = None


class Trabajador(QObject):
    """Procesa el lote en varios procesos para no congelar la ventana."""
    avance = Signal(int, object)     # fila, Resultado
    terminado = Signal(bool)         # True si se cancelo

    def __init__(self, archivos, plan, opciones):
        super().__init__()
        self.archivos, self.plan, self.opciones = archivos, plan, opciones
        self.cancelar = False

    def run(self):
        procesos = max(1, min(4, (os.cpu_count() or 2) - 1))
        with ProcessPoolExecutor(max_workers=procesos) as ex:
            futuros = {ex.submit(core.procesar, ruta, salida, self.opciones): fila
                       for fila, (ruta, salida) in enumerate(zip(self.archivos, self.plan))}
            for fut in as_completed(futuros):
                if self.cancelar:
                    for f in futuros:
                        f.cancel()
                    break
                self.avance.emit(futuros[fut], fut.result())
        self.terminado.emit(self.cancelar)


class Ventana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Muestras RGB {core.VERSION} · e22lab")
        self.setAcceptDrops(True)
        self.ajustes = QSettings(ORG, APP)
        self.archivos = []
        self.salida_manual = False
        self.hilo = None
        self.trabajador = None

        central = QWidget()
        self.setCentralWidget(central)
        raiz = QVBoxLayout(central)

        # --- Carpetas -------------------------------------------------------
        carpetas = QGroupBox(t("grp_carpetas"))
        fc = QFormLayout(carpetas)
        self.ed_entrada = QLineEdit()
        self.ed_entrada.setPlaceholderText(t("ph_entrada"))
        self.ed_entrada.editingFinished.connect(self.cargar_entrada)
        self.ed_salida = QLineEdit()
        self.ed_salida.textEdited.connect(self.marcar_salida_manual)
        self.chk_sub = QCheckBox(t("chk_sub"))
        self.chk_sub.toggled.connect(self.cargar_entrada)
        fc.addRow(t("lbl_entrada"), self._con_boton(self.ed_entrada, self.elegir_entrada))
        fc.addRow("", self.chk_sub)
        fc.addRow(t("lbl_salida"), self._con_boton(self.ed_salida, self.elegir_salida))

        # --- Tamano ---------------------------------------------------------
        tamano = QGroupBox(t("grp_muestra"))
        ft = QFormLayout(tamano)
        self.sp_lado = self._spin(100, 20000, 2000, " px")
        self.sp_lado.setToolTip(t("tip_lado"))
        self.sp_dpi = self._spin(1, 1200, 72, " dpi")
        self.sp_calidad = self._spin(1, 100, 92, "")
        self.sp_calidad.setToolTip(t("tip_calidad"))
        ft.addRow(t("lbl_lado"), self.sp_lado)
        ft.addRow(t("lbl_dpi"), self.sp_dpi)
        ft.addRow(t("lbl_calidad"), self.sp_calidad)
        self.cb_perfil = QComboBox()
        self.cb_perfil.setToolTip(t("tip_perfil"))
        self.cb_perfil.addItem(t("perfil_saltar"), "")
        for desc, ruta in core.buscar_perfiles_cmyk():
            self.cb_perfil.addItem(t("perfil_asumir", desc=desc), ruta)
        self.cb_perfil.addItem(t("perfil_elegir"), ELEGIR_ICC)
        self.cb_perfil.activated.connect(self.al_elegir_perfil)
        ft.addRow(t("lbl_perfil"), self.cb_perfil)

        # --- Nombre ---------------------------------------------------------
        nombre = QGroupBox(t("grp_nombre"))
        fn = QFormLayout(nombre)
        self.ed_prefijo = QLineEdit()
        self.ed_sufijo = QLineEdit()
        self.ed_nuevo = QLineEdit()
        self.ed_nuevo.setPlaceholderText(t("ph_nuevo"))
        self.chk_numerar = QCheckBox(t("chk_numerar"))
        self.sp_digitos = self._spin(1, 6, 3, t("suf_digitos"))
        self.sp_inicio = self._spin(0, 99999, 1, "")
        self.sp_inicio.setPrefix(t("pre_desde"))
        num = QHBoxLayout()
        for w in (self.chk_numerar, self.sp_digitos, self.sp_inicio):
            num.addWidget(w)
        self.cb_existe = QComboBox()
        for clave, texto in SI_EXISTE.items():
            self.cb_existe.addItem(t(texto), clave)
        self.lb_ejemplo = QLabel()
        self.lb_ejemplo.setStyleSheet("color: gray;")
        fn.addRow(t("lbl_prefijo"), self.ed_prefijo)
        fn.addRow(t("lbl_sufijo"), self.ed_sufijo)
        fn.addRow(t("lbl_nuevo"), self.ed_nuevo)
        fn.addRow("", num)
        fn.addRow(t("lbl_existe"), self.cb_existe)
        fn.addRow(t("lbl_ejemplo"), self.lb_ejemplo)

        # --- Entrega: marca de agua y hoja de contactos --------------------------
        entrega = QGroupBox(t("grp_entrega"))
        fe = QFormLayout(entrega)
        self.cb_marca = QComboBox()
        for clave, texto in MARCAS.items():
            self.cb_marca.addItem(t(texto), clave)
        self.ed_marca = QLineEdit(t("marca_default"))
        self.ed_logo = QLineEdit()
        self.ed_logo.setPlaceholderText(t("ph_logo"))
        self.cb_posicion = QComboBox()
        for clave, texto in POSICIONES.items():
            self.cb_posicion.addItem(t(texto), clave)
        self.sp_opacidad = self._spin(5, 100, 35, " %")
        pos = QHBoxLayout()
        pos.addWidget(self.cb_posicion, 1)
        pos.addWidget(QLabel(t("lbl_opacidad")))
        pos.addWidget(self.sp_opacidad)
        self.chk_hoja = QCheckBox(t("chk_hoja"))
        self.ed_titulo = QLineEdit()
        self.ed_titulo.setPlaceholderText(t("ph_titulo"))
        self.cb_pagina = QComboBox()
        self.cb_pagina.addItem(t("pagina_carta"), "carta")
        self.cb_pagina.addItem(t("pagina_a4"), "a4")
        fe.addRow(t("lbl_marca"), self.cb_marca)
        fe.addRow(t("lbl_texto"), self.ed_marca)
        fe.addRow(t("lbl_logo"), self._con_boton(self.ed_logo, self.elegir_logo))
        fe.addRow(t("lbl_posicion"), pos)
        fe.addRow("", self.chk_hoja)
        fe.addRow(t("lbl_titulo"), self.ed_titulo)
        fe.addRow(t("lbl_pagina"), self.cb_pagina)
        for w in (self.cb_marca, self.chk_hoja):
            (w.currentIndexChanged if isinstance(w, QComboBox) else w.toggled).connect(
                self.actualizar_entrega)

        opciones = QHBoxLayout()
        opciones.addWidget(tamano)
        opciones.addWidget(nombre, 1)
        opciones.addWidget(entrega, 1)

        # --- Tabla ----------------------------------------------------------
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            [t(c) for c in ("col_archivo", "col_salida", "col_tamano", "col_peso", "col_perfil",
                            "col_estado")])
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.verticalHeader().hide()
        cab = self.tabla.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(COL_ESTADO, QHeaderView.Stretch)

        # --- Pie --------------------------------------------------------------
        self.barra = QProgressBar()
        self.lb_resumen = QLabel()
        self.bt_abrir = QPushButton(t("bt_abrir"))
        self.bt_abrir.clicked.connect(self.abrir_salida)
        self.bt_convertir = QPushButton(t("bt_convertir"))
        self.bt_convertir.setDefault(True)
        self.bt_convertir.clicked.connect(self.convertir_o_cancelar)
        self.cb_idioma = QComboBox()
        for clave, nombre_idioma in IDIOMAS.items():
            self.cb_idioma.addItem(nombre_idioma or t("idioma_auto"), clave)
        pie = QHBoxLayout()
        pie.addWidget(self.lb_resumen, 1)
        pie.addWidget(QLabel(t("lbl_idioma")))
        pie.addWidget(self.cb_idioma)
        pie.addWidget(self.bt_abrir)
        pie.addWidget(self.bt_convertir)

        raiz.addWidget(carpetas)
        raiz.addLayout(opciones)
        raiz.addWidget(self.tabla, 1)
        raiz.addWidget(self.barra)
        raiz.addLayout(pie)

        self.cargar_ajustes()
        for w in (self.ed_prefijo, self.ed_sufijo, self.ed_nuevo):
            w.textChanged.connect(self.actualizar_nombres)
        for w in (self.sp_digitos, self.sp_inicio):
            w.valueChanged.connect(self.actualizar_nombres)
        self.chk_numerar.toggled.connect(self.actualizar_nombres)
        self.cb_existe.currentIndexChanged.connect(self.actualizar_nombres)
        self.cargar_entrada()
        self.actualizar_entrega()
        self.cb_idioma.setCurrentIndex(max(0, self.cb_idioma.findData(self.ajustes.value("idioma", "auto"))))
        self.cb_idioma.currentIndexChanged.connect(self.cambiar_idioma)
        self.resize(1280, 780)

    # --- utilidades de construccion ---------------------------------------
    def _spin(self, minimo, maximo, valor, sufijo):
        s = QSpinBox()
        s.setRange(minimo, maximo)
        s.setValue(valor)
        s.setSuffix(sufijo)
        return s

    def _con_boton(self, editor, accion):
        caja = QHBoxLayout()
        caja.addWidget(editor, 1)
        bt = QPushButton(t("bt_elegir"))
        bt.clicked.connect(accion)
        caja.addWidget(bt)
        return caja

    # --- ajustes persistentes -----------------------------------------------
    def cargar_ajustes(self):
        a = self.ajustes
        self.ed_entrada.setText(a.value("entrada", ""))
        self.sp_lado.setValue(int(a.value("lado", 2000)))
        self.sp_dpi.setValue(int(a.value("dpi", 72)))
        self.sp_calidad.setValue(int(a.value("calidad", 92)))
        self.ed_prefijo.setText(a.value("prefijo", ""))
        self.ed_sufijo.setText(a.value("sufijo", ""))
        self.chk_numerar.setChecked(a.value("numerar", False, type=bool))
        self.sp_digitos.setValue(int(a.value("digitos", 3)))
        self.cb_existe.setCurrentIndex(max(0, self.cb_existe.findData(a.value("si_existe", "numerar"))))
        self.poner_perfil(a.value("perfil_cmyk", ""))
        self.cb_marca.setCurrentIndex(max(0, self.cb_marca.findData(a.value("marca", ""))))
        marca = a.value("marca_texto", t("marca_default"))
        # El texto por defecto sigue al idioma; uno escrito por el usuario se respeta.
        self.ed_marca.setText(t("marca_default") if marca in textos.todas("marca_default") else marca)
        self.ed_logo.setText(a.value("marca_logo", ""))
        self.cb_posicion.setCurrentIndex(
            max(0, self.cb_posicion.findData(a.value("marca_posicion", "centro"))))
        self.sp_opacidad.setValue(int(a.value("marca_opacidad", 35)))
        self.chk_hoja.setChecked(a.value("hoja", False, type=bool))
        self.cb_pagina.setCurrentIndex(max(0, self.cb_pagina.findData(a.value("pagina", "carta"))))

    def guardar_ajustes(self):
        a = self.ajustes
        o = self.opciones()
        a.setValue("entrada", self.ed_entrada.text())
        a.setValue("marca", self.cb_marca.currentData())
        a.setValue("marca_texto", self.ed_marca.text())
        a.setValue("marca_logo", self.ed_logo.text())
        a.setValue("hoja", self.chk_hoja.isChecked())
        a.setValue("pagina", self.cb_pagina.currentData())
        for clave in ("lado", "dpi", "calidad", "prefijo", "sufijo", "numerar", "digitos", "si_existe",
                      "perfil_cmyk", "marca_posicion", "marca_opacidad"):
            a.setValue(clave, getattr(o, clave))

    def closeEvent(self, ev):
        if self.trabajador:
            self.trabajador.cancelar = True
            self.hilo.quit()
            self.hilo.wait()
        self.guardar_ajustes()
        super().closeEvent(ev)

    # --- carpetas -------------------------------------------------------------
    def elegir_entrada(self):
        d = QFileDialog.getExistingDirectory(self, t("dlg_entrada"),
                                             self.ed_entrada.text())
        if d:
            self.ed_entrada.setText(d)
            self.cargar_entrada()

    def marcar_salida_manual(self, _texto):
        # Metodo y no lambda: una lambda que captura self hace que PySide6 truene
        # (segfault) al destruir la ventana.
        self.salida_manual = True

    def elegir_salida(self):
        d = QFileDialog.getExistingDirectory(self, t("dlg_salida"),
                                             self.ed_salida.text() or self.ed_entrada.text())
        if d:
            self.ed_salida.setText(d)
            self.salida_manual = True
            self.actualizar_nombres()

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        ruta = ev.mimeData().urls()[0].toLocalFile()
        if os.path.isfile(ruta):
            ruta = os.path.dirname(ruta)
        self.ed_entrada.setText(ruta)
        self.cargar_entrada()

    def cargar_entrada(self):
        if self.trabajador:
            return
        carpeta = self.ed_entrada.text().strip()
        if not os.path.isdir(carpeta):
            self.archivos = []
        else:
            carpeta = os.path.normpath(carpeta)
            if not self.salida_manual:
                self.ed_salida.setText(os.path.join(carpeta, t("subcarpeta")))
            destino = os.path.normpath(self.ed_salida.text())
            # Nunca reprocesar las muestras que ya generamos dentro de la entrada.
            self.archivos = [f for f in core.listar_archivos(carpeta, self.chk_sub.isChecked())
                             if not os.path.normpath(f).startswith(destino + os.sep)]
        self.tabla.setRowCount(len(self.archivos))
        for fila, ruta in enumerate(self.archivos):
            rel = os.path.relpath(ruta, carpeta)
            self.tabla.setItem(fila, COL_ARCHIVO, QTableWidgetItem(rel))
            for col in range(1, 6):
                self.tabla.setItem(fila, col, QTableWidgetItem(""))
        self.barra.setValue(0)
        self.actualizar_nombres()

    # --- nombres ------------------------------------------------------------
    def opciones(self):
        return core.Opciones(
            lado=self.sp_lado.value(), calidad=self.sp_calidad.value(), dpi=self.sp_dpi.value(),
            prefijo=self.ed_prefijo.text(), sufijo=self.ed_sufijo.text(),
            nombre_nuevo=self.ed_nuevo.text(), numerar=self.chk_numerar.isChecked(),
            digitos=self.sp_digitos.value(), inicio=self.sp_inicio.value(),
            si_existe=self.cb_existe.currentData(), perfil_cmyk=self.cb_perfil.currentData(),
            marca_texto=self.ed_marca.text() if self.cb_marca.currentData() == "texto" else "",
            marca_logo=self.ed_logo.text().strip() if self.cb_marca.currentData() == "logo" else "",
            marca_posicion=self.cb_posicion.currentData(), marca_opacidad=self.sp_opacidad.value(),
            idioma=textos.actual())

    # --- entrega --------------------------------------------------------------
    def actualizar_entrega(self, *_):
        marca = self.cb_marca.currentData()
        self.ed_marca.setEnabled(marca == "texto")
        self.ed_logo.setEnabled(marca == "logo")
        self.cb_posicion.setEnabled(bool(marca))
        self.sp_opacidad.setEnabled(bool(marca))
        self.ed_titulo.setEnabled(self.chk_hoja.isChecked())
        self.cb_pagina.setEnabled(self.chk_hoja.isChecked())

    def elegir_logo(self):
        ruta, _ = QFileDialog.getOpenFileName(self, t("dlg_logo"),
                                              self.ed_logo.text(), t("filtro_png"))
        if ruta:
            self.ed_logo.setText(ruta)
            self.cb_marca.setCurrentIndex(self.cb_marca.findData("logo"))

    def titulo_hoja(self):
        return (self.ed_titulo.text().strip()
                or os.path.basename(os.path.normpath(self.ed_entrada.text().strip()))
                or t("hoja_titulo_defecto"))

    def crear_hoja(self):
        destino = self.ed_salida.text().strip()
        titulo = self.titulo_hoja()
        ruta = os.path.join(destino, t("hoja_archivo",
                                       titulo=core.limpiar_nombre(titulo) or t("hoja_titulo_defecto")))
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            paginas = hoja_contactos.crear(
                [r for r in self.resultados if r], ruta, titulo, self.cb_pagina.currentData())
            return t("resumen_hoja", n=paginas)
        except Exception as e:
            QMessageBox.warning(self, APP, t("err_hoja", e=e))
            return ""
        finally:
            QApplication.restoreOverrideCursor()

    # --- perfil para CMYK sin perfil --------------------------------------------
    def poner_perfil(self, ruta):
        """Selecciona `ruta` en la lista (agregandola si no estaba); vacia = saltar."""
        if not ruta or not os.path.isfile(ruta) or not core.es_perfil_cmyk(ruta):
            self.cb_perfil.setCurrentIndex(0)
            return
        i = self.cb_perfil.findData(ruta)
        if i < 0:
            desc = core.descripcion_perfil(core.leer_perfil(ruta))
            i = self.cb_perfil.count() - 1          # antes de "Elegir archivo…"
            self.cb_perfil.insertItem(i, t("perfil_asumir", desc=desc), ruta)
        self.cb_perfil.setCurrentIndex(i)

    def al_elegir_perfil(self, _indice):
        if self.cb_perfil.currentData() != ELEGIR_ICC:
            return
        ruta, _ = QFileDialog.getOpenFileName(self, t("dlg_perfil"), "", t("filtro_icc"))
        if ruta and not core.es_perfil_cmyk(ruta):
            QMessageBox.warning(self, APP, t("err_no_icc"))
            ruta = ""
        self.poner_perfil(ruta)

    def actualizar_nombres(self):
        if self.trabajador:
            return
        o = self.opciones()
        forzado = bool(o.nombre_nuevo.strip())
        self.sp_digitos.setEnabled(o.numerar or forzado)
        self.sp_inicio.setEnabled(o.numerar or forzado)
        ejemplo = self.archivos[0] if self.archivos else t("ejemplo_archivo")
        self.lb_ejemplo.setText(core.nombre_salida(ejemplo, o, 0))
        destino = self.ed_salida.text().strip()
        plan = core.planear_salidas(self.archivos, destino, o) if destino else []
        for fila, salida in enumerate(plan):
            self.tabla.item(fila, COL_SALIDA).setText(
                os.path.basename(salida) if salida else t("salida_existe"))
            for col in range(COL_TAMANO, 6):
                self.tabla.item(fila, col).setText("")
        self.lb_resumen.setText(t("resumen_archivos", n=len(self.archivos)))

    # --- conversion -----------------------------------------------------------
    def convertir_o_cancelar(self):
        if self.trabajador:
            self.trabajador.cancelar = True
            self.bt_convertir.setEnabled(False)
            self.bt_convertir.setText(t("bt_cancelando"))
            return
        if not self.archivos:
            QMessageBox.information(self, APP, t("err_sin_archivos"))
            return
        destino = self.ed_salida.text().strip()
        if not destino:
            QMessageBox.information(self, APP, t("err_sin_salida"))
            return
        o = self.opciones()
        if self.cb_marca.currentData() == "logo":
            try:
                core.Image.open(o.marca_logo).verify()
            except Exception:
                QMessageBox.information(self, APP, t("err_logo"))
                return
        plan = core.planear_salidas(self.archivos, destino, o)
        if o.si_existe == "sobrescribir":
            existentes = sum(1 for s in plan if s and os.path.exists(s))
            if existentes and QMessageBox.question(
                    self, APP, t("confirma_sobrescribir", n=existentes)
            ) != QMessageBox.Yes:
                return
        self.guardar_ajustes()
        self.ok = self.saltados = self.peso = 0
        self.resultados = [None] * len(self.archivos)
        self.barra.setRange(0, len(self.archivos))
        self.barra.setValue(0)
        for fila, salida in enumerate(plan):
            self.tabla.item(fila, COL_SALIDA).setText(os.path.basename(salida) if salida else "")
            self.tabla.item(fila, COL_ESTADO).setText(t("en_cola"))

        self.hilo = QThread()
        self.trabajador = Trabajador(self.archivos, plan, o)
        self.trabajador.moveToThread(self.hilo)
        self.hilo.started.connect(self.trabajador.run)
        self.trabajador.avance.connect(self.al_avanzar)
        self.trabajador.terminado.connect(self.al_terminar)
        self.bt_convertir.setText(t("bt_cancelar"))
        self.cb_idioma.setEnabled(False)
        self.hilo.start()

    def al_avanzar(self, fila, r):
        self.resultados[fila] = r
        estado = t("estado_" + r.estado)
        if r.motivo:
            estado += f": {r.motivo}"
        self.tabla.item(fila, COL_ESTADO).setText(estado)
        self.tabla.item(fila, COL_ESTADO).setToolTip(estado)
        self.tabla.item(fila, COL_PERFIL).setText(
            f"{r.modo_origen} · {r.perfil_origen}" if r.modo_origen else "")
        if r.estado in ("ok", "aviso"):
            self.ok += 1
            self.peso += r.peso
            self.tabla.item(fila, COL_TAMANO).setText(f"{r.ancho}×{r.alto}")
            self.tabla.item(fila, COL_PESO).setText(f"{r.peso/1024:.0f} KB")
        if r.estado != "ok":
            self.saltados += 1
        self.barra.setValue(self.barra.value() + 1)
        self.lb_resumen.setText(t("resumen_avance", ok=self.ok, avisos=self.saltados,
                                  mb=self.peso / 1024 / 1024))

    def al_terminar(self, cancelado):
        self.hilo.quit()
        self.hilo.wait()
        self.hilo = self.trabajador = None
        self.bt_convertir.setEnabled(True)
        self.bt_convertir.setText(t("bt_convertir"))
        self.cb_idioma.setEnabled(True)
        if cancelado:
            self.lb_resumen.setText(self.lb_resumen.text() + t("resumen_cancelado"))
        elif self.chk_hoja.isChecked() and self.ok:
            self.lb_resumen.setText(self.lb_resumen.text() + self.crear_hoja())

    def cambiar_idioma(self, _indice):
        """Guarda todo, aplica el idioma y reabre la ventana en el mismo lugar."""
        self.ajustes.setValue("idioma", self.cb_idioma.currentData())
        self.guardar_ajustes()
        aplicar_idioma(QApplication.instance(), self.cb_idioma.currentData())
        nueva = Ventana()
        if self.salida_manual:          # la automatica se recalcula en el idioma nuevo
            nueva.salida_manual = True
            nueva.ed_salida.setText(self.ed_salida.text())
            nueva.cargar_entrada()
        nueva.setGeometry(self.geometry())
        nueva.show()
        _ventanas.append(nueva)
        self.hide()

    def abrir_salida(self):
        d = self.ed_salida.text().strip()
        if os.path.isdir(d):
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))


def autoprueba(entrada, salida):
    """
    Prueba de humo del ejecutable empaquetado (la usa la GitHub Action): crea la
    ventana sin mostrarla y convierte `entrada` en `salida` con varios procesos,
    que es lo que suele romperse al congelar con PyInstaller. Escribe un reporte
    en salida/autoprueba.txt y devuelve 0 si nada termino en error.
    """
    Ventana()
    archivos = core.listar_archivos(entrada)
    # Marca de agua y hoja de contactos: comprueban que la fuente y el icono de
    # recursos/ quedaron dentro del paquete.
    opciones = core.Opciones(lado=500, si_existe="sobrescribir", marca_texto=t("marca_default"),
                             marca_posicion="mosaico", idioma=textos.actual())
    plan = core.planear_salidas(archivos, salida, opciones)
    with ProcessPoolExecutor(max_workers=2) as ex:
        resultados = list(ex.map(core.procesar, archivos, plan, [opciones] * len(archivos)))
    os.makedirs(salida, exist_ok=True)
    if not os.path.isfile(core.recurso("icono.png")):
        raise SystemExit("falta recursos/icono.png en el paquete")
    paginas = hoja_contactos.crear(resultados, os.path.join(salida, "hoja.pdf"), "Autoprueba ñ")
    with open(os.path.join(salida, "autoprueba.txt"), "w", encoding="utf-8") as f:
        f.write(f"muestras-rgb {core.VERSION} · hoja de contactos: {paginas} pag.\n")
        for r in resultados:
            f.write(f"{r.estado}\t{os.path.basename(r.origen)}\t{r.motivo}\n")
    convertidos = sum(r.estado in ("ok", "aviso") for r in resultados)
    errores = sum(r.estado == "error" for r in resultados)
    return 0 if convertidos and not errores else 1


def aplicar_idioma(app, preferencia):
    """
    'auto' sigue al sistema (espanol si el sistema esta en espanol; si no, ingles).
    Tambien cambia los botones de los dialogos estandar de Qt (Si/No, Cancelar,
    selector de carpetas).
    """
    global _traductor_qt
    idioma = textos.resolver(preferencia, QLocale.system().name())
    textos.usar(idioma)
    if _traductor_qt:
        app.removeTranslator(_traductor_qt)
    _traductor_qt = QTranslator(app)
    if _traductor_qt.load(QLocale(idioma), "qtbase", "_",
                          QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(_traductor_qt)


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName(ORG)
    app.setApplicationName(APP)
    app.setWindowIcon(QIcon(core.recurso("icono.png")))
    aplicar_idioma(app, QSettings(ORG, APP).value("idioma", "auto"))
    if len(sys.argv) == 4 and sys.argv[1] == "--autoprueba":
        sys.exit(autoprueba(sys.argv[2], sys.argv[3]))
    v = Ventana()
    v.show()
    _ventanas.append(v)
    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()   # necesario en el .exe de PyInstaller
    main()
