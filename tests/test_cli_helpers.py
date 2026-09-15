"""Test-only access to Typer parsing and request validation."""

from types import SimpleNamespace

from typer import _click as typer_click
from typer.main import get_command
from typer.testing import CliRunner

from multisubs import cli


class TestParser:
    """Inspect Typer parsing while exercising the existing request validators."""

    def parse_args(self, argv: list[str]) -> SimpleNamespace:
        try:
            self.context = get_command(cli.app).make_context("multisubs", argv)
        except typer_click.ClickException as exc:
            raise SystemExit(exc.exit_code) from exc
        return SimpleNamespace(**self.context.params)

    def fail(self, message: str) -> None:
        try:
            self.context.fail(message)
        except typer_click.ClickException as exc:
            exc.show()
            raise SystemExit(exc.exit_code) from exc

    def format_help(self) -> str:
        original_markup_mode = cli.app.rich_markup_mode
        cli.app.rich_markup_mode = None
        try:
            return CliRunner().invoke(cli.app, ["--help"]).output
        finally:
            cli.app.rich_markup_mode = original_markup_mode
