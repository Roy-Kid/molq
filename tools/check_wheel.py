"""Exercise the installed artifact; run outside the repository checkout."""

import importlib
import importlib.resources
import os
import pkgutil
import tempfile
from pathlib import Path

import molq
from molq import Molq

source = Path(__file__).resolve().parents[1] / "src"
assert not Path(molq.__file__).resolve().is_relative_to(source)
assert molq.__version__ == "0.9.0"
for item in pkgutil.walk_packages(molq.__path__, prefix="molq."):
    importlib.import_module(item.name)
for name in molq.__all__:
    getattr(molq, name)
for obsolete in ("submitor", "store", "retry", "plugins", "dashboard"):
    assert importlib.util.find_spec("molq." + obsolete) is None, obsolete
assert importlib.resources.files("molq.protocol").joinpath("v1.json").is_file()
for name in ("index.html", "app.js", "style.css", "wire.js"):
    assert importlib.resources.files("molq.web").joinpath(name).is_file()


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    with Molq(registry=root / "registry.db") as mq:
        if os.name != "nt":
            mq.clusters.register(
                name="local", scheduler="shell", target_root=str(root / "target")
            )
            job = mq.cluster("local").submit(argv=["echo", "installed-wheel"])
            assert job.wait(timeout=10, interval=0.05)["completion"]["successful"]
            assert "installed-wheel" in job.logs()["text"]
        else:
            mq.clusters.register(
                name="hpc",
                scheduler="slurm",
                target_root="/scratch",
                transport={"kind": "ssh", "alias": "hpc"},
            )
        assert len(mq.clusters.list()) == 1
print("Installed wheel modules, public exports, assets and no-service RPC pass.")
