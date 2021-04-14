import time

from celery.result import AsyncResult
from django.utils import timezone
from requests import HTTPError

from . import UBDCBaseTestWorker
from . import get_fixture
from ..errors import UBDCError, UBDCRetriableError
from ..models import AirBnBResponseTypes


class TestGridOps(UBDCBaseTestWorker):
    fixtures = [
        get_fixture("EDIN_AOI_SHAPE.json"),
        get_fixture("EDIN_GRID_LISTINGS.json"),
    ]

    def setUp(self):
        self.listing_404 = 30729869
        self.listing_200 = 40197612
        self.quadkey = "03113323321103333"

        from app.models import UBDCGrid

        g = UBDCGrid.objects.get(quadkey=self.quadkey)
        g.datetime_last_estimated_listings_scan = timezone.now()
        g.save()
        # call_command('flush', no_input='yes')
        # call_command('import_world_mask', only_iso='GRC')
        # call_command('add_aoi', create_grid=False, geo_file=self.test_input_aoi.as_posix())

    def test_warmup(self):
        from app.models import AirBnBListing

        all_listings = AirBnBListing.objects.all()

        self.assertEqual(all_listings.count(), 20)

    def test_op_grab_booking(self):
        from app.operations.bookings import op_get_booking_detail_periodical

        task = op_get_booking_detail_periodical.s()

        job = task.apply_async()
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(1)
        result = job.get()

        print('hi')
