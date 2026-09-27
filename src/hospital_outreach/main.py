"""Main entry point: python -m hospital_outreach or the `ho` console script."""

from .clients.cli.app import app


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
