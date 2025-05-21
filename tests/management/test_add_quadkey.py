import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_create_grid_qk(capsys):
    from ubdc_airbnb.models import UBDCGrid

    qk = "0311332233311"
    call_command("add-quadkey", qk)
    out, err = capsys.readouterr()
    assert UBDCGrid.objects.count() == 1
    grid: UBDCGrid = UBDCGrid.objects.get(quadkey=qk)
    assert grid.tile_z == len(qk)
    assert grid.quadkey == qk

    # try to add the same quadkey again
    call_command("add-quadkey", qk)
    out, err = capsys.readouterr()
    assert UBDCGrid.objects.count() == 1

    # try to add the parent quadkey
    parent_qk = qk[:-1]
    call_command("add-quadkey", parent_qk)
    out, err = capsys.readouterr()
    assert UBDCGrid.objects.count() == 4
