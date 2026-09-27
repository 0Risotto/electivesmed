from tests import constants as C


def test_compliance_page(client):
    response = client.get("/compliance")

    assert response.status_code == 200
    assert "Compliance" in response.text
    assert "No suppressions" in response.text


def test_suppress_valid_email(client, container):
    response = client.post(
        "/compliance/suppress",
        data={"email": C.CONTACT_EMAIL, "reason": "unsubscribe"},
        follow_redirects=True,
    )

    assert "suppressed jane.doe@testhospital.org" in response.text
    assert container.dao.is_suppressed(C.CONTACT_EMAIL)


def test_suppress_invalid_email(client):
    response = client.post(
        "/compliance/suppress",
        data={"email": "not-an-email", "reason": "x"},
        follow_redirects=True,
    )

    assert "invalid email" in response.text


def test_purge(client, container, seeded):
    response = client.post("/compliance/purge", data={"days": "0"}, follow_redirects=True)

    assert "purged 1 contacts, 1 drafts, 0 sends" in response.text
    assert container.dao.summary()["contacts"] == 0
