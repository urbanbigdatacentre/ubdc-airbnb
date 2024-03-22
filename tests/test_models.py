# model related testes
import pytest


@pytest.mark.django_db(transaction=True)
def test_get_or_create_user():
    from ubdc_airbnb.model_defaults import AIRBNBUSER_FIRST_NAME
    from ubdc_airbnb.models import AirBnBUser

    user_id = "1234"
    user, created = AirBnBUser.objects.get_or_create(user_id=user_id)

    assert user.user_id == user_id
    assert user.first_name == AIRBNBUSER_FIRST_NAME
