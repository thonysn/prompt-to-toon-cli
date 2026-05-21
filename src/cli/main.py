"""
src/cli/main.py
toon CLI — convert any prompt or structured file to .toon format.

Usage:
  toon spec.json
  toon spec.json --pretty --validate
  toon --text "Create a FastAPI auth service"
  cat spec.yaml | toon --stdin --stdout
  toon validate result.toon
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from ..generator.toon_generator import generate
from ..parser.input_parser import parse_file, parse_stdin, parse_text
from ..parser.normalizer import normalize
from ..validator.toon_validator import validate as toon_validate
from ..writer.file_writer import derive_output_path, write


# ---------------------------------------------------------------------------
# Shared pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(parsed_input, output, compact, pretty, validate_flag, stdout_flag):
    doc = normalize(parsed_input)
    toon = generate(doc, compact=compact, pretty=pretty)
    result = toon_validate(toon)
    if not result.valid:
        click.echo(f"Error: Validation failed:\n{result}", err=True)
        sys.exit(1)
    if validate_flag:
        click.echo(str(result))
    if stdout_flag:
        sys.stdout.write(toon)
        return
    out_path = write(toon, output)
    click.echo(f"Saved → {out_path}  ({len(toon.encode())} bytes, {toon.count('@')} directives)")


# ---------------------------------------------------------------------------
# CLI group (allows `toon validate <file>` as a subcommand)
# ---------------------------------------------------------------------------

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


class DefaultGroup(click.Group):
    """Group that invokes the 'convert' command when no subcommand is given."""

    def parse_args(self, ctx, args):
        # If the first arg looks like a known subcommand, let Group handle it.
        # Otherwise inject 'convert' so the default command runs.
        if args and args[0] in self.commands:
            return super().parse_args(ctx, args)
        # Inject the default subcommand
        args = ["convert"] + args
        return super().parse_args(ctx, args)

    def invoke(self, ctx):
        return super().invoke(ctx)


@click.group(cls=DefaultGroup, context_settings=CONTEXT_SETTINGS,
             invoke_without_command=False)
def cli():
    """toon — convert any prompt or structured file to compact .toon format.

    \b
    Examples:
      toon spec.json
      toon spec.md --pretty --validate
      toon --text "Build a FastAPI auth service"
      cat spec.yaml | toon --stdin --stdout
      toon validate result.toon
    """


@cli.command(name="convert", short_help="Convert input to .toon (default).")
@click.argument("file", required=False, type=click.Path(path_type=Path))
@click.option("--text", "-t", default=None, help="Inline natural-language prompt.")
@click.option("--stdin", "from_stdin", is_flag=True, help="Read from stdin.")
@click.option("--output", "-o", default=None, type=click.Path(path_type=Path),
              help="Output .toon path (default: <input>.toon or output.toon).")
@click.option("--validate", "-v", "validate_flag", is_flag=True,
              help="Validate output and print report.")
@click.option("--pretty", "-p", is_flag=True, help="Add comments and blank lines.")
@click.option("--compact", "-c", is_flag=True, help="Minimal single-line output.")
@click.option("--stdout", "stdout_flag", is_flag=True,
              help="Print toon to stdout instead of saving.")
def convert_cmd(file, text, from_stdin, output, validate_flag, pretty, compact, stdout_flag):
    """Convert a file, inline text, or stdin to .toon format."""
    if [bool(file), bool(text), from_stdin].count(True) > 1:
        click.echo("Error: Specify only one of: <file>, --text, or --stdin.", err=True)
        sys.exit(1)
    if compact and pretty:
        click.echo("Error: --compact and --pretty are mutually exclusive.", err=True)
        sys.exit(1)
    try:
        if file:
            parsed = parse_file(file)
            if output is None and not stdout_flag:
                output = derive_output_path(file, text_mode=False)
        elif text:
            parsed = parse_text(text)
            if output is None and not stdout_flag:
                output = derive_output_path(None, text_mode=True)
        elif from_stdin:
            parsed = parse_stdin()
            if output is None and not stdout_flag:
                output = derive_output_path(None, text_mode=True)
        else:
            click.echo(click.get_current_context().get_help())
            return
        _run_pipeline(parsed, output, compact, pretty, validate_flag, stdout_flag)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


@cli.command(name="validate")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
def validate_cmd(file: Path):
    """Validate an existing .toon file and report errors."""
    content = file.read_text(encoding="utf-8")
    result = toon_validate(content)
    click.echo(str(result))
    sys.exit(0 if result.valid else 1)


def main():
    cli()


if __name__ == "__main__":
    cli()
