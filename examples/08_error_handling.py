"""Inspect typed errors; uncertain mutations are never automatically resent."""

from molq import Molq, MolqError

try:
    with Molq() as mq:
        mq.cluster("not-registered").submit(argv=["echo", "hello"])
except MolqError as error:
    print(error.to_wire())
