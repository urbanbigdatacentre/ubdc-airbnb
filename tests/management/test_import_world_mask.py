from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class ImportWorldMaskTest(TestCase):
    def test_import_world_mask(self):
        out = StringIO()
        call_command("import_world_mask", stdout=out)
        self.assertGreaterEqual(WorldShape.objects.all().count(), 116311)

    def test_import_world_mask_only(self):
        out = StringIO()
        call_command("import_world_mask", only_iso="NPL", stdout=out)
        self.assertGreaterEqual(WorldShape.objects.all().count(), 1)
