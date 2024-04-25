import datetime
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

utc = ZoneInfo("UTC")


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
    assert listings_model.objects.all().count() == 10
    assert id_mock.called == False


@pytest.mark.django_db
def test_task_register_listings_or_divide_at_qk_divide(
    ubdcgrid_model,
    responses_model,
    mocker,
    mock_airbnb_client,
):
    from ubdc_airbnb.models import UBDCGroupTask

    epsilon = datetime.timedelta(seconds=2)
    mock_group = mocker.patch("ubdc_airbnb.tasks.group")
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

    for grid in ubdcgrid_model.objects.all():
        timestamp = grid.timestamp
        assert timestamp is not None
        assert timestamp.tzinfo is not None
        assert abs(datetime.datetime.now(tz=utc) - timestamp) < epsilon
    assert mock_group.call_count == 1
    assert len(list(mock_group.call_args.args[0])) == 4


def test_task_update_calendar(responses_model, mock_airbnb_client):
    from ubdc_airbnb.tasks import task_update_calendar

    # status 200
    task_update_calendar(listing_id=1234567)
    assert responses_model.objects.all().count() == 1
    response = responses_model.objects.first()
    assert response.listing_id == 1234567
    assert response.status_code == 200

    # status 403 but is handled
    task_update_calendar(listing_id=1234567)
    assert responses_model.objects.all().count() == 2
    response = responses_model.objects.last()
    assert response.listing_id == 1234567
    assert response.status_code == 403

    # status 503, should raise an exception
    from ubdc_airbnb.errors import UBDCRetriableError

    with pytest.raises(UBDCRetriableError):
        task_update_calendar(listing_id=1234567)
        assert responses_model.objects.all().count() == 2


def test_task_get_listing_details(
    responses_model,
    mock_airbnb_client,
    mocker,
    listings_model,
):
    m = mocker.patch.object(listings_model, "objects")
    from ubdc_airbnb.tasks import task_get_listing_details

    task_get_listing_details(listing_id=1234567)
    assert responses_model.objects.all().count() == 1
    response = responses_model.objects.first()
    assert response.listing_id == 1234567
    assert m.get.called == True
    assert m.get().save.called == True
    assert m.get().responses.add.called == True


@pytest.mark.django_db
def test_task_add_reviews_of_listing(
    responses_model,
    mock_airbnb_client,
    mocker,
    listings_model,
):
    listing_id = 1234567
    listings_model.objects.create(listing_id=listing_id)
    from ubdc_airbnb.tasks import task_add_reviews_of_listing

    mock_signature = mocker.MagicMock(spec=task_add_reviews_of_listing)
    group_mock = mocker.patch("ubdc_airbnb.tasks.group")
    task_add_reviews_of_listing.s = mock_signature

    task_add_reviews_of_listing(listing_id=1234567)
    assert responses_model.objects.all().count() == 1
    response = responses_model.objects.first()
    assert response.listing_id == 1234567
    assert mock_signature().apply_async.call_count == 3

    task_add_reviews_of_listing(listing_id=1234567, offset=300)
    assert mock_signature().apply_async.call_count == 3


def test_task_task_update_user_details(mock_airbnb_client, user_model, responses_model):
    from requests.exceptions import HTTPError

    from ubdc_airbnb.errors import UBDCRetriableError
    from ubdc_airbnb.tasks import task_update_user_details

    task_update_user_details(user_id=12345)

    assert user_model.objects.count() == 1
    assert responses_model.objects.count() == 1

    # 2nd call return 404 but it's handled
    task_update_user_details(user_id=12345)
    assert user_model.objects.count() == 1
    assert responses_model.objects.count() == 2

    # 3rd call return 503, throughs an exception that will be re-tried
    with pytest.raises(UBDCRetriableError):
        task_update_user_details(user_id=12345)
        assert user_model.objects.count() == 1
        assert responses_model.objects.count() == 2
