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
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

import muestras_core as core

APP = "muestras-rgb"
ORG = "e22lab"
COL_ARCHIVO, COL_SALIDA, COL_TAMANO, COL_PESO, COL_PERFIL, COL_ESTADO = range(6)
ELEGIR_ICC = "<elegir>"
TEXTO_SI_EXISTE = {"numerar": "Agregar (2), (3)…", "sobrescribir": "Sobrescribir",
                   "saltar": "Saltar"}


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
        carpetas = QGroupBox("Carpetas")
        fc = QFormLayout(carpetas)
        self.ed_entrada = QLineEdit()
        self.ed_entrada.setPlaceholderText("Arrastra aquí una carpeta con JPG/TIFF de impresión")
        self.ed_entrada.editingFinished.connect(self.cargar_entrada)
        self.ed_salida = QLineEdit()
        self.ed_salida.textEdited.connect(self.marcar_salida_manual)
        self.chk_sub = QCheckBox("Incluir subcarpetas")
        self.chk_sub.toggled.connect(self.cargar_entrada)
        fc.addRow("Entrada:", self._con_boton(self.ed_entrada, self.elegir_entrada))
        fc.addRow("", self.chk_sub)
        fc.addRow("Salida:", self._con_boton(self.ed_salida, self.elegir_salida))

        # --- Tamano ---------------------------------------------------------
        tamano = QGroupBox("Muestra")
        ft = QFormLayout(tamano)
        self.sp_lado = self._spin(100, 20000, 2000, " px")
        self.sp_lado.setToolTip("Las imágenes más chicas que esto no se agrandan.")
        self.sp_dpi = self._spin(1, 1200, 72, " dpi")
        self.sp_calidad = self._spin(1, 100, 92, "")
        self.sp_calidad.setToolTip("92 ≈ 500-700 KB a 2000 px; 85 aligera para envío.")
        ft.addRow("Lado más largo:", self.sp_lado)
        ft.addRow("Resolución:", self.sp_dpi)
        ft.addRow("Calidad JPEG:", self.sp_calidad)
        self.cb_perfil = QComboBox()
        self.cb_perfil.setToolTip(
            "Qué hacer con un CMYK que no trae perfil incrustado. Photoshop usa su espacio\n"
            "de trabajo CMYK (en Norteamérica suele ser U.S. Web Coated SWOP v2; en Europa,\n"
            "Coated FOGRA39). Si asumes uno, la muestra queda marcada con aviso.")
        self.cb_perfil.addItem("Saltarlos (recomendado)", "")
        for desc, ruta in core.buscar_perfiles_cmyk():
            self.cb_perfil.addItem(f"Asumir {desc}", ruta)
        self.cb_perfil.addItem("Elegir archivo .icc…", ELEGIR_ICC)
        self.cb_perfil.activated.connect(self.al_elegir_perfil)
        ft.addRow("CMYK sin perfil:", self.cb_perfil)

        # --- Nombre ---------------------------------------------------------
        nombre = QGroupBox("Nombre de salida")
        fn = QFormLayout(nombre)
        self.ed_prefijo = QLineEdit()
        self.ed_sufijo = QLineEdit()
        self.ed_nuevo = QLineEdit()
        self.ed_nuevo.setPlaceholderText("(vacío = conservar el nombre original)")
        self.chk_numerar = QCheckBox("Numerar")
        self.sp_digitos = self._spin(1, 6, 3, " dígitos")
        self.sp_inicio = self._spin(0, 99999, 1, "")
        self.sp_inicio.setPrefix("desde ")
        num = QHBoxLayout()
        for w in (self.chk_numerar, self.sp_digitos, self.sp_inicio):
            num.addWidget(w)
        self.cb_existe = QComboBox()
        for clave, texto in TEXTO_SI_EXISTE.items():
            self.cb_existe.addItem(texto, clave)
        self.lb_ejemplo = QLabel()
        self.lb_ejemplo.setStyleSheet("color: gray;")
        fn.addRow("Prefijo:", self.ed_prefijo)
        fn.addRow("Sufijo:", self.ed_sufijo)
        fn.addRow("Nombre nuevo:", self.ed_nuevo)
        fn.addRow("", num)
        fn.addRow("Si ya existe:", self.cb_existe)
        fn.addRow("Ejemplo:", self.lb_ejemplo)

        opciones = QHBoxLayout()
        opciones.addWidget(tamano)
        opciones.addWidget(nombre, 1)

        # --- Tabla ----------------------------------------------------------
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["Archivo", "Salida", "Tamaño", "Peso", "Perfil de origen", "Estado"])
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.verticalHeader().hide()
        cab = self.tabla.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(COL_ESTADO, QHeaderView.Stretch)

        # --- Pie --------------------------------------------------------------
        self.barra = QProgressBar()
        self.lb_resumen = QLabel()
        self.bt_abrir = QPushButton("Abrir carpeta de salida")
        self.bt_abrir.clicked.connect(self.abrir_salida)
        self.bt_convertir = QPushButton("Convertir")
        self.bt_convertir.setDefault(True)
        self.bt_convertir.clicked.connect(self.convertir_o_cancelar)
        pie = QHBoxLayout()
        pie.addWidget(self.lb_resumen, 1)
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
        self.resize(1000, 700)

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
        bt = QPushButton("Elegir…")
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

    def guardar_ajustes(self):
        a = self.ajustes
        o = self.opciones()
        a.setValue("entrada", self.ed_entrada.text())
        for clave in ("lado", "dpi", "calidad", "prefijo", "sufijo", "numerar", "digitos", "si_existe",
                      "perfil_cmyk"):
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
        d = QFileDialog.getExistingDirectory(self, "Carpeta con los archivos de impresión",
                                             self.ed_entrada.text())
        if d:
            self.ed_entrada.setText(d)
            self.cargar_entrada()

    def marcar_salida_manual(self, _texto):
        # Metodo y no lambda: una lambda que captura self hace que PySide6 truene
        # (segfault) al destruir la ventana.
        self.salida_manual = True

    def elegir_salida(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta donde guardar las muestras",
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
                self.ed_salida.setText(os.path.join(carpeta, "muestras"))
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
            si_existe=self.cb_existe.currentData(), perfil_cmyk=self.cb_perfil.currentData())

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
            self.cb_perfil.insertItem(i, f"Asumir {desc}", ruta)
        self.cb_perfil.setCurrentIndex(i)

    def al_elegir_perfil(self, _indice):
        if self.cb_perfil.currentData() != ELEGIR_ICC:
            return
        ruta, _ = QFileDialog.getOpenFileName(self, "Perfil CMYK a asumir", "",
                                              "Perfiles ICC (*.icc *.icm)")
        if ruta and not core.es_perfil_cmyk(ruta):
            QMessageBox.warning(self, APP, "Ese archivo no es un perfil ICC CMYK.")
            ruta = ""
        self.poner_perfil(ruta)

    def actualizar_nombres(self):
        if self.trabajador:
            return
        o = self.opciones()
        forzado = bool(o.nombre_nuevo.strip())
        self.sp_digitos.setEnabled(o.numerar or forzado)
        self.sp_inicio.setEnabled(o.numerar or forzado)
        ejemplo = self.archivos[0] if self.archivos else "portada.tif"
        self.lb_ejemplo.setText(core.nombre_salida(ejemplo, o, 0))
        destino = self.ed_salida.text().strip()
        plan = core.planear_salidas(self.archivos, destino, o) if destino else []
        for fila, salida in enumerate(plan):
            self.tabla.item(fila, COL_SALIDA).setText(
                os.path.basename(salida) if salida else "(ya existe: se salta)")
            for col in range(COL_TAMANO, 6):
                self.tabla.item(fila, col).setText("")
        self.lb_resumen.setText(f"{len(self.archivos)} archivos JPG/TIFF")

    # --- conversion -----------------------------------------------------------
    def convertir_o_cancelar(self):
        if self.trabajador:
            self.trabajador.cancelar = True
            self.bt_convertir.setEnabled(False)
            self.bt_convertir.setText("Cancelando…")
            return
        if not self.archivos:
            QMessageBox.information(self, APP, "No hay archivos JPG/TIFF en la carpeta de entrada.")
            return
        destino = self.ed_salida.text().strip()
        if not destino:
            QMessageBox.information(self, APP, "Elige una carpeta de salida.")
            return
        o = self.opciones()
        plan = core.planear_salidas(self.archivos, destino, o)
        if o.si_existe == "sobrescribir":
            existentes = sum(1 for s in plan if s and os.path.exists(s))
            if existentes and QMessageBox.question(
                    self, APP, f"Se sobrescribirán {existentes} muestras existentes. ¿Continuar?"
            ) != QMessageBox.Yes:
                return
        self.guardar_ajustes()
        self.ok = self.saltados = self.peso = 0
        self.barra.setRange(0, len(self.archivos))
        self.barra.setValue(0)
        for fila, salida in enumerate(plan):
            self.tabla.item(fila, COL_SALIDA).setText(os.path.basename(salida) if salida else "")
            self.tabla.item(fila, COL_ESTADO).setText("en cola")

        self.hilo = QThread()
        self.trabajador = Trabajador(self.archivos, plan, o)
        self.trabajador.moveToThread(self.hilo)
        self.hilo.started.connect(self.trabajador.run)
        self.trabajador.avance.connect(self.al_avanzar)
        self.trabajador.terminado.connect(self.al_terminar)
        self.bt_convertir.setText("Cancelar")
        self.hilo.start()

    def al_avanzar(self, fila, r):
        estado = {"ok": "✔ listo", "aviso": "✔ listo, ojo", "saltado": "⚠ saltado",
                  "error": "✖ error"}[r.estado]
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
        self.lb_resumen.setText(f"{self.ok} listos · {self.saltados} con aviso · "
                                f"{self.peso/1024/1024:.1f} MB")

    def al_terminar(self, cancelado):
        self.hilo.quit()
        self.hilo.wait()
        self.hilo = self.trabajador = None
        self.bt_convertir.setEnabled(True)
        self.bt_convertir.setText("Convertir")
        if cancelado:
            self.lb_resumen.setText(self.lb_resumen.text() + " · cancelado")

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
    opciones = core.Opciones(lado=500, si_existe="sobrescribir")
    plan = core.planear_salidas(archivos, salida, opciones)
    with ProcessPoolExecutor(max_workers=2) as ex:
        resultados = list(ex.map(core.procesar, archivos, plan, [opciones] * len(archivos)))
    os.makedirs(salida, exist_ok=True)
    with open(os.path.join(salida, "autoprueba.txt"), "w", encoding="utf-8") as f:
        f.write(f"muestras-rgb {core.VERSION}\n")
        for r in resultados:
            f.write(f"{r.estado}\t{os.path.basename(r.origen)}\t{r.motivo}\n")
    convertidos = sum(r.estado in ("ok", "aviso") for r in resultados)
    errores = sum(r.estado == "error" for r in resultados)
    return 0 if convertidos and not errores else 1


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName(ORG)
    app.setApplicationName(APP)
    # Botones de los dialogos estandar (Si/No, Cancelar, selector de carpetas) en el
    # idioma del sistema.
    traductor = QTranslator(app)
    if traductor.load(QLocale.system(), "qtbase", "_",
                      QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(traductor)
    if len(sys.argv) == 4 and sys.argv[1] == "--autoprueba":
        sys.exit(autoprueba(sys.argv[2], sys.argv[3]))
    v = Ventana()
    v.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()   # necesario en el .exe de PyInstaller
    main()
