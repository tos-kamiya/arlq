"""Check that player-visible translation IDs have Japanese catalog entries."""

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


def _event_message_locals(tree):
    """Names assigned from a tribe's event_message before being passed to tr()."""
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if isinstance(target, ast.Name) and isinstance(value, ast.Attribute) and value.attr == "event_message":
            names.add(target.id)
    return names


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
        elif isinstance(value, (ast.Dict, ast.List, ast.Tuple)):
            if isinstance(value, ast.Dict):
                values = value.values
            else:
                values = value.elts
            texts = []
            if all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in values):
                texts = [item.value for item in values]
                bindings[target.id] = texts
    return bindings


def _iterated_string_locals(tree):
    """String values passed through tr() in loops over string-containing sequences."""

    def string_values(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, (ast.List, ast.Tuple)):
            return set().union(*(string_values(item) for item in node.elts))
        return set()

    sequences = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if isinstance(target, ast.Name) and isinstance(value, (ast.List, ast.Tuple)):
            sequences[target.id] = string_values(value)

    locals_by_name = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        iterable = node.iter
        if (
            isinstance(iterable, ast.Call)
            and isinstance(iterable.func, ast.Name)
            and iterable.func.id == "enumerate"
            and len(iterable.args) == 1
        ):
            iterable = iterable.args[0]
        if not isinstance(iterable, ast.Name) or iterable.id not in sequences:
            continue
        target_names = {
            target.id for target in ast.walk(node.target) if isinstance(target, ast.Name)
        }
        translated_names = {
            call.args[0].id
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "tr"
            and len(call.args) == 1
            and isinstance(call.args[0], ast.Name)
        }
        for name in target_names & translated_names:
            locals_by_name[name] = sequences[iterable.id]
    return locals_by_name


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
            elif isinstance(value, ast.Name) and value.id == "event_message":
                # Forwarded through Tribe/ElfTribe constructors; the literal
                # catalog keys are collected from the tribe declarations.
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

    def collect_conditional_strings(node, path):
        """Collect string IDs from both branches of a conditional expression."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, ast.IfExp):
            return collect_conditional_strings(node.body, path) | collect_conditional_strings(
                node.orelse, path
            )
        raise AssertionError(f"{path}: unsupported conditional tr() argument: {ast.dump(node)}")

    for path, tree in _trees():
        bindings = _module_bindings(tree)
        event_message_locals = _event_message_locals(tree)
        iterated_string_locals = _iterated_string_locals(tree)
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
            elif isinstance(arg, ast.Name) and arg.id in event_message_locals:
                needs_event_messages = True
            elif isinstance(arg, ast.Name) and arg.id in iterated_string_locals:
                ids.update(iterated_string_locals[arg.id])
            elif (
                isinstance(arg, ast.Subscript)
                and isinstance(arg.value, ast.Name)
                and arg.value.id in bindings
            ):
                ids.update(bindings[arg.value.id])
            elif isinstance(arg, ast.Attribute) and arg.attr == "event_message":
                needs_event_messages = True
            elif isinstance(arg, ast.IfExp):
                ids.update(collect_conditional_strings(arg, path))
            else:
                raise AssertionError(f"{path}: unsupported tr() argument: {ast.dump(arg)}")
    if needs_event_messages:
        ids.update(_event_messages())
    return ids


def _catalog_keys():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert isinstance(catalog, dict)
    return set(catalog)


def test_japanese_catalog_contains_string_mappings():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in catalog.items()
    )


def test_tr_message_ids_exist_in_japanese_catalog():
    # Button face labels remain identical in Japanese, and blank labels carry
    # no translatable text.
    untranslated_ids = {"", "A", "B", "X", "Y"}
    missing = sorted(_tr_message_ids() - _catalog_keys() - untranslated_ids)
    assert missing == []
