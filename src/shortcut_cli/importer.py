#!/usr/bin/env python3

import functools
import logging
import re
import shelve

from github import Github, Issue
import jmespath
import requests.exceptions
from zenhub import Zenhub

from .shortcut import Shortcut

_logger = logging.getLogger(__name__)

skip_labels_re = re.compile("size::")


class Importer:
    """Imports issues into Shortcut from GitHub, optionally with ZenHub data"""

    estimate_p = jmespath.compile("estimate.value")

    def __init__(self, config):
        self.config = config
        self.github_org = self.config["github"]["org"]
        self._github = Github(config["github"]["token"])
        self._zenhub = Zenhub(config["zenhub"]["token"])
        shortcut_token = config["shortcut"]["tokens"][config["shortcut"]["workspace"]]
        self._shortcut = Shortcut(token=shortcut_token)
        migrated_fn = "{}-{}".format(config["migrated_filename"], config["shortcut"]["workspace"])
        self.migrated = shelve.open(migrated_fn)
        self.strict = True
        self.allow_duplicates = False

    @functools.lru_cache(maxsize=1000)
    def _map_username(self, github_username):
        try:
            return self.config["github_shortcut_user_map"][github_username]
        except KeyError:
            if not self.strict:
                _logger.warning("GitHub user %s is unmapped" % (github_username,))
                return None

    def connect_epics_from_zenhub(self, repo_name):
        """Connect already-migrated issues to epics from the specified repo
        
        """
        
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
                try:
                    resp = self._shortcut.put(f"stories/{child_public_id}", {"epic_id": parent_public_id})
                    _logger.info(
                        "Story %s [%s] is child of epic %s [%s]"
                        % (child_public_id, child_key, parent_public_id, parent_key)
                    )
                except requests.exceptions.HTTPError:
                    _logger.info(
                        "Story %s [%s] was child of epic %s [%s], but no longer exists (probably deleted)"
                        % (child_public_id, child_key, parent_public_id, parent_key)
                    )

    def migrate_issue(self, issue: Issue, technical_area=None, labels=None):
        repo_name = issue.repository.name  # better: i.r.full_name
        is_epic = any(l for l in issue.labels if l.name == "Epic")
        original_comment = f"Migrated from GitHub [{self.github_org}/{repo_name}#{issue.number}]({issue.html_url})"

        el_stories = self._shortcut._story_find_by_external_link(issue.html_url)
        if el_stories:
            story = el_stories[0]
            _logger.info("[link] Skipping %s; already migrated to %s" % (issue.html_url, story["app_url"]))
            return None

        issue_key = str((issue.repository.id, issue.number))
        if issue_key in self.migrated and not (self.allow_duplicates):
            _logger.info("[migrated] Skipping %s; already migrated to %s" % (issue.html_url, self.migrated[issue_key]))
            sc_issue_id = self.migrated[issue_key]
            try:
                self._shortcut.put(f"stories/{sc_issue_id}", {"external_links": [issue.html_url]})
            except requests.exceptions.HTTPError as e:
                if "404" not in str(e):
                    raise
            return None

        # prepare elements common to shortcut epics and issues
        body = dict(
            created_at=issue.created_at,
            description=original_comment + "\n\n---\n\n" + (issue.body or ""),
            external_id=issue.html_url,
            labels=labels,
            name=issue.title,
            owners=list(filter(None, [self._map_username(a.login) for a in issue.assignees])),
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
            sc_issue = epic

        else:  # Story
            body["state"] = self.config["github_shortcut_issue_state_map"][issue.state]
            body["external_links"] = [body["external_id"]]
            if technical_area:
                body["custom_fields"] = [
                    {
                        "field_id": self._shortcut.technical_area["id"],
                        "value_id": self._shortcut.technical_area["value_id_map"][technical_area],
                        "value": technical_area,
                    }
                ]
            if self._zenhub:
                issue_data = self._zenhub.get_issue_data(issue.repository.id, issue.number)
                body["estimate"] = self.estimate_p.search(issue_data)
            story = self._shortcut.create_story(**body)
            for c in issue.get_comments():
                self._shortcut.create_story_comment(
                    story["id"],
                    author=self._map_username(c.user.login),
                    created_at=c.created_at,
                    text=c.body,
                )
            sc_issue = story

        self.migrated[issue_key] = sc_issue["id"]
        return sc_issue

    def migrate_repo(self, repo_name, /, starting_issue=None, technical_area=None, labels=None):
        n_epics = n_stories = 0
        org = self._github.get_organization(self.github_org)
        repo = org.get_repo(repo_name)
        for issue in repo.get_issues(state="all", sort="created", direction="asc"):
            is_epic = any(l for l in issue.labels if l.name == "Epic")
            if is_epic:
                n_epics += 1
            else:
                n_stories += 1
            if starting_issue and int(issue.number) < int(starting_issue):
                continue
            issue_abbr = f"{issue.repository.organization.login}/{repo_name}#{issue.number}"
            sc_issue = self.migrate_issue(issue, technical_area=technical_area, labels=labels)
            if sc_issue:
                _logger.info("%s → %s" % (issue_abbr, sc_issue["app_url"]))
        _logger.info("%s: Migrated %s stories and %s epics" % (repo_name, n_stories, n_epics))