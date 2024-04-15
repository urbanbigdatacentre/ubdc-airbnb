from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, List, Tuple

import celery.states as c_states
import mercantile
from celery.result import AsyncResult
from celery.utils.log import get_task_logger
from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import QuerySet
from django.utils.functional import cached_property
from django_celery_results.models import TaskResult as celery_Task
from more_itertools import flatten

from ubdc_airbnb import model_defaults
from ubdc_airbnb.errors import UBDCError
from ubdc_airbnb.managers import AirBnBResponseManager, UBDCGridManager, UserManager

logger = get_task_logger(__name__)


class WorldShape(models.Model):

    iso3_alpha = models.CharField(max_length=3, db_index=True)
    name_0 = models.CharField(max_length=255, db_index=True)
    md5_checksum = models.CharField(max_length=255, editable=False, unique=True)

    geom_3857 = models.PolygonField(srid=3857)  # lets all play at www.epsg.io/3857

    def __repr__(self):
        return f"Id: {self.pk}/Alpha: {self.iso3_alpha}"


class AOIShape(models.Model):
    geom_3857 = models.MultiPolygonField(srid=3857, help_text="Geometry column. Defined at EPSG:3857", editable=False)
    name = models.TextField(
        default=model_defaults.AIOSHAPE_NAME,
        help_text="Name to display.",
    )
    notes = models.JSONField(default=dict, encoder=DjangoJSONEncoder, help_text="Notes.")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Date of entry")

    scan_for_new_listings = models.BooleanField(default=True, db_index=True)

    collect_calendars = models.BooleanField(
        default=model_defaults.AOISHAPE_COLLECT_CALENDARS,
        db_index=True,
    )
    collect_listing_details = models.BooleanField(
        default=model_defaults.AOISHAPE_COLLECT_LISTING_DETAILS,
        db_index=True,
    )
    collect_reviews = models.BooleanField(
        default=model_defaults.AOISHAPE_COLLECT_REVIEWS,
        db_index=True,
    )
    collect_bookings = models.BooleanField(
        default=model_defaults.AOISHAPE_COLLECT_BOOKINGS,
        db_index=True,
    )

    @property
    def geom_4326(self):
        return self.reproject(4326)

    @classmethod
    def create_from_geojson(cls, geojson: Path) -> "AOIShape":

        "Create an AOI from a GeoJSON file. Returns the created object."

        import json

        assert geojson.exists(), f"File {geojson} does not exist."

        payload = json.loads(geojson.read_text())
        json_geom = json.dumps(payload["features"][0]["geometry"])

        geom = GEOSGeometry(json_geom)
        if not geom.geom_type.endswith("Polygon"):
            raise ValueError("Only Polygon Like geometries are supported.")

        if geom.geom_type == "Polygon":
            geom = MultiPolygon(geom)

        # geojson are supposed to be in 4326
        geom.srid = 4326
        # reproject to 3857 in place
        geom.transform(3857)

        rv = cls(
            geom_3857=geom,
            name=geojson.stem,
            collect_calendars=False,
            collect_listing_details=False,
            collect_reviews=False,
            collect_bookings=False,
            scan_for_new_listings=False,
        )
        rv.save()
        rv.refresh_from_db()

        return rv

    @classmethod
    def create_from_bbox(cls, bbox: Tuple[float, float, float, float], name: str) -> "AOIShape":
        from django.contrib.gis.geos import Polygon

        geom = MultiPolygon(Polygon.from_bbox(bbox))
        geom.srid = 4326
        geom.transform(3857)

        rv = cls(
            geom_3857=geom,
            name=name,
            collect_calendars=False,
            collect_listing_details=False,
            collect_reviews=False,
            collect_bookings=False,
            scan_for_new_listings=False,
        )
        rv.save()
        rv.refresh_from_db()

        return rv

    def reproject(self, epsg: int = 4326):
        geom = self.geom_3857
        return geom.transform(ct=epsg, clone=True)

    def bbox(self, epsg: int = 4326) -> Tuple[float, float, float, float]:
        """Returns LR->UL bbox coordinates as tuple."""
        return self.geom_3857.transform(epsg, clone=True).extent

    def as_mtile(self) -> mercantile.Tile:
        bbox = self.bbox(4326)
        # NB: when the bbox spans lines of lng 0 or lat 0, the bounding tile
        # will be Tile(x=0, y=0, z=0).
        return mercantile.bounding_tile(*bbox)

    def create_grid(self) -> bool:
        "Create Grids from this AOI. The grids will be automatically sized based on existing grids. Returns True if successful."
        from itertools import chain

        from ubdc_airbnb.utils.grids import clean_quadkeys, quadkeys_of_geom
        from ubdc_airbnb.utils.spatial import cut_polygon_at_prime_lines

        # cut the aoi geom at the prime lines.
        # if not, and the aoi passes the primes, it's initial grid will cover the whole world.
        geoms = cut_polygon_at_prime_lines(self.geom_4326)

        # depending on the complexity of the initial geom, we could have lists of lists of geometries
        init_qks = [quadkeys_of_geom(geom) for geom in geoms]
        # so in this step we flatten the list of lists
        init_qks = list(chain.from_iterable(init_qks))

        qks = list(chain.from_iterable([clean_quadkeys(qk) for qk in init_qks]))

        # create unsaved objects
        objs = [UBDCGrid.objects.model_from_quadkey(qk) for qk in qks]

        # bulk save them
        UBDCGrid.objects.bulk_create(objs)

        return True

    @property
    def listings(self) -> QuerySet:
        return AirBnBListing.objects.filter(geom_3857__intersects=self.geom_3857)


