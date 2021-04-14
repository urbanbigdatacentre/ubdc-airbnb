from datetime import datetime
from typing import Tuple, List, Union

import celery.states as c_states
import mercantile
from celery.result import AsyncResult
from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry, Polygon
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import QuerySet
from django.utils.functional import cached_property
from django_celery_results.models import TaskResult as celery_Task
from more_itertools import flatten

from app.errors import UBDCError
from app.managers import UserManager, UBDCGridManager, AirBnBResponseManager


class WorldShape(models.Model):
    iso3_alpha: str = models.CharField(max_length=3, db_index=True)
    name_0: str = models.CharField(max_length=255, db_index=True)
    md5_checksum: str = models.CharField(max_length=255, editable=False, unique=True)

    geom_3857: Polygon = models.PolygonField(srid=3857)  # lets all play at www.epsg.io/3857

    def __repr__(self):
        return f'Id: {self.id}/Alpha: {self.iso3_alpha}'


class AOIShape(models.Model):
    geom_3857 = models.MultiPolygonField(srid=3857, help_text='Geometry column. Defined at EPSG:3857',
                                         editable=False)
    name = models.TextField(default='', help_text='Name to display.')
    notes = models.JSONField(default=dict, encoder=DjangoJSONEncoder, help_text='Notes.')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Date of entry')

    scan_for_new_listings = models.BooleanField(default=True, db_index=True)

    collect_calendars = models.BooleanField(default=True, db_index=True)
    collect_listing_details = models.BooleanField(default=True, db_index=True)
    collect_reviews = models.BooleanField(default=True, db_index=True)
    collect_bookings = models.BooleanField(default=True, db_index=True)

    @property
    def geom_4326(self):
        return self.as_wkt(4326)

    def as_wkt(self, epsg: int = 4326) -> str:
        geom = self.geom_3857
        return geom.transform(ct=epsg, clone=True)

    def bbox(self, epsg: int = 4326) -> Tuple[float, float, float, float]:
        """ Returns LR->UL bbox coordinates as tuple. """
        return self.geom_3857.transform(epsg, clone=True).extent

    def as_mtile(self) -> mercantile.Tile:
        bbox = self.bbox(4326)
        # NB: when the bbox spans lines of lng 0 or lat 0, the bounding tile
        # will be Tile(x=0, y=0, z=0).
        return mercantile.bounding_tile(*bbox)

    @property
    def listings(self) -> QuerySet:
        return AirBnBListing.objects.filter(geom_3857__intersects=self.geom_3857)


