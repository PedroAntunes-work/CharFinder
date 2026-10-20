from __future__ import annotations

import shutil
import sys
import sysconfig
import zipfile
from pathlib import Path, PurePosixPath

from PyInstaller.utils.hooks.tcl_tk import tcltk_info


def _extract_library(archive: Path, expected_root: str, destination: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        entries = [
            (PurePosixPath(name), name)
            for name in bundle.namelist()
            if not name.endswith("/")
        ]
        roots = {parts.parts[0] for parts, _name in entries if parts.parts}
        if roots != {expected_root}:
            raise ValueError(f"Estrutura inesperada no arquivo {archive.name}.")
        for parts, name in entries:
            relative = parts.parts[1:]
            if not relative or any(part in {".", ".."} for part in relative):
                raise ValueError(f"Caminho inválido no arquivo {archive.name}.")
            target = destination.joinpath(*relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(name) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def _copy_library(source: Path, destination: Path) -> None:
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def prepare(destination: Path) -> bool:
    if tcltk_info.data_files:
        print("O hook do PyInstaller já coletou os dados Tcl/Tk.")
        return False

    tcl_root = Path(sysconfig.get_config_var("prefix")) / "tcl"
    libraries = (
        ("libtcl*.zip", "tcl_library", "_tcl_data", "init.tcl"),
        ("libtk*.zip", "tk_library", "_tk_data", "tk.tcl"),
    )
    destination.mkdir(parents=True, exist_ok=True)
    for archive_pattern, archive_root, output_name, marker in libraries:
        output = destination / output_name
        archives = sorted(tcl_root.glob(archive_pattern))
        if archives:
            _extract_library(archives[0], archive_root, output)
            continue

        candidates = [
            path.parent
            for path in tcl_root.glob("**/" + marker)
            if path.parent.name.lower().startswith(("tcl", "tk"))
        ]
        if not candidates:
            raise FileNotFoundError(
                f"Não foi possível localizar os dados Tcl/Tk de {sys.version_info.major}."
                f"{sys.version_info.minor} em {tcl_root}."
            )
        _copy_library(candidates[0], output)

    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: prepare_tcl_data.py DIRETORIO_DE_SAIDA")
    output_dir = Path(sys.argv[1]).resolve()
    if output_dir.name != "CharFinder-tcl-data" or output_dir.parent.name != "build":
        raise SystemExit("Diretório de saída de dados Tcl/Tk inválido.")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    if prepare(output_dir):
        print(f"Dados Tcl/Tk preparados em {output_dir}.")