class UBDCGrid(models.Model):
    geom_3857 = models.PolygonField(srid=3857, null=False)

    quadkey = models.TextField(
        null=False,
        unique=True,
        blank=True,
        editable=False,
        db_index=True,
    )
    tile_x = models.BigIntegerField(null=False)
    tile_y = models.BigIntegerField(null=False)
    tile_z = models.BigIntegerField(null=False)
    x_distance_m = models.FloatField()
    y_distance_m = models.FloatField()

    bbox_ll_ur = models.TextField(null=False)
    area = models.FloatField()

    timestamp = models.DateTimeField(auto_now_add=True)

    # Functional
    datetime_last_estimated_listings_scan = models.DateTimeField(
        db_index=True,
        null=True,
        blank=True,
    )
    datetime_last_listings_scan = models.DateTimeField(
        db_index=True,
        null=True,
        blank=True,
    )
    estimated_listings = models.IntegerField(
        verbose_name="Estimated Listings reported from AirBnB",
        default=-1,
    )

    objects: ClassVar[UBDCGridManager] = UBDCGridManager()

    def __str__(self):
        return f"{self.__class__.__name__}: {self.pk}/{self.quadkey}"

    @property
    def intersects_with_aoi(self) -> bool:
        """Check if this grid intersects with any AOI."""
        q = AOIShape.objects.filter(geom_3857__intersects=self.geom_3857)
        return q.exists()

    @property
    def as_ewkt(self) -> str:
        """Return a WTK representation of the geometry. Includes SRID."""
        return self.geom_3857.ewkt

    @property
    def as_wkt(self) -> str:
        """Alias for as_ewkt"""
        return self.as_ewkt

    @property
    def listings(self):
        return AirBnBListing.objects.filter(geom_3857__intersects=self.geom_3857)

    @property
    def as_tile(self) -> mercantile.Tile:
        if self.quadkey is None:
            raise ValueError("QuadKey is not set.")
        return mercantile.quadkey_to_tile(self.quadkey)

    def children(self) -> "List[UBDCGrid]":
        """Return unsaved grid childrens of this grid."""
        from mercantile import children

        tile = self.as_tile
        children_tiles = children(tile)
        return [UBDCGrid.objects.model_from_tile(t) for t in children_tiles]

    @classmethod
    def model_from_quadkey(cls, quadkey: str) -> "UBDCGrid":
        """Make an UBDCGrid object and return a ref of it."""
        tile = mercantile.quadkey_to_tile(quadkey)
        return cls.model_from_tile(tile)

    @classmethod
    def as_geojson(cls) -> str | None:
        """Return a GeoJSON FeatureCollection of the queryset."""
        from django.contrib.gis.db.models.functions import Transform
        from django.contrib.gis.serializers.geojson import (
            Serializer as GeoJSONSerializer,
        )

        qset = cls.objects.only("geom_3857")
        # qset = qset.annotate(geom=Transform("geom_3857", 4326))
        serializer = GeoJSONSerializer()
        serializer.serialize(qset, fields=("geom_3857",))

        data = serializer.getvalue()
        if data and isinstance(data, str):
            return data

    @classmethod
    def save_as_geojson(cls, filename: Path) -> str | None:
        context = cls.as_geojson()
        if context:
            filename.write_text(context)
            return filename.as_posix()

    @classmethod
    def model_from_tile(
        cls,
        tile: mercantile.Tile,
    ) -> "UBDCGrid":
        """Make an UBDCGrid object and return a ref of it."""
        from django.contrib.gis.geos import Polygon as GEOSPolygon

        from ubdc_airbnb.utils.spatial import postgis_distance_a_to_b

        quadkey = mercantile.quadkey(tile)
        bbox = list(mercantile.xy_bounds(*tile))
        min_x, min_y, max_x, max_y = bbox
        mid_x = min_x + max_x / 2
        mid_y = min_y + max_y / 2
        geom_3857 = GEOSPolygon.from_bbox(bbox)

        return cls(
            geom_3857=geom_3857,
            quadkey=quadkey,
            bbox_ll_ur=",".join(map(str, bbox)),
            tile_x=tile.x,
            tile_y=tile.y,
            tile_z=tile.z,
            area=geom_3857.area,
            x_distance_m=postgis_distance_a_to_b((min_x, mid_y), (max_x, mid_y)),
            y_distance_m=postgis_distance_a_to_b((mid_x, min_y), (mid_x, max_y)),
        )


