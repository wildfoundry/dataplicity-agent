import pytest
from mock import call, patch

from dataplicity import constants, remote_directory
from dataplicity.limiter import Limiter
from dataplicity.m2mmanager import M2MManager
from dataplicity.portforward import PortForwardManager

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

@pytest.fixture
def limiter():
    return Limiter("services", constants.LIMIT_SERVICES)


def test_open_service_which_doesnt_exist_results_in_noop(manager, route, limiter):
    with patch('dataplicity.portforward.Service.connect') as connect:
        assert manager.get_service('new-service') is None
        assert manager.get_service_on_port(1234) is None

        manager.open_service(limiter, 'port-1234', route)
        # this method should not be called because it is an unknown service
        # and therefore the whole action should be turn into a no-op

        assert not connect.called


def test_redirect_service(manager, route, limiter):
    remote_directory = None
    manager.client.m2m = M2MManager.init(manager.client, remote_directory, 'ws://localhost/')
    with patch('dataplicity.portforward.Connection.start') as connection_start:
        manager.redirect_port(limiter, 9999, 22)

        assert connection_start.called


def test_calling_redirect_service_from_m2mmanager_works():
    with patch(
        'dataplicity.portforward.PortForwardManager.redirect_port'
    ) as redirect_port:
        client = FakeClient()
        client.port_forward = PortForwardManager(client)
        m2m_manager = M2MManager(client=client, remote_directory=None, url='ws://localhost/')
        m2m_manager.on_instruction(
            'sender', {
                b'action': b'open-portredirect',
                b'device_port': 22,
                b'm2m_port': 1234
            }
        )
        assert redirect_port.call_args == call(1234, 22)


def test_can_open_service_by_name(manager, limiter):
    with patch('dataplicity.portforward.Service.connect') as connect:
        manager.open(limiter, 1234, service='web')
    assert connect.called


def test_can_open_service_by_port(manager, limiter):
    with patch('dataplicity.portforward.Service.connect') as connect:
        manager.open(limiter, 1234, port=80)
    assert connect.called


def test_that_using_empty_service_and_port_raises(manager, limiter):
    """ unit test for PortForwardManager::open_service """
    with pytest.raises(ValueError):
        route = ('localhost', 22, 'example.com', None)
        manager.open_service(limiter, None, route)
