"""Manage packet types / encoding."""

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

from enum import IntEnum, unique
from .packetbase import PacketBase
from ..compat import text_type, int_types


@unique
class PacketType(IntEnum):
    """The top level packet type."""

    # Null packet, does nothing
    null = 0

    # Client sends this to join the server
    request_join = 1

    # Client sends this to re-connect
    request_identify = 2

    # Sent by the server if request_join or request_identity was successful
    welcome = 3

    # Textual information for developer
    log = 4

    # Send a packet to another node
    request_send = 5

    # Incoming data from the server
    route = 6

    # Send the packet back
    ping = 7

    # A ping return
    pong = 8

    # Set the clients identity
    set_identity = 9

    # Open a channel
    request_open = 10

    # Close a channel
    request_close = 11

    # Close all channels
    request_close_all = 12

    # Keep alive packet
    keep_alive = 13

    # Sent by the server to notify a client that a channel has been opened
    notify_open = 14

    # Request login for privileged accounts
    request_login = 15

    instruction = 16

    notify_login_success = 17

    notify_login_fail = 18

    # Notify the client that a channel has closed
    notify_close = 19

    # Client wishes to disconnect
    request_leave = 20

    # An out of band route control packet
    route_control = 21

    # Send a route_control packet
    request_send_control = 22

    response = 100

    command_add_route = 101

    command_send_instruction = 102

    command_log = 103

    command_broadcast_log = 104

    #command_forward = 105

    command_set_name = 106

    command_check_nodes = 107

    command_get_identities = 108

    command_set_auth = 109

    # Associate meta info with a node
    command_set_meta = 110

    # Get Meta info
    command_get_meta = 111

    peer_add_route = 200

    peer_forward = 201

    peer_notify_disconnect = 202

    # Tell peers about a named connection
    peer_notify_name = 203

    peer_close_port = 204


class M2MPacket(PacketBase):
    """Base class, not a real packet."""

    type = -1

    registry = {}

    @classmethod
    def process_packet_type(cls, packet_type):
        """Enable the use of strings to identify packets."""
        if isinstance(packet_type, (bytes, text_type)):
            packet_type = PacketType[packet_type].value
        return int(packet_type)


# ------------------------------------------------------------
# Packet classes
# ------------------------------------------------------------


class NullPacket(M2MPacket):
    """Probably never sent, this may be used as a sentinel at some point."""

    type = PacketType.null


class RequestJoinPacket(M2MPacket):
    """Client requests joining the server."""

    type = PacketType.request_join


class RequestIdentifyPacket(M2MPacket):
    """Client requests joining the server with a particular identity."""

    type = PacketType.request_identify
    attributes = [('uuid', bytes)]


class WelcomePacket(M2MPacket):
    """Send to the client when an identity has been recorded."""

    type = PacketType.welcome


class LogPacket(M2MPacket):
    """Log information, client may ignore."""

    type = PacketType.log
    attributes = [('text', bytes)]


class RequestSendPacket(M2MPacket):
    """Request to send data to a connection."""

    type = PacketType.request_send
    attributes = [('channel', int_types),
                  ('data', bytes)]


class KeepAlivePacket(M2MPacket):
    """Keep alive packet."""

    type = PacketType.keep_alive


class RoutePacket(M2MPacket):
    """Route data."""

    type = PacketType.route
    attributes = [('channel', int_types),
                  ('data', bytes)]


class RouteControlPacket(M2MPacket):
    """Route data."""

    type = PacketType.route_control
    attributes = [('channel', int_types),
                  ('data', bytes)]


class RequestSendControlPacket(M2MPacket):
    """Request to send data to a connection."""

    type = PacketType.request_send_control
    attributes = [('channel', int_types),
                  ('data', bytes)]


class PingPacket(M2MPacket):
    """Ping packet to check connection."""

    type = PacketType.ping
    attributes = [('data', bytes)]


class PongPacket(M2MPacket):
    """Response to Ping packet."""

    type = PacketType.pong
    attributes = [('data', bytes)]


class SetIdentityPacket(M2MPacket):
    """
    Sets a client's identity.

    This was for debugging, clients are sent an identity normally.

    """

    type = PacketType.set_identity
    attributes = [('uuid', bytes)]


class NotifyOpenPacket(M2MPacket):
    """Let the client know a channel was opened."""

    type = PacketType.notify_open
    attributes = [('channel', int_types)]


class RequestLoginPacket(M2MPacket):
    """Login for extra privileges."""

    type = PacketType.request_login
    attributes = [('username', bytes),
                  ('password', bytes)]


