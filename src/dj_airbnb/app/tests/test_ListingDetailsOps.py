from django.utils import timezone

from django.utils import timezone

from . import UBDCBaseTestWorker
from . import get_fixture
from ..models import AirBnBResponse, AOIShape, AirBnBListing, AirBnBResponseTypes
from ..tasks import task_add_listing_detail


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

    def test_op_listing_detail_for_listings(self):
        listing_id = task_add_listing_detail(self.listing_200)
        self.assertEqual(listing_id, self.listing_200)

        listing = AirBnBListing.objects.get(listing_id=listing_id)
        latest_listing_detail: AirBnBResponse = listing.responses.filter(
            _type=AirBnBResponseTypes.listingDetail).latest('timestamp')

        self.assertEqual(latest_listing_detail.listing_id, self.listing_200)
