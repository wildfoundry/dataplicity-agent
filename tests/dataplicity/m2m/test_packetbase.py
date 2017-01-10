import pytest
from dataplicity.m2m.packetbase import (PacketFormatError,
                                        UnknownPacketError)
from dataplicity.m2m.packets import CommandSendInstructionPacket, M2MPacket
from dataplicity.m2m.packets import PingPacket


@pytest.fixture
def cmd():
    return CommandSendInstructionPacket(
        command_id=CommandSendInstructionPacket.type.value,
        node=b'\x01\x02',
        data={
            b'foo': b'bar',
            b'baz': [
                b'1', 2, {b'3': 4}
            ]
        }
    )


def test_from_bytes(cmd):
    """ unit test for from_bytes factory
    """
    # let's prepare some packet. SendInstructionPacket seems to be simple
    # enough for the tests, but not overly simple to omit any branch of the
    # code.

    cmd_binary = cmd.encode_binary()
    assert cmd.as_bytes == cmd_binary

    decoded = CommandSendInstructionPacket.from_bytes(cmd_binary)
    assert decoded.kwargs == cmd.kwargs
    # ideally, we would compare the repr's, however the keys from dict dont
    # have order. However, regardless of this, the lengths should be the same.
    assert repr(decoded) is not None
    assert len(repr(decoded)) == len(repr(cmd))
    assert decoded.attributes == cmd.attributes


def test_invalid_binary_raises_decoding_error(cmd):
    """
    """
    _bin = cmd.as_bytes[:-1]
    with pytest.raises(PacketFormatError):
        CommandSendInstructionPacket.from_bytes(_bin)


def test_nonlist_data_raises_formaterror():
    """
    """
    _bin = b'i1e'  # bencode for 1 (int)
    with pytest.raises(PacketFormatError):
        CommandSendInstructionPacket.from_bytes(_bin)


def test_nonint_packet_type_raises_formaterror():
    """
    """
    _bin = b'l1:ae'
    with pytest.raises(PacketFormatError):
        CommandSendInstructionPacket.from_bytes(_bin)


def test_unknown_packet_type_raises_unknown_packeterror():
    """
    """
    _bin = b'li-1ee'
    with pytest.raises(UnknownPacketError):
        M2MPacket.from_bytes(_bin)


def test_create_packet_dynamically(cmd):
    """ The M2MPacket base class has the registry of all available packets.
        We can utilize the .create factory to obtain dynamic packet by passing
        necesary arguments.
    """
    dynamic_cmd = M2MPacket.create(
        packet_type=cmd.type.value,
        node=b'a-node',
        command_id=cmd.command_id,
        data=cmd.data
    )

    assert isinstance(dynamic_cmd, CommandSendInstructionPacket)

    # we can also check that specifying an unknown packet type yields an error.
    with pytest.raises(ValueError):
        M2MPacket.create(
            packet_type=-1
        )


def test_validation_of_init_params_works():
    """ We can assert whether the base class checks for required attributes.
    """
    # PingPacket has one attribute, therefore calling the factory without
    # any parameters will yield an error
    with pytest.raises(PacketFormatError) as e:
        M2MPacket.create(packet_type=PingPacket.type)

    assert str(e.value).startswith("missing attribute")

    # similary, specifying invalid type will also throw an exception.
    # the PingPacket has only one attribute of type bytes
    with pytest.raises(PacketFormatError) as e:
        M2MPacket.create(packet_type=PingPacket.type, data=["foo"])
    assert str(e.value).startswith("parameter")


def test_get_method_args(cmd):
    """ this method tests the functionality of splitting constructor parameters
        into args and kwargs
    """
    args, kwargs = cmd.get_method_args(3)

    assert len(args) + len(kwargs.keys()) == len(cmd.attributes)
