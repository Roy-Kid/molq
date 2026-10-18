"""Inspect typed errors; uncertain mutations are never automatically resent."""

import json

from molq import JobSpec, MolqError, submit

destination = submit("not-registered")


@destination
def hello():
    job = yield JobSpec.argv(["echo", "hello"])
    return job


try:
    hello()
except MolqError as error:
    print(json.dumps(error.to_wire(), ensure_ascii=False))
finally:
    destination.close()
