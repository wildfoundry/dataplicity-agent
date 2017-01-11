from dataplicity.subcommands.version import Version
from dataplicity import __version__


def test_version(capsys):
    """ unit test for version subcommand
    """
    # dependency injection - can't change its name
    capture_sys = capsys

    version = Version(None)
    version.run()
    out, err = capture_sys.readouterr()

    assert out == __version__
    assert err == ''
