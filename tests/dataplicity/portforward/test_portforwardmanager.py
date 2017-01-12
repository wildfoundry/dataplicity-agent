from dataplicity.portforward import PortForwardManager, Service
import pytest
from weakref import ref


class Client(object):
    def __init__(self, m2m=None):
        self.m2m = m2m


@pytest.fixture()
def client():
    return Client('test-m2m')


def test_manager_m2m_returns_none_without_client():
    """ using the fixture was causing the weakref to not work """
    client = Client('test-m2m')
    manager = PortForwardManager(client=client)
    assert manager.client is not None
    assert manager.m2m == client.m2m
    # ok, now let's delete the client, thus forcing the weakref to not be
    # unfulfilled.
    del client
    assert manager.m2m is None


@pytest.mark.parametrize("service,port", [
    ("web", 80),
    ("ext", 81),
    ("extalt", 8000),
    ("alt", 8080)
])
def test_default_services_are_added_during_init(client, service, port):
    manager = PortForwardManager.init(client)
    assert isinstance(manager, PortForwardManager)
    service_object = manager.get_service(service)
    assert isinstance(service_object, Service)
    assert service_object.name == service
    service_by_port = manager.get_service_on_port(port)
    assert isinstance(service_by_port, Service)
    assert service_by_port == service_object
