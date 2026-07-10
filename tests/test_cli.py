import json
from pathlib import Path

from typer.testing import CliRunner

from ebook_utils.cli import app


def test_organize_is_dry_run_by_default_and_yolo_copy_applies(tmp_path: Path) -> None:
    source = tmp_path / "Example Book - Jane Doe.epub"
    source.write_text("not a real epub")
    output = tmp_path / "library"
    runner = CliRunner()

    dry_run = runner.invoke(app, ["organize", str(tmp_path), "--output-dir", str(output), "--json"])

    assert dry_run.exit_code == 0, dry_run.output
    assert '"mode": "dry-run"' in dry_run.output
    assert '"field_confidence"' in dry_run.output
    assert source.exists()
    assert not output.exists()

    yolo = runner.invoke(app, ["organize", str(tmp_path), "--output-dir", str(output), "--yolo", "--copy"])

    assert yolo.exit_code == 0, yolo.output
    assert source.exists()
    assert (output / "Example Book - Jane Doe" / "Example Book - Jane Doe.epub").exists()

    rerun = runner.invoke(app, ["plan", str(tmp_path), "--output-dir", str(output), "--yolo", "--json"])
    assert rerun.exit_code == 0, rerun.output
    rerun_plan = json.loads(rerun.output)
    assert rerun_plan["bundles"][0]["files"] == [str(source)]


def test_yolo_moves_actionable_books(tmp_path: Path) -> None:
    source = tmp_path / "Move Me - Jane Doe.pdf"
    source.write_text("not a real pdf")
    output = tmp_path / "library"

    result = CliRunner().invoke(app, ["organize", str(tmp_path), "--output-dir", str(output), "--yolo"])

    assert result.exit_code == 0, result.output
    assert not source.exists()
    assert (output / "Move Me - Jane Doe" / "Move Me - Jane Doe.pdf").exists()
