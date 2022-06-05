from collections.abc import Iterator
import itertools
import logging

from github import Github, Repository, Issue
import zenhub

_logger = logging.getLogger(__name__)



class GitHubZenHub:
    def __init__(self, github_config, zenhub_config):
        self._github = Github(github_config["token"])
        self._zenhub: zenhub.Zenhub = zenhub.Zenhub(zenhub_config["token"])

    def fetch_issues(self, org_name: str, repo_name: str) -> Iterator[Issue.Issue]:
        """Fetch epics with child issues issues

        Args:
            org_name (str): organization name
            repo_name (str): repo name

        Yields:
            Iterator[Issue.Issue]: Epic issues with zh_epic_issues property
        """
        def get_zh_info(repo, issue):
            issue_data = self._zenhub.get_issue_data(
                repo_id=repo.id, issue_number=issue.number
            )
            issue_type = "Epic" if issue_data["is_epic"] else "Story"
            child_issues = []
            if issue_type == "Epic":
                child_issues = self._zenhub.get_epic_data(repo_id=repo.id, epic_id=issue.number)["issues"]
            return dict(
                issue_type = issue_type,
                child_issues = child_issues
            )
        
        org = self._github.get_organization(org_name)
        repo = org.get_repo(repo_name)
        for issue in iter(
            repo.get_issues(state="all", sort="created", direction="asc")
        ):
            zh_info = get_zh_info(repo, issue)
            issue.zh_issue_type = zh_info["issue_type"]
            issue.zh_child_issues = zh_info["child_issues"]
            yield issue

    def fetch_epics(self, org_name: str, repo_name: str) -> Iterator[Issue.Issue]:
        org = self._github.get_organization(org_name)
        repo = org.get_repo(repo_name)
        zh_epics = self._zenhub.get_epics(repo.id)["epic_issues"]
        for zhe in zh_epics:
            issue = repo.get_issue(zhe["issue_number"])
            issue.zh_epic_issues = self._zenhub.get_epic_data(repo_id=repo.id, epic_id=zhe["issue_number"])["issues"]
            yield issue


if __name__ == "__main__":
    import coloredlogs
    import yaml

    coloredlogs.install(level="INFO")
    config_fn = "config.yaml"
    config = yaml.safe_load(open(config_fn))
    gz = GitHubZenHub(github_config=config["github"], zenhub_config=config["zenhub"])
    issues = list(gz.fetch_issues("myome", "infra"))