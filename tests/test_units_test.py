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
