from electivesmed.services.importing import import_contacts_csv

from tests import constants as C


def _write(tmp_path, text: str) -> str:
    path = tmp_path / "contacts.csv"
    path.write_text(text, encoding="utf-8")
    return path.read_text(encoding="utf-8-sig")


def test_import_contacts_creates_hospitals_and_contacts(container, tmp_path):
    text = _write(
        tmp_path,
        "name,title,email,hospital_name,city,state,country,lawful_basis\n"
        "Jane Doe,CMO,jane@example.org,Test Hospital,Fresno,CA,US,consent\n"
        ",,,No Person Hospital,,,,\n",
    )

    result = import_contacts_csv(container, text, source_url="test.csv")

    assert result == {"rows_seen": 1, "saved": 1}
    contact = container.dao.find_contacts(with_email_only=True)[0]
    assert contact.country == "US"
    assert contact.lawful_basis == "consent"
    assert container.dao.summary()["hospitals"] == 1


def test_import_contacts_defaults_from_options(container, tmp_path):
    text = _write(tmp_path, "name,email\nHans,hans@klinik.de\n")

    import_contacts_csv(
        container, text, hospital_name="Default Hospital", country="DE"
    )

    contact = container.dao.find_contacts(with_email_only=True)[0]
    assert contact.country == "DE"
    assert contact.hospital_name == "Default Hospital"


def test_import_contacts_tolerates_ragged_rows(container, tmp_path):
    text = "name,email\n,,\nJane,jane@example.org,extra\n"

    result = import_contacts_csv(container, text)

    assert result["saved"] == 1
