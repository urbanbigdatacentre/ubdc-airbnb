import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from ubdc_airbnb.models import AOIShape


@pytest.mark.django_db
def test_command_updates_aoi_collect_calendars(test_aoi, capsys):
    """Test that the command correctly updates AOI collect_calendars flag."""
    # Test setting to True
    output = call_command("edit-aoi", test_aoi.pk, calendars=True)

    # Refresh from db and check the flag was updated
    test_aoi.refresh_from_db()
    out, err = capsys.readouterr()
    assert test_aoi.collect_calendars is True
    assert "Setting collect_calendars to True" in out

    # Test setting to False
    call_command("edit-aoi", test_aoi.pk, no_calendars=True)
    test_aoi.refresh_from_db()

    out, err = capsys.readouterr()
    assert test_aoi.collect_calendars is False
    assert "Setting collect_calendars to False" in out


@pytest.mark.django_db
def test_command_updates_aoi_collect_listing_details(test_aoi, capsys):
    """Test that the command correctly updates AOI collect_listing_details flag."""
    # Test setting to True
    call_command("edit-aoi", test_aoi.pk, listing_details=True)
    test_aoi.refresh_from_db()

    out, err = capsys.readouterr()
    assert test_aoi.collect_listing_details is True
    assert "Setting collect_listing_details to True" in out

    # Test setting to False
    call_command("edit-aoi", test_aoi.pk, no_listing_details=True)
    test_aoi.refresh_from_db()

    out, err = capsys.readouterr()
    assert test_aoi.collect_listing_details is False
    assert "Setting collect_listing_details to False" in out


@pytest.mark.django_db
def test_command_raises_error_for_nonexistent_aoi():
    """Test that the command raises an error for a non-existent AOI."""
    # Use a PK that doesn't exist
    non_existent_pk = 9999

    # Ensure the AOI does not exist
    assert not AOIShape.objects.filter(pk=non_existent_pk).exists()

    # Check that CommandError is raised
    with pytest.raises(CommandError) as excinfo:
        call_command("edit_aoi", non_existent_pk)


@pytest.mark.django_db
def test_command_handles_multiple_flags(test_aoi, capsys):
    """Test that the command handles multiple flags correctly."""
    # Call command with both flags set to True
    call_command("edit-aoi", test_aoi.pk, calendars=True, listing_details=True)

    # Refresh from db and check both flags were updated
    test_aoi.refresh_from_db()
    assert test_aoi.collect_calendars is True
    assert test_aoi.collect_listing_details is True

    # Check output contains both messages
    out, err = capsys.readouterr()
    assert "Setting collect_calendars to True" in out
    assert "Setting collect_listing_details to True" in out
    assert "Successfully updated AOI" in out


def test_command_handles_mutually_exclusive_flags(test_aoi):
    """Test that mutually exclusive flags raise an error."""
    with pytest.raises(CommandError):
        call_command(f"edit-aoi", "--calendars", "--no-calendars", test_aoi.pk)

    with pytest.raises(CommandError):
        call_command("edit-aoi", "--listing_details", "--no-listing-details", test_aoi.pk)


def test_command_handles_delete_aoi(test_aoi, capsys, aoishape_model):
    """Test deleting an AOI."""
    call_command("edit-aoi", test_aoi.pk, delete=True)
    out, err = capsys.readouterr()

    assert "Successfully deleted AOI" in out
    assert not aoishape_model.objects.filter(pk=test_aoi.pk).exists()
