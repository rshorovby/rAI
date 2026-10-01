"""Схема structured output: реестр тегов, каталог упражнений, проверка ответа."""

import copy
import json
from pathlib import Path
from typing import Optional

from issue_tags import issue_tag_slugs

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "response-schema.json"
MAX_DRILL_IDS = 40

_SDK_KEYS = {
    "propertyOrdering": "property_ordering",
    "minItems": "min_items",
    "maxItems": "max_items",
    "maxLength": "max_length",
    "minLength": "min_length",
}

_TAG_ENUM_PATHS = (
    ("properties", "issue_tags", "items"),
    ("properties", "findings", "items", "properties", "issue_tags", "items"),
)
_DRILL_ENUM_PATHS = (
    ("properties", "drills", "items"),
    ("properties", "findings", "items", "properties", "drill_ids", "items"),
)


def load_response_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def drill_ids_from_catalog(catalog: Optional[str], limit: int = MAX_DRILL_IDS) -> list:
    ids = []
    for line in (catalog or "").splitlines():
        marker = "id="
        if marker not in line:
            continue
        token = line.split(marker, 1)[1].split(":", 1)[0].strip()
        if token and token not in ids:
            ids.append(token)
        if len(ids) >= limit:
            break
    return ids


def build_response_schema(drill_ids: Optional[list] = None) -> dict:
    """Enum тегов один и тот же в findings и на верхнем уровне. Пустой каталог без enum."""
    schema = copy.deepcopy(load_response_schema())
    tags = issue_tag_slugs()
    for path in _TAG_ENUM_PATHS:
        _node(schema, path)["enum"] = list(tags)
    ids = list(drill_ids or [])[:MAX_DRILL_IDS]
    for path in _DRILL_ENUM_PATHS:
        node = _node(schema, path)
        if ids:
            node["enum"] = ids
        else:
            node.pop("enum", None)
    return schema


# Gemini отвечает 400, если в response schema больше ~100 значений enum.
# Справочник тегов (46) и длинный каталог упражнений в запрос не кладём:
# их проверяет apply_checks. Короткие enum сегментов и осей остаются.
_API_ENUM_LIMIT = 12


def to_sdk_schema(schema: dict):
    """Словарь в форму google-genai Schema: nullable остаётся, ключи в snake_case."""
    from google.genai import types

    payload = copy.deepcopy(schema)
    _strip_long_enums(payload)
    return types.Schema.model_validate(_rename(payload))


def _strip_long_enums(node) -> None:
    if isinstance(node, dict):
        enum = node.get("enum")
        if isinstance(enum, list) and len(enum) > _API_ENUM_LIMIT:
            node.pop("enum")
        for value in node.values():
            _strip_long_enums(value)
    elif isinstance(node, list):
        for value in node:
            _strip_long_enums(value)


def schema_errors(data, schema: Optional[dict] = None) -> list:
    """Ошибки JSON Schema. Пустой findings при тенисе сюда не входит: это бизнес-проверка."""
    return _check(data, schema if schema is not None else load_response_schema(), "$")


def _node(schema: dict, path: tuple) -> dict:
    node = schema
    for key in path:
        node = node[key]
    return node


def _rename(node):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            name = _SDK_KEYS.get(key, key)
            if name == "type" and isinstance(value, str):
                out[name] = value.upper()
            else:
                out[name] = _rename(value)
        return out
    if isinstance(node, list):
        return [_rename(item) for item in node]
    return node


def _check(data, schema: dict, path: str) -> list:
    errors = []
    if not isinstance(schema, dict):
        return errors
    if data is None and schema.get("nullable"):
        return errors
    expected = schema.get("type")
    if expected and not _type_ok(data, expected):
        errors.append(f"{path}: ожидался {expected}")
        return errors
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: значение вне enum")
    if expected == "object" and isinstance(data, dict):
        for key in schema.get("required") or []:
            if key not in data:
                errors.append(f"{path}.{key}: нет поля")
        props = schema.get("properties") or {}
        for key, value in data.items():
            if key in props:
                errors.extend(_check(value, props[key], f"{path}.{key}"))
    if expected == "array" and isinstance(data, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if minimum is not None and len(data) < minimum:
            errors.append(f"{path}: короче minItems")
        if maximum is not None and len(data) > maximum:
            errors.append(f"{path}: длиннее maxItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(data):
                errors.extend(_check(item, item_schema, f"{path}[{index}]"))
    if expected in ("integer", "number") and isinstance(data, (int, float)):
        if isinstance(data, bool):
            return errors
        if schema.get("minimum") is not None and data < schema["minimum"]:
            errors.append(f"{path}: меньше minimum")
        if schema.get("maximum") is not None and data > schema["maximum"]:
            errors.append(f"{path}: больше maximum")
    return errors


def _type_ok(data, expected: str) -> bool:
    if expected == "object":
        return isinstance(data, dict)
    if expected == "array":
        return isinstance(data, list)
    if expected == "string":
        return isinstance(data, str)
    if expected == "boolean":
        return isinstance(data, bool)
    if expected == "integer":
        return isinstance(data, int) and not isinstance(data, bool)
    if expected == "number":
        return isinstance(data, (int, float)) and not isinstance(data, bool)
    return True
