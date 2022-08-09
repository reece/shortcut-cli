"""Command line interface to Shortcut"""

import argparse
from ipaddress import ip_network
import logging
from pprint import pprint

import requests_cache
from yaml import safe_load

from . import __version__
from .importer import Importer
from .shortcut import Shortcut


_logger = logging.getLogger(__name__)


def _create_arg_parser() -> argparse.ArgumentParser:
    top_p = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="seqrepo " + __version__ + ". See https://github.com/biocommons/biocommons.seqrepo for more information",
    )
    top_p.add_argument("--config-file", "-C", help="config file (yaml)", type=str, default="config.yaml")
    top_p.add_argument("--verbose", "-v", action="count", default=0, help="be verbose; multiple accepted")
    top_p.add_argument("--version", action="version", version=__version__)
    top_p.add_argument("--workspace", "-w", required=True)

    subparsers = top_p.add_subparsers(title="commands", dest="_subcommands")
    subparsers.required = True

    # import-from-github
    ap = subparsers.add_parser(
        "import-from-github", help="Import issues from GitHub, optionally with ZenHub information"
    )
    ap.set_defaults(func=import_github_issues)
    ap.add_argument(
        "--zenhub", "-z", default=False, action="store_true", help="pull epic and estimate data from zenhub"
    )
    ap.add_argument("--technical-area", "-t")
    ap.add_argument("--starting-issue", "-s")
    ap.add_argument("repos", nargs=1, help="Repo name, like org/name")

    # shell
    ap = subparsers.add_parser("shell", help="Open IPython shell with shortcut initialized")
    ap.set_defaults(func=shell)

    return top_p


def parse_args():
    ap = _create_arg_parser()
    opts = ap.parse_args()
    opts._config = safe_load(open(opts.config_file))
    opts._config["shortcut"]["workspace"] = opts.workspace  # ugly! remove config workspace entirely
    return opts


def import_github_issues(opts):
    impr = Importer(opts._config)
    for repo in opts.repos:
        impr.migrate_repo(repo, technical_area=opts.technical_area, starting_issue=opts.starting_issue)


def setup_requests_cache(config):
    requests_cache.install_cache(
        config["requests_cache_filename"],
        backend="sqlite",
        urls_expire_after={"api.app.shortcut.com": requests_cache.DO_NOT_CACHE, "*": 3600},
    )
    _logger.info(
        "Installed requests cache %s w/%d s TTL" % (config["requests_cache_filename"], config["requests_cache_ttl"])
    )

    cache = requests_cache.get_cache()
    if any(u for u in cache.urls if "shortcut" in u):
        raise RuntimeError("cache contains shortcut URLs which fails when using multiple workspaces")

    return cache


def shell(opts):
    config = opts._config
    shortcut_token = config["shortcut"]["tokens"][config["shortcut"]["workspace"]]
    sc = Shortcut(token=shortcut_token)
    import IPython

    IPython.embed()


def main():
    import coloredlogs

    coloredlogs.install(level="INFO")
    opts = parse_args()
    setup_requests_cache(opts._config)
    opts.func(opts)


if __name__ == "__main__":
    main()
