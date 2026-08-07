"""`import molq` must stay cheap.

molq is a library and a CLI: every `molq status` pays the import before doing
any work. The heavy dependencies (mollog -> logfire, rich, termios) are all
reachable but none of them should load until something actually needs them.
"""

from __future__ import annotations

import subprocess
import sys


def _imported_modules(statement: str) -> set[str]:
    """Module names loaded by *statement* in a fresh interpreter."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"{statement}\nimport sys; print('\\n'.join(sys.modules))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.split())


class TestImportCost:
    def test_logfire_is_not_imported(self):
        # mollog pulls in logfire, ~200ms — most of what `import molq` used
        # to cost. Loggers resolve on first log call instead.
        assert "logfire" not in _imported_modules("import molq")

    def test_rich_is_not_imported(self):
        # rich arrives via molq.dashboard, which is lazily exported.
        assert "rich" not in _imported_modules("import molq")

    def test_termios_is_not_imported(self):
        # termios/tty are Unix-only; importing molq must not require them.
        assert "termios" not in _imported_modules("import molq")

    def test_dashboard_module_is_not_eagerly_loaded(self):
        assert "molq.dashboard" not in _imported_modules("import molq")

    def test_dashboard_exports_still_resolve(self):
        from molq import DashboardState, JobRow, MolqMonitor, RunDashboard

        assert MolqMonitor.__name__ == "MolqMonitor"
        assert RunDashboard.__name__ == "RunDashboard"
        assert DashboardState.__name__ == "DashboardState"
        assert JobRow.__name__ == "JobRow"

    def test_lazy_names_appear_in_dir(self):
        import molq

        assert "MolqMonitor" in dir(molq)

    def test_unknown_attribute_still_raises(self):
        import molq

        try:
            molq.no_such_name
        except AttributeError as exc:
            assert "no_such_name" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected AttributeError")

    def test_logger_resolves_on_use(self):
        from molq._log import get_logger

        logger = get_logger("molq.test")
        assert "deferred" in repr(logger)
        logger.info("resolving now")
        assert "resolved" in repr(logger)
