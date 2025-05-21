import csv
from unittest.mock import patch

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestListAOICommand:
    """Test suite for the list-aoi management command."""

    def test_basic_list(self, test_aois, capsys):
        """Test basic listing of AOIs without any options."""
        call_command(
            "list-aoi",
        )
        out, err = capsys.readouterr()

        # Basic assertions
        assert "Found 3 AOI(s):" in out
        for i in range(1, 3):
            assert f"Test Area {i+1}" in out
            assert f"testuser{i+1}" in out
            assert f"/test/path{i+1}" in out

    def test_filter_by_name(self, test_aois, capsys):
        """Test filtering AOIs by name."""
        call_command("list-aoi", filter="Area 1")
        out, err = capsys.readouterr()

        assert "Found 1 AOI(s):" in out
        assert "Test Area 1" in out
        assert "Test Area 2" not in out
        assert "Test Area 3" not in out

    def test_limit_results(self, test_aois, capsys):
        """Test limiting the number of results."""
        call_command("list-aoi", limit=2)
        out, err = capsys.readouterr()

        assert "Found 2 AOI(s):" in out
        assert out.count("testuser") == 2

    def test_csv_output(self, test_aois, capsys):
        """Test CSV output format."""
        call_command("list-aoi", csv=True)
        out, err = capsys.readouterr()

        # Parse CSV output
        reader = csv.reader(out.splitlines())
        rows = list(reader)

        # Check header
        expected_headers = ["id", "name", "created_at", "user", "path", "file_name", "import_date"]
        assert rows[0] == expected_headers

        # Check data rows
        assert len(rows) == 4  # Header + 3 data rows
        for i, row in enumerate(rows[1:], 1):
            assert f"Test Area {i}" in row
            assert f"testuser{i}" in row
            assert f"/test/path{i}" in row

    def test_csv_file_output(self, test_aois, tmp_path, capsys):
        """Test CSV output to a file."""
        output_file = tmp_path / "aois.csv"

        call_command("list-aoi", output=str(output_file))
        out, err = capsys.readouterr()

        # Check console output
        assert f"Exporting AOIs to {output_file}" in out
        assert "CSV export complete" in out

        # Verify file contents
        assert output_file.exists()
        rows = list(csv.reader(output_file.open()))
        assert len(rows) == 4  # Header + 3 data rows

    def test_no_results(self, test_aois, capsys):
        """Test output when no AOIs match the filter."""
        call_command("list-aoi", filter="NonExistent")
        out, err = capsys.readouterr()

        assert "No AOIs found" in out

    def test_combined_filter_and_limit(self, test_aois, capsys):
        """Test combining filter and limit options."""
        call_command("list-aoi", filter="Area", limit=2)
        out, err = capsys.readouterr()

        assert "Found 2 AOI(s):" in out
        assert out.count("Test Area") == 2
