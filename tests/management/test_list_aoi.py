import csv
import io
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest
from django.contrib.gis.geos import GEOSGeometry
from django.core.management import call_command
from django.utils import timezone

from ubdc_airbnb.models import AOIShape


@pytest.fixture
def aoi_test_data():
    """Create test AOIs for testing."""
    # Create test polygons
    poly1 = GEOSGeometry("SRID=3857;MULTIPOLYGON (((0 0, 0 1, 1 1, 1 0, 0 0)))")
    poly2 = GEOSGeometry("SRID=3857;MULTIPOLYGON (((0 0, 0 2, 2 2, 2 0, 0 0)))")
    poly3 = GEOSGeometry("SRID=3857;MULTIPOLYGON (((10 10, 10 20, 20 20, 20 10, 10 10)))")

    # Create test AOIs with different attributes and notes
    aoi1 = AOIShape.objects.create(
        geom_3857=poly1,
        name="Test Area 1",
        notes={
            "user": "testuser1",
            "path": "/test/path1",
            "name": "test1.geojson",
            "import_date": datetime.utcnow().isoformat(),
        },
    )

    aoi2 = AOIShape.objects.create(
        geom_3857=poly2,
        name="Test Area 2",
        notes={
            "user": "testuser2",
            "path": "/test/path2",
            "name": "test2.geojson",
            "import_date": datetime.utcnow().isoformat(),
        },
    )

    aoi3 = AOIShape.objects.create(
        geom_3857=poly3,
        name="Different Region",
        notes={
            "user": "testuser3",
            "path": "/test/path3",
            "name": "region.geojson",
            "import_date": datetime.utcnow().isoformat(),
        },
    )

    # Add some timestamps to ensure they're different
    # Update the created_at directly in DB to have deterministic test data
    AOIShape.objects.filter(id=aoi1.pk).update(timestamp=timezone.datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc))

    AOIShape.objects.filter(id=aoi2.pk).update(timestamp=timezone.datetime(2023, 1, 2, 10, 0, tzinfo=timezone.utc))
    AOIShape.objects.filter(id=aoi3.pk).update(timestamp=timezone.datetime(2023, 1, 3, 10, 0, tzinfo=timezone.utc))

    # Refresh from database to get updated timestamps
    aoi1.refresh_from_db()
    aoi2.refresh_from_db()
    aoi3.refresh_from_db()

    # Return the created AOIs in case tests need to reference them directly
    return {"aoi1": aoi1, "aoi2": aoi2, "aoi3": aoi3}


@pytest.mark.django_db
def test_command_no_args(aoi_test_data):
    """Test the command with no arguments shows all AOIs in terminal format."""
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        call_command("list-aoi")
        output = mock_stdout.getvalue()

        # Check that the output contains basic header information
        assert "Found 3 AOI(s):" in output
        assert "ID" in output  # Header should be present
        assert "Name" in output  # Header should be present

        # Check that all AOI names are in the output
        assert "Test Area 1" in output
        assert "Test Area 2" in output
        assert "Different Region" in output

        # Check for usernames in the output
        assert "testuser1" in output
        assert "testuser2" in output
        assert "testuser3" in output


@pytest.mark.django_db
def test_filter_by_name(aoi_test_data):
    """Test filtering AOIs by name."""
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        call_command("list-aoi", filter="Test")
        output = mock_stdout.getvalue()

        # Should find 2 AOIs
        assert "Found 2 AOI(s):" in output
        assert "Test Area 1" in output
        assert "Test Area 2" in output
        assert "Different Region" not in output


@pytest.mark.django_db
def test_limit_results(aoi_test_data):
    """Test limiting the number of results."""
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        call_command("list-aoi", limit=2)
        output = mock_stdout.getvalue()

        # Should show only first 2 AOIs (ordered by name)
        assert "Found 2 AOI(s):" in output

        # Verify only 2 AOIs are displayed by checking
        # the number of occurrences of a pattern present in each row
        assert output.count("Path: /test") == 2


@pytest.mark.django_db
def test_csv_output_to_stdout(aoi_test_data):
    """Test CSV output to stdout."""
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        call_command("list-aoi", csv=True)
        output = mock_stdout.getvalue()

        # CSV should have a header row and three data rows
        csv_reader = csv.reader(io.StringIO(output))
        rows = list(csv_reader)

        # Check header row
        assert rows[0] == ["id", "name", "created_at", "updated_at", "user", "path", "file_name", "import_date"]

        # Check we have the expected number of data rows
        assert len(rows) == 4  # header + 3 data rows

        # Verify all AOI names are in the CSV
        aoi_names = [row[1] for row in rows[1:]]  # Skip header row
        assert "Test Area 1" in aoi_names
        assert "Test Area 2" in aoi_names
        assert "Different Region" in aoi_names


@pytest.mark.django_db
def test_csv_output_to_file(aoi_test_data, tmp_path):
    """Test CSV output to a file."""
    # Create a temporary file path using tmp_path
    output_path = tmp_path / "aois.csv"

    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        call_command("list-aoi", output=str(output_path))
        console_output = mock_stdout.getvalue()

    # Check console output shows export message
    assert f"Exporting AOIs to {output_path}" in console_output
    assert "CSV export complete" in console_output

    # Verify the file was created and has expected content
    assert output_path.exists()

    # Read and verify CSV contents
    rows = list(csv.reader(output_path.open("r")))

    # Check header row
    assert rows[0] == ["id", "name", "created_at", "user", "path", "file_name", "import_date"]

    # Check we have the expected number of data rows
    assert len(rows) == 4  # header + 3 data rows

    # Verify all AOI names are in the CSV
    aoi_names = [row[1] for row in rows[1:]]  # Skip header row
    assert "Test Area 1" in aoi_names
    assert "Test Area 2" in aoi_names
    assert "Different Region" in aoi_names


@pytest.mark.django_db
def test_no_aois_found(aoi_test_data):
    """Test output when no AOIs match the filter."""
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        call_command("list-aoi", filter="NonExistentName")
        output = mock_stdout.getvalue()

        # Should show warning about no AOIs found
        assert "No AOIs found" in output


@pytest.fixture
def additional_aoi_test_data(aoi_test_data):
    """Add extra test data for combined filtering and limiting test."""
    # Create additional test data to ensure we have enough to filter and limit
    poly4 = GEOSGeometry("SRID=3857;MULTIPOLYGON(((5 5, 5 6, 6 6, 6 5, 5 5)))")
    poly5 = GEOSGeometry("SRID=3857;MULTIPOLYGON(((7 7, 7 8, 8 8, 8 7, 7 7)))")

    aoi4 = AOIShape.objects.create(geom_3857=poly4, name="Test Extra 1", notes={"user": "testuser4"})

    aoi5 = AOIShape.objects.create(geom_3857=poly5, name="Test Extra 2", notes={"user": "testuser5"})

    # Return combined dict of all test AOIs
    return {**aoi_test_data, "aoi4": aoi4, "aoi5": aoi5}


@pytest.mark.django_db
def test_combined_filter_and_limit(additional_aoi_test_data):
    """Test combining filter and limit options."""
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        call_command("list-aoi", filter="Test", limit=3)
        output = mock_stdout.getvalue()

        # Should find only 3 out of 4 AOIs with "Test" in the name
        assert "Found 3 AOI(s):" in output

        # Count occurrences to verify limit is working
        assert output.count("testuser") == 3
