"""Execute the molq binary. This module does not implement serve."""

from __future__ import annotations

import json
import os
import sys

from molq.client.binary import executable
from molq.errors import MolqError


def main() -> None:
    """Replace this process with the serve binary."""
    try:
        binary = executable()
        os.execv(binary, [binary, *sys.argv[1:]])
    except (MolqError, OSError) as cause:
        exc = (
            cause
            if isinstance(cause, MolqError)
            else MolqError("RUNTIME_UNAVAILABLE", str(cause))
        )
        print(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32000,
                        "message": str(exc),
                        "data": exc.to_wire(),
                    },
                }
            )
        )
        raise SystemExit(4) from None


if __name__ == "__main__":
    main()
