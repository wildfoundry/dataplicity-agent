import logging

from .base import CommandBase

from sys import stdout
from sh import ps, ErrorReturnCode


log = logging.getLogger("agent")


class Proc(CommandBase):
    # timestamp always goes in the first position
    enabled_attrs = ["timestamp", "user", "cmd"]
    kind = "proc"


    def to_dict(self):
        return { label: str.strip(getattr(self, label).encode()) for label in self.enabled_attrs}

    @staticmethod
    def _get_cmd():
        try:
            data = ps("-afwwo", "user cmd", "--no-headers")
            return data
        except ErrorReturnCode:
            # 'ps' could return -1 if no processes are listed
            return []

    @staticmethod
    def _clean_cmd(cmd):
        # TODO: clean this data somehow and store only in logs the original reference
        return cmd.replace("\_ ", "")



    def parse_params(self, data):
        data = data.split()
        cmd = self._trim_sensitive_data(
            " ".join(data[1:]), 
            ["auth", "password", "serial", "pass"]
            )
        return {
            "timestamp": self._get_timestamp(),
            "user": data[0],
            "cmd": self._clean_cmd(cmd)
            }

    def execute(self):
        """
            USER     COMMAND
            root     bash
            root      \_ ps -afwwo user,command
            root     bash
            root      \_ python -m dataplicity.app -s http://api:8001 --remote-dir /secrets_values.yml --auth <hidden> --serial <hidden>
        """
        result = set()
        data_class = self.get_data_model()
        cmd_result = self._get_cmd()
        for proc_row in cmd_result:
            result.add(
                data_class(**self.parse_params(proc_row))
            )
        return result


if __name__ == "__main__":
    proc_list = Proc().execute()
    stdout.write("Process list: \n")
    for proc in proc_list:
        stdout.write("\t" + str(proc) + "\n")