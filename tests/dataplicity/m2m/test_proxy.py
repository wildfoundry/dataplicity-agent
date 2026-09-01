import signal

import pytest
from mock import patch

from dataplicity.m2m import proxy


def test_spawn_resets_sigint_before_exec():
    interceptor = proxy.Interceptor()

    with patch.object(
        proxy.pty, "fork", return_value=(proxy.pty.CHILD, 42)
    ), patch.object(proxy.signal, "signal") as set_signal, patch.object(
        proxy.os, "execlp", side_effect=RuntimeError("exec")
    ), pytest.raises(
        RuntimeError, match="exec"
    ):
        interceptor.spawn(["bash", "-i"])

    set_signal.assert_called_once_with(signal.SIGINT, signal.SIG_DFL)
