import logging
import os
from argparse import ArgumentParser
from hashlib import md5
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile

import click
import requests
from django.conf import settings
from django.contrib.gis.gdal.feature import Feature
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from ubdc_airbnb.models import WorldShape

from ...utils.spatial import reproject
from . import _GeoFileHandler

logger = logging.getLogger(__name__)

WORLDSHAPE_URL = os.getenv(
    "MASK_GDAM_SHAPEFILE_URL",
    "https://data.biogeo.ucdavis.edu/data/gadm3.6/gadm36_levels_shp.zip",
)
DEFAULT_SAVE_DIR: Path = os.getenv("MASK_CACHE_FOLDER", settings.BASE_DIR / "worldBoundaries_cache")


def add_feature(geometry, iso3_alpha, name_0):
    geom = reproject(geometry, from_srid=4326, to_srid=3857)
    md5_checksum = md5(geom.wkb).hexdigest()
    obj = WorldShape(
        iso3_alpha=iso3_alpha,
        name_0=name_0,
        md5_checksum=md5_checksum,
        geom_3857=reproject(geometry, to_srid=3857),
    )
    try:
        obj.save()
    except IntegrityError:
        msg = f"Feature from {iso3_alpha} exists. Skipping."
        logger.info(msg)
        print(msg)


def download_worldshape(url, output_path: Path):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total_length = int(r.headers.get("content-length"))

        file_handle: TextIOWrapper
        with output_path.open("wb") as file_handle:
            bar: click.ProgressBar
            with click.progressbar(length=total_length, label="Downloading File") as bar:
                for chunk in r.iter_content(1024):
                    file_handle.write(chunk)
                    bar.update(len(chunk))


class Command(BaseCommand):
    help = "Download and import WorldBoundary Mask from GADM "

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            "--only-download",
            help="Only download the file and exit.",
            action="store_true",
        )
        parser.add_argument("--only-iso", type=str, help="import only this ISO")

    def handle(self, *args, **kwargs):
        only_iso: str = kwargs["only_iso"]
        only_download: bool = kwargs["only_download"]

        save_dir = DEFAULT_SAVE_DIR

        out_file = save_dir / WORLDSHAPE_URL.split("/")[-1]
        # assert save_dir.is_dir()
        if not save_dir.is_dir():
            logger.info(
                logger.info(f"Folder {save_dir.name} at {save_dir.parent.as_posix()} does not exists; creating")
            )
            save_dir.mkdir(exist_ok=True, parents=True)
        else:
            logger.info(f"Folder {save_dir.name} at {save_dir.parent.as_posix()} exists")

        download = True
        if out_file.is_file():
            # check file
            with ZipFile(out_file) as zipfile:
                if zipfile.testzip():
                    logger.info(f"cached file failed check; removing and re-downloading")
                    download = True
                else:
                    logger.info(f"cached file found and passed integrity check")
                    download = False

        if download:
            download_worldshape(WORLDSHAPE_URL, output_path=out_file)

        if not only_download:
            g = _GeoFileHandler("/vsizip/" + out_file.as_posix() + "/gadm36_0.shp")
            bar: click.ProgressBar
            with click.progressbar(g.layer, label="Processing Features") as bar:
                f: Feature
                for f in bar:
                    GID_0 = f["GID_0"].value
                    NAME_0 = f["NAME_0"].value
                    bar.label = f"Processing Features: {GID_0}"
                    # skip Antarctica
                    if GID_0 == "ATA":
                        continue
                    if only_iso:
                        if GID_0 != only_iso.upper():
                            continue

                    parent_geom = f.geom
                    # mix of Multi and Polys
                    if parent_geom.geom_type.name.startswith("Multi"):
                        for idx, c_geom in enumerate(parent_geom):
                            # print("c_child",f.fid,idx)
                            add_feature(c_geom, iso3_alpha=GID_0, name_0=NAME_0)
                    else:
                        # print(f.fid)
                        add_feature(parent_geom, iso3_alpha=GID_0, name_0=NAME_0)
