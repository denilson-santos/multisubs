import subprocess
from pathlib import Path

import pytest

from multisubs import text_measurement
from multisubs.models import (
    FontWeight,
    FontWeightInputForm,
    SubtitleAppearance,
    SubtitleBackdrop,
)
from multisubs.text_measurement import (
    TextMeasurementInfo,
    TextMeasurer,
    build_text_measurer,
    build_unicode_text_measurer,
    estimate_unicode_text_width,
)


def _appearance(
    *,
    font: str = "Fixture Sans",
    fonts_dir: Path | None = None,
    font_weight: FontWeight = FontWeight.REGULAR,
    italic: bool = False,
    letter_spacing: int = 0,
):
    return SubtitleAppearance(
        font=font,
        font_size=40,
        letter_spacing=letter_spacing,
        text_color="#FFFFFF",
        font_weight=font_weight,
        italic=italic,
        backdrop=SubtitleBackdrop.BOX,
        backdrop_color="#00000099",
        backdrop_size=0,
        shadow_size=2,
        fonts_dir=fonts_dir,
        font_weight_input=font_weight.canonical_name,
        font_weight_input_form=FontWeightInputForm.NAME,
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
    ("style", "font_weight", "italic", "expected"),
    [
        ("Regular", FontWeight.REGULAR, False, (0, 0)),
        ("Bold", FontWeight.BOLD, False, (0, 0)),
        ("Oblique", FontWeight.REGULAR, True, (0, 0)),
        ("SemiBold Italic", FontWeight.SEMI_BOLD, True, (0, 0)),
        ("Regular", FontWeight.BOLD, True, (300, 1)),
        ("Extra Bold", FontWeight.BLACK, False, (100, 0)),
    ],
)
def test_style_distance_selects_weight_and_italic_faces(
    style,
    font_weight,
    italic,
    expected,
):
    assert (
        text_measurement._style_distance(
            style,
            font_weight=font_weight,
            italic=italic,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ("Hairline", FontWeight.THIN),
        ("UltraLight Italic", FontWeight.EXTRA_LIGHT),
        ("Light", FontWeight.LIGHT),
        ("Book", FontWeight.REGULAR),
        ("Medium", FontWeight.MEDIUM),
        ("DemiBold", FontWeight.SEMI_BOLD),
        ("Bold", FontWeight.BOLD),
        ("ExtraBold", FontWeight.EXTRA_BOLD),
        ("Heavy", FontWeight.BLACK),
        ("Unspecified", FontWeight.REGULAR),
    ],
)
def test_style_metadata_maps_to_canonical_weight(style, expected):
    assert text_measurement._weight_from_style(style) is expected


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
        "requested_weight_name": "regular",
        "requested_weight": 400,
        "requested_weight_input": "regular",
        "requested_weight_input_form": "name",
        "resolved_weight_name": None,
        "resolved_weight": None,
        "weight_substituted": None,
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
    assert measurer.info.resolved_weight == 400
    assert measurer.info.weight_substituted is False
    assert measurer.measure("olá") == pytest.approx(30)
    assert fake_font.calls == [("olá", "ltr", "pt")]


def test_fonts_directory_selects_nearest_weight_with_stable_tie_breaker(
    tmp_path: Path,
    monkeypatch,
):
    regular_path = tmp_path / "a-regular.ttf"
    bold_path = tmp_path / "b-bold.ttf"
    regular_path.write_bytes(b"regular")
    bold_path.write_bytes(b"bold")
    image_font = _FakeImageFont(
        {
            regular_path.name: _FakeFont("Fixture Sans", "Regular"),
            bold_path.name: _FakeFont("Fixture Sans", "Bold"),
        }
    )
    monkeypatch.setattr(
        "multisubs.text_measurement._load_pillow",
        lambda: (image_font, _FakeFeatures()),
    )
    monkeypatch.setattr(
        "multisubs.text_measurement._resolve_face_from_fontconfig",
        lambda *args, **kwargs: pytest.fail("fontconfig should not be queried"),
    )

    semibold = build_text_measurer(
        _appearance(fonts_dir=tmp_path, font_weight=FontWeight.SEMI_BOLD)
    )
    medium = build_text_measurer(
        _appearance(fonts_dir=tmp_path, font_weight=FontWeight.MEDIUM)
    )

    assert semibold.info.resolved_style == "Bold"
    assert semibold.info.resolved_weight == 700
    assert semibold.info.weight_substituted is True
    assert "weight 'bold' (700)" in (semibold.diagnostic or "")
    assert medium.info.resolved_style == "Regular"
    assert medium.info.resolved_weight == 400


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
    calls: list[list[str]] = []

    def run(args, **kwargs):
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=output,
            stderr="",
        )

    monkeypatch.setattr("multisubs.text_measurement.subprocess.run", run)

    measurer = build_text_measurer(
        _appearance(font="Requested Sans"),
        language="ar",
    )

    assert measurer.info.font_source == "fontconfig"
    assert measurer.info.resolved_font == "Resolved Sans"
    assert measurer.info.metric_size == 27
    assert image_font.loaded_sizes == [40, 27]
    assert "resolved to 'Resolved Sans'" in (measurer.diagnostic or "")
    assert calls[0][-1].endswith(":weight=80:slant=0")
    assert measurer.measure("مرحبا") == pytest.approx(50)
    assert fake_font.calls == [("مرحبا", "rtl", "ar")]


