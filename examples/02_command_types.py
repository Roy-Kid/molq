"""Canonical argv, explicit shell and inline script constructors."""

from molq import ExecutionUnit

argv = ExecutionUnit.argv("argv", ["echo", "literal $HOME"])
shell = ExecutionUnit.shell("shell", 'printf "%s\\n" "$HOME"')
script = ExecutionUnit.script("script", "printf 'first\\n'\ntrue\n")
for unit in (argv, shell, script):
    print(unit.to_wire())
