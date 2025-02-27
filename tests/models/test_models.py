# model related tests
from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon
from faker import Faker

from ubdc_airbnb.models import AirBnBResponseTypes

faker = Faker()

if TYPE_CHECKING:
    from ubdc_airbnb.models import AOIShape


@pytest.mark.django_db
def test_aoishape_model_create_from_geom(aoishape_model):
    name = "test-aoi"
    geom = MultiPolygon(Polygon.from_bbox((0, 0, 10, 10)), srid=4326)
    aoi = aoishape_model.create_from_geometry(geom, name=name)
    assert aoi.geom_3857
    assert aoi.geom_3857.srid == 3857
    assert aoi.geom_3857 == geom.transform(3857, clone=True)
    assert aoi.name == name


@pytest.mark.django_db(transaction=True)
def test_user_model_get_or_create_user(user_model):
    from ubdc_airbnb.model_defaults import AIRBNBUSER_FIRST_NAME

    user_id = "1234"
    user, created = user_model.objects.get_or_create(user_id=user_id)

    assert user.user_id == user_id
    assert user.first_name == AIRBNBUSER_FIRST_NAME
    # assert user.needs_update is True


@pytest.mark.skip(reason="Not Implemented/Broken")
@pytest.mark.django_db(transaction=True)
def test_aoishape_model_create_grid(aoishape_model, ubdcgrid_model, geojson_gen, tmp_path):
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
def test_ubdcgrid_model_intesects_with_aoi(ubdcgrid_model, aoishape_model):
    from django.contrib.gis.geos import MultiPolygon, Point
    from mercantile import tile

    p = (10, 10)
    p_geom = Point(p, srid=4326)
    aoi_area = p_geom.buffer(10)
    t = tile(*p, 10)
    aoi_shape = MultiPolygon(aoi_area)
    aoi_shape.srid = 4326
    geom_3857 = aoi_shape.transform(3857, clone=True)

    aoi = aoishape_model.objects.create(name="test-aoi", geom_3857=geom_3857)
    grid = ubdcgrid_model.objects.create_from_tile(t)
    assert grid.intersects_with_aoi


@pytest.mark.django_db
def test_ubdcgrid_model_as_geojson(tmp_path, ubdcgrid_model):
    import json

    ubdcgrid_model.objects.create_from_quadkey("120200230")
    ubdcgrid_model.objects.create_from_quadkey("120200231")
    ubdcgrid_model.objects.create_from_quadkey("120200233")
    ubdcgrid_model.objects.create_from_quadkey("120200232")

    rv = ubdcgrid_model.as_geojson()

    assert rv
    data = json.loads(rv)
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 4

    f = tmp_path / "test.geojson"
    rv2 = ubdcgrid_model.save_as_geojson(f)

    assert rv2
    assert rv2 == f.as_posix()

    writen_data = open(rv2, "rt").read()
    assert rv == writen_data


@pytest.mark.django_db
def test_grid_objects_intersect_with_aoi(ubdcgrid_model, aoishape_model):

    aoi_1_geom = MultiPolygon(Polygon.from_bbox((0, 0, 10, 10)), srid=4326).transform(3857, clone=True)
    aoi_2_geom = MultiPolygon(Polygon.from_bbox((5, 5, 15, 15)), srid=4326).transform(3857, clone=True)

    aoi_1 = aoishape_model.objects.create(name="aoi-1", geom_3857=aoi_1_geom)
    aoi_2 = aoishape_model.objects.create(name="aoi-2", geom_3857=aoi_2_geom)

    aoi_1.create_grid()
    aoi_2.create_grid()

    # rv = UBDCGrid.as_geojson()

    rv = ubdcgrid_model.objects.intersect_with_aoi([aoi_1, aoi_2])
    assert len(list(rv)) == 4


@pytest.mark.skip(reason="Not Implemented/Broken")
@pytest.mark.django_db
def test_aoishape_create_from_geojson(aoishape_model, geojson_gen, tmp_path):
    for idx, gj in enumerate(geojson_gen):
        f = tmp_path / f"test-aoi-{idx}.geojson"
        f.write_text(gj)
        aoishape_model.create_from_geojson(f)

    assert aoishape_model.objects.filter(name__startswith="test-aoi-").count() == 2


