#!/venv/bin/python3
"""Adapt the base image REST bridge to the upgraded unoserver client."""

from __future__ import annotations

import fcntl
import os
import sys
from collections.abc import Iterable


UNOCONVERT = "/venv/bin/unoconvert"
LOCKFILE = "/var/run/unoconvert.lock"


def translate_arguments(arguments: Iterable[str]) -> list[str]:
    """Translate legacy unoconvert interface flags to unoserver 3.x flags."""
    translated: list[str] = []
    arguments_iterator = iter(arguments)

    for argument in arguments_iterator:
        if argument == "--interface":
            translated.extend(("--host", next(arguments_iterator)))
        elif argument.startswith("--interface="):
            translated.append("--host=" + argument.partition("=")[2])
        else:
            translated.append(argument)

    return translated


def main() -> int:
    """Run one serialized upgraded unoconvert invocation."""
    translated_arguments = translate_arguments(sys.argv[1:])

    with open(LOCKFILE, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        os.execv(UNOCONVERT, [UNOCONVERT, *translated_arguments])

    return 0


if __name__ == "__main__":
    sys.exit(main())
