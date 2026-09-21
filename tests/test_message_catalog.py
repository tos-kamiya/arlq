"""The English message text is also the catalog key.

These checks keep src/arlq/locales/ja.json aligned with the strings the
game actually passes to tr().
"""

import ast
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "arlq"
CATALOG = PACKAGE / "locales" / "ja.json"


def _python_files():
    return sorted(PACKAGE.rglob("*.py"))


def _trees():
    for path in _python_files():
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _string_literals():
    found = set()
    for _, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.add(node.value)
    return found


def _module_bindings(tree):
    """Module-level string constants and dicts whose values are all strings."""
    bindings = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            bindings[target.id] = [value.value]
        elif isinstance(value, ast.Dict):
            texts = []
            if all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.values):
                texts = [item.value for item in value.values]
                bindings[target.id] = texts
    return bindings


def _event_messages():
    found = set()
    for path, tree in _trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.keyword) or node.arg != "event_message":
                continue
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                found.add(value.value)
            elif isinstance(value, ast.Constant) and value.value is None:
                continue
            else:
                raise AssertionError(f"{path}: event_message is not a string literal")
    return found


def _tr_message_ids():
    """String IDs that can reach tr(), including indirect ones.

    Tribe event_message fields and module-level constants are included when
    a tr() call reads them. An argument shape this function does not
    understand fails the test, so a new call pattern cannot skip the check.
    """
    ids = set()
    needs_event_messages = False
    for path, tree in _trees():
        bindings = _module_bindings(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "tr" or len(node.args) != 1 or node.keywords:
                if isinstance(node.func, ast.Name) and node.func.id == "tr":
                    raise AssertionError(f"{path}: unsupported tr() call")
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                ids.add(arg.value)
            elif isinstance(arg, ast.Name) and arg.id in bindings:
                ids.update(bindings[arg.id])
            elif (
                isinstance(arg, ast.Subscript)
                and isinstance(arg.value, ast.Name)
                and arg.value.id in bindings
            ):
                ids.update(bindings[arg.value.id])
            elif isinstance(arg, ast.Attribute) and arg.attr == "event_message":
                needs_event_messages = True
            else:
                raise AssertionError(f"{path}: unsupported tr() argument: {ast.dump(arg)}")
    if needs_event_messages:
        ids.update(_event_messages())
    return ids


def _catalog_keys():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert isinstance(catalog, dict)
    return set(catalog)


def test_japanese_catalog_keys_exist_in_source():
    missing = sorted(_catalog_keys() - _string_literals())
    assert missing == []


def test_tr_message_ids_exist_in_japanese_catalog():
    missing = sorted(_tr_message_ids() - _catalog_keys())
    assert missing == []
