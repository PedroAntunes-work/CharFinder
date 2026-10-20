from __future__ import annotations

import codecs
import json
import os
import re
import sys
import unicodedata
import xml.parsers.expat
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

XML_DECLARATION = re.compile(
    br"<\?xml\b[^>]*\bencoding\s*=\s*(['\"])([^'\"]+)\1",
    re.IGNORECASE,
)

AUTOMATIC_REPLACEMENTS = {
    "\u2010": ("-", "Hífen tipográfico"),
    "\u2011": ("-", "Hífen não separável"),
    "\u2012": ("-", "Travessão curto"),
    "\u2013": ("-", "Travessão"),
    "\u2014": ("-", "Travessão longo"),
    "\u2015": ("-", "Travessão horizontal"),
    "\u2212": ("-", "Sinal de menos"),
    "\u2018": ("'", "Aspas curvas"),
    "\u2019": ("'", "Aspas curvas"),
    "\u201a": ("'", "Aspas curvas"),
    "\u201b": ("'", "Aspas curvas"),
    "\u201c": ('"', "Aspas curvas"),
    "\u201d": ('"', "Aspas curvas"),
    "\u201e": ('"', "Aspas curvas"),
    "\u201f": ('"', "Aspas curvas"),
    "\u2026": ("...", "Reticências"),
    "\u200b": (" ", "Espaço de largura zero"),
    "\u009f": (" ", "Caractere de controle C1"),
}


def exception_catalog_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    return base / "character-exceptions.json"


def _legacy_exception_catalog_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "CharFinder" / "character-exceptions.json"


def _rule_key(character: str, raw_hex: str) -> tuple[str, str]:
    return character, raw_hex.replace(" ", "").upper()


def _builtin_exception_rules() -> dict[tuple[str, str], tuple[str, str]]:
    rules = {
        (character, character.encode("utf-8").hex().upper()): (replacement, label)
        for character, (replacement, label) in AUTOMATIC_REPLACEMENTS.items()
    }
    for byte_value, character in CP1252_TO_UNICODE.items():
        if character in AUTOMATIC_REPLACEMENTS:
            replacement, label = AUTOMATIC_REPLACEMENTS[character]
            rules[(chr(byte_value), f"{byte_value:02X}")] = (replacement, label)
    return rules

def load_exception_catalog(
    path: str | Path | None = None,
) -> dict[tuple[str, str], tuple[str, str]]:
    catalog_path = Path(path) if path is not None else exception_catalog_path()
    if path is None and not catalog_path.exists():
        legacy_path = _legacy_exception_catalog_path()
        if legacy_path.exists():
            catalog_path = legacy_path
    if not catalog_path.exists():
        return {}
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Não foi possível ler o catálogo de caracteres: {exc}") from exc
    if (
        not isinstance(catalog, dict)
        or catalog.get("version") != 1
        or not isinstance(catalog.get("rules"), list)
    ):
        raise ValueError("O catálogo de caracteres tem formato ou versão inválidos.")
    rules: dict[tuple[str, str], tuple[str, str]] = {}
    for rule in catalog["rules"]:
        if not isinstance(rule, dict):
            raise ValueError("O catálogo contém uma regra inválida.")
        character = rule.get("character")
        raw_hex = rule.get("raw_hex")
        replacement = rule.get("replacement")
        note = rule.get("note", "Regra personalizada")
        if (
            not isinstance(character, str)
            or len(character) != 1
            or not isinstance(raw_hex, str)
            or not re.fullmatch(r"(?:[0-9A-Fa-f]{2})+", raw_hex.replace(" ", ""))
            or not isinstance(replacement, str)
            or not isinstance(note, str)
        ):
            raise ValueError("O catálogo contém uma regra com campos inválidos.")
        rules[_rule_key(character, raw_hex)] = (replacement, note)
    return rules


def load_effective_exception_catalog(
    path: str | Path | None = None,
) -> dict[tuple[str, str], tuple[str, str]]:
    rules = _builtin_exception_rules()
    rules.update(load_exception_catalog(path))
    return rules


