import pytest


@pytest.mark.parametrize(
    argnames='status_code,expected',
    argvalues=[
        [200, True],
        [404, False],
        [503, False],
    ]
)
def test_airbnbresponse_model_was_successful(responses_model, status_code, expected):
    "it's successful if the status code is 200"

    response = responses_model(status_code=status_code)
    assert response.was_successful == expected


@pytest.mark.parametrize(
    argnames='status_code,expected',
    argvalues=[
        [200, True],
        [404, False],
        [503, False],
    ]
)
def test_airbnbresponse_model_is_user_valid(
        responses_model,
        status_code,
        expected):
    "it's a valid user if the status code is 200"

    response = responses_model(status_code=status_code, _type='USR')
    assert response.is_user_valid == expected
