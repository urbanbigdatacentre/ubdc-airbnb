# model related testes
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from ubdc_airbnb.models import AOIShape


@pytest.mark.django_db(transaction=True)
def test_get_or_create_user():
    from ubdc_airbnb.model_defaults import AIRBNBUSER_FIRST_NAME
    from ubdc_airbnb.models import AirBnBUser

    user_id = "1234"
    user, created = AirBnBUser.objects.get_or_create(user_id=user_id)

    assert user.user_id == user_id
    assert user.first_name == AIRBNBUSER_FIRST_NAME
    assert user.needs_update is True


@pytest.mark.django_db(transaction=True)
def test_aoi_create_grid(aoishape_model, ubdcgrid_model):
    import mercantile
    from django.contrib.gis.geos import MultiPolygon, Point, Polygon

    from ubdc_airbnb.utils.spatial import reproject

    p1 = (-4.29151610736088, 55.87456761451867)
    p2 = (-4.311980830393486, 55.88206103641572)

    for idx, p in enumerate([p1, p2]):
        point = Point(p1, srid=4326)
        point = reproject(point, to_srid=3857, from_srid=4326)
        geom = MultiPolygon(point.buffer(pow(10, idx)))
        aoi: "AOIShape" = aoishape_model.objects.create(
            name=f"Test AOI-{idx}",
            geom_3857=geom,
        )
        result = aoi.create_grid()

    assert aoishape_model.objects.filter(name__startswith="Test AOI-").count() == 2
    assert ubdcgrid_model.objects.all().count() == 16
    grid = ubdcgrid_model.objects.first()
    assert grid.quadkey.startswith("0")
