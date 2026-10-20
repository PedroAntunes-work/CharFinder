from pathlib import Path

import pytest

import xml_analyzer
from xml_analyzer import (
    analyze_bytes,
    analyze_file,
    apply_replacements,
    exception_catalog_path,
    load_exception_catalog,
    save_exception_rule,
    save_corrected_copy,
)


def test_exception_catalog_path_uses_executable_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable_path = tmp_path / "CharFinder.exe"
    monkeypatch.setattr(xml_analyzer.sys, "frozen", True, raising=False)
    monkeypatch.setattr(xml_analyzer.sys, "executable", str(executable_path))

    assert exception_catalog_path() == tmp_path / "character-exceptions.json"


def test_exception_catalog_path_uses_source_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(xml_analyzer.sys, "frozen", False, raising=False)

    assert exception_catalog_path() == Path(xml_analyzer.__file__).resolve().parent / (
        "character-exceptions.json"
    )


def test_saving_rule_migrates_legacy_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "app" / "character-exceptions.json"
    legacy_catalog = tmp_path / "legacy" / "character-exceptions.json"
    save_exception_rule("é", "E9", "e", legacy_catalog)
    monkeypatch.setattr(xml_analyzer, "exception_catalog_path", lambda: destination)
    monkeypatch.setattr(xml_analyzer, "_legacy_exception_catalog_path", lambda: legacy_catalog)

    save_exception_rule("ñ", "F1", "n")

    migrated_rules = load_exception_catalog(destination)
    assert migrated_rules[("é", "E9")] == ("e", "Regra personalizada")
    assert migrated_rules[("ñ", "F1")] == ("n", "Regra personalizada")
    assert legacy_catalog.exists()


def test_replaces_zero_width_space_with_regular_space() -> None:
    source = b'<?xml version="1.0" encoding="UTF-8"?><Root><Name>A\xe2\x80\x8bB</Name></Root>'
    result = analyze_bytes(source)

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.codepoint == "U+200B"
    assert finding.suggested == " "
    assert finding.path == "/Root/Name"
    assert finding.line == 1

    corrected = apply_replacements(result, {finding.offset: finding.suggested})
    assert corrected == source.replace(b"\xe2\x80\x8b", b" ")
    assert corrected[:finding.offset] == source[:finding.offset]


def test_finds_windows_1252_punctuation_under_latin1_declaration() -> None:
    source = (
        b'<?xml version="1.0" encoding="ISO-8859-1"?>'
        b"<Root><ObjetoEmenda>Transferencia Voluntaria \x96 modalidade</ObjetoEmenda></Root>"
    )
    result = analyze_bytes(source)

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.raw_hex == "96"
    assert finding.suggested == "-"
    assert finding.path == "/Root/ObjetoEmenda"
    assert finding.description == "–"
    assert "incompatibilidade" in finding.suggestion_note


def test_recognizes_curly_quotes_and_ellipsis_in_utf8() -> None:
    source = '<Root>“ação” — pronto…</Root>'.encode("utf-8")
    result = analyze_bytes(source)

    assert [finding.suggested for finding in result.findings] == ['"', '"', "-", "..."]
    assert [finding.description for finding in result.findings] == ["“", "”", "—", "…"]
    corrected = apply_replacements(
        result,
        {finding.offset: finding.suggested for finding in result.findings},
    )
    assert corrected.decode("utf-8") == '<Root>"ação" - pronto...</Root>'


def test_unclassified_unicode_format_character_is_reported_as_unknown() -> None:
    result = analyze_bytes("<Root>a\u2060b</Root>".encode("utf-8"))
    assert len(result.findings) == 1
    assert result.findings[0].codepoint == "U+2060"
    assert result.findings[0].suggested is None
    assert "desconhecido" in result.findings[0].suggestion_note


def test_xml_10_forbidden_control_is_reported_for_removal() -> None:
    result = analyze_bytes(b"<Root>a\x01b</Root>")
    finding = result.findings[0]
    assert finding.codepoint == "U+0001"
    assert finding.description == "U+0001"
    assert finding.suggested == ""
    assert finding.path == "/Root"
    assert apply_replacements(result, {finding.offset: ""}) == b"<Root>ab</Root>"


def test_replaces_c1_control_9f_with_regular_space() -> None:
    source = (
        b'<?xml version="1.0" encoding="ISO-8859-1"?>'
        b"<Root>BRANCA\x9fMARCA</Root>"
    )
    result = analyze_bytes(source)

    finding = result.findings[0]
    assert finding.codepoint == "U+009F"
    assert finding.raw_hex == "9F"
    assert finding.suggested == " "
    assert finding.suggestion_note == "Substituição automática"
    assert apply_replacements(result, {finding.offset: finding.suggested}) == source.replace(
        b"\x9f", b" "
    )


