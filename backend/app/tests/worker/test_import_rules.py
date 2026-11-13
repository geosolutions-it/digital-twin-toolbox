import ast
from pathlib import Path

WORKER = Path(__file__).resolve().parents[2] / "worker"


def _module(path):
    return "app." + ".".join(path.relative_to(WORKER.parent).with_suffix("").parts)


def _imports(path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            yield node.module
            yield from (f"{node.module}.{alias.name}" for alias in node.names)


def _under(name, prefix):
    return name == prefix or name.startswith(prefix + ".")


SOURCES = sorted(WORKER.rglob("*.py"))
IMPORTS = [(_module(p), sorted(set(_imports(p)))) for p in SOURCES]


def _violations(rule):
    return [(m, i) for m, names in IMPORTS for i in names if rule(m, i)]


def test_lib_imports_only_lib_and_third_party():
    def rule(module, name):
        return (
            _under(module, "app.worker.lib")
            and _under(name, "app")
            and not _under(name, "app.worker.lib")
        )

    assert _violations(rule) == []


def test_runtime_does_not_import_tasks_or_queues():
    def rule(module, name):
        return _under(module, "app.worker.runtime") and (
            _under(name, "app.worker.tasks") or _under(name, "app.worker.queues")
        )

    assert _violations(rule) == []


def _task_package(name):
    parts = name.split(".")
    return ".".join(parts[:4]) if _under(name, "app.worker.tasks") else None


def test_tasks_do_not_import_other_tasks_queues_or_main():
    def rule(module, name):
        own = _task_package(module)
        if own is None:
            return False
        other = _task_package(name)
        return (
            (other is not None and other != own)
            or _under(name, "app.worker.queues")
            or _under(name, "app.worker.main")
        )

    assert _violations(rule) == []


def test_only_queues_import_task_modules():
    def rule(module, name):
        return (
            _task_package(name) is not None
            and name.split(".")[-1] == "task"
            and _task_package(module) is None
            and not _under(module, "app.worker.queues")
        )

    assert _violations(rule) == []


def test_no_unused_import_suppressions():
    assert [p for p in SOURCES if "noqa: F401" in p.read_text()] == []
