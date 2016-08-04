from __future__ import unicode_literals
from __future__ import print_function

from os.path import abspath, normpath, exists, expanduser, join, dirname, basename

from . import errors
from .compat import PY2, text_type

if PY2:
    import ConfigParser as configparser
    from ConfigParser import SafeConfigParser
else:
    import configparser
    from configparser import SafeConfigParser


class ConfigSection(object):
    """A proxy object for a single conf setting"""

    def __init__(self, conf, section):
        self.conf = conf
        self.section = section

    def get(self, key, default=Ellipsis):
        return self.conf.get(self.section, key, default=default)

    def get_bool(self, key, default=False):
        return self.conf.get_bool(self.section, key, default=default)

    def get_float(self, key, default=0.0):
        return self.conf.get_float(self.section, key, default=default)

    def get_list(self, key, default=None):
        return self.conf.get_list(self.section, key, default=default)


class DPConfigParser(SafeConfigParser):
    """Custom ConfigParser that has a get that can return defaults"""

    def __init__(self, *args, **kwargs):
        SafeConfigParser.__init__(self, *args, **kwargs)
        self.path = ''

    def __repr__(self):
        return "<settings {}>".format(basename(self.path))

    def get_section(self, section):
        return ConfigSection(self, section)

    def get(self, section, key, default=Ellipsis):
        try:
            return SafeConfigParser.get(self, section, key)
        except configparser.Error:
            if default is Ellipsis:
                raise errors.ConfigError("required key [{}]/{} is missing from conf file".format(section, key))
            return default

    def has_setting(self, section, key):
        try:
            SafeConfigParser.get(self, section, key)
        except configparser.Error:
            return False
        else:
            return True

    def get_path(self, section, key, default=Ellipsis):
        """Gets a path relative to this location of the conf files"""
        if not self.has_setting(section, key):
            if default is not Ellipsis:
                return default
        path = self.get(section, key)
        path = abspath(normpath(join(dirname(self.path), path)))
        return path

    def get_bool(self, section, key, default=Ellipsis):
        setting = self.get(section, key, default=default)
        if isinstance(setting, text_type):
            return setting.lower() in ('1', 'y', 'yes', 'true')
        else:
            return bool(setting)

    def get_float(self, section, key, default=Ellipsis):
        setting = self.get(section, key, default=default)
        try:
            setting = float(setting)
        except ValueError:
            raise errors.ConfigError("conf value [{}]/{} must be a valid float".format(section, key))
        return setting

    def get_integer(self, section, key, default=Ellipsis):
        setting = self.get(section, key, default=default)
        try:
            setting = int(setting)
        except ValueError:
            raise errors.ConfigError("conf value [{}]/{} must be a valid integer".format(section, key))
        return setting

    def get_list(self, section, key, default=Ellipsis):
        """Get a list from a conf key.

        Lists are multiple indented lines. For example:

        [Middle Earth]
        hobbits = Frodo
            Bilbo
            Sam

        get_list('Middle Earth', 'hobbits') would return ['Frodo', 'Bilbo', 'Sam']

        """
        text = self.get(section, key, default)
        if text is default:
            return default
        return parse_list(text)

    def qualified_sections(self, section_type):
        """Yields sections qualified with a colon, i.e. [task:monitor]

        Yields a sequence of the qualified section followed by the section name

        """
        for section in self.sections():
            if ':' in section:
                _section_type, colon, section_name = section.partition(':')
                if colon and _section_type == section_type:
                    yield section, section_name


def _normalize_path(p):
    return normpath(expanduser(p))


def extend_cfg(cfg, path):
    """Extend the cfg"""
    # If the cfg contains an [extend] section then overlay paths
    # in the 'conf' option

    visited = set()
    extends_chain = [cfg]
    path_dir = dirname(path)

    extend = cfg.get('extend', 'conf', None)
    while extend is not None:
        extend_path = abspath(join(path_dir, extend))
        if extend_path in visited:
            raise errors.StartupError("Recursive extends in conf files")
        visited.add(extend_path)
        cfg = DPConfigParser()
        try:
            with open(extend_path, 'rb') as conf_file:
                cfg.read(extend_path)
        except IOError:
            # Doesn't exist. Extends chain ends here
            break
        extends_chain.insert(0, cfg)
        extend = cfg.get('extend', 'conf', None)

    # Merge extended conf files
    extended_cfg = extends_chain[0]
    for cfg in extends_chain[1:]:
        for section in cfg.sections():
            if section == 'extend':
                continue
            if not extended_cfg.has_section(section):
                extended_cfg.add_section(section)
            for k, v in cfg.items(section):
                extended_cfg.set(section, k, v)

    extended_cfg.path = path
    return extended_cfg


def read(*paths):
    """Reads conf file from one of a number of locations"""
    cfg = DPConfigParser()
    expanded_paths = [abspath(normpath(expanduser(p))) for p in paths]
    for path in expanded_paths:
        if not exists(path):
            continue
        try:
            with open(path, 'rt') as conf_file:
                cfg.path = path
                cfg.readfp(conf_file, filename=path)
        except IOError:
            pass
        else:
            return extend_cfg(cfg, path)
    paths_txt = ", ".join('"%s"' % p for p in paths)
    raise errors.StartupError("conf not found, looked for %s" % paths_txt)


def read_default(*paths):
    """Read settings or return an empty cfg if no conf file is found"""
    try:
        return read(*paths)
    except errors.StartupError:
        return DPConfigParser()


def read_from_file(conf_file, filename='?'):
    cfg = DPConfigParser()
    cfg.readfp(conf_file, filename=filename)
    return cfg


def read_contents(path, blank=False):
    """Read a settings file and return the contents plus a settings instance"""
    cfg = DPConfigParser()
    try:
        with open(path, 'rb') as conf_file:
            contents = conf_file.read()
            conf_file.seek(0)
            cfg.path = path
            cfg.readfp(conf_file, filename=path)
    except (OSError, IOError):
        if blank:
            return b'', cfg
        raise
    return contents, cfg


def parse_list(s):
    """Parse a multi-line string in to a list"""
    return [l.strip() for l in s.splitlines() if l]


if __name__ == "__main__":
    cfg = read("./test.conf")
    print(repr(cfg.get_list('middle earth', 'hobbits')))
    print(cfg.get_list('middle earth', 'evil'))

    import sys
    cfg.write(sys.stdout)
