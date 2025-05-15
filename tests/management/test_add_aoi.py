from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
@pytest.mark.parametrize(
    argnames="bbox,expected_aois",
    argvalues=[
        ["-1.0,-1.0,1.0,1.0", 1],  # valid bbox
        ["0,0,1,1", 1],  # valid bbox
        ["0,0,0,0", 0],  # zero bbox
        ["5.0,6.0,7.0", 0],  # invalid bbox - missing coordinates
        ["0.0,0.0,-1.0,-1.0", 1],  # valid bbox - wrong order
        ["-1.0,-1.0,1.0,1.0,2.0", 0],  # invalid bbox - too many coordinates
    ],
    ids=["correct_bbox", "integer_bbox", "zero_bbox", "three_coordinates", "wrong_order", "too_many_coordinates"],
)
def test_add_aoi_bbox(bbox, expected_aois, aoishape_model, ubdcgrid_model):
    """
    Test the add-aoi command with a bounding box.
    """

    output = StringIO()
    result = call_command("add-aoi", f"--bbox={bbox}", stdout=output)

    assert aoishape_model.objects.count() == expected_aois
    if expected_aois:
        assert ubdcgrid_model.objects.count() > 0
    else:
        assert ubdcgrid_model.objects.count() == 0