def listing_detail_content_gen() -> bytes:
    import json

    def gen_fake_user():
        return {
            "id": faker.random_int(min=300000, max=1000000),
            "first_name": faker.first_name(),
            "picture_url": faker.image_url(),
            "is_superhost": faker.boolean(),
        }

    json_data = {
        "pdp_listing_detail": {
            "primary_host": gen_fake_user(),
            "additional_hosts": [gen_fake_user() for _ in range(3)],
            "illegal_strings": {"null-char": "\u0000"},
        }
    }
    return json.dumps(json_data).encode("utf-8", errors="ignore")


@pytest.mark.parametrize(
    "asset_id,response_type",
    [
        (1234, AirBnBResponseTypes.listingDetail),
        (1234, AirBnBResponseTypes.calendar),
        (None, AirBnBResponseTypes.search),
        (1234, AirBnBResponseTypes.userDetail),
        (None, AirBnBResponseTypes.userDetail),
    ],
)
@pytest.mark.parametrize(
    "status_code, responses",
    [
        (
            503,
            [
                {"content": b"Proxy-Error"},
                {"content": b"Proxy-Error"},
            ],
        ),
        (
            503,
            [
                {"content": b""},
            ],
        ),
        (
            503,
            [
                {"content": None},
            ],
        ),
    ],
)
@pytest.mark.django_db(reset_sequences=True)
def test_AirBnBResponse_fetch_x_raises(
    asset_id,
    responses,
    status_code,
    response_type,
    mock_airbnb_client,
    response_queue,
    responses_model
):

    from requests.exceptions import HTTPError
    from ubdc_airbnb.errors import UBDCRetriableError

    expected_exceptions = (HTTPError, UBDCRetriableError)

    for r in responses:
        r.update(status_code=status_code)
        response_queue.put(r)

    for idx, r in responses:
        with pytest.raises(expected_exceptions):
            responses_model.objects.fetch_response(
                type=response_type,
                asset_id=asset_id,
            )
    db_rs = responses_model.objects.all()
    assert len(db_rs) == len(responses)
    for idx, db_r in enumerate(db_rs):
        if response_type == AirBnBResponseTypes.userDetail:
            assert db_r.listing_id is None
        else:
            assert db_r.listing_id == asset_id
        assert db_r.pk == idx + 1
        assert db_r.ubdc_task == None
        assert db_r.status_code == status_code
        assert db_r._type == response_type
        assert isinstance(db_r.payload, dict)


@pytest.mark.parametrize(
    "asset_id,response_type",
    [
        (1234, AirBnBResponseTypes.listingDetail),
        (1234, AirBnBResponseTypes.calendar),
        (None, AirBnBResponseTypes.search),
        (1234, AirBnBResponseTypes.userDetail),
        (None, AirBnBResponseTypes.userDetail),
    ],
)
@pytest.mark.parametrize(
    "status_code,responses",
    [
        (
            200,
            [
                {"content": b'{ "pdp_listing_detail": { "id": 1234 } }'},
            ]),
        (
            403,
            [
                {"content": b"Forbidden"},
            ],
        ),
    ],
)
@pytest.mark.django_db(reset_sequences=True)
def test_AirBnBResponse_fetch_x(
    asset_id, responses, status_code, response_type, mock_airbnb_client, response_queue, responses_model
):

    for r in responses:
        r.update(status_code=status_code)
        response_queue.put(r)

    db_r = responses_model.objects.fetch_response(
        type=response_type,
        asset_id=asset_id,
    )
    db_rs = responses_model.objects.all()
    assert len(db_rs) == len(responses)
    if response_type == AirBnBResponseTypes.userDetail:
        assert db_r.listing_id is None
    else:
        assert db_r.listing_id == asset_id
    assert db_r.pk == 1
    assert db_r.ubdc_task == None
    assert db_r.status_code == status_code
    assert db_r._type == response_type
    assert isinstance(db_r.payload, dict)
