import json

import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon
from mercantile import LngLatBbox

from ubdc_airbnb.utils.json_parsers import airbnb_response_parser

EXPECTED_BBOX = LngLatBbox(west=0, east=0, north=0, south=0)
GEOGRAPHY_PAYLOAD = {"geography": {"sw_lng": 0, "ne_lng": 0, "ne_lat": 0, "sw_lat": 0}}


@pytest.mark.parametrize(
    "payload,expected",
    [
        (
            {
                "metadata": {"page_metadata": GEOGRAPHY_PAYLOAD},
                "explore_tabs": [{"home_tab_metadata": {"search": GEOGRAPHY_PAYLOAD}}],
            },
            EXPECTED_BBOX,
        ),
        ({"explore_tabs": [{"home_tab_metadata": GEOGRAPHY_PAYLOAD}],
         "metadata": GEOGRAPHY_PAYLOAD}, EXPECTED_BBOX),
    ],
)
def test_parser_get_lnglat_bbox(payload, expected):
    rv = airbnb_response_parser.get_lnglat_bbox(payload)
    assert rv == expected


def test_price_histogram_sum():
    """Test the price histogram sum calculation functionality.
    """
    t = json.loads(
        """
    {
    "data":
    {
        "listings_count": 59,
        "price_histogram":
        {
            "histogram":
            [
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0
            ],
            "average_price": 64
        }
    }
}"""
    )
    rv = airbnb_response_parser.price_histogram_sum(t)
    expected = 0
    assert rv == expected


def test_parser_get_primary_host():
    """Test the primary host parsing functionality.
    """
    t = json.loads(
        r"""
        {
         "pdp_listing_detail":
            {
                "primary_host":
                {
                 "id": 123456,
                 "is_superhost": true
                }
            }
        }
        """
    )
    pattern = r"$..primary_host"
    rv = list(airbnb_response_parser.generic(pattern, t))
    expected = [{"id": 123456, "is_superhost": True}]
    assert rv == expected


def test_parser_get_additional_hosts():
    """Test the additional hosts parsing functionality.
    """
    t = json.loads(
        """
        {"pdp_listing_detail":
            {
                "additional_hosts":[
                {
                 "id": 123456,
                 "is_superhost": true
                },
                {
                 "id": 123457,
                 "is_superhost": true
                }
                ]
            }
        }
        """
    )
    pattern = r"$..additional_hosts[*]"
    rv = list(airbnb_response_parser.generic(pattern, t))
    expected = [{"id": 123456, "is_superhost": True}, {"id": 123457, "is_superhost": True}]
    assert rv == expected
    for e in expected:
        e.get("id")


@pytest.mark.parametrize(
    "payload,expected_result",
    [
        ({"explore_tabs": [{"pagination_metadata": {"has_next_page": True}}]}, True),
        ({"explore_tabs": [{"pagination_metadata": {"has_next_page": False}}]}, False),
    ],
)
def test_parser_has_next_page(payload, expected_result):
    parser = airbnb_response_parser.has_next_page
    rv = parser(payload)

    assert rv == expected_result


@pytest.mark.parametrize(
    "payload,expected_result", [({}, False), ({"explore_tabs": [{"pagination_metadata": {}}]}, False)]
)
def test_parser_has_next_page_error(payload, expected_result):
    parser = airbnb_response_parser.has_next_page
    with pytest.raises(Exception):
        rv = parser(payload)


def test_chain_host_parsers():
    """Test the chaining of host parser functions. """
    t1 = json.loads(
        r"""
        {
         "pdp_listing_detail":
            {
                "primary_host":
                {
                 "id": 123456,
                 "is_superhost": true
                }
            }
        }
        """
    )
    t2 = json.loads(
        """
        {"pdp_listing_detail":
            {
                "additional_hosts":[
                {
                 "id": 123456,
                 "is_superhost": true
                },
                {
                 "id": 123457,
                 "is_superhost": true
                }
                ]
            }
        }
        """
    )
    pattern = r"$..primary_host"
    pattern2 = r"$..additional_hosts[*]"
    a = airbnb_response_parser.generic(pattern, t1)
    b = airbnb_response_parser.generic(pattern2, t2)

    l = []
    for e in a, b:
        l.extend(e)

    assert len(l)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "geom,expected",
    [
        # coords are ll, ur
        (Polygon.from_bbox((-10, -10, 10, 10)), 4),
        (Polygon.from_bbox((-10, 10, 10, 20)), 2),
        (
            MultiPolygon(
                Polygon.from_bbox((-10, 5, -5, 10)),
                Polygon.from_bbox((5, 5, 15, -5)),
            ),
            3,
        ),
        (
            MultiPolygon(
                Polygon.from_bbox((-10, 10, 10, 20)),
                Polygon.from_bbox((5, 5, 15, -5)),
            ),
            4,
        ),
        (MultiPolygon(Polygon.from_bbox((1, 1, 10, 10))), 1),
    ],
)
def test_cut_polygon_at_prime_lines(geom, expected):
    from ubdc_airbnb.utils.spatial import cut_polygon_at_prime_lines

    geom.srid = 4326
    geometries = cut_polygon_at_prime_lines(geom)
    assert len(geometries) == expected
    for g in geometries:
        assert g.srid == 4326
        assert g.geom_type in ["Polygon", "MultiPolygon"]
        assert g.valid, f"Invalid geometry: {g.ewkt}"
        assert g.area > 0, f"Empty geometry: {g.ewkt}"
        assert g.intersects(geom), f"Geometry does not intersect original: {g.ewkt}"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "qk",
    ["031133223331", "0311332233311"],
)
def test_qk_has_children(qk):
    """Test the quadkey children existence check.
    """
    initial_grid = "0311332233311"
    from ubdc_airbnb.models import UBDCGrid
    from ubdc_airbnb.utils.grids import qk_has_children

    UBDCGrid.objects.create_from_quadkey(initial_grid)
    assert qk_has_children(qk)


@pytest.mark.django_db
def test_qk_has_parent():
    """Test the quadkey parent existence check. """
    initial_grid = "0311332233311"
    from ubdc_airbnb.models import UBDCGrid
    from ubdc_airbnb.utils.grids import qk_has_parent

    UBDCGrid.objects.create_from_quadkey(initial_grid)
    qk = "03113322333110101"
    assert qk_has_parent(qk)


@pytest.mark.django_db
def test_replace_grid_with_children():
    """Test the grid replacement with children functionality."""
    from ubdc_airbnb.models import UBDCGrid
    from ubdc_airbnb.utils.grids import replace_quadkey_with_children

    initial_grid = "0311332233311"
    grid = UBDCGrid.objects.create_from_quadkey(initial_grid)
    rv = replace_quadkey_with_children(initial_grid)
    assert len(rv) == 4
    for qk in rv:
        assert len(qk) > 12
        assert qk.startswith("0311332233311")

    assert UBDCGrid.objects.filter(quadkey=initial_grid).exists() is False
