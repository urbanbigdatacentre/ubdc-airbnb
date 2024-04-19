# model related testes
from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon

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
    # assert user.needs_update is True


@pytest.mark.django_db(transaction=True)
def test_aoi_create_grid(aoishape_model, ubdcgrid_model, geojson_gen, tmp_path):
    for idx, gj in enumerate(geojson_gen):
        f = tmp_path / f"test-aoi-{idx}.geojson"
        f.write_text(gj)
        aoi = aoishape_model.create_from_geojson(f)
        aoi.create_grid()
        if idx >= 1:
            # only use the first two AOIs
            break

    assert aoishape_model.objects.filter(name__startswith="test-aoi-").count() == 2
    assert ubdcgrid_model.objects.all().count() == 13


@pytest.mark.django_db
def test_grid_intesects_with_aoi():
    from django.contrib.gis.geos import MultiPolygon, Point
    from mercantile import tile

    from ubdc_airbnb.models import AOIShape, UBDCGrid

    p = (10, 10)
    p_geom = Point(p, srid=4326)
    aoi_area = p_geom.buffer(10)
    t = tile(*p, 10)
    aoi_shape = MultiPolygon(aoi_area)
    aoi_shape.srid = 4326
    geom_3857 = aoi_shape.transform(3857, clone=True)

    aoi = AOIShape.objects.create(name="test-aoi", geom_3857=geom_3857)
    grid = UBDCGrid.objects.create_from_tile(t)
    assert grid.intersects_with_aoi


@pytest.mark.django_db
def test_grid_as_geojson(tmp_path):
    import json

    from ubdc_airbnb.models import UBDCGrid

    UBDCGrid.objects.create_from_quadkey("120200230")
    UBDCGrid.objects.create_from_quadkey("120200231")
    UBDCGrid.objects.create_from_quadkey("120200233")
    UBDCGrid.objects.create_from_quadkey("120200232")

    rv = UBDCGrid.as_geojson()

    assert rv
    data = json.loads(rv)
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 4

    f = tmp_path / "test.geojson"
    rv2 = UBDCGrid.save_as_geojson(f)

    assert rv2
    assert rv2 == f.as_posix()

    writen_data = open(rv2, "rt").read()
    assert rv == writen_data


@pytest.mark.django_db
def test_grid_objects_intersect_with_aoi(ubdcgrid_model):
    from ubdc_airbnb.models import AOIShape, UBDCGrid

    aoi_1_geom = MultiPolygon(Polygon.from_bbox((0, 0, 10, 10)), srid=4326).transform(3857, clone=True)
    aoi_2_geom = MultiPolygon(Polygon.from_bbox((5, 5, 15, 15)), srid=4326).transform(3857, clone=True)

    aoi_1 = AOIShape.objects.create(name="aoi-1", geom_3857=aoi_1_geom)
    aoi_2 = AOIShape.objects.create(name="aoi-2", geom_3857=aoi_2_geom)

    aoi_1.create_grid()
    aoi_2.create_grid()

    # rv = UBDCGrid.as_geojson()

    rv = ubdcgrid_model.objects.intersect_with_aoi([aoi_1, aoi_2])
    assert len(list(rv)) == 4


@pytest.mark.django_db
def test_create_aoi_from_geojson(aoishape_model, geojson_gen, tmp_path):
    for idx, gj in enumerate(geojson_gen):
        f = tmp_path / f"test-aoi-{idx}.geojson"
        f.write_text(gj)
        aoishape_model.create_from_geojson(f)

    assert aoishape_model.objects.filter(name__startswith="test-aoi-").count() == 2


@pytest.mark.django_db
def test_get_listing_detail_from_listing_id(mock_airbnb_client):
    from ubdc_airbnb.models import AirBnBResponse, AirBnBResponseTypes

    listing_id = 1234
    response = AirBnBResponse.objects.fetch_response(
        type=AirBnBResponseTypes.listingDetail,
        listing_id=listing_id,
    )

    assert response
    assert response.listing_id == listing_id
    assert response.pk
    assert response.ubdc_task == None
