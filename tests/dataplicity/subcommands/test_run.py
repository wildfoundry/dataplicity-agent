from dataplicity.subcommands.run import Run
from dataplicity.app import App
import mock


@mock.patch('dataplicity.client.Client.run_forever')
def test_run_command(run_forever, serial_file, auth_file):
    """ unit test for run subcommand.
        There are couple of caveats, which I will briefly describe here:
        -> we don't want to literally call run_forever on the client, because
           it would deadlock the tests. Because of that, we simply want to
           check whether the function in question was called. As you can see,
           there is a magic parameter called run_forever, which is tightly
           coupled with the mock.patch decorator. It is a mocked copy of an
           actual function from the module dataplicity.client.Client
        -> We have to fake command-line arguments, because otherwise the App
           module won't create a client for us - hence, instead of creating
           a parser and parsing an empty string, we're hard-coding two url's
           which are irrelevant to our test anyway.
    """
    class FakeArgs(object):
        """ fake stdargs object
        """
        server_url = 'http://example.com'
        m2m_url = 'ws://example.com'

    app = App()
    # set fake command-line args
    app.args = FakeArgs()
    # initiate subcommand
    cmd = Run(app)

    # execute subcommand. This should call run_forever on the client ...
    cmd.run()

    # ... as asserted here.
    assert run_forever.call_count == 1
