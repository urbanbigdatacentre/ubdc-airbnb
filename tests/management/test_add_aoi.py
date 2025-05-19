import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from ubdc_airbnb.models import AOIShape


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bbox,expected_success",
    [
        ("-1.0,-1.0,1.0,1.0", True),  # Valid bbox
        ("0,0,1,1", True),  # Valid integer bbox
        ("0,0,0,0", False),  # A degenerate polygon (zero area)
        ("5.0,6.0,7.0", False),  # Missing coordinate
        ("0.0,0.0,-1.0,-1.0", True),  # Valid but reversed coordinates
        ("-1.0,-1.0,1.0,1.0,2.0", False),  # Too many coordinates
    ],
)
def test_add_aoi_with_bbox(bbox, expected_success, capsys):
    """Test adding AOI using bounding box coordinates."""
    if expected_success:
        call_command("add-aoi", f"--bbox={bbox}")
        out, err = capsys.readouterr()
        assert err == ""
        assert "Successfully added" in out
        assert AOIShape.objects.count() == 1
    else:
        with pytest.raises(CommandError):
            call_command("add-aoi", f"--bbox={bbox}")
        assert AOIShape.objects.count() == 0


@pytest.mark.django_db
def test_add_aoi_with_name(capsys):
    """Test adding AOI with a custom name."""
    bbox = "0,0,1,1"
    name = "Test Area"

    call_command("add-aoi", f"--bbox={bbox}", f"--name={name}")
    out, err = capsys.readouterr()

    assert "Successfully added" in out
    aoi = AOIShape.objects.first()
    assert aoi is not None
    assert aoi.name == name


@pytest.mark.django_db
def test_add_aoi_with_description(capsys):
    """Test adding AOI with a description."""
    bbox = "0,0,1,1"
    description = "Test Description"

    call_command(
        "add-aoi",
        f"--bbox={bbox}",
        f"--description={description}",
    )
    out, err = capsys.readouterr()

    assert "Successfully added" in out
    aoi = AOIShape.objects.first()
    assert aoi is not None
    assert aoi.notes.get("description") == description


@pytest.mark.django_db
def test_add_aoi_without_required_args(capsys):
    """Test that command fails when no required arguments are provided."""
    with pytest.raises(CommandError):
        call_command("add-aoi")


@pytest.mark.django_db
def test_add_aoi_creates_grids(capsys):
    """Test that adding an AOI creates associated grids."""
    bbox = "0,0,1,1"

    call_command("add-aoi", f"--bbox={bbox}")
    out, err = capsys.readouterr()

    assert "Successfully added" in out
    assert "Created" in out
    call_command("add-aoi", f"--bbox={bbox}")
    out, err = capsys.readouterr()

    assert "Successfully added" in out
    assert "Created" in out
    assert "grids for AOI" in out
