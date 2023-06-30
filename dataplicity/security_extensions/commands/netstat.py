from sys import stdout

from .base import CommandBase
from sh import ss


class Netstat(CommandBase):
    """_summary_
        $ netstat -an 
        Active Internet connections (servers and established)
        Proto Recv-Q Send-Q Local Address           Foreign Address         State      
        tcp        0      0 127.0.0.53:53           0.0.0.0:*               LISTEN     
        tcp        0      0 127.0.0.1:631           0.0.0.0:*               LISTEN     
        tcp        0      0 0.0.0.0:9080            0.0.0.0:*               LISTEN     
        tcp        0      0 127.0.0.1:9050          0.0.0.0:*               LISTEN     
        tcp        0      0 127.0.0.1:41663         0.0.0.0:*               LISTEN     
        tcp        0      0 0.0.0.0:9000            0.0.0.0:*               LISTEN     
        tcp        0      0 127.0.0.1:3306          0.0.0.0:*               LISTEN     
        tcp        0      0 0.0.0.0:8080            0.0.0.0:*               LISTEN
        [...]

    Args:
        object (_type_): _description_

    Returns:
        _type_: _description_
    """

    # timestamp always goes in the first position
    enabled_attrs = ["timestamp", "protocol", "state", "local_address", "local_port", "peer_address", "peer_port"]
    kind = "netstat"

    @staticmethod
    def _get_cmd():
        return ss("-anH", _iter=True)

    def parse_params(self, data):
        data = data.split()
        local = data[4]
        local_address = local if ":" not in local else local.split(":")[0]
        local_port = "*" if ":" not in local else local.split(":")[1]
        peer = data[5]
        peer_address = peer if ":" not in peer else peer.split(":")[0]
        peer_port = "*" if ":" not in peer else peer.split(":")[1]
        
        return {
            "timestamp": self._get_timestamp(),
            "protocol": data[0],
            "state": data[1],
            "local_address": local_address,
            "local_port": local_port,
            "peer_address": peer_address,
            "peer_port": peer_port,
            }

    def should_skip_row(self, row):
        return row.protocol == u"nl"


if __name__ == "__main__":
    proc_list = Netstat().execute()
    stdout.write("Process list: \n")
    for proc in proc_list:
        stdout.write("\t" + str(proc) + "\n")