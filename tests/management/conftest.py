import pytest
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.utils import timezone

from ubdc_airbnb.models import AOIShape, UBDCGrid


@pytest.fixture
def test_geometry():
    """Create a test geometry for AOIs."""
    return GEOSGeometry("SRID=3857;MULTIPOLYGON(((30 20, 45 40, 10 40, 30 20)))")


@pytest.fixture
def test_aoi(db, test_geometry):
    """Create a basic test AOI."""
    aoi = AOIShape.objects.create(
        name="Test AOI",
        geom_3857=test_geometry,
        collect_calendars=False,
        collect_listing_details=False,
        notes={
            "user": "testuser",
            "path": "/test/path",
            "name": "test.geojson",
            "import_date": timezone.now().isoformat(),
        },
    )
    return aoi


@pytest.fixture
def test_aois(db, test_geometry):
    """Create multiple test AOIs."""
    aois = []
    for i in range(3):
        # Shift geometry for each AOI to make them unique
        polys = []
        for poly in test_geometry:
            p = Polygon([[x + i + 1, y + i + 1] for x, y in poly[0]])
            polys.append(p)

        shifted_geom = MultiPolygon(polys)

        aoi = AOIShape.objects.create(
            name=f"Test Area {i+1}",
            geom_3857=shifted_geom,
            collect_calendars=bool(i % 2),
            collect_listing_details=bool(i % 2),
            notes={
                "user": f"testuser{i+1}",
                "path": f"/test/path{i+1}",
                "name": f"test{i+1}.geojson",
                "import_date": timezone.now().isoformat(),
            },
        )
        aois.append(aoi)
    return aois


@pytest.fixture
def test_grid(db):
    """Create a test grid."""
    return UBDCGrid.objects.create_from_quadkey(quadkey="120210233")