def test_fontconfig_requests_semibold_italic_and_reports_actual_face(
    tmp_path: Path,
    monkeypatch,
):
    font_path = tmp_path / "regular.ttf"
    font_path.write_bytes(b"fixture")
    image_font = _FakeImageFont(_FakeFont("Fixture Sans", "Regular"))
    monkeypatch.setattr(
        "multisubs.text_measurement._load_pillow",
        lambda: (image_font, _FakeFeatures()),
    )
    monkeypatch.setattr(
        "multisubs.text_measurement.shutil.which",
        lambda executable: "/usr/bin/fc-match",
    )
    output = "Fixture Sans\x1fRegular\x1f" + str(font_path) + "\x1f0"
    calls: list[list[str]] = []

    def run(args, **kwargs):
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=output)

    monkeypatch.setattr("multisubs.text_measurement.subprocess.run", run)

    measurer = build_text_measurer(
        _appearance(font_weight=FontWeight.SEMI_BOLD, italic=True)
    )

    assert calls[0][-1].endswith(":weight=180:slant=100")
    assert measurer.info.resolved_weight_name == "regular"
    assert measurer.info.resolved_weight == 400
    assert measurer.info.weight_substituted is True
    assert "weight 'regular' (400)" in (measurer.diagnostic or "")


def test_explicit_unicode_measurer_never_claims_exact_font_metrics():
    measurer = build_unicode_text_measurer("Unknown", 20)

    assert measurer.info.mode == "unicode-estimate"
    assert measurer.info.resolved_font is None
    assert measurer.measure("test") > 0


@pytest.mark.parametrize(
    ("text", "expected_gaps"),
    [
        ("abc", 2),
        ("e\u0301f", 1),
        ("👩\u200d💻!", 1),
        ("字幕", 1),
        ("a b", 2),
        ("a!", 1),
        ("ab\ncd", 2),
    ],
)
def test_letter_spacing_counts_rendered_grapheme_gaps(text, expected_gaps):
    measurer = build_unicode_text_measurer("Unknown", 20, letter_spacing=3)
    base = estimate_unicode_text_width(text, 20)

    assert measurer.measure(text) == pytest.approx(base + expected_gaps * 3)


def test_letter_spacing_zero_preserves_base_measurement():
    text = "e\u0301 👩\u200d💻"
    measurer = build_unicode_text_measurer("Unknown", 20)

    assert measurer.measure(text) == pytest.approx(
        estimate_unicode_text_width(text, 20)
    )


def test_pillow_measurement_applies_shared_letter_spacing(tmp_path: Path, monkeypatch):
    font_path = tmp_path / "fixture.ttf"
    font_path.write_bytes(b"fixture")
    fake_font = _FakeFont("Fixture Sans", "Regular")
    monkeypatch.setattr(
        "multisubs.text_measurement._load_pillow",
        lambda: (_FakeImageFont(fake_font), _FakeFeatures()),
    )

    measurer = build_text_measurer(
        _appearance(fonts_dir=tmp_path, letter_spacing=3), language="pt"
    )

    assert measurer.measure("abc") == pytest.approx(36)


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

    def __init__(self, font: _FakeFont | dict[str, _FakeFont]) -> None:
        self.font = font
        self.loaded_sizes: list[int] = []

    def truetype(self, path, size, *, index, layout_engine):
        del layout_engine
        if index > 0:
            raise OSError("no additional face")
        self.loaded_sizes.append(size)
        if isinstance(self.font, dict):
            return self.font[Path(path).name]
        return self.font
