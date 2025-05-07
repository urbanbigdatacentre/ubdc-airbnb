import json
from datetime import timezone

from faker import Faker
from mercantile import LngLatBbox, bounds, quadkey_to_tile

# Funcs here return valid payloads for testing

fake = Faker()
UTC = timezone.utc
static_uuid4 = fake.uuid4(cast_to=str)


def user_body_generator() -> bytes:
    rv = {
        "user": {
            "id": fake.random_int(min=300000, max=1000000),
            "first_name": fake.first_name(),
            "picture_url": fake.image_url(),
            "is_superhost": fake.boolean(),
            "location": fake.country(),
            "listings_count": fake.random_int(min=0, max=100),
            "reviewee_count": fake.random_int(min=0, max=100),
            "verifications": [fake.word() for _ in range(3)],
            "created_at": fake.iso8601(tzinfo=UTC),
            "picture_urls": [fake.image_url() for _ in range(3)],
        }
    }
    return json.dumps(rv).encode()


def search_body_generator(
    qk: str, has_next_page: bool = False, federated_search_session_id: str = static_uuid4, number_of_listings=10
) -> bytes:

    tile = quadkey_to_tile(qk)
    rv = {}
    bbox: LngLatBbox = bounds(tile)
    lng = (bbox.east + bbox.west) / 2
    lat = (bbox.north + bbox.south) / 2

    random_ids = [fake.random_int(min=10000, max=10000000) for _ in range(number_of_listings)]
    explore_tabs = [
        {
            "tab_id": "home_tab",
            "pagination_metadata": {
                "has_next_page": has_next_page,
                "items_offset": 28,
                "previous_page_items_offset": 0,
            },
            "sections": [
                {},
                {},
                {
                    "listings": [
                        {
                            "listing": {
                                "city": fake.city(),
                                "id": id,
                                "id_str": str(id),
                                "lat": float(fake.coordinate(lat, 0.0001)),
                                "lng": float(fake.coordinate(lng, 0.0001)),
                                "user": {
                                    "first_name": fake.first_name(),
                                    "id": fake.random_int(),
                                },
                            }
                        }
                        for id in random_ids
                    ],
                },
            ],
            "home_tab_metadata": {
                "listings_count": number_of_listings,
                "geography": {
                    "ne_lat": bbox.north,
                    "ne_lng": bbox.east,
                    "sw_lat": bbox.south,
                    "sw_lng": bbox.west,
                },
            },
        },
    ]
    metadata = {
        "federated_search_session_id": federated_search_session_id,
        "geography": {
            "ne_lat": bbox.north,
            "ne_lng": bbox.east,
            "sw_lat": bbox.south,
            "sw_lng": bbox.west,
        },
    }
    layout = {}
    filters = {}
    page_title = {}
    search_header = {}
    search_footer = {}

    rv.update(
        explore_tabs=explore_tabs,
        metadata=metadata,
        layout=layout,
        filters=filters,
        page_title=page_title,
        search_header=search_header,
        search_footer=search_footer,
    )

    return json.dumps(rv).encode()


def review_body_generator() -> bytes:
    review_id = fake.random_int(min=300000, max=1000000)
    author_id = fake.random_int(min=300000, max=1000000)
    recipient_id = fake.random_int(min=300000, max=1000000)
    json_data = {
        "reviews": [
            {
                "id": review_id,
                "role": "guest",
                "author": {
                    "id": author_id,
                    "first_name": fake.first_name(),
                    "picture_url": fake.image_url(),
                },
                "id_str": str(review_id),
                "comments": fake.text(),
                "author_id": author_id,
                "recipient_id": recipient_id,
                "recipient": {
                    "id": recipient_id,
                    "first_name": fake.first_name(),
                    "picture_url": fake.image_url(),
                },
                "created_at": fake.iso8601(tzinfo=UTC),
            }
        ],
        "metadata": {
            "reviews_count": 350,
            "should_show_review_translations": False,
        },
    }

    return json.dumps(json_data).encode()


def listing_details_generator() -> bytes:
    metadata = {}
    pdp_listing_detail = {
        "id": fake.random_int(min=300000, max=1000000),
        "lat": float(fake.coordinate()),
        "lng": float(fake.coordinate()),
        "city": fake.city(),
        "state": fake.state(),
        "is_str": str(fake.pyint()),
        "photos": [
            {
                "id": fake.random_int(min=300000, max=1000000),
            }
            for _ in range(3)
        ],
        "country": fake.country(),
        "is_hotel": fake.boolean(),
    }
    json_data = {
        "metadata": metadata,
        "pdp_listing_detail": pdp_listing_detail,
    }

    return json.dumps(json_data).encode()


def calendar_generator() -> bytes:
    metadata = {}
    calendar_months = [
        {
            "listing_id": fake.random_int(min=300000, max=1000000),
            "condition_ranges": [],
            "dynamic_pricing_updated_at": fake.iso8601(tzinfo=UTC),
            "days": [
                {
                    "date": fake.date(),
                    "price": {"date": fake.date(), "type": "default"},
                    "available": fake.boolean(),
                    "max_nights": fake.random_int(min=1, max=1125),
                    "min_nights": fake.random_int(min=1, max=1125),
                }
                for _ in range(31)
            ],
        }
        for x in range(12)
    ]

    json_data = {
        "metadata": metadata,
        "calendar_months": calendar_months,
    }
    return json.dumps(json_data).encode()
