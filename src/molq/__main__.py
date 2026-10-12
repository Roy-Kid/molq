"""Execute the molq binary. This module does not implement serve."""

from __future__ import annotations

import os
import sys

from molq.client.binary import executable
from molq.errors import MolqError


def main() -> None:
    """Replace this process with the serve binary."""
    try:
        binary = executable()
    except MolqError as exc:
        print(
            '{"jsonrpc":"2.0","id":null,"error":{"code":-32000,"message":"'
            + exc.kind
            + '","data":'
            + __import__("json").dumps(exc.to_wire())
            + "}}"
        )
        raise SystemExit(4) from None
    os.execv(binary, [binary, *sys.argv[1:]])


if __name__ == "__main__":
    main()
