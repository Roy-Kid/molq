"""Observe collections in one RPC scope instead of one worker per Job."""

import json
import sys

from molq import Molq

# Pass a JSON file containing an array of saved JobRefs.
if __name__ == "__main__":
    with open(sys.argv[1]) as file:
        refs = json.load(file)
    with Molq() as mq:
        print(mq.jobs(refs).status())
