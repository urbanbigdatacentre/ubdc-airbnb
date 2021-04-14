from pathlib import Path

from django.utils import timezone

from . import UBDCBaseTestWorker
from . import get_fixture

from app.operations.reviews import op_update_reviews_aoi, op_update_reviews_periodical, op_update_comment_at_listings
from ..models import AirBnBReview, AirBnBResponse, AirBnBUser, AOIShape
from ..tasks import task_update_or_add_reviews_at_listing


class TestReviewsOps(UBDCBaseTestWorker):
    fixtures = [
        get_fixture("EDIN_AOI_SHAPE.json"),
        get_fixture("EDIN_GRID_LISTINGS.json"),
    ]

    def setUp(self):
        self.listing_404 = 30729869
        self.listing_200 = 40197612
        self.listing_200_multiple_reviews = 10944167
        self.quadkey = "03113323321103333"
        from app.models import UBDCGrid

        g = UBDCGrid.objects.get(quadkey=self.quadkey)
        g.datetime_last_estimated_listings_scan = timezone.now()
        g.save()

        self.aoi = AOIShape.objects.first()

    def test_op_update_comment_at_listings(self):
        op_update_comment_at_listings(self.listing_200)

    def test_op_update_comment_at_listings_task(self):
        task = op_update_comment_at_listings.s(self.listing_200)
        job = task.apply_async()

    def test_task_update_or_add_comments_at_listing(self):
        q = task_update_or_add_reviews_at_listing(self.listing_200, defer_user_creation=False)

        self.assertTrue("AirBnBReview" in q)
        self.assertTrue("AirBnBListing" in q)

    def test_task_update_or_add_comments_at_listing_task(self):
        job = task_update_or_add_reviews_at_listing.s(self.listing_200)
        result = job.apply_async()

        result.get(timeout=10)
        self.assertGreater(len(result.children), 1)
        self.assertEqual(AirBnBResponse.objects.filter(listing_id__isnull=False, _type='RVW').count(), 1)
        self.assertGreater(AirBnBReview.objects.count(), 40)
        self.assertGreater(AirBnBUser.objects.count(), 40)

    def test_task_op_update_reviews_aoi(self):
        job = op_update_reviews_aoi.s(id_shape=self.aoi.id)
        result = job.apply_async()

        result
        print('hi')