class NotifyLoginSuccessPacket(M2MPacket):
    """Login success."""

    type = PacketType.notify_login_success
    attributes = [('user', bytes)]


class NotifyLoginFailPacket(M2MPacket):
    """Login failed."""

    type = PacketType.notify_login_fail
    attributes = [('message', bytes)]


class NotifyClosePacket(M2MPacket):
    """channel was closed."""

    type = PacketType.notify_close
    attributes = [('port', int)]


class RequestClosePacket(M2MPacket):
    """Ask server to close a port."""

    type = PacketType.request_close
    attributes = [('port', int)]


class RequestLeavePacket(M2MPacket):
    """Polite way of disconnecting from the server."""

    type = PacketType.request_leave


class InstructionPacket(M2MPacket):
    """Send an 'instruction' which is an application define packet not send through a channel."""

    type = PacketType.instruction
    attributes = [('sender', bytes),
                  ('data', dict)]


class CommandResponsePacket(M2MPacket):
    """Sent in response to a command."""

    type = PacketType.response
    attributes = [('command_id', int_types),
                  ('result', dict)]


class CommandAddRoutePacket(M2MPacket):
    """Command the server to generate a route from uuid1 to uuid2."""

    type = PacketType.command_add_route
    attributes = [('command_id', int_types),
                  ('node1', bytes),
                  ('port1', int_types),
                  ('node2', bytes),
                  ('port2', int_types),
                  ('requester', bytes),
                  ('forwarded', int_types)]


class CommandSendInstructionPacket(M2MPacket):
    """Send an instruction to a client."""

    type = PacketType.command_send_instruction
    attributes = [('command_id', int_types),
                  ('node', bytes),
                  ('data', dict)]


class CommandLogPacket(M2MPacket):
    """Send a message to be written to the logs."""

    type = PacketType.command_log
    attributes = [('command_id', int_types),
                  ('node', bytes),
                  ('text', bytes)]


class CommandBroadcastLogPacket(M2MPacket):
    """Send a message to all clients."""

    # Probably just for debug. Not sure what would happen with 1000s of clients
    type = PacketType.command_broadcast_log
    attributes = [('command_id', int_types),
                  ('text', bytes)]


class CommandSetName(M2MPacket):
    """Set an alternative name of a node."""

    type = PacketType.command_set_name
    attributes = [('command_id', int_types),
                  ('node', bytes),
                  ('name', bytes)]


class CommandCheckNodes(M2MPacket):
    """Get identities from a list of names."""

    type = PacketType.command_check_nodes
    attributes = [('command_id', int_types),
                  ('nodes', list)]


class CommandGetIdentities(M2MPacket):
    """Get identities from a list of names."""

    type = PacketType.command_get_identities
    attributes = [('command_id', int_types),
                  ('nodes', list)]


class CommandSetAuth(M2MPacket):
    """Set auth information."""

    type = PacketType.command_set_auth
    attributes = [('command_id', int_types),
                  ('expire', int_types),
                  ('value', bytes)]


class CommandSetMeta(M2MPacket):
    """Set a meta key/value associated with a node."""

    type = PacketType.command_set_meta
    attributes = [('command_id', int_types),
                  ('requester', bytes),
                  ('node', bytes),
                  ('key', bytes),
                  ('value', bytes)]


class CommandGetMeta(M2MPacket):
    """Get a dictionary of meta values associated with a node."""

    type = PacketType.command_get_meta
    attributes = [('command_id', int_types),
                  ('requester', bytes),
                  ('node', bytes)]


class PeerAddRoutePacket(M2MPacket):
    """Tell the peer cluster about a route."""

    type = PacketType.peer_add_route
    attributes = [('command_id', int),
                  ('requester', bytes),
                  ('node1', bytes),
                  ('port1', int_types),
                  ('node2', bytes),
                  ('port2', int_types)]


class PeerForwardPacket(M2MPacket):
    """Forward a packet to another node."""

    type = PacketType.peer_forward
    attributes = [('recipient', bytes),
                  ('packet', bytes)]


class PeerNotifyDisconnect(M2MPacket):
    """Tell the peer cluster a client disconnected."""

    type = PacketType.peer_notify_disconnect
    attributes = [('node', bytes)]


class PeerNotifyName(M2MPacket):
    """Notify peer(s) about a named connection."""

    type = PacketType.peer_notify_name
    attributes = [('node', bytes),
                  ('name', bytes)]


class PeerClosePort(M2MPacket):
    """Tell peer about a closed port."""

    type = PacketType.peer_close_port
    attributes = [('node', bytes),
                  ('port', int)]
