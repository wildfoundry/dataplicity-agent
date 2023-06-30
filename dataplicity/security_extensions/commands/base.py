import logging

from collections import namedtuple
from datetime import datetime, timezone

PARAM_SEPARATOR = [" ", "="]

logging.getLogger("sh").setLevel(logging.WARNING)


class CommandBase(object):

    enabled_attrs = []
    kind = None


    def get_data_model(self):
        return  namedtuple(self.kind, self.enabled_attrs)

    def _trim_sensitive_data(self, input_data, sensitive_data, HIDDEN_STR="<hidden>"):
        """Given a string with --some-password=confidential-data 
        or --some-password confidential-data; hides all confidential values. """
        
        _data = input_data
        for separator in PARAM_SEPARATOR:
            _data = _data.split(separator)
            _result = [_data[0]]
            for prev, current in zip(_data, _data[1:]):
                for keyword in sensitive_data:
                    if keyword in prev:
                        current = HIDDEN_STR
                _result.append(current)
            _data = separator.join(_result)
        return _data

    def _get_timestamp(selfo):
        dt_now = datetime.now(tz=timezone.utc)
        return int(dt_now.timestamp())

    def should_skip_row(self, row):
        return False

    def execute(self):
        data_class = self.get_data_model()
        data = {
            data_class(**self.parse_params(row))
            for row in self._get_cmd() 
        }
        return { row for row in data if not self.should_skip_row(row) }