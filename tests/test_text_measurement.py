import subprocess
from pathlib import Path

import pytest

from multisubs import text_measurement
from multisubs.models import SubtitleAppearance, SubtitleBackdrop
from multisubs.text_measurement import (
    TextMeasurementInfo,
    TextMeasurer,
    build_text_measurer,
    build_unicode_text_measurer,
    estimate_unicode_text_width,
)


def _appearance(*, font: str = "Fixture Sans", fonts_dir: Path | None = None):
    return SubtitleAppearance(
        font=font,
        font_size=40,
        text_color="#FFFFFF",
        bold=False,
        italic=False,
        backdrop=SubtitleBackdrop.BOX,
        backdrop_color="#00000099",
        backdrop_size=0,
        shadow_size=2,
        fonts_dir=fonts_dir,
    )


def test_text_measurer_caches_repeated_text_for_one_run():
    calls: list[str] = []
    measurer = TextMeasurer(
        TextMeasurementInfo(
            mode="font-metrics",
            requested_font="Fixture Sans",
            resolved_font="Fixture Sans",
            resolved_style="Regular",
            font_source="fonts-dir",
            shaping="raqm",
            metric_size=40,
        ),
        lambda text: calls.append(text) or 123.5,
    )

    assert measurer.measure("repeated") == pytest.approx(123.5)
    assert measurer.measure("repeated") == pytest.approx(123.5)
    assert calls == ["repeated"]


def test_unicode_fallback_distinguishes_narrow_and_wide_glyphs():
    assert estimate_unicode_text_width("iiii", 40) < estimate_unicode_text_width(
        "MMMM", 40
    )
    assert estimate_unicode_text_width("字幕", 40) == pytest.approx(80)


@pytest.mark.parametrize(
    ("style", "bold", "italic", "expected"),
    [
        ("Regular", False, False, 0),
        ("Bold", True, False, 0),
        ("Oblique", False, True, 0),
        ("Bold Italic", True, True, 0),
        ("Regular", True, True, 2),
    ],
)
def test_style_distance_selects_bold_and_italic_faces(
    style,
    bold,
    italic,
    expected,
):
    assert text_measurement._style_distance(style, bold=bold, italic=italic) == expected


def test_missing_pillow_uses_visible_unicode_fallback(monkeypatch):
    monkeypatch.setattr("multisubs.text_measurement._load_pillow", lambda: None)

    measurer = build_text_measurer(_appearance())

    assert measurer.info.as_json() == {
        "mode": "unicode-estimate",
        "requested_font": "Fixture Sans",
        "resolved_font": None,
        "resolved_style": None,
        "font_source": "unresolved",
        "shaping": None,
        "metric_size": None,
    }
    assert "could not be resolved" in (measurer.diagnostic or "")


def test_fonts_directory_matches_internal_family_before_filename(
    tmp_path: Path,
    monkeypatch,
):
    font_path = tmp_path / "unrelated-filename.ttf"
    font_path.write_bytes(b"fixture")
    fake_font = _FakeFont("Fixture Sans", "Regular")
    image_font = _FakeImageFont(fake_font)
    monkeypatch.setattr(
        "multisubs.text_measurement._load_pillow",
        lambda: (image_font, _FakeFeatures()),
    )
    monkeypatch.setattr(
        "multisubs.text_measurement._resolve_face_from_fontconfig",
        lambda *args, **kwargs: pytest.fail("fontconfig should not be queried"),
    )

    measurer = build_text_measurer(
        _appearance(fonts_dir=tmp_path),
        language="pt",
    )

    assert measurer.info.font_source == "fonts-dir"
    assert measurer.info.resolved_font == "Fixture Sans"
    assert measurer.measure("olá") == pytest.approx(30)
    assert fake_font.calls == [("olá", "ltr", "pt")]


def test_fontconfig_substitution_is_measured_and_reported(
    tmp_path: Path,
    monkeypatch,
):
    font_path = tmp_path / "fallback.ttf"
    font_path.write_bytes(b"fixture")
    fake_font = _FakeFont("Resolved Sans", "Regular", metrics=(48, 12))
    image_font = _FakeImageFont(fake_font)
    monkeypatch.setattr(
        "multisubs.text_measurement._load_pillow",
        lambda: (image_font, _FakeFeatures()),
    )
    monkeypatch.setattr(
        "multisubs.text_measurement.shutil.which",
        lambda executable: "/usr/bin/fc-match",
    )
    output = "Resolved Sans\x1fRegular\x1f" + str(font_path) + "\x1f0"
    monkeypatch.setattr(
        "multisubs.text_measurement.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=output,
            stderr="",
        ),
    )

    measurer = build_text_measurer(
        _appearance(font="Requested Sans"),
        language="ar",
    )

    assert measurer.info.font_source == "fontconfig"
    assert measurer.info.resolved_font == "Resolved Sans"
    assert measurer.info.metric_size == 27
    assert image_font.loaded_sizes == [40, 27]
    assert "resolved to 'Resolved Sans'" in (measurer.diagnostic or "")
    assert measurer.measure("مرحبا") == pytest.approx(50)
    assert fake_font.calls == [("مرحبا", "rtl", "ar")]


def test_explicit_unicode_measurer_never_claims_exact_font_metrics():
    measurer = build_unicode_text_measurer("Unknown", 20)

    assert measurer.info.mode == "unicode-estimate"
    assert measurer.info.resolved_font is None
    assert measurer.measure("test") > 0


class _FakeFeatures:
    @staticmethod
    def check(feature: str) -> bool:
        assert feature == "raqm"
        return True


class _FakeFont:
    def __init__(
        self,
        family: str,
        style: str,
        *,
        metrics: tuple[int, int] = (32, 8),
    ) -> None:
        self.family = family
        self.style = style
        self.metrics = metrics
        self.calls: list[tuple[str, str | None, str | None]] = []

    def getname(self):
        return self.family, self.style

    def getmetrics(self):
        return self.metrics

    def getlength(self, text, *, direction=None, language=None):
        self.calls.append((text, direction, language))
        return len(text) * 10


class _FakeImageFont:
    class Layout:
        RAQM = "raqm"
        BASIC = "basic"

    def __init__(self, font: _FakeFont) -> None:
        self.font = font
        self.loaded_sizes: list[int] = []

    def truetype(self, path, size, *, index, layout_engine):
        del path, layout_engine
        if index > 0:
            raise OSError("no additional face")
        self.loaded_sizes.append(size)
        return self.font
