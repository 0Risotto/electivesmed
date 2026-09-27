def test_sources_page_lists_entries(client):
    response = client.get("/sources")

    assert response.status_code == 200
    assert "cms" in response.text
    assert "osm" in response.text
    assert "wikidata" in response.text


def test_ingest_success(client, container, fake_fetch):
    response = client.post(
        "/sources/ingest",
        data={"name": "cms", "limit": "5"},
        follow_redirects=True,
    )

    assert "ingested 2 hospitals" in response.text
    assert container.dao.summary()["hospitals"] == 2


def test_ingest_unknown_source(client, fake_fetch):
    response = client.post(
        "/sources/ingest",
        data={"name": "nope", "limit": "5"},
        follow_redirects=True,
    )

    assert "ingest failed" in response.text
