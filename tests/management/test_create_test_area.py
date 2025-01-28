from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_create_test_area():
    from ubdc_airbnb.models import AOIShape, UBDCGrid

    out = StringIO()
    call_command("create-test-area", "031133223313221", stdout=out)
    assert "Command executed successfully" in out.getvalue()

    assert UBDCGrid.objects.count() == 1
    assert AOIShape.objects.count() == 1

    aoi = AOIShape.objects.first()
    assert aoi
    assert aoi.collect_calendars == True
    assert aoi.collect_listing_details == True
    assert aoi.collect_listing_details == True
    assert aoi.collect_bookings == True
    assert aoi.name.startswith("Test-Area-")
