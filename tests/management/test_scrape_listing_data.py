import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from ubdc_airbnb.models import AirBnBListing


@pytest.fixture
def test_listing(listings_model):
    """Fixture to create a test listing."""
    from django.contrib.gis.geos import Point

    p = Point(0.0, 0.0)
    return listings_model.objects.create(
        listing_id=1234,
        geom_3857=p,
    )


def test_scrape_calendar_data(test_listing, mocker, capsys):
    """Test scraping calendar data for a listing."""
    task_update_calendar = mocker.patch("ubdc_airbnb.tasks.task_update_calendar")
    task_get_listing_details = mocker.patch("ubdc_airbnb.tasks.task_get_listing_details")

    call_command(
        "scrape-listing-data",
        "--listing-id",
        test_listing.listing_id,
        "--calendar",
    )
    out, err = capsys.readouterr()
    task_update_calendar.assert_called_once_with(listing_id=test_listing.listing_id)
    assert "Fetched calendar for listing" in out

    call_command(
        "scrape-listing-data",
        "--listing-id",
        test_listing.listing_id,
        "--listing-detail",
    )
    out, err = capsys.readouterr()
    task_get_listing_details.assert_called_once_with(listing_id=test_listing.listing_id)
    assert "Fetched listing-details for listing" in out


def test_missing_operation_flag(test_listing, capsys):
    """Test that command fails when no operation flag is provided."""
    with pytest.raises(CommandError):
        call_command("scrape-listing-data", "--listing-id", test_listing.listing_id)


def test_missing_listing_id(capsys):
    """Test that command fails when no listing ID is provided."""
    with pytest.raises(CommandError):
        call_command("scrape-listing-data", "--calendar")


def test_invalid_listing_id(test_listing, capsys):
    """Test handling of non-existent listing ID."""
    with pytest.raises(CommandError):
        call_command("scrape-listing-data", "--listing-id", 999999, "--calendar")


def test_mutually_exclusive_flags(test_listing, capsys):
    """Test that calendar and listing-detail flags are mutually exclusive."""
    with pytest.raises(CommandError):
        call_command("scrape-listing-data", "--listing-id", test_listing.listing_id, "--calendar", "--listing-detail")
