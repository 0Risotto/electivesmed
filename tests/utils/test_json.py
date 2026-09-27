import pytest

from electivesmed.errors import LlmError
from electivesmed.utils.json import extract_json


def test_extract_json_plain_object():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    assert extract_json('```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}


def test_extract_json_wraps_top_level_array():
    assert extract_json('[{"id": 1}]') == {"items": [{"id": 1}]}


def test_extract_json_finds_embedded_object():
    assert extract_json('noise before {"a": 1} noise after') == {"a": 1}


def test_extract_json_finds_embedded_array():
    assert extract_json("noise [1, 2] noise") == {"items": [1, 2]}


def test_extract_json_garbage_raises():
    with pytest.raises(LlmError, match="valid JSON"):
        extract_json("this is not json at all")


def test_extract_json_unparsable_braces_raise():
    with pytest.raises(LlmError):
        extract_json("{this is not valid}")
