from pathlib import Path

from django.core.management import call_command
from django.test import TransactionTestCase
from . import UBDCBaseTestWorker
from . import get_fixture


class TestGridOps(UBDCBaseTestWorker):
    fixtures = [
        get_fixture("UBDCGrid.json")
    ]
    test_input_aoi = Path(__file__).parent / "testFiles/santorini.geojson"
    test_input_mask = Path(__file__).parent / "testFiles/santorini_mask.shp"

    qkey = '122102100023'

    def setUp(self):
        # call_command('flush', no_input='yes')
        call_command('import_world_mask', only_iso='GRC')
        call_command('add_aoi', create_grid=False, geo_file=self.test_input_aoi.as_posix())

    def test_estimate_listings(self):
        # from app.models import UBDCGrid
        from app.operations import op_estimate_listings_or_divide_at_grid

        # grid = UBDCGrid.objects.get(quadkey='122102100023')
        task = op_estimate_listings_or_divide_at_grid.s(quadkey=self.qkey)
        result = task.apply_async()

        result.get()
        print('hi')
