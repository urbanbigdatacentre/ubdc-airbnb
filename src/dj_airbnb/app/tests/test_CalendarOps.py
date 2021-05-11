import os
import time

from django.utils import timezone

from . import UBDCBaseTestWorker
from . import get_fixture
from ..errors import UBDCError
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

    def test_get_calendar(self):
        from app.tasks import task_update_calendar

        task = task_update_calendar.s(listing_id=self.listing_404)
        job = task.apply_async()

        ref = None
        with self.assertRaises(UBDCError) as exc:
            job.get()
            ref = exc

        print('end')

    def test_scan_for_listings(self):
        from app.operations import op_discover_new_listings_at_grid

        task = op_discover_new_listings_at_grid.s(self.quadkey)
        job = task.apply_async()
        time.sleep(1)
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(1)
        group_result_id = job.get()

        print('do some actual testing')

    def test_grab_listing_calendar(self):
        from app.operations import op_update_calendars_for_listing_ids
        from app.models import AirBnBResponse
        task = op_update_calendars_for_listing_ids.s(self.listing_200)

        job = task.apply_async()
        time.sleep(1)
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(2)
        result = job.get()
        r = AirBnBResponse.objects.filter(listing_id=self.listing_200).order_by("timestamp").first()
        task_obj = r.ubdc_task
        self.assertEqual(r.status_code, 200)

        print('do some actual testing')

    def test_grab_listing_calendar_non_existent(self):
        from app.operations import op_update_calendars_for_listing_ids
        from app.models import AirBnBResponse
        from app.errors import UBDCRetriableError

        from app.errors import UBDCError

        task = op_update_calendars_for_listing_ids.s(self.listing_404)

        job = task.apply_async()
        time.sleep(1)
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(1)

        try:
            list(job.collect())
        except (UBDCRetriableError, UBDCError) as exc:
            r = AirBnBResponse.objects.filter(listing_id=self.listing_404).first()
            self.assertIsNotNone(r)
            self.assertIn(r.status_code, [503, 403], 'unexpected return code')
            self.assertEqual(r._type, AirBnBResponseTypes.calendar)
        else:
            self.fail('error was not raised')
