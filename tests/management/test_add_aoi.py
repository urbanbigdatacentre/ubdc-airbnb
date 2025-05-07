from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import TestCase

# Test for the add_aoi command


@pytest.mark.skip(reason="Not implemented")
class AddAOITest(TestCase):
    output = StringIO()
    result = call_command("add-aoi", stdout=output)

    # do some assertions here
