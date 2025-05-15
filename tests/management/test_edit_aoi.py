from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from ubdc_airbnb.models import AOIShape


@pytest.fixture
def test_aoi(db):
    """Fixture to create a test AOI."""
    geom = "SRID=4326;MULTIPOLYGON(((30 20, 45 40, 10 40, 30 20)))"  # Example geometry
    aoi = AOIShape.objects.create(
        name="Test AOI", collect_calendars=False, collect_listing_details=False, geom_3857=geom
    )
    return aoi


@pytest.fixture
def run_command():
    """Fixture to run the edit_aoi command with various options."""

    def _run_command(pk, output_buffer, **kwargs):
        call_command("edit_aoi", pk, stdout=output_buffer, **kwargs)
        return output_buffer.getvalue()

    return _run_command


@pytest.mark.django_db
def test_command_updates_aoi_collect_calendars(test_aoi, run_command):
    """Test that the command correctly updates AOI collect_calendars flag."""
    output_buffer = StringIO()
    # Test setting to True
    output = run_command(test_aoi.pk, calendars=True, output_buffer=output_buffer)

    # Refresh from db and check the flag was updated
    test_aoi.refresh_from_db()
    assert test_aoi.collect_calendars is True
    assert "Setting collect to True" in output

    # Reset output buffer
    output_buffer.truncate(0)
    output_buffer.seek(0)

    # Test setting to False
    output = run_command(test_aoi.pk, output_buffer, **{"no_calendars": True})

    test_aoi.refresh_from_db()
    assert test_aoi.collect_calendars is False
    assert "Setting collect to False" in output


@pytest.mark.django_db
def test_command_updates_aoi_collect_listing_details(test_aoi, run_command):
    """Test that the command correctly updates AOI collect_listing_details flag."""
    output_buffer = StringIO()
    # Test setting to True
    output = run_command(test_aoi.pk, output_buffer, **{"listing_details": True})

    # Refresh from db and check the flag was updated
    test_aoi.refresh_from_db()
    assert test_aoi.collect_listing_details is True
    assert "Setting collect_listing_details to True" in output

    # Reset output buffer
    output_buffer.truncate(0)
    output_buffer.seek(0)

    # Test setting to False
    output = run_command(test_aoi.pk, output_buffer, **{"no_listing_details": True})

    test_aoi.refresh_from_db()
    assert test_aoi.collect_listing_details is False
    assert "Setting collect_listing_details to False" in output


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

    assert f"AOI with primary key {non_existent_pk} does not exist" in str(excinfo.value)


@pytest.mark.django_db
def test_command_handles_multiple_flags(test_aoi, run_command):
    """Test that the command handles multiple flags correctly."""
    # Call command with both flags set to True
    output_buffer = StringIO()
    output = run_command(test_aoi.pk, output_buffer=output_buffer, calendars=True, **{"listing_details": True})

    # Refresh from db and check both flags were updated
    test_aoi.refresh_from_db()
    assert test_aoi.collect_calendars is True
    assert test_aoi.collect_listing_details is True

    # Check output contains both messages
    assert "Setting collect to True" in output
    assert "Setting collect_listing_details to True" in output
    assert "Successfully updated AOI" in output
