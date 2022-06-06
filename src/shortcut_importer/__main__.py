#!/usr/bin/env python3

"""shortcut_importer

"""

import logging

import coloredlogs
import requests
import requests_cache
import yaml

from .importer import Importer

_logger = logging.getLogger(__name__)

coloredlogs.install(level="info")

config_fn = "config.yaml"
config = yaml.safe_load(open(config_fn))

requests_cache.install_cache(
    config["requests_cache_filename"],
    backend="sqlite",
    expire_after=config["requests_cache_ttl"],
    urls_expire_after={
        "api.app.shortcut.com": requests_cache.DO_NOT_CACHE
    }
)
_logger.info(
    "Installed requests cache %s w/%d s TTL"
    % (config["requests_cache_filename"], config["requests_cache_ttl"])
)

cache = requests_cache.get_cache()
if any(u for u in cache.urls if "shortcut" in u):
    raise RuntimeError("cache contains shortcut URLs which fails when using multiple workspaces")

impr = Importer(config)

for repo_name in config["github"]["repos"]:
    impr.migrate_repo(repo_name=repo_name)
