import pytest
from geoapi.exceptions import MissingServiceAccount
from geoapi.utils.agave import service_account_client


def test_service_account_client():
    service_account = service_account_client("designsafe")
    assert "ABCDEFG12344" in service_account.client.headers['Authorization']

    service_account = service_account_client("DesignSafe")
    assert "ABCDEFG12344" in service_account.client.headers['Authorization']


def test_service_account_client_missing():
    with pytest.raises(MissingServiceAccount):
        service_account_client("non_existing_tenant")
