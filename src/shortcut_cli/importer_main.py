#!/usr/bin/env python3

"""migrate github issues to shortcut stories

includes support for:
- zenhub epics

"""

import argparse
import logging
import re

import coloredlogs
import requests
import requests_cache
import yaml

from .importer import Importer

_logger = logging.getLogger(__name__)

issue_re = re.compile(r"(?P<slug>[\w/]*)#(?P<issue_no>\d+)")


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--config", "-c", default="config.yaml")
    ap.add_argument("--issues", "-i", action="append", default=[])
    ap.add_argument("--repos", "-r", action="append", default=[])
    ap.add_argument("--init", default=False, action="store_true")
    ap.add_argument("--import-repos", "-I", default=False, action="store_true")
    ap.add_argument("--zenhub-epics", "-z", default=False, action="store_true")
    # ap.add_argument("--allow-duplicates", "-D", default=False, action="store_true")

    opts = ap.parse_args()
    return opts


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


def main():
    coloredlogs.install(level="info")

    opts = parse_args()
    config = yaml.safe_load(open(opts.config))
    opts.repos = opts.repos or config["github"]["repos"]

    setup_requests_cache(config)
    impr = Importer(config)

    if opts.init:
        impr._shortcut._config_workspace(config["shortcut"])

    elif opts.issues:
        for issue_key in opts.issues:
            m = issue_re.match(issue_key)
            if not m:
                raise ValueError("issue (%) should have the form org/repo#number, e.g., joseph/heller#22" % (issue,))
            issued = m.groupdict()
            repo = impr._github.get_repo(issued["slug"])
            issue = repo.get_issue(int(issued["issue_no"]))
            sc_issue = impr.migrate_issue(issue)
            if sc_issue:
                _logger.info("%s → %s" % (issue_key, sc_issue["app_url"]))
            pass

    elif opts.import_repos:
        for repo_name in opts.repos:
            impr.migrate_repo(repo_name=repo_name)

    elif opts.zenhub_epics:
        for repo_name in opts.repos:
            impr.connect_epics_from_zenhub(repo_name)


if __name__ == "__main__":
    main()
