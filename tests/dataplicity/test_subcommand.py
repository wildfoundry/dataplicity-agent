from dataplicity import subcommand


def test_subcommand_registration():
    """ test for registering subcommands
    """
    class TestSubCommand(subcommand.SubCommand):
        pass

    assert 'testsubcommand' in subcommand.registry
    assert issubclass(TestSubCommand, subcommand.registry['testsubcommand'])