class UBDCGrid(models.Model):
    geom_3857 = models.PolygonField(srid=3857, null=False)

    quadkey = models.TextField(null=False, unique=True, blank=True, editable=False, db_index=True)
    tile_x = models.IntegerField(null=False)
    tile_y = models.IntegerField(null=False)
    tile_z = models.IntegerField(null=False)
    x_distance_m = models.FloatField()
    y_distance_m = models.FloatField()

    bbox_ll_ur = models.TextField(null=False)
    area = models.FloatField()

    timestamp = models.DateTimeField(auto_now_add=True)

    # Functional
    datetime_last_estimated_listings_scan = models.DateTimeField(db_index=True, null=True, blank=True)
    datetime_last_listings_scan = models.DateTimeField(db_index=True, null=True, blank=True)
    estimated_listings = models.IntegerField(verbose_name="Estimated Listings reported from AirBnB", default=-1)

    objects = UBDCGridManager()

    def __str__(self):
        return f'{self.__class__.__name__}: {self.id}/{self.quadkey}'

    @property
    def as_ewkt(self) -> str:
        """ Return a WTK representation of the geometry. Includes SRID. """
        return self.geom_3857.ewkt

    @property
    def as_wkt(self) -> str:
        """ Alias for as_ewkt """
        return self.as_ewkt

    @property
    def listings(self):
        return AirBnBListing.objects.filter(geom_3857__intersects=self.geom_3857)

    @property
    def as_mtile(self) -> mercantile.Tile:
        if self.quadkey is None:
            raise ValueError('QuadKey is not set.')
        return mercantile.quadkey_to_tile(self.quadkey)

    def children(self, intersect_with: Union[int, str] = None, zoom=None, use_landmask=True) -> List[mercantile.Tile]:
        """ Find the children for this Grid.

        :param intersect_with: Optionally (recommended) use a *AOISHAPE id* to filter out disjointed children
        :param use_landmask: Use the internal landmask. (UK only)
        :param zoom:

        """

        # Clean all fields and raise a ValidationError containing
        # a dict with all validation errors if any.
        self.clean_fields()

        tile = self.as_mtile

        # assume zoom + 1
        if zoom is None:
            zoom = self.tile_z + 1

        if self.tile_z <= zoom:
            _zoom = tile.z

            while _zoom <= zoom:
                if tile.z == _zoom:
                    children = mercantile.children(*tile)
                else:
                    children = list(flatten(map(lambda t: mercantile.children(t, zoom=_zoom), children)))

                _zoom += 1

                if intersect_with:
                    # if intersects_with is an integer, assume it's an ID that refers to a user-AOI
                    if isinstance(intersect_with, int):
                        aoi_geom = AOIShape.objects.get(pk=intersect_with).geom_3857
                    # else if its a string, try to parse it to a geometry
                    elif isinstance(intersect_with, str):
                        aoi_geom = GEOSGeometry(intersect_with)
                    else:
                        raise UBDCError('Could not generate valid geometry to filter with.')

                    aoi_geom = aoi_geom.prepared

                    def filter_func_intersects_with(_tile: mercantile.Tile) -> bool:
                        polygon = Polygon.from_bbox(mercantile.xy_bounds(*_tile))
                        return aoi_geom.intersects(polygon)

                    children = filter(filter_func_intersects_with, children)

                if use_landmask:
                    potential_hits = WorldShape.objects.filter(geom_3857__intersects=self.geom_3857)
                    # cast to prepared version
                    potential_hits_prep = list(geom.prepared for geom in (x.geom_3857 for x in potential_hits))

                    def filter_function_intersects_with_mask(_tile: mercantile.Tile) -> bool:
                        polygon = Polygon.from_bbox(mercantile.xy_bounds(*_tile))
                        polygon.srid = 3857
                        # polygon = polygon.prepared

                        return any([geom.intersects(polygon) for geom in potential_hits_prep])

                    children = filter(filter_function_intersects_with_mask, children)

        return children

    def make_children(self, zoom=None, use_landmask=True) -> List['UBDCGrid']:
        # higher zoom is up
        if zoom is None:
            zoom = self.tile_z + 1

        if zoom <= self.tile_z:
            raise UBDCError()

        children = self.children(zoom=zoom, use_landmask=use_landmask)
        c_tiles = []
        for m_tile in children:
            c_tiles.append(UBDCGrid.objects.create_from_tile(m_tile))

        UBDCGrid.objects.bulk_create(c_tiles)
        self.delete()

        return c_tiles

    # def estimate_listings(self, **kwargs) -> int:
    #     """ Query airbnb for an estimation of how many listings are in this grid
    #
    #     :returns int
    #     """
    #
    #     if self.id is None:
    #         raise self.DoesNotExist('This instance has not been saved in the database yet.')
    #
    #     bbox = bbox_from_quadkey(self.quadkey)
    #
    #     (west=west, south=south, east=east, north=north)
    #     ubdc_response : AirBnBResponse = AirBnBResponse.objects.response_and_create(
    #         "number_of_listings", _type=AirBnBResponseTypes.searchMetaOnly,
    #     )
    #     estimated_listings, response = estimate_listings_at_grid(self.quadkey)
    #     search_response: AirBnBResponse = AirBnBResponse.objects.create_from_response(response,
    #                                                                                   _type=AirBnBResponseTypes.search,
    #                                                                                   **kwargs)
    #
    #     self.estimated_listings = estimated_listings
    #
    #     search_response.grid = self
    #     search_response.save()
    #
    #     return self.estimated_listings


