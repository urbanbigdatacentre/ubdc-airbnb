from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

# from pathlib import Path
# from unittest import skipIf


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


# from django.test import TransactionTestCase

# from ubdc_airbnb.models import AOIShape, WorldShape


# class ManagmentCmdsTest(TransactionTestCase):
#     test_input_aoi = Path(__file__).parent / "testFiles/santorini.geojson"
#     test_input_mask = Path(__file__).parent / "testFiles/santorini_mask.shp"

#     @skipIf(True, "takes too long")
#     def test_import_world_mask(self):
#         out = StringIO()
#         call_command("import_world_mask", stdout=out)

#         self.assertGreaterEqual(WorldShape.objects.all().count(), 116311)

#     def test_import_world_mask_only(self):
#         out = StringIO()
#         call_command("import_world_mask", only_iso="NPL", stdout=out)

#         self.assertGreaterEqual(WorldShape.objects.all().count(), 1)

#     def test_add_aoi(self):
#         out = StringIO()
#         call_command(
#             "add_aoi",
#             create_grid=False,
#             geo_file=self.test_input_aoi.as_posix(),
#             stdout=out,
#         )
#         assert AOIShape.objects.all().count() >= 1

#     def test_add_mask_aoi_grids(self):
#         from ubdc_airbnb.models import AOIShape, UBDCGrid

#         out = StringIO()
#         call_command("import_world_mask", only_iso="GRC", stdout=out)
#         call_command(
#             "add_aoi",
#             create_grid=True,
#             geo_file=self.test_input_aoi.as_posix(),
#             stdout=out,
#         )
#         assert AOIShape.objects.all().count() >= 1
#         assert UBDCGrid.objects.all().count() == 7
