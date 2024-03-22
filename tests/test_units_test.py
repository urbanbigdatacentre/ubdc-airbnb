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


def test_primary_host():
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


def test_additional_hosts():
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


def test_chain():
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
    pattern2
    pattern2 = r"$..additional_hosts[*]"
    a = airbnb_response_parser.generic(pattern, t1)
    b = airbnb_response_parser.generic(pattern2, t2)

    l = []
    for e in a, b:
        l.extend(e)

    assert len(l)
