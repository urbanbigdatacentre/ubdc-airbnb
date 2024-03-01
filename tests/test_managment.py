# from io import StringIO
# from pathlib import Path
# from unittest import skipIf

# from django.core.management import call_command
# # from django.test import TestCase
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
