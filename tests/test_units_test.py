import json

from ubdc_airbnb.utils.json_parsers import airbnb_response_parser


def test_price_histogram_sum():
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


def test_chain_host_parsers():
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


import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon


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
