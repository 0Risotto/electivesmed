from electivesmed.services.ingestion.parsers.common import (
    cell,
    first_value,
    norm_key,
    normalized_row,
)


def test_norm_key():
    assert norm_key("Facility Name") == "facility_name"
    assert norm_key(" City/Town ") == "city_town"
    assert norm_key("") == ""


def test_cell_handles_lists_and_empties():
    assert cell(["first", "second"]) == "first"
    assert cell([]) == ""
    assert cell(None) == ""
    assert cell("  value ") == "value"


def test_normalized_row():
    assert normalized_row({"Facility Name": " Hospital ", None: ["extra"]}) == {
        "facility_name": "Hospital",
        "": "extra",
    }


def test_first_value():
    row = {"name": "", "hospital": "General"}
    assert first_value(row, ("name", "hospital")) == "General"
    assert first_value(row, ("missing",)) == ""
