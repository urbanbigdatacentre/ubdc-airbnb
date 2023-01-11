import time

from celery.result import AsyncResult
from django.utils import timezone
from requests import HTTPError

from . import UBDCBaseTestWorker, UBDCBaseTest
from . import get_fixture
from ubdc_airbnb.errors import UBDCError, UBDCRetriableError
from ubdc_airbnb.models import AirBnBResponseTypes, AirBnBUser, AirBnBResponse
from ubdc_airbnb.tasks import task_get_or_create_user


class TestsUnits(UBDCBaseTest):
    fixtures = [
        get_fixture("EDIN_AOI_SHAPE.json"),
        get_fixture("EDIN_GRID_LISTINGS.json"),
    ]

    def setUp(self):
        self.listing_404 = 30729869
        self.listing_200 = 40197612
        self.quadkey = "03113323321103333"
        self.me = '141986833'  # me

        from ubdc_airbnb.models import UBDCGrid

        g = UBDCGrid.objects.get(quadkey=self.quadkey)
        g.datetime_last_estimated_listings_scan = timezone.now()
        g.save()
        # call_command('flush', no_input='yes')
        # call_command('import_world_mask', only_iso='GRC')
        # call_command('add_aoi', create_grid=False, geo_file=self.test_input_aoi.as_posix())

    def test_warmup(self):
        from ubdc_airbnb.models import AirBnBListing

        all_listings = AirBnBListing.objects.all()

        self.assertEqual(all_listings.count(), 20)

    def test_create_response_cal(self):
        from ubdc_airbnb.models import AirBnBResponse

        ubdc_response = AirBnBResponse.objects.response_and_create('get_calendar',
                                                                   _type=AirBnBResponseTypes.calendar,
                                                                   listing_id=self.listing_200)

        self.assertEqual(ubdc_response._type, AirBnBResponseTypes.calendar)

    def test_create_response_cal_404(self):
        from ubdc_airbnb.models import AirBnBResponse

        try:
            AirBnBResponse.objects.response_and_create('get_calendar',
                                                       _type=AirBnBResponseTypes.calendar,
                                                       listing_id=self.listing_404)
        except HTTPError as exc:
            r = exc.ubdc_response
            self.assertIsNotNone(r)

            self.assertGreater(r.status_code, 399)

    def test_response_and_log_user(self):
        ubdc_response = AirBnBResponse.objects.response_and_create("get_user", user_id=self.me,
                                                                   _type=AirBnBResponseTypes.userDetail)

        self.assertEqual(ubdc_response.status_code, 200)

    def test_get_or_create_user_defer(self):
        u = task_get_or_create_user(user_id=self.me, defer=False)
        user = AirBnBUser.objects.get(user_id=u)

        # tasks = UBDCTask.objects.filter(task_name__contains='task_get_or_create_user').first()
        # result = AsyncResult(tasks.task_id)
        self.assertIsNotNone(user)
