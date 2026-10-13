# -*- coding: utf-8 -*-
"""
Empaqueta la interfaz grafica con PyInstaller y la comprime en un .zip listo para
publicar. Se usa igual en local y en la GitHub Action (.github/workflows/empaquetar.yml).

    pip install -r requirements.txt pyinstaller
    python empaquetar.py                 (version de muestras_core.VERSION)
    python empaquetar.py --version 0.2.0

Sale en dist/:
  Windows  MuestrasRGB-<version>-windows-x64.zip   (carpeta con MuestrasRGB.exe)
  macOS    MuestrasRGB-<version>-macos-<arch>.zip   (Muestras RGB.app)
  Linux    MuestrasRGB-<version>-linux-x64.zip      (solo para probar)

Se empaqueta en modo carpeta (--onedir), no en un solo .exe: arranca mas rapido y
los antivirus lo marcan mucho menos como falso positivo.
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys

import PyInstaller.__main__

import muestras_core as core

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(RAIZ, "dist")
NOMBRE_MAC = "Muestras RGB"     # nombre visible del .app
NOMBRE = "MuestrasRGB"          # ejecutable de Windows/Linux y nombre del zip


def plataforma():
    if sys.platform == "win32":
        return "windows-x64"
    if sys.platform == "darwin":
        return "macos-" + ("arm64" if platform.machine() == "arm64" else "x64")
    return "linux-x64"


# Traducciones de Qt que se conservan; las otras ~100 solo ocupan espacio.
IDIOMAS = ("es", "en")


def podar_traducciones(carpeta):
    for raiz, _, nombres in os.walk(carpeta):
        if os.path.basename(raiz) != "translations":
            continue
        for n in nombres:
            idioma = os.path.splitext(n)[0].split("_", 1)[-1]
            if n.endswith(".qm") and idioma.split("_")[0] not in IDIOMAS:
                os.remove(os.path.join(raiz, n))


def main():
    p = argparse.ArgumentParser(description="Empaqueta muestras-rgb con PyInstaller.")
    p.add_argument("--version", default=core.VERSION)
    args = p.parse_args()
    version = args.version.lstrip("v")
    mac = sys.platform == "darwin"
    nombre = NOMBRE_MAC if mac else NOMBRE

    opciones = [
        os.path.join(RAIZ, "muestras_gui.py"),
        "--name", nombre,
        "--windowed",
        "--onedir",
        "--noconfirm",
        "--clean",
        "--distpath", DIST,
        "--workpath", os.path.join(RAIZ, "build"),
        "--specpath", os.path.join(RAIZ, "build"),
        # Nada de esto se usa; solo engorda el paquete.
        "--exclude-module", "tkinter",
        "--exclude-module", "numpy",
    ]
    if mac:
        opciones += ["--osx-bundle-identifier", "com.estudioveintidoslab.muestrasrgb"]
    PyInstaller.__main__.run(opciones)

    podar_traducciones(DIST)

    if mac:
        app = os.path.join(DIST, f"{NOMBRE_MAC}.app")
        plist = os.path.join(app, "Contents", "Info.plist")
        for clave, valor in (("CFBundleShortVersionString", version),
                             ("CFBundleVersion", version)):
            subprocess.run(["plutil", "-replace", clave, "-string", valor, plist], check=True)
        subprocess.run(["plutil", "-replace", "NSHumanReadableCopyright", "-string",
                        "Estudio Veintidós Lab (e22lab) · MIT", plist], check=True)
        # Tocar el .app (plist, traducciones) invalida la firma ad-hoc que pone
        # PyInstaller, y en Apple Silicon un binario sin firma valida no abre.
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", app], check=True)

    zip_base = os.path.join(DIST, f"{NOMBRE}-{version}-{plataforma()}")
    if mac:
        # ditto conserva los symlinks y atributos del .app; shutil.make_archive no.
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        app, zip_base + ".zip"], check=True)
    else:
        shutil.make_archive(zip_base, "zip", DIST, nombre)
    print(f"OK {zip_base}.zip")


if __name__ == "__main__":
    main()
