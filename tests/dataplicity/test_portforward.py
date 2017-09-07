import pytest
from dataplicity.m2mmanager import M2MManager
from dataplicity.portforward import PortForwardManager
from mock import call, patch

_weakref_table = {}


class FakeClient(object):
    pass


@pytest.fixture
def manager():
    client = FakeClient()
    _weakref_table['client'] = client
    yield PortForwardManager.init(client=client)
    del _weakref_table['client']


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
    manager.client.m2m = M2MManager.init('ws://localhost/')
    with patch('dataplicity.portforward.Connection.start') as connection_start:
        manager.redirect_port(9999, 22)

        assert connection_start.called


def test_calling_redirect_service_from_m2mmanager_works():
    with patch(
        'dataplicity.portforward.PortForwardManager.redirect_port'
    ) as redirect_port:
        client = FakeClient()
        client.port_forward = PortForwardManager(client)
        m2m_manager = M2MManager(client=client, url='ws://localhost/')
        m2m_manager.on_instruction(
            'sender', {
                'action': 'open-portredirect',
                'device_port': 22,
                'm2m_port': 1234
            }
        )
        assert redirect_port.call_args == call(1234, 22)


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
