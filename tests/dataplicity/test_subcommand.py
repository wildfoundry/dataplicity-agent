from dataplicity import subcommand


def test_subcommand_registration():
    """ test for registering subcommands
    """
    class TestSubCommand(subcommand.SubCommand):
        """ Dummy class, it's only purpose is to subclass from SubCommand
            and call the __new__ function. This checks, whether it would
            register in the subcommand.registry
        """
        pass

    assert 'testsubcommand' in subcommand.registry
    assert issubclass(TestSubCommand, subcommand.registry['testsubcommand'])