def save_exception_rule(
    character: str, raw_hex: str, replacement: str, path: str | Path | None = None
) -> None:
    if len(character) != 1:
        raise ValueError("A exceção deve corresponder a um único caractere.")
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*", raw_hex):
        raise ValueError("Os bytes de origem devem estar em hexadecimal válido.")
    if any(char in replacement for char in "<>&"):
        raise ValueError("A substituição contém caracteres reservados do XML.")
    catalog_path = Path(path) if path is not None else exception_catalog_path()
    rules = _builtin_exception_rules()
    rules.update(load_exception_catalog(path))
    rules[_rule_key(character, raw_hex)] = (replacement, "Regra personalizada")
    catalog = {
        "version": 1,
        "rules": [
            {
                "character": char,
                "raw_hex": raw,
                "replacement": value,
                "note": note,
            }
            for (char, raw), (value, note) in sorted(
                rules.items(), key=lambda item: (ord(item[0][0]), item[0][1])
            )
        ],
    }
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = catalog_path.with_suffix(catalog_path.suffix + ".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(catalog_path)

CP1252_TO_UNICODE = {
    0x80: "\u20ac",
    0x82: "\u201a",
    0x83: "\u0192",
    0x84: "\u201e",
    0x85: "\u2026",
    0x86: "\u2020",
    0x87: "\u2021",
    0x88: "\u02c6",
    0x89: "\u2030",
    0x8A: "\u0160",
    0x8B: "\u2039",
    0x8C: "\u0152",
    0x8E: "\u017d",
    0x91: "\u2018",
    0x92: "\u2019",
    0x93: "\u201c",
    0x94: "\u201d",
    0x95: "\u2022",
    0x96: "\u2013",
    0x97: "\u2014",
    0x98: "\u02dc",
    0x99: "\u2122",
    0x9A: "\u0161",
    0x9B: "\u203a",
    0x9C: "\u0153",
    0x9E: "\u017e",
    0x9F: "\u0178",
}

@dataclass(frozen=True)
class Finding:
    offset: int
    end_offset: int
    character: str
    codepoint: str
    description: str
    line: int
    column: int
    path: str | None
    suggested: str | None
    suggestion_note: str
    raw_hex: str


@dataclass(frozen=True)
class Analysis:
    path: Path
    data: bytes
    encoding: str
    codec: str
    bom_length: int
    findings: tuple[Finding, ...]
    parse_error: str | None
    reported_offset: int | None


class XmlEncodingError(ValueError):
    def __init__(self, message: str, offset: int | None = None):
        super().__init__(message)
        self.offset = offset


def _declared_encoding(data: bytes) -> str:
    match = XML_DECLARATION.search(data[:1024])
    return match.group(2).decode("ascii") if match else "UTF-8"


def _encoding_info(data: bytes) -> tuple[str, str, int]:
    if data.startswith(codecs.BOM_UTF8):
        return "UTF-8 with BOM", "utf-8", len(codecs.BOM_UTF8)
    if data.startswith(codecs.BOM_UTF16_LE):
        return "UTF-16 LE", "utf-16-le", len(codecs.BOM_UTF16_LE)
    if data.startswith(codecs.BOM_UTF16_BE):
        return "UTF-16 BE", "utf-16-be", len(codecs.BOM_UTF16_BE)
    if data.startswith(codecs.BOM_UTF32_LE):
        return "UTF-32 LE", "utf-32-le", len(codecs.BOM_UTF32_LE)
    if data.startswith(codecs.BOM_UTF32_BE):
        return "UTF-32 BE", "utf-32-be", len(codecs.BOM_UTF32_BE)

    declared = _declared_encoding(data)
    try:
        codec = codecs.lookup(declared).name
    except LookupError as exc:
        raise XmlEncodingError(f"CodificaÃƒÂ§ÃƒÂ£o declarada nÃƒÂ£o reconhecida: {declared}.") from exc

    if codec == "utf-16":
        raise XmlEncodingError(
            "A declaraÃƒÂ§ÃƒÂ£o UTF-16 exige BOM para identificar a ordem dos bytes."
        )
    if codec == "utf-32":
        raise XmlEncodingError(
            "A declaraÃƒÂ§ÃƒÂ£o UTF-32 exige BOM para identificar a ordem dos bytes."
        )
    return declared, codec, 0


def _decode_text(data: bytes, codec: str, bom_length: int) -> str:
    payload = data[bom_length:]
    try:
        return payload.decode(codec, errors="strict")
    except UnicodeDecodeError as exc:
        raise XmlEncodingError(
            f"Os bytes nÃƒÂ£o sÃƒÂ£o vÃƒÂ¡lidos para a codificaÃƒÂ§ÃƒÂ£o {codec}.",
            bom_length + exc.start,
        ) from exc

def _is_xml10_character(character: str) -> bool:
    value = ord(character)
    return (
        value in (0x9, 0xA, 0xD)
        or 0x20 <= value <= 0xD7FF
        or 0xE000 <= value <= 0xFFFD
        or 0x10000 <= value <= 0x10FFFF
    )


def _path_spans(
    data: bytes, codec: str
) -> tuple[list[tuple[int, int, str]], str | None]:
    parser = xml.parsers.expat.ParserCreate()
    stack: list[str] = []
    spans: list[tuple[int, int, str]] = []
    parse_error = None

    def start_element(name: str, _attributes: dict[str, str]) -> None:
        stack.append(name)

    def end_element(_name: str) -> None:
        if stack:
            stack.pop()

    def character_data(value: str) -> None:
        start = parser.CurrentByteIndex
        if not stack or start < 0:
            return
        try:
            raw_text = value.encode(codec)
        except UnicodeEncodeError:
            return
        end = start + len(raw_text)
        if data[start:end] == raw_text:
            spans.append((start, end, "/" + "/".join(stack)))

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.CharacterDataHandler = character_data
    parser.SetParamEntityParsing(xml.parsers.expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        parser.Parse(data, True)
    except xml.parsers.expat.ExpatError as exc:
        parse_error = f"{exc} (linha {exc.lineno}, coluna {exc.offset})"
    return spans, parse_error


def _location(text: str, character_index: int) -> tuple[int, int]:
    line = text.count("\n", 0, character_index) + 1
    last_newline = text.rfind("\n", 0, character_index)
    return line, character_index - last_newline


def _context_path(spans: list[tuple[int, int, str]], offset: int) -> str | None:
    if not spans:
        return None
    starts = [span[0] for span in spans]
    index = bisect_right(starts, offset) - 1
    if index >= 0:
        start, end, element_path = spans[index]
        if start <= offset < end:
            return element_path
    return None


def analyze_bytes(
    data: bytes,
    path: str | Path = "<memÃƒÂ³ria>",
    reported_offset: int | None = None,
    exception_catalog: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> Analysis:
    display_encoding, codec, bom_length = _encoding_info(data)
    text = _decode_text(data, codec, bom_length)
    xml_paths, parse_error = _path_spans(data, codec)
    if parse_error:
        sanitized = bytearray(data)
        changed = False
        cursor = bom_length
        for character in text:
            try:
                encoded = character.encode(codec, errors="strict")
            except UnicodeEncodeError as exc:
                raise XmlEncodingError(
                    f"NÃƒÂ£o foi possÃƒÂ­vel mapear um caractere usando {codec}.", cursor
                ) from exc
            if not encoded:
                raise XmlEncodingError(
                    f"NÃƒÂ£o foi possÃƒÂ­vel mapear bytes de forma segura usando {codec}.",
                    cursor,
                )
            end = cursor + len(encoded)
            if not _is_xml10_character(character):
                replacement = " ".encode(codec)
                if len(replacement) == end - cursor:
                    sanitized[cursor:end] = replacement
                    changed = True
            cursor = end
        if cursor != len(data):
            raise XmlEncodingError(
                f"NÃƒÂ£o foi possÃƒÂ­vel mapear as posiÃƒÂ§ÃƒÂµes de bytes com seguranÃƒÂ§a usando {codec}.",
                cursor,
            )
        if changed:
            recovered_paths, _ = _path_spans(bytes(sanitized), codec)
            if recovered_paths:
                xml_paths = recovered_paths
    path_starts = [span[0] for span in xml_paths]

    findings: list[Finding] = []
    exception_catalog = exception_catalog or {}
    cp1252_compatible = codec in {"iso8859-1", "latin-1", "cp1252"}
    cursor = bom_length
    line = 1
    column = 1
    for character in text:
        try:
            encoded = character.encode(codec, errors="strict")
        except UnicodeEncodeError as exc:
            raise XmlEncodingError(
                f"NÃƒÂ£o foi possÃƒÂ­vel mapear um caractere usando {codec}.", cursor
            ) from exc
        if not encoded:
            raise XmlEncodingError(
                f"NÃƒÂ£o foi possÃƒÂ­vel mapear bytes de forma segura usando {codec}.", cursor
            )
        start = cursor
        end = start + len(encoded)
        current_line, current_column = line, column
        cursor = end
        if character == "\n":
            line += 1
            column = 1
        else:
            column += 1

        suggested = None
        note = ""
        description = character
        cp_value = ord(character)

        raw_hex = data[start:end].hex(" ").upper()
        catalog_rule = exception_catalog.get((character, raw_hex.replace(" ", "").upper()))
        if catalog_rule is not None:
            suggested, note = catalog_rule
            description = character if character.isprintable() else f"U+{cp_value:04X}"
        elif character in AUTOMATIC_REPLACEMENTS:
            suggested, _replacement_label = AUTOMATIC_REPLACEMENTS[character]
            description = character if character.isprintable() else f"U+{cp_value:04X}"
            note = "Substituição automática"
        elif not _is_xml10_character(character):
            suggested = ""
            description = f"U+{cp_value:04X}"
            note = "Remover este caractere"
        elif cp1252_compatible and 0x80 <= cp_value <= 0x9F:
            windows_character = CP1252_TO_UNICODE.get(cp_value)
            if windows_character in AUTOMATIC_REPLACEMENTS:
                suggested, _replacement_label = AUTOMATIC_REPLACEMENTS[windows_character]
                description = windows_character
                note = "Possível incompatibilidade de codificação"
            else:
                description = f"U+{cp_value:04X}"
                note = "Caractere desconhecido — considere salvar uma exceção"
        elif unicodedata.category(character) == "Cc" and cp_value not in (0x9, 0xA, 0xD):
            description = f"U+{cp_value:04X}"
            note = "Caractere desconhecido — considere salvar uma exceção"
        elif unicodedata.category(character) in {"Cf", "Co", "Cn", "Cs", "Zl", "Zp"}:
            description = f"U+{cp_value:04X}"
            note = "Caractere desconhecido — considere salvar uma exceção"
        if suggested is None and not note:
            continue

        path_index = bisect_right(path_starts, start) - 1
        element_path = None
        if path_index >= 0:
            span_start, span_end, candidate_path = xml_paths[path_index]
            if span_start <= start < span_end:
                element_path = candidate_path
        findings.append(
            Finding(
                offset=start,
                end_offset=end,
                character=character,
                codepoint=f"U+{cp_value:04X}",
                description=description,
                line=current_line,
                column=current_column,
                path=element_path,
                suggested=suggested,
                suggestion_note=note,
                raw_hex=data[start:end].hex(" ").upper(),
            )
        )

    if cursor != len(data):
        raise XmlEncodingError(
            f"NÃƒÂ£o foi possÃƒÂ­vel mapear as posiÃƒÂ§ÃƒÂµes de bytes com seguranÃƒÂ§a usando {codec}.",
            cursor,
        )

    return Analysis(
        path=Path(path),
        data=data,
        encoding=display_encoding,
        codec=codec,
        bom_length=bom_length,
        findings=tuple(findings),
        parse_error=parse_error,
        reported_offset=reported_offset,
    )


def analyze_file(
    path: str | Path,
    reported_offset: int | None = None,
    exception_catalog: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> Analysis:
    file_path = Path(path)
    return analyze_bytes(file_path.read_bytes(), file_path, reported_offset, exception_catalog)


def replacement_bytes(replacement: str, codec: str) -> bytes:
    if any(character in replacement for character in "<>&"):
        raise ValueError("A substituiÃƒÂ§ÃƒÂ£o contÃƒÂ©m caracteres reservados do XML.")
    try:
        return replacement.encode(codec, errors="strict")
    except (UnicodeEncodeError, LookupError) as exc:
        raise ValueError(
            f"A substituiÃƒÂ§ÃƒÂ£o nÃƒÂ£o pode ser representada na codificaÃƒÂ§ÃƒÂ£o {codec} do arquivo."
        ) from exc


def apply_replacements(analysis: Analysis, replacements: dict[int, str]) -> bytes:
    findings_by_offset = {finding.offset: finding for finding in analysis.findings}
    edits: list[tuple[int, int, bytes]] = []

    for offset, replacement in replacements.items():
        finding = findings_by_offset.get(offset)
        if finding is None:
            raise ValueError(f"Nenhum caractere analisado no byte {offset}.")
        if finding.path is None and any(char in replacement for char in "\"'"):
            raise ValueError(
                "NÃƒÂ£o ÃƒÂ© seguro inserir aspas em uma ocorrÃƒÂªncia fora de conteÃƒÂºdo XML identificado."
            )
        edits.append(
            (
                finding.offset,
                finding.end_offset,
                replacement_bytes(replacement, analysis.codec),
            )
        )

    result = bytearray(analysis.data)
    previous_start = len(analysis.data) + 1
    for start, end, replacement in sorted(edits, reverse=True):
        if end > previous_start:
            raise ValueError("As substituiÃƒÂ§ÃƒÂµes selecionadas se sobrepÃƒÂµem.")
        result[start:end] = replacement
        previous_start = start
    return bytes(result)


def xml_structure(data: bytes) -> tuple[tuple[str, tuple[str, ...]], ...]:
    parser = xml.parsers.expat.ParserCreate()
    structure: list[tuple[str, tuple[str, ...]]] = []
    parser.StartElementHandler = lambda name, attrs: structure.append(
        ("start", (name, *sorted(attrs)))
    )
    parser.EndElementHandler = lambda name: structure.append(("end", (name,)))
    parser.SetParamEntityParsing(xml.parsers.expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.Parse(data, True)
    return tuple(structure)


def save_corrected_copy(
    analysis: Analysis,
    replacements: dict[int, str],
    destination: str | Path,
) -> Path:
    destination_path = Path(destination)
    if destination_path.resolve() == analysis.path.resolve():
        raise ValueError("A cÃƒÂ³pia corrigida nÃƒÂ£o pode sobrescrever o arquivo original.")

    corrected = apply_replacements(analysis, replacements)
    try:
        original_structure = xml_structure(analysis.data)
        corrected_structure = xml_structure(corrected)
    except xml.parsers.expat.ExpatError:
        original_structure = None
        corrected_structure = None
    if original_structure is not None and corrected_structure != original_structure:
        raise ValueError("A substituiÃƒÂ§ÃƒÂ£o alteraria a estrutura XML; a cÃƒÂ³pia nÃƒÂ£o foi salva.")

    expected = apply_replacements(analysis, replacements)
    if corrected != expected:
        raise ValueError("A verificaÃƒÂ§ÃƒÂ£o byte a byte falhou; a cÃƒÂ³pia nÃƒÂ£o foi salva.")

    destination_path.write_bytes(corrected)
    return destination_path