class AirBnBResponseTypes(models.TextChoices):
    unknown = 'UNK', 'Unknown'

    bookingQuote = 'BQT', 'Booking Detail'
    calendar = 'CAL', 'Calendar'
    review = 'RVW', 'Review'
    listingDetail = 'LST', 'Listing'
    search = 'SRH', 'Search'
    searchMetaOnly = 'SHM', 'Search (MetaOnly)'
    userDetail = 'USR', 'User'


class AirBnBResponse(models.Model):
    """ A model to hold Airbnb responses.
    If ubdc_task is Null, that means the data fetch was initiated manually """

    listing_id: str = models.IntegerField(null=True, db_index=True)

    _type = models.CharField(max_length=3, db_column='type',
                             db_index=True,
                             choices=AirBnBResponseTypes.choices,
                             default=AirBnBResponseTypes.unknown,
                             verbose_name='Response Type')
    status_code: int = models.IntegerField(db_index=True, help_text='Status code of the response')
    resource_url: str = models.TextField()
    payload: dict = models.JSONField(default=dict)
    url: str = models.TextField(null=False, blank=False)
    query_params: dict = models.JSONField(default=dict)
    seconds_to_complete: int = models.IntegerField(null=False,
                                                   blank=False,
                                                   help_text='Time in seconds for the response to come back.')

    timestamp: datetime = models.DateTimeField(auto_now_add=True,
                                               db_index=True,
                                               verbose_name='Date of row creation.')

    # many 2 one
    ubdc_task = models.ForeignKey('UBDCTask',
                                  null=True,
                                  on_delete=models.DO_NOTHING,
                                  to_field='task_id')

    objects = AirBnBResponseManager()

    def __str__(self):
        return f'{self.id}/{self.get__type_display()}'

    class Meta:
        ordering = ["timestamp", ]


class AirBnBListing(models.Model):
    listing_id = models.IntegerField(unique=True, null=False, help_text='(PK) Airbnb ListingID', primary_key=True)
    geom_3857 = models.PointField(srid=3857, help_text='Current Geom Point (\'3857\') of listing\'s location')
    timestamp = models.DateTimeField(auto_now_add=True, help_text='Datetime of entry')
    listing_updated_at = models.DateTimeField(null=True, blank=True, help_text='Datetime of last listing update')
    calendar_updated_at = models.DateTimeField(null=True, blank=True, help_text='Datetime of last calendar update')
    booking_quote_updated_at = models.DateTimeField(null=True, blank=True,
                                                    help_text='Datetime of latest booking quote update')
    reviews_updated_at = models.DateTimeField(null=True, blank=True, help_text='Datetime of last comment update')
    notes = models.JSONField(default=dict,
                             encoder=DjangoJSONEncoder,
                             help_text='Notes about this listing')

    responses = models.ManyToManyField('AirBnBResponse')

    objects = AirBnBResponseManager()


# not using the User name, so we wont get confused with functional user
class AirBnBUser(models.Model):
    user_id = models.IntegerField(unique=True, null=False, blank=True, help_text='Airbnb User id')
    first_name = models.TextField(default='')
    about = models.TextField(default='')
    airbnb_listing_count = models.IntegerField(default=0, help_text='as reported by airbnb')
    location = models.TextField()
    verifications = ArrayField(base_field=models.CharField(max_length=255), blank=True, null=True)
    picture_url = models.TextField()
    is_superhost = models.BooleanField(help_text='if the user is super host', default=False)
    created_at = models.DateTimeField(blank=True, null=True, help_text='profile created at airbnb')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Date of row creation.')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Latest update.')

    listings = models.ManyToManyField(AirBnBListing, related_name='users')
    responses = models.ManyToManyField('AirBnBResponse')

    objects = UserManager()

    @cached_property
    def listing_count(self) -> int:
        return self.listings.count()

    @cached_property
    def url(self) -> str:
        return f'https://www.airbnb.co.uk/users/show/{self.user_id}'


