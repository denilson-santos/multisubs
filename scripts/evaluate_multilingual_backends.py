"""Evaluate pinned local text libraries, with socket access disabled.

Use the isolated environment described in the multilingual Plan 0. No speech
model is loaded. The output contains only synthetic fixture text and hashes.
"""

from __future__ import annotations

import hashlib
import json
import socket
import tempfile
import time
from importlib.metadata import distribution
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def evaluate() -> dict[str, Any]:
    """Return reproducible observations, not a production segmentation adapter."""
    import jieba
    from fontTools.ttLib import TTFont
    from sudachipy import dictionary, tokenizer
    from uniseg.graphemecluster import grapheme_clusters
    from uniseg.linebreak import line_break_boundaries

    cases = json.loads((ROOT / "tests/fixtures/multilingual/cases.json").read_text())
    report: dict[str, Any] = {"packages": {}, "graphemes": [], "lexical": []}
    for name in ("fonttools", "uniseg", "SudachiPy", "SudachiDict-small", "jieba"):
        package = distribution(name)
        report["packages"][name] = {
            "version": package.version,
            "requires_python": package.metadata["Requires-Python"],
            "installed_bytes": sum(
                Path(str(package.locate_file(f))).stat().st_size
                for f in package.files or ()
                if Path(str(package.locate_file(f))).is_file()
            ),
            "resource_sha256": {
                str(f): hashlib.sha256(
                    Path(str(package.locate_file(f))).read_bytes()
                ).hexdigest()
                for f in package.files or ()
                if str(f).endswith(("system.dic", "dict.txt"))
            },
        }
    with patch.object(socket, "socket", side_effect=AssertionError("Network disabled")):
        started = time.perf_counter()
        japanese = dictionary.Dictionary(dict="small").create()
        report["japanese_init_seconds"] = time.perf_counter() - started
        for case in cases["clusters"]:
            actual = list(grapheme_clusters(case["text"]))
            assert actual == case["clusters"], case["id"]
            report["graphemes"].append({"id": case["id"], "clusters": actual})
        with tempfile.TemporaryDirectory(prefix="multisubs-jieba-") as cache:
            chinese = jieba.Tokenizer()
            chinese.tmp_dir = cache
            chinese.initialize()
            for case in cases["lexical"]:
                text = case["text"]
                if case["language"] == "ja":
                    tokens = [
                        {
                            "text": m.surface(),
                            "start": m.begin(),
                            "end": m.end(),
                            "pos": list(m.part_of_speech()),
                        }
                        for m in japanese.tokenize(
                            text, tokenizer.Tokenizer.SplitMode.B
                        )
                    ]
                else:
                    tokens = [
                        {"text": token, "start": start, "end": end}
                        for token, start, end in chinese.tokenize(text, HMM=True)
                    ]
                assert "".join(t["text"] for t in tokens) == text
                assert all(text[t["start"] : t["end"]] == t["text"] for t in tokens)
                # Prototype adapter: rejoin inflectional tails and graphemes.
                boundaries = {0, len(text), *(t["end"] for t in tokens)}
                for token in tokens:
                    pos = token.get("pos", [])
                    if pos and (
                        pos[0] == "助動詞"
                        or (pos[0] in {"動詞", "形容詞"} and pos[1] == "非自立可能")
                    ):
                        boundaries.discard(token["start"])
                grapheme_ends = {0}
                cursor = 0
                for cluster in grapheme_clusters(text):
                    cursor += len(cluster)
                    grapheme_ends.add(cursor)
                boundaries = sorted(boundaries & grapheme_ends | {0})
                groups = [
                    text[a:b]
                    for a, b in zip(
                        boundaries[:-1],
                        boundaries[1:],
                        strict=True,
                    )
                ]
                assert "".join(groups) == text
                assert any(case["protected"] in group for group in groups)
                report["lexical"].append(
                    {
                        "text": text,
                        "tokens": tokens,
                        "prototype_display_groups": groups,
                        "protected_is_raw_token": case["protected"]
                        in [t["text"] for t in tokens],
                        "line_boundaries": list(line_break_boundaries(text)),
                    }
                )
        face_path = ROOT / "multisubs/assets/fonts/inter/Inter-SemiBold.ttf"
        with TTFont(face_path, lazy=True) as face:
            cmap = face.getBestCmap() or {}
            report["inter_coverage"] = {c: ord(c) in cmap for c in "字幕A"}
        report["inter_sha256"] = hashlib.sha256(face_path.read_bytes()).hexdigest()
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
