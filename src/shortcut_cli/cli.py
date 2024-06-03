"""Command line interface to Shortcut


"""

import argparse
import functools
import logging

import pendulum
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
        epilog="shortcut-cli " + __version__,
    )
    top_p.add_argument("--config-file", "-C", help="config file (yaml)", type=str, default="config.yaml")
    top_p.add_argument("--verbose", "-v", action="count", default=0, help="be verbose; multiple accepted")
    top_p.add_argument("--version", action="version", version=__version__)
    top_p.add_argument("--workspace", "-w", required=True)
    top_p.add_argument("--dry-run", default=False, action=argparse.BooleanOptionalAction, help="run queries but do not modify workspace")

    subparsers = top_p.add_subparsers(title="commands", dest="_subcommands")
    subparsers.required = True

    # archive-epics
    ap = subparsers.add_parser("archive-epics", help="Archive completed epics")
    ap.set_defaults(func=archive_epics)
    ap.add_argument("--age", "-a", default=90, type=int, help="Age in days of completed epics to archive")
    ap.add_argument("EPICS", nargs="*", help="Epics to unarchive")

    # create-iterations
    ap = subparsers.add_parser("create-iterations", help="Create iterations")
    ap.set_defaults(func=create_iterations)
    ap.add_argument("--duration", "-d", default=10, type=int, help="duration of iteration")
    ap.add_argument("--n-iterations", "-n", default=1, type=int, help="number of iterations to create")
    ap.add_argument("--period", "-p", default=14, help="start every n days")
    ap.add_argument(
        "--start-date",
        "-s",
        required=True,
        type=lambda x: pendulum.from_format(x, "YYYY-MM-DD").date(),
        help="iteration start date",
    )
    ap.add_argument("--team-slug", "-t", required=True, help="Team slug (not name)")

    # connect-zenhub-epics
    ap = subparsers.add_parser(
        "connect-zenhub-epics", help="Connect issues that have already been migrated"
    )
    ap.set_defaults(func=connect_zenhub_epics)
    ap.add_argument(
        "--zenhub", "-z", default=False, action="store_true", help="pull epic and estimate data from zenhub"
    )
    ap.add_argument("repos", nargs=1, help="Repo name")

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
    ap.add_argument("--labels", "-l", default=[], action="append")
    ap.add_argument("repos", nargs=1, help="Repo name")

    # shell
    ap = subparsers.add_parser("shell", help="Open IPython shell with shortcut initialized")
    ap.set_defaults(func=shell)

    # unarchive-epics
    ap = subparsers.add_parser("unarchive-epics", help="Unarchive specified epics")
    ap.set_defaults(func=unarchive_epics)
    ap.add_argument("EPICS", nargs="+", help="Epics to unarchive")

    return top_p


def _parse_args():
    ap = _create_arg_parser()
    opts = ap.parse_args()
    opts._config = safe_load(open(opts.config_file))
    opts._config["shortcut"]["workspace"] = opts.workspace  # ugly! remove config workspace entirely
    if getattr(opts, "labels", None):
        opts.labels = functools.reduce(lambda l,r: l + r.split(","), opts.labels, [])    # split on , and flatten list
    return opts


def _setup_requests_cache(config):
    requests_cache.install_cache(
        config["requests_cache_filename"],
        backend="sqlite",
        urls_expire_after={"api.app.shortcut.com": requests_cache.DO_NOT_CACHE, "*": 3600},
    )
    _logger.info(
        "Installed requests cache %s w/%d s TTL" % (config["requests_cache_filename"], config["requests_cache_ttl"])
    )
    cache = requests_cache.get_cache()
    if any(u for u in cache.urls() if "shortcut" in u):
        raise RuntimeError("cache contains shortcut URLs which fails when using multiple workspaces")
    return cache


## Subcommands
def archive_epics(opts):
    config = opts._config
    shortcut_token = config["shortcut"]["tokens"][config["shortcut"]["workspace"]]
    sc = Shortcut(token=shortcut_token)
    cutoff_timestamp = pendulum.now().subtract(days=opts.age)
    if len(opts.EPICS) > 0:
        epics = {int(epic_id): None for epic_id in opts.EPICS}
        _logger.info(f"Archiving {len(epics)} specified epics")
    else:
        epics = {}
        for epic in sc.get_epics():
            if epic["archived"]:
                continue
            updated_at = pendulum.parse(epic["updated_at"])
            if updated_at < cutoff_timestamp:
                epics[epic["id"]] = epic["name"]
        _logger.info(f"Archiving {len(epics)} epics with age > {opts.age} days")
    if opts.dry_run:
        _logger.info("(dry-run specified... not really archiving)")
    else:
        for epic_id in epics:
            sc.put(f"epics/{epic_id}", {"archived": True})
            _logger.info(f"Archived {epic_id} ({epics[epic_id]})")


def create_iterations(opts):
    config = opts._config
    shortcut_token = config["shortcut"]["tokens"][config["shortcut"]["workspace"]]
    sc = Shortcut(token=shortcut_token)
    assert opts.period > opts.duration > 0, "period must be greater than duration, both > 0"
    it_start_date = opts.start_date
    for i in range(opts.n_iterations):
        resp = sc.create_iteration(
            start_date=it_start_date,
            end_date=it_start_date.add(days=opts.duration),
            team_slug=opts.team_slug
        )
        _logger.info(f"Created iteration {resp['name']} ({resp['app_url']})")
        it_start_date = it_start_date.add(days=opts.period)


def import_github_issues(opts):
    impr = Importer(opts._config)
    _logger.info(f"Importing issues from {len(opts.repos)} repos with labels {opts.labels}")
    for repo in opts.repos:
        impr.migrate_repo(repo, technical_area=opts.technical_area, starting_issue=opts.starting_issue, labels=opts.labels)

def connect_zenhub_epics(opts):
    impr = Importer(opts._config)
    for repo in opts.repos:
        impr.connect_epics_from_zenhub(repo)


def shell(opts):
    config = opts._config
    shortcut_token = config["shortcut"]["tokens"][config["shortcut"]["workspace"]]
    sc = Shortcut(token=shortcut_token)
    import IPython
    IPython.embed()


def unarchive_epics(opts):
    config = opts._config
    shortcut_token = config["shortcut"]["tokens"][config["shortcut"]["workspace"]]
    sc = Shortcut(token=shortcut_token)
    epic_ids = opts.EPICS
    _logger.info(f"Unarchiving {len(epic_ids)} epics")
    if opts.dry_run:
        _logger.info("(dry-run specified... not really unarchiving)")
    else:
        for epic_id in epic_ids:
            sc.put(f"epics/{epic_id}", {"archived": False})
            _logger.info(f"Unarchived {epic_id}")


def main():
    import coloredlogs

    coloredlogs.install(level="INFO")
    opts = _parse_args()
    _setup_requests_cache(opts._config)
    opts.func(opts)


if __name__ == "__main__":
    main()
