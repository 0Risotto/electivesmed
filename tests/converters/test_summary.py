from electivesmed.converters.summary import summary_to_view


def test_summary_to_view_computes_remaining():
    view = summary_to_view(
        {
            "hospitals": 2,
            "contacts": 5,
            "contacts_with_email": 4,
            "contacts_scored": 3,
            "drafts_pending": 1,
            "drafts_approved": 1,
            "sent_today": 10,
            "sent_total": 20,
            "suppressed": 2,
        },
        daily_cap=50,
    )

    assert view.hospitals == 2
    assert view.sent_today == 10
    assert view.remaining_today == 40


def test_summary_to_view_handles_empty_summary():
    view = summary_to_view({}, daily_cap=50)

    assert view.hospitals == 0
    assert view.remaining_today == 50


def test_summary_to_view_never_negative_remaining():
    view = summary_to_view({"sent_today": 75}, daily_cap=50)

    assert view.remaining_today == 0