class AirBnBResponseTypes(models.TextChoices):
    unknown = "UNK", "Unknown"

    bookingQuote = "BQT", "Booking Detail"
    calendar = "CAL", "Calendar"
    review = "RVW", "Review"
    listingDetail = "LST", "Listing"
    search = "SRH", "Search"
    searchMetaOnly = "SHM", "Search (MetaOnly)"
    userDetail = "USR", "User"


class AirBnBResponse(models.Model):
    """A model to hold Airbnb responses."""

    # convience if response is about a listing
    listing_id = models.BigIntegerField(
        null=True,
        db_index=True,
        help_text="Airbnb ListingID",
    )

    _type = models.CharField(
        max_length=3,
        db_column="type",
        db_index=True,
        choices=AirBnBResponseTypes.choices,
        default=AirBnBResponseTypes.unknown,
        verbose_name="Response Type",
    )
    status_code = models.IntegerField(
        db_index=True,
        help_text="Status code of the response",
    )
    payload = models.JSONField(
        default=dict,
        help_text="Response payload",
    )
    request_headers = models.JSONField(default=dict)
    url = models.TextField(
        null=False,
        blank=False,
    )
    query_params = models.JSONField(default=dict)
    seconds_to_complete = models.IntegerField(
        null=False,
        blank=False,
        help_text="Time in seconds for the response to come back.",
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Date of row creation.",
    )

    # many 2 one
    ubdc_task = models.ForeignKey(
        "UBDCTask",
        null=True,
        on_delete=models.DO_NOTHING,
        to_field="task_id",
    )

    objects: ClassVar[AirBnBResponseManager] = AirBnBResponseManager()

    def __str__(self):
        return f"{self.pk}/{self.get__type_display()}"  # type: ignore # TODO: fix typing?

    class Meta:
        ordering = [
            "timestamp",
        ]


class AirBnBListing(models.Model):
    listing_id = models.BigIntegerField(
        unique=True,
        null=False,
        help_text="(PK) Airbnb ListingID",
        primary_key=True,
    )
    geom_3857 = models.PointField(
        null=True,
        srid=3857,
        help_text="Current Geom Point ('3857') of listing's location",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Datetime of entry",
    )
    listing_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Datetime of last listing update",
    )
    calendar_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Datetime of last calendar update",
    )
    booking_quote_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Datetime of latest booking quote update",
    )
    reviews_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Datetime of last comment update",
    )
    notes = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text="Notes about this listing",
    )

    responses = models.ManyToManyField("AirBnBResponse")

    objects: ClassVar[AirBnBResponseManager] = AirBnBResponseManager()


class AirBnBUser(models.Model):
    user_id = models.BigIntegerField(
        unique=True,
        null=False,
        blank=True,
        help_text="Airbnb User id",
    )
    first_name = models.TextField(
        default=model_defaults.AIRBNBUSER_FIRST_NAME,
        help_text="First name of the user",
    )
    about = models.TextField(
        default=model_defaults.AIRBNBUSER_ABOUT,
        help_text="Self description of the user",
    )
    airbnb_listing_count = models.IntegerField(
        default=0,
        help_text="as reported by airbnb",
    )
    location = models.TextField()
    verifications = ArrayField(base_field=models.CharField(max_length=255), blank=True, null=True)
    picture_url = models.TextField()
    is_superhost = models.BooleanField(
        default=False,
        help_text="if the user is super host",
    )
    created_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="profile created at airbnb",
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Date of row creation.")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Latest update.")

    listings = models.ManyToManyField(AirBnBListing, related_name="users")
    responses = models.ManyToManyField("AirBnBResponse")

    objects: ClassVar[UserManager] = UserManager()

    @cached_property
    def listing_count(self) -> int:
        return self.listings.count()

    @cached_property
    def url(self) -> str:
        return f"https://www.airbnb.co.uk/users/show/{self.user_id}"

    class Meta:
        indexes = [
            models.Index(
                fields=["first_name"],
                condition=models.Q(first_name="UBDC-PLACEHOLDER"),
                name="ubdc_airbnbuser_D87O85F2_idx",
            )
        ]


