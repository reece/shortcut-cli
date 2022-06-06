#!/usr/bin/env python3

import functools
import logging
import os
import shelve

from github import Github
from zenhub import Zenhub
import yaml

from .services.shortcut import EasyShortcut

_logger = logging.getLogger(__name__)


class Importer:
    def __init__(self, config):
        self.config = config
        self.github_org = self.config["github"]["org"]
        self._github = Github(config["github"]["token"])
        self._zenhub = Zenhub(config["zenhub"]["token"])
        shortcut_token = config["shortcut"]["tokens"][config["shortcut"]["workspace"]]
        self._shortcut = EasyShortcut(token=shortcut_token)
        migrated_fn = "{}-{}".format(config["migrated_filename"], config["shortcut"]["workspace"])
        self.migrated = shelve.open(migrated_fn)
        self.strict = True

    @functools.lru_cache(maxsize=1000)
    def _map_username(self, github_username):
        try:
            return self.config["github_shortcut_user_map"][github_username]
        except KeyError:
            if not self.strict:
                _logger.warning("GitHub user %s is unmapped" % (github_username,))
                return None

    def connect_epics_from_zenhub(self, repo_name):
        """connect epics in given repo to child issues, which must have been already migrated"""
        org = self._github.get_organization(self.github_org)
        repo = org.get_repo(repo_name)
        epics = self._zenhub.get_epics(repo.id)["epic_issues"]
        for epic in epics:
            parent_key = str((epic["repo_id"], epic["issue_number"]))
            parent_public_id = self.migrated.get(parent_key)
            if parent_public_id is None:
                _logger.warn("Epic %s has not been migrated" % (parent_key))
                continue
            epic_children = self._zenhub.get_epic_data(repo_id=repo.id, epic_id=epic["issue_number"])["issues"]
            for child in epic_children:
                child_key = str((child["repo_id"], child["issue_number"]))
                child_public_id = self.migrated.get(child_key)
                if child_public_id is None:
                    _logger.warn("Child story %s has not been migrated for epic %s" % (child_key, parent_key))
                    continue
                resp = self._shortcut.put(f"stories/{child_public_id}", {"epic_id": parent_public_id})
                _logger.info(
                    "Story %s [%s] is child of epic %s [%s]"
                    % (child_public_id, child_key, parent_public_id, parent_key)
                )

    def migrate_issue(self, issue):
        repo_name = issue.repository.name  # better: i.r.full_name
        is_epic = any(l for l in issue.labels if l.name == "Epic")
        original_comment = f"Migrated from GitHub [{self.github_org}/{repo_name}#{issue.number}]({issue.html_url})"

        # prepare elements common to shortcut epics and issues
        body = dict(
            name=issue.title,
            description=original_comment + "\n\n---\n\n" + (issue.body or ""),
            created_at=issue.created_at,
            owners=list(filter(None, [self._map_username(a.login) for a in issue.assignees])),
            external_id=issue.html_url,
            requested_by=self._map_username(issue.user.login),
        )

        if is_epic:
            body["state"] = self.config["github_shortcut_epic_state_map"][issue.state]
            epic = self._shortcut.create_epic(**body)
            for c in issue.get_comments():
                self._shortcut.create_epic_comment(
                    epic["id"],
                    author=self._map_username(c.user.login),
                    created_at=c.created_at,
                    text=c.body,
                )
            return epic

        else:  # Story
            body["state"] = self.config["github_shortcut_issue_state_map"][issue.state]
            story = self._shortcut.create_story(**body)
            for c in issue.get_comments():
                self._shortcut.create_story_comment(
                    story["id"],
                    author=self._map_username(c.user.login),
                    created_at=c.created_at,
                    text=c.body,
                )
            return story

    def migrate_repo(self, repo_name):
        org = self._github.get_organization(self.github_org)
        repo = org.get_repo(repo_name)
        for issue in repo.get_issues(state="all", sort="created", direction="asc"):
            issue_key = str((repo.id, issue.number))
            issue_abbr = f"{issue.repository.organization.login}/{repo_name}#{issue.number}"
            if issue_key in self.migrated:
                _logger.debug("Skipping %s; already migrated to %s" % (issue.html_url, self.migrated[issue_key]))
                continue
            sc_issue = self.migrate_issue(issue)
            self.migrated[issue_key] = sc_issue["id"]
            _logger.info("%s → %s" % (issue_abbr, sc_issue["app_url"]))
