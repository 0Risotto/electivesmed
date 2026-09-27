from hospital_outreach.services.ingestion import ingest_cms_csv

CMS_SAMPLE = b'"Facility ID","Facility Name",Address,City/Town,State,"ZIP Code","Hospital Type","Hospital Ownership",\n010001,"SOUTHEAST HEALTH MEDICAL CENTER",1108 ROSS CLARK CIRCLE,DOTHAN,AL,36301,"Acute Care Hospitals","Government - Hospital District or Authority",\n010002,COMMUNITY HOSPITAL,1 MAIN ST,ANYTOWN,CA,90001,"Critical Access Hospitals",Voluntary,\n'


def test_ingest_cms_csv(container):
    added = ingest_cms_csv(container.dao, CMS_SAMPLE, source_url="test://cms", limit=10)
    assert added == 2
    hospitals = container.dao.find_hospitals()
    names = {h.name for h in hospitals}
    assert "Southeast Health Medical Center" in names
    cms = next(h for h in hospitals if h.city == "DOTHAN")
    assert cms.state == "AL"
    assert cms.hospital_type == "Acute Care Hospitals"
    assert cms.ownership.startswith("Government")


def test_ingest_cms_csv_respects_limit(container):
    added = ingest_cms_csv(container.dao, CMS_SAMPLE, source_url="test://cms", limit=1)
    assert added == 1
    assert len(container.dao.find_hospitals()) == 1
