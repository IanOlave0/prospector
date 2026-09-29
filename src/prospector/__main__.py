"""Allow running the CLI with ``python -m prospector``."""

from prospector.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
