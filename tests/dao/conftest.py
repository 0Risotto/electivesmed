"""Fixtures for the DAO layer."""

import pytest

from electivesmed.dao import SqliteDao
from electivesmed.models.entities import Contact, Draft, Hospital
from electivesmed.models.values import EmailAddress

from tests import constants as C


@pytest.fixture
def dao(tmp_path):
    instance = SqliteDao(tmp_path / "dao.db")
    instance.init_schema()
    yield instance
    instance.close()


@pytest.fixture
def hospital_id(dao) -> int:
    return dao.upsert_hospital(
        Hospital(name=C.HOSPITAL_NAME, city=C.HOSPITAL_CITY, state=C.HOSPITAL_STATE)
    )


@pytest.fixture
def contact_id(dao, hospital_id) -> int:
    return dao.save_contacts(
        [
            Contact(
                hospital_id=hospital_id,
                name=C.CONTACT_NAME,
                title=C.CONTACT_TITLE,
                email=EmailAddress(value=C.CONTACT_EMAIL),
            )
        ]
    )[0]


@pytest.fixture
def draft_id(dao, contact_id) -> int:
    return dao.save_draft(
        Draft(
            invocation_id=C.INVOCATION_ID,
            contact_id=contact_id,
            subject=C.DRAFT_SUBJECT,
            body_text=C.DRAFT_BODY,
        )
    )