class AirBnBReview(models.Model):
    review_id = models.IntegerField(unique=True, null=False, blank=False, help_text='AirBNB Review id')  # required
    created_at = models.DateTimeField(help_text='as reported by AirBNB', blank=False, null=False)  # required
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Date of row creation.')
    review_text = models.TextField()
    language = models.CharField(max_length=10, default='')

    listing = models.ForeignKey(AirBnBListing, on_delete=models.SET_NULL, to_field='listing_id',
                                related_name='comments', verbose_name='(AirBNB) Listing id.', null=True)

    # # one to many
    author = models.ForeignKey(AirBnBUser, on_delete=models.SET_NULL, to_field='user_id',
                               related_name='comments_authored',
                               verbose_name='Author (airbnb user id) of Review', null=True)
    recipient = models.ForeignKey(AirBnBUser, on_delete=models.SET_NULL, to_field='user_id',
                                  related_name='comments_received',
                                  verbose_name='recipient (airbnb user id) of the comment/review', null=True)
    response = models.ForeignKey('AirBnBResponse', on_delete=models.SET_NULL, related_name='comments',
                                 null=True)


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
    op_initiator = models.TextField(max_length=255, default='')

    class Meta:
        ordering = ["timestamp", ]
        unique_together = ['group_task_id', 'root_id']


class UBDCTask(models.Model):
    class TaskTypeChoices(models.TextChoices):
        SUBMITTED = 'SUBMITTED'
        STARTED = c_states.STARTED
        SUCCESS = c_states.SUCCESS
        FAILURE = c_states.FAILURE
        REVOKED = c_states.REVOKED
        RETRY = c_states.RETRY
        UNKNOWN = 'UNKNOWN'

    task_id = models.UUIDField(editable=False, unique=True, db_index=True)
    task_name = models.TextField(blank=False)
    task_args = models.TextField(default='[]')
    parent_id = models.UUIDField(editable=False, db_index=True, null=True)

    status = models.TextField(choices=TaskTypeChoices.choices, default=TaskTypeChoices.SUBMITTED, db_index=True)

    datetime_submitted = models.DateTimeField(auto_now_add=True, db_index=True)
    datetime_started = models.DateTimeField(null=True, blank=True)
    datetime_finished = models.DateTimeField(null=True, blank=True)
    time_to_complete = models.TextField(blank=True, default='')
    retries = models.IntegerField(default=0)
    task_kwargs = models.JSONField(default=dict)

    group_task = models.ForeignKey('UBDCGroupTask', on_delete=models.DO_NOTHING, null=True,
                                   related_query_name='ubdc_task', related_name='ubdc_tasks',
                                   to_field='group_task_id')

    root_id = models.UUIDField(editable=False, db_index=True, null=True)

    class Meta:
        ordering = ["datetime_submitted", ]
        indexes = [
            GinIndex(fields=['task_kwargs'])
        ]

    @property
    def is_root(self):
        return self.root_id == self.task_id

    def associated_tasks(self):
        return UBDCTask.objects.filter(root_id=self.task_id)

    @property
    def async_result(self) -> AsyncResult:
        return AsyncResult(self.task_id)

    def revoke_task(self) -> None:
        if self.status in c_states.READY_STATES:
            print('Task already finished! Cannot revoke')
            return

        c_task = celery_Task.objects.filter(task_id=self.task_id)
        if c_task.exists():
            print('Task found at celery task registry')
            self.async_result.revoke()
        else:
            print('Task NOT found at celery task registry. Assuming tombstone-ed and marking as REVOKED')
            self.status = c_states.REVOKED
            self.save()
