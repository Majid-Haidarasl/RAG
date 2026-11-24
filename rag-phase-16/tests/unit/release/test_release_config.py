"""config/release.yaml and the file readers of the release check."""

from pathlib import Path
import zipfile

import pytest

from rag_core.quality.infrastructure.release_config import (
    load_release_settings,
    release_settings_from_dict,
)
from rag_core.quality.infrastructure.release_files import (
    evidence_matches,
    kit_texts,
    read_text,
    version_in,
    zip_names,
)
from rag_core.shared_kernel.errors import InvariantError

pytestmark = [pytest.mark.release]

ROOT = Path(__file__).resolve().parents[3]
MINIMAL = {"version": "1.0.0", "tag": "v1.0"}


def test_shipped_release_config() -> None:
    r = load_release_settings(ROOT / "config" / "release.yaml")
    assert r.config_version == "1.0.0" and r.version == "1.0.0" and r.tag == "v1.0"
    assert r.presentation.min_slides == 10 and r.presentation.max_slides == 15
    assert r.changelog.versions[0] == "0.3.0" and r.changelog.versions[-1] == "1.0.0"
    assert (
        len(r.changelog.versions) == 14 and len(r.evidence) == 13 and len(r.docs) >= 12
    )
    assert r.eval_expected == {
        "retrieval": "baseline",
        "qa_prompt": "qa.answer",
        "judge_prompt": "strict_precheck",
        "ai_ids": "baseline",
    }
    assert "config/release.yaml" in r.scan.exclude and len(r.scan.phrases) >= 8
    assert set(r.versions.values()) <= {
        "pyproject",
        "package",
        "yaml:config_version",
        "yaml:version",
    }


def test_minimal_config_defaults() -> None:
    r = release_settings_from_dict(MINIMAL)
    assert r.docs == () and r.evidence == () and r.scan.phrases == ()
    assert (
        r.presentation.path == "presentation/armanrayan-rag-core.pptx"
        and ".md" in r.scan.suffixes
    )


@pytest.mark.parametrize(
    "data",
    [
        None,
        ["x"],
        {**MINIMAL, "extra": 1},
        {**MINIMAL, "version": "1.0"},
        {**MINIMAL, "tag": "1.0"},
        {**MINIMAL, "tag": "vX"},
        {**MINIMAL, "docs": [{"path": "/abs.md"}]},
        {**MINIMAL, "docs": [{"path": "a.md", "size": 3}]},
        {**MINIMAL, "evidence": [{"name": "x"}]},
        {**MINIMAL, "scan": {"phrases": "one"}},
        {**MINIMAL, "versions": ["pyproject.toml"]},
        {**MINIMAL, "versions": {"pyproject.toml": "toml"}},
        {**MINIMAL, "eval": {"expected": ["baseline"]}},
        {**MINIMAL, "presentation": {"slides": 10}},
    ],
)
def test_release_config_errors(data: object) -> None:
    with pytest.raises(InvariantError):
        release_settings_from_dict(data)


def test_version_in(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    (tmp_path / "pkg.py").write_text(
        '"""doc"""\n\n__version__ = "1.0.0"\n', encoding="utf-8"
    )
    (tmp_path / "c.yaml").write_text("config_version: 0.15.0\n", encoding="utf-8")
    assert version_in(tmp_path, "pyproject.toml", "pyproject") == "1.0.0"
    assert version_in(tmp_path, "pkg.py", "package") == "1.0.0"
    assert version_in(tmp_path, "c.yaml", "yaml:config_version") == "0.15.0"
    assert version_in(tmp_path, "c.yaml", "yaml:version") is None
    assert version_in(tmp_path, "missing.yaml", "yaml:version") is None
    with pytest.raises(ValueError):
        version_in(tmp_path, "c.yaml", "json")


def test_kit_texts_skips_excluded_hidden_and_binary(tmp_path: Path) -> None:
    for rel in (
        "README.md",
        "docs/a.md",
        "corpus/fa/x.md",
        ".venv/lib/y.py",
        "src/pkg/__pycache__/z.py",
        "src/pkg.egg-info/SOURCES.txt",
        "data/b.json",
        "config/release.yaml",
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("text", encoding="utf-8")
    (tmp_path / "docs" / "bin.md").write_bytes(b"\xff\xfe\x00bad")
    got = [
        p
        for p, _ in kit_texts(
            tmp_path, (".md", ".py", ".txt", ".yaml"), ("corpus", "config/release.yaml")
        )
    ]
    assert got == ["README.md", "docs/a.md"]


def test_read_text_zip_names_and_evidence(tmp_path: Path) -> None:
    assert (
        read_text(tmp_path, "none.md") is None
        and zip_names(tmp_path / "none.pptx") is None
    )
    (tmp_path / "plain.pptx").write_text("not a zip", encoding="utf-8")
    assert zip_names(tmp_path / "plain.pptx") is None
    with zipfile.ZipFile(tmp_path / "deck.pptx", "w") as z:
        z.writestr("[Content_Types].xml", "<x/>")
        z.writestr("ppt/slides/slide1.xml", "<x/>")
    assert zip_names(tmp_path / "deck.pptx") == [
        "[Content_Types].xml",
        "ppt/slides/slide1.xml",
    ]
    folder = tmp_path / "results" / "phase-08"
    folder.mkdir(parents=True)
    for stamp in ("20261124T010000Z", "20261123T010000Z"):
        (folder / f"rag-demo-{stamp}.json").write_text("{}", encoding="utf-8")
    assert evidence_matches(tmp_path, "results/phase-08/rag-demo-*.json") == [
        "results/phase-08/rag-demo-20261123T010000Z.json",
        "results/phase-08/rag-demo-20261124T010000Z.json",
    ]
    assert evidence_matches(tmp_path, "results/phase-09/*.json") == []