class AirBnBReview(models.Model):
    review_id = models.BigIntegerField(unique=True, null=False, blank=False, help_text="AirBNB Review id")  # required
    created_at = models.DateTimeField(help_text="as reported by AirBNB", blank=False, null=False)  # required
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Date of row creation.")
    review_text = models.TextField()
    language = models.CharField(max_length=10, default="")

    listing = models.ForeignKey(
        AirBnBListing,
        on_delete=models.SET_NULL,
        to_field="listing_id",
        related_name="comments",
        verbose_name="(AirBNB) Listing id.",
        null=True,
    )

    # # one to many
    author = models.ForeignKey(
        AirBnBUser,
        on_delete=models.SET_NULL,
        to_field="user_id",
        related_name="comments_authored",
        verbose_name="Author (airbnb user id) of Review",
        null=True,
    )
    recipient = models.ForeignKey(
        AirBnBUser,
        on_delete=models.SET_NULL,
        to_field="user_id",
        related_name="comments_received",
        verbose_name="recipient (airbnb user id) of the comment/review",
        null=True,
    )
    response = models.ForeignKey(
        "AirBnBResponse",
        on_delete=models.SET_NULL,
        related_name="comments",
        null=True,
    )


# TODO: This is not needed anymore, as celery natively supports saving group tasks
class UBDCGroupTask(models.Model):
    # Convenience model to retrieve tasks

    group_task_id = models.UUIDField(editable=False, db_index=True, unique=True)
    root_id = models.UUIDField(editable=False, db_index=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    datetime_started = models.DateTimeField(null=True)
    datetime_finished = models.DateTimeField(null=True)  # TODO: find a good way to find when a group-task finishes

    op_name = models.TextField(blank=True, null=True)
    op_args = ArrayField(base_field=models.CharField(max_length=255), blank=True, null=True)
    op_kwargs = models.JSONField(default=dict)
    op_initiator = models.TextField(max_length=255, default="")

    class Meta:
        ordering = [
            "timestamp",
        ]
        unique_together = ["group_task_id", "root_id"]


class UBDCTask(models.Model):
    class TaskTypeChoices(models.TextChoices):
        SUBMITTED = "SUBMITTED"
        STARTED = c_states.STARTED
        SUCCESS = c_states.SUCCESS
        FAILURE = c_states.FAILURE
        REVOKED = c_states.REVOKED
        RETRY = c_states.RETRY
        UNKNOWN = "UNKNOWN"

    task_id = models.UUIDField(editable=False, unique=True, db_index=True)
    task_name = models.TextField(blank=False)
    task_args = models.TextField(default="[]")
    parent_id = models.UUIDField(editable=False, db_index=True, null=True)

    status = models.TextField(
        choices=TaskTypeChoices.choices,
        default=TaskTypeChoices.SUBMITTED,
        db_index=True,
    )

    datetime_submitted = models.DateTimeField(auto_now_add=True, db_index=True)
    datetime_started = models.DateTimeField(null=True, blank=True)
    datetime_finished = models.DateTimeField(null=True, blank=True)
    time_to_complete = models.TextField(blank=True, default="")
    retries = models.IntegerField(default=0)
    task_kwargs = models.JSONField(default=dict)

    group_task = models.ForeignKey(
        "UBDCGroupTask",
        on_delete=models.DO_NOTHING,
        null=True,
        related_query_name="ubdc_task",
        related_name="ubdc_tasks",
        to_field="group_task_id",
    )

    root_id = models.UUIDField(editable=False, db_index=True, null=True)

    class Meta:
        ordering = [
            "datetime_submitted",
        ]
        indexes = [GinIndex(fields=["task_kwargs"])]

    @property
    def is_root(self):
        return self.root_id == self.task_id

    def associated_tasks(self):
        return UBDCTask.objects.filter(root_id=self.task_id)

    @property
    def async_result(self) -> AsyncResult:
        task_id = self.task_id
        task_id = str(task_id)
        return AsyncResult(task_id)

    def revoke_task(self) -> None:
        if self.status in c_states.READY_STATES:
            # TODO: replace print with logger statements
            print("Cannot revoke: Task already finished.")
            return

        c_task = celery_Task.objects.filter(task_id=self.task_id)
        if c_task.exists():
            # TODO: replace print with logger statements
            print("Task found at celery task registry")
            self.async_result.revoke()
        else:
            # TODO: replace print with logger statements
            print("Task NOT found at celery task registry. Assuming tombstone-ed and marking as REVOKED")
            self.status = c_states.REVOKED
            self.save()
