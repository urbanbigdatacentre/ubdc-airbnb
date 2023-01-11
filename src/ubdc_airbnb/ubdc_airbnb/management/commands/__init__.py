from argparse import ArgumentTypeError
from pathlib import Path
from typing import List, Optional, Union

from django.contrib.gis.gdal.datasource import DataSource
from django.contrib.gis.gdal.layer import Layer
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon

from ubdc_airbnb.models import AOIShape, AirBnBListing


class _GeoFileHandler(object):
    _nFeatures: int = None

    def __init__(self, geo_file: Union[Path, str]):
        self._file_path = Path(geo_file)
        # if not self._file_path.is_file():
        #     raise FileNotFoundError(f'File {self._file_path.as_posix()} could not be opened')
        self._data_source: DataSource = DataSource(geo_file)

        if self.driver_name not in ('ESRI Shapefile', 'GeoJSON'):
            raise ValueError('Only shapefiles or GeoJSON are supported in this time')

        self.layer: Layer = self._data_source[0]
        if self.geometry_type not in ('Polygon', 'MultiPolygon'):
            raise ValueError('Only Polygons or Multipolygons are supported')

    @property
    def nFeatures(self):
        if self._nFeatures is None:
            self._nFeatures = len(self.layer.get_geoms())
        return self._nFeatures

    @property
    def driver_name(self) -> str:
        return self._data_source.driver.name

    @property
    def geometry_type(self) -> str:
        return self.layer.geom_type.name

    @property
    def name(self) -> str:
        return self.layer.name

    @property
    def srid(self) -> Optional[int]:
        """Return the SRID of top-level authority, or None if undefined."""
        return self.layer.srs.srid

    def __str__(self) -> str:
        return f'{self.__class__.__name__}/{self.name}'

    def convert(self, source_srid=None):
        """ Return a MultiPolygon suitable for entrance to AOIShape model. """

        # if the file contains one (multipolygon) polygon -> multipolygon
        # if the file contains multiple features -> merge -> multipolygon

        destination_srid: int = 3857

        geom_list: List[GEOSGeometry] = self.layer.get_geoms()
        if not len(geom_list):
            raise AttributeError('No geometries in this file')

        _source_srid = self.srid or source_srid

        if len(geom_list) == 1:
            try:
                geom = geom_list[0]
                if not geom.srid:
                    geom.srid = _source_srid
                xformed_geom = geom_list[0].transform(destination_srid, clone=True)
                # because:
                # above op returns ..gdal.geometries.Polygon
                # but MultiPolygon accepts ..geos.polygon.Polygon
                #  ...

                # I am using ewkt instead of ewkb because django does not support it as ewkb is only postgis specific
                # wkb exists, but does not retain srid information
                return_geom = GEOSGeometry.from_ewkt(xformed_geom.ewkt)
                if isinstance(return_geom, MultiPolygon):
                    return return_geom
                elif isinstance(return_geom, Polygon):
                    return_geom = MultiPolygon(return_geom)

                else:
                    Exception()
            except Exception as e:
                raise e
        else:
            geom_bag = []
            for gdal_geom in geom_list:
                if gdal_geom.geom_type == 'MultiPolygon':
                    for p in gdal_geom:
                        geom_bag.append(GEOSGeometry(p.ewkt))
                else:
                    geom_bag.append(GEOSGeometry(gdal_geom.ewkt))
            mp = MultiPolygon(geom_bag)
            mp.srid = _source_srid
            return_geom: MultiPolygon = MultiPolygon(mp.unary_union, srid=_source_srid)
            return_geom.transform(destination_srid)

        return return_geom


def int_to_aoi(pk: int) -> AOIShape:
    """ Cast to AOI Object"""
    return AOIShape.objects.get(id=pk)


def int_to_listing(value) -> AirBnBListing:
    """ Cast to AirBnBListing Object"""
    listing = AirBnBListing.objects.get(listing_id=value)

    return listing