def test_exception_catalog_preserves_character_and_raw_bytes(tmp_path: Path) -> None:
    catalog_path = tmp_path / "character-exceptions.json"
    save_exception_rule("é", "E9", "e", catalog_path)
    with pytest.raises(ValueError, match="caracteres reservados"):
        save_exception_rule("x", "78", "<Root>", catalog_path)

    rules = load_exception_catalog(catalog_path)
    assert rules[("é", "E9")] == ("e", "Regra personalizada")

    latin_source = b'<?xml version="1.0" encoding="ISO-8859-1"?><Root>\xe9</Root>'
    utf8_source = "<Root>é</Root>".encode("utf-8")
    latin_result = analyze_bytes(latin_source, exception_catalog=rules)
    utf8_result = analyze_bytes(utf8_source, exception_catalog=rules)
    assert latin_result.findings[0].suggested == "e"
    assert latin_result.findings[0].raw_hex == "E9"
    assert utf8_result.findings == ()


def test_xml_whitespace_controls_are_not_reported_as_findings() -> None:
    source = b"<Root>\r\n\t<Value>ok</Value>\r\n</Root>"
    result = analyze_bytes(source)

    assert result.findings == ()
    assert apply_replacements(result, {}) == source


def test_unknown_format_and_known_characters_are_reported() -> None:
    source = "<Root>ação\u2060 normal\u200b</Root>".encode("utf-8")
    result = analyze_bytes(source)

    assert [finding.codepoint for finding in result.findings] == ["U+2060", "U+200B"]


def test_utf16_offsets_and_replacement_preserve_encoding() -> None:
    text = '<?xml version="1.0" encoding="UTF-16"?><Root>–</Root>'
    source = b"\xff\xfe" + text.encode("utf-16-le")
    result = analyze_bytes(source)
    assert result.encoding == "UTF-16 LE"
    assert result.findings[0].raw_hex == "13 20"
    corrected = apply_replacements(result, {result.findings[0].offset: "-"})
    assert corrected.startswith(b"\xff\xfe")
    assert corrected.decode("utf-16") == text.replace("–", "-")


def test_malformed_xml_is_still_scanned_for_known_characters() -> None:
    result = analyze_bytes("<Root><Name>value\u200b</Root>".encode("utf-8"))
    assert result.parse_error is not None
    assert any(finding.codepoint == "U+200B" for finding in result.findings)


def test_copy_saves_only_selected_bytes_and_keeps_original(tmp_path: Path) -> None:
    source_path = tmp_path / "source.xml"
    destination_path = tmp_path / "corrected.xml"
    source = b'<?xml version="1.0" encoding="UTF-8"?><Root><Name>one\xe2\x80\x8b two</Name></Root>'
    source_path.write_bytes(source)
    result = analyze_file(source_path)
    finding = result.findings[0]

    saved = save_corrected_copy(result, {finding.offset: " "}, destination_path)

    assert saved == destination_path
    assert source_path.read_bytes() == source
    assert destination_path.read_bytes() == source.replace(b"\xe2\x80\x8b", b" ")


def test_copy_cannot_overwrite_original(tmp_path: Path) -> None:
    source_path = tmp_path / "source.xml"
    source_path.write_bytes("<Root>\u2013</Root>".encode("utf-8"))
    result = analyze_file(source_path)

    with pytest.raises(ValueError, match="sobrescrever"):
        save_corrected_copy(
            result,
            {result.findings[0].offset: "-"},
            source_path,
        )


def test_rejects_replacement_that_could_change_xml_structure() -> None:
    result = analyze_bytes("<Root>\u2013</Root>".encode("utf-8"))
    with pytest.raises(ValueError, match="caracteres reservados"):
        apply_replacements(result, {result.findings[0].offset: "<Other>"})


def test_real_sample_offset_points_to_expected_candidate() -> None:
    sample_path = Path(__file__).parents[1] / "CADASTROSCONTABEIS_2026_A_6565_09.xml"
    if not sample_path.exists():
        pytest.skip("O XML de exemplo não está presente neste ambiente.")

    result = analyze_file(sample_path, reported_offset=1_209_088)
    sample_findings = [
        finding
        for finding in result.findings
        if finding.offset in {1_209_087, 1_209_088}
    ]

    assert sample_findings
    assert sample_findings[0].path.endswith("/ObjetoEmenda")
    assert sample_findings[0].suggested == "-"
