from unittest.mock import patch
from uuid import uuid4

import pytest


@pytest.mark.django_db
def test_task_register_listings_or_divide_at_qk_process(
    responses_model,
    ubdcgrid_model,
    listings_model,
    mock_airbnb_client,
    mocker,
):
    # call this 3 times to force the 4th mock response next time its called
    from ubdc_airbnb.airbnb_interface.airbnb_api import AirbnbApi

    api = AirbnbApi()
    api.get_homes()
    api.get_homes()
    api.get_homes()

    mock_group = mocker.patch("ubdc_airbnb.tasks.group")
    from ubdc_airbnb.models import UBDCGroupTask

    id_mock = mocker.PropertyMock(return_value=str(uuid4()))
    mock_ubdcgroup = mocker.patch.object(UBDCGroupTask, "objects")
    type(mock_group().apply_async()).id = id_mock
    from ubdc_airbnb.tasks import task_register_listings_or_divide_at_quadkey

    quadkey = "031133233211"
    grid = ubdcgrid_model.model_from_quadkey(quadkey)
    grid.save()

    task_register_listings_or_divide_at_quadkey(quadkey=quadkey)

    assert ubdcgrid_model.objects.all().count() == 1
    assert responses_model.objects.all().count() == 1
    # 30 listings by default; 10 from the mock response
    assert listings_model.objects.all().count() == 30 + 10
    assert id_mock.called == False


@pytest.mark.django_db
def test_task_register_listings_or_divide_at_qk_divide(
    ubdcgrid_model,
    responses_model,
    mocker,
    mock_airbnb_client,
):

    mock_group = mocker.patch("ubdc_airbnb.tasks.group")
    from ubdc_airbnb.models import UBDCGroupTask

    quadkey = "031133233211"

    id_mock = mocker.PropertyMock(return_value=str(uuid4()))
    mock_ubdcgroup = mocker.patch.object(UBDCGroupTask, "objects")
    type(mock_group.apply_async()).id = id_mock
    from ubdc_airbnb.tasks import task_register_listings_or_divide_at_quadkey

    grid = ubdcgrid_model.model_from_quadkey(quadkey)
    grid.save()

    task_register_listings_or_divide_at_quadkey(quadkey=quadkey)

    assert ubdcgrid_model.objects.all().count() == 4
    assert responses_model.objects.all().count() == 1
    # we have
    assert mock_group.call_count == 1
    assert len(list(mock_group.call_args.args[0])) == 4


def test_task_update_calendar_200(responses_model, mock_airbnb_client):
    from ubdc_airbnb.tasks import task_update_calendar

    rv = task_update_calendar(listing_id=1234567)
    assert responses_model.objects.all().count() == 1
    response = responses_model.objects.first()
    assert response.listing_id == 1234567
