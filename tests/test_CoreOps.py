import time
from datetime import timedelta

from django.utils import timezone

from ubdc_airbnb.operations import (
    op_discover_new_listings_periodical,
    op_estimate_listings_or_divide_periodical,
    op_update_calendar_periodical,
    op_update_listing_details_periodical,
    op_update_reviews_periodical,
)
from . import UBDCBaseTestWorker
from . import get_fixture


# These test represent the X core ops that beat will run periodically

class TestCoreOps(UBDCBaseTestWorker):
    fixtures = [
        get_fixture("EDIN_AOI_SHAPE.json"),
        get_fixture("EDIN_GRID_LISTINGS.json"),
    ]

    def setUp(self):
        self.aoi_id = 1
        self.listing_404 = 30729869
        self.listing_200 = 40197612
        self.quadkey = "03113323321103333"

        from ubdc_airbnb.models import UBDCGrid

        self.g = UBDCGrid.objects.get(quadkey=self.quadkey)
        self.g.datetime_last_estimated_listings_scan = timezone.now() - timedelta(days=10)
        self.g.save()

    def test_op_discover_new_listings_periodical(self):
        task = op_discover_new_listings_periodical.s()
        job = task.apply_async()
        time.sleep(1)
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(1)

        self.assertTrue(abs(timezone.now() - self.g.datetime_last_estimated_listings_scan) < timedelta(seconds=20))

    def test_op_estimate_listings_or_divide_periodical(self):
        task = op_estimate_listings_or_divide_periodical.s()
        job = task.apply_async()
        time.sleep(1)
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(1)
        print('waiting...')

    def test_op_update_calendar_periodical(self):
        task = op_update_calendar_periodical.s(how_many=17_000 * 3)
        job = task.apply_async()
        time.sleep(1)
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(1)
        print('waiting...')

    def test_op_update_listing_details_periodical(self):
        task = op_update_listing_details_periodical.s()
        job = task.apply_async()
        time.sleep(2)
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(1)
        print('waiting...')

    def test_op_update_reviews_periodical(self):
        task = op_update_reviews_periodical.s(how_many=50)
        job = task.apply_async()
        time.sleep(1)
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(1)
        print('waiting...')
