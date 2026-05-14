from __future__ import annotations

import sys

from cli_rich.cli import main


def run() -> None:
    if len(sys.argv) == 1:
        sys.argv.append("chat")
    main(prog_name="awiseoctopus")


if __name__ == "__main__":
    run()
