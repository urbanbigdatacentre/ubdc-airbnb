import pytest

from ubdc_airbnb.utils.grids import bbox_from_quadkey

## Test Functions here, not tasks.
## Use https://labs.mapbox.com/what-the-tile/ to get quadkeys

# The object of these functions is to determine if that grid has listings or not,
# and if it has if they're served in one page or not.

gla_quadkey = "0311332233311"  # glasgow city centre
desert_quadkey = "3103113332302"  # somewhere in the australia desert
near_city = "031133232200301030"  # middle of a field near city


@pytest.mark.parametrize(
    "quadkey,expected",
    (
        [gla_quadkey, True],  # an area with listings
        [desert_quadkey, False],  # an area with no listings
        [near_city, False],  # an area with no listings, but near a city with listings
    ),
)
@pytest.mark.django_db(transaction=True)
def test_search_listings_at_grid(
    mock_airbnb_client,
    listings_model,
    responses_model,
    ubdcgrid_model,
    quadkey,
    expected,
):
    from ubdc_airbnb.workunits import bbox_has_next_page

    grid = ubdcgrid_model.objects.create_from_quadkey(quadkey=quadkey, save=True)

    assert ubdcgrid_model.objects.count() == 1
    bbox = bbox_from_quadkey(grid.quadkey)
    north = bbox.north
    south = bbox.south
    east = bbox.east
    west = bbox.west
    has_next_page = bbox_has_next_page(east=east, north=north, south=south, west=west)
    assert has_next_page == expected
    assert responses_model.objects.count() == 1
