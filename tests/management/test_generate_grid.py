from io import StringIO

import pytest
from django.core.management import call_command

# Test the creation of a grid from an AOI  (--input-type aoi option)


@pytest.mark.skip(reason="generate_grid command needs to be rewritten")
@pytest.mark.django_db
def test_create_grid_qk():
    out = StringIO()
    from ubdc_airbnb.models import UBDCGrid

    qk = "0311332233311"
    call_command("generate_grid", qk, "--input-type", "quadkey", stdout=out)
    assert UBDCGrid.objects.count() == 1
    grid: UBDCGrid = UBDCGrid.objects.get(quadkey=qk)
    assert grid.tile_z == len(qk)
    assert grid.quadkey == qk


# Test the creation of a grid from an AOI  (--input-type aoi option)
@pytest.mark.skip(reason="generate_grid command needs to be rewritten")
@pytest.mark.django_db
def test_create_grid_aoi(geojson_gen, aoishape_model, tmp_path):
    out = StringIO()
    from ubdc_airbnb.models import UBDCGrid

    p = tmp_path / "test-file.json"
    p.write_text(geojson_gen[0])
    aoi = aoishape_model.create_from_geojson(p)
    aoi_id = aoi.id
    call_command("generate_grid", aoi_id, "--input-type", "aoi", stdout=out)
    assert UBDCGrid.objects.count() == 1
