import time

import responses
from django.conf import settings
from django.utils import timezone

from ubdc_airbnb.errors import UBDCError
from ubdc_airbnb.models import AirBnBResponseTypes
from . import UBDCBaseTestWorker
from . import get_fixture


class TestCalendarOps(UBDCBaseTestWorker):
    fixtures = [
        get_fixture("EDIN_AOI_SHAPE.json"),
        get_fixture("EDIN_GRID_LISTINGS.json"),
    ]

    def setUp(self):
        self.listing_404 = 30729869
        self.listing_200 = 51593353
        self.quadkey = "03113323321103333"

        from ubdc_airbnb.models import UBDCGrid

        g = UBDCGrid.objects.get(quadkey=self.quadkey)
        g.datetime_last_estimated_listings_scan = timezone.now()
        g.save()

        responses.get(
            settings.AIRBNB_API_ENDPOINT + "/v2/calendar_months",
            body="within setup"
        )


    def test_warmup(self):
        from ubdc_airbnb.models import AirBnBListing
        all_listings = AirBnBListing.objects.all()
        self.assertEqual(all_listings.count(), 20)
    @responses.activate
    def test_grab_listing_calendar(self):
        from ubdc_airbnb.operations import op_update_calendars_for_listing_ids
        from ubdc_airbnb.models import AirBnBResponse
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

    def test_get_calendar_404(self):
        from ubdc_airbnb.tasks import task_update_calendar

        task = task_update_calendar.s(listing_id=self.listing_404)
        job = task.apply_async()

        ref = None
        with self.assertRaises(UBDCError) as exc:
            job.get()
            ref = exc

        print('end')

    def test_scan_for_listings(self):
        from ubdc_airbnb.operations import op_discover_new_listings_at_grid

        task = op_discover_new_listings_at_grid.s(self.quadkey)
        job = task.apply_async()
        time.sleep(1)
        while not all(list(x.ready() for x in job.children)):
            print('waiting...')
            time.sleep(1)
        group_result_id = job.get()

        print('do some actual testing')

    def test_grab_listing_calendar_non_existent(self):
        from ubdc_airbnb.operations import op_update_calendars_for_listing_ids
        from ubdc_airbnb.models import AirBnBResponse
        from ubdc_airbnb.errors import UBDCRetriableError

        from ubdc_airbnb.errors import UBDCError

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
