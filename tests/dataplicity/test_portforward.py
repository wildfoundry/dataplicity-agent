import pytest
from mock import patch
from dataplicity.portforward import PortForwardManager


class FakeClient(object):
    pass


@pytest.fixture
def manager():
    client = FakeClient()
    return PortForwardManager.init(client=client)


@pytest.fixture
def route():
    return ('node1', 8888, 'node2', 8888)


def test_open_service_which_doesnt_exist_results_in_noop(manager, route):
    with patch('dataplicity.portforward.Service.connect') as connect:
        assert manager.get_service('new-service') is None
        assert manager.get_service_on_port(1234) is None

        manager.open_service('port-1234', route)
        # this method should not be called because it is an unknown service
        # and therefore the whole action should be turn into a no-op

        assert not connect.called


def test_redirect_service(manager, route):
    with patch('dataplicity.portforward.Service.connect') as connect:
        manager.redirect_service(9999, 22)

        assert connect.called


def test_can_open_service_by_name(manager):
    with patch('dataplicity.portforward.Service.connect') as connect:
        manager.open(1234, service='web')
    assert connect.called


def test_can_open_service_by_port(manager):
    with patch('dataplicity.portforward.Service.connect') as connect:
        manager.open(1234, port=80)
    assert connect.called


def test_that_using_empty_service_and_port_raises(manager):
    """ unit test for PortForwardManager::open_service """
    with pytest.raises(ValueError):
        route = ('localhost', 22, 'example.com', None)
        manager.open_service(None, route)
