import datetime
import logging
import re

import ratelimit
import requests

_logger = logging.getLogger(__name__)


skip_labels_re = re.compile("size::")

class Shortcut:
    def __init__(self, token):
        session = requests.Session()
        session.headers = {"Shortcut-Token": token}
        self.session = session
        self.base_url = "https://api.app.shortcut.com/api/v3"

    @ratelimit.sleep_and_retry
    @ratelimit.limits(calls=25, period=10)
    def get(self, path):
        url = self.base_url + "/" + path
        try:
            resp = self.session.get(url=url)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            e.args = (e.args[0], resp.json()["message"])
            raise(e)
        return resp.json()

    @ratelimit.sleep_and_retry
    @ratelimit.limits(calls=25, period=10)
    def post(self, path, data):
        url = self.base_url + "/" + path
        try:
            resp = self.session.post(url=url, json=data)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            e.args = (e.args[0], resp.json()["message"])
            raise(e)
        return resp.json()
            
    @ratelimit.sleep_and_retry
    @ratelimit.limits(calls=25, period=10)
    def put(self, path, data):
        url = self.base_url + "/" + path
        try:
            resp = self.session.put(url=url, json=data)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            e.args = (e.args[0], resp.json()["message"])
            raise(e)
        return resp.json()

class EasyShortcut(Shortcut):
    def __init__(self, token):
        super().__init__(token)
        self._refresh_metadata()

    def _config_workspace(self, config: dict):
        """INCOMPLETE: configure new or existing workspace per config files

        Args:
            config (dict): _description_
        """
        for group_name, group_info in config["groups"].items():
            body = dict(
                name=group_name,
                mention_name=group_name,
                description=group_info["description"],
            )
            self.post("groups", body)

    def _refresh_metadata(self):
        # eg {'unstarted': 500000002, 'started': 500000003, 'done': 500000004}
        workflows = self.get("workflows")
        assert (
            len(workflows) == 1
        ), "This workspace has multiple workflows but I can handle exactly one"
        self.issue_state_id_map = {
            wfs["name"]: wfs["id"] for wfs in workflows[0]["states"]
        }

        # eg {'unstarted': 500000002, 'started': 500000003, 'done': 500000004}
        self.epic_state_id_map = {
            es["name"]: es["id"] for es in self.get("epic-workflow")["epic_states"]
        }

        # eg {'reece': '5fc55794-...', 'kateim': '5fcd04f2...'}
        self.member_id_map = {
            m["profile"]["mention_name"]: m["id"]
            for m in self.get("members")
        }

        # eg {'backend': 394, 'frontend': 393, 'high priority': 395, 'low priority': 396}
        self.labels_id_map = {
            lr["name"]: lr["id"] for lr in self.get("labels") if not lr["archived"]
        }

        _logger.info(
            "%d issue states, %d epic states, %d members, %d labels"
            % (
                len(self.issue_state_id_map),
                len(self.epic_state_id_map),
                len(self.member_id_map),
                len(self.labels_id_map)
            )
        )

    def _map_members(self, members: list):
        """map list of members to list of member_ids"""
        return [self.member_id_map.get(m) for m in members]

    def create_epic(
        self,
        name: str,
        description: str,
        created_at: datetime.datetime = None,
        state: str = None,
        owners: list = None,
        requested_by: str = None,
        **kwargs,
    ) -> dict:

        owner_ids = list(filter(None, self._map_members(owners)) if owners else [])
        body = dict(
            name=name,
            description=description,
            created_at=created_at.strftime("%FT%TZ"),
            epic_state_id=self.epic_state_id_map[state] if state else None,
            owner_ids=owner_ids,
            requested_by_id=self.member_id_map.get(requested_by),
            **kwargs,
        )
        body = {k: v for k, v in body.items() if v is not None}
        return self.post("epics", body)

    def create_epic_comment(
        self,
        epic_public_id: int,
        text: str,
        author: str = None,
        created_at: datetime.datetime = None,
        **kwargs,
    ):
        body = dict(
            text=text,
            created_at=created_at.strftime("%FT%TZ") if created_at else None,
            author_id=self.member_id_map.get(author) if author else None,
            **kwargs,
        )
        body = {k: v for k, v in body.items() if v is not None}
        return self.post(f"epics/{epic_public_id}/comments", body)

    def create_story(
        self,
        name: str,
        description: str,
        created_at: datetime.datetime = None,
        state: str = None,
        owners: list = None,
        requested_by: str = None,
        **kwargs,
    ) -> dict:

        owner_ids = list(filter(None, self._map_members(owners)) if owners else [])
        body = dict(
            name=name,
            description=description,
            created_at=created_at.strftime("%FT%TZ"),
            workflow_state_id=self.issue_state_id_map[state] if state else None,
            owner_ids=owner_ids,
            requested_by_id=self.member_id_map.get(requested_by),
            **kwargs,
        )
        body = {k: v for k, v in body.items() if v is not None}
        return self.post("stories", body)

    def create_story_comment(
        self,
        id: int,
        text: str,
        author: str = None,
        created_at: datetime.datetime = None,
        **kwargs,
    ):
        body = dict(
            text=text,
            created_at=created_at.strftime("%FT%TZ") if created_at else None,
            author_id=self.member_id_map.get(author) if author else None,
            **kwargs,
        )
        body = {k: v for k, v in body.items() if v is not None}
        return self.post(f"stories/{id}/comments", body)


if __name__ == "__main__":
    import os
    import coloredlogs

    coloredlogs.install(level="DEBUG")
    # Tip: export SHORTCUT_API_TOKEN=$(yq .shortcut.token config.yaml)
    sc = EasyShortcut(token=os.environ["SHORTCUT_API_TOKEN"])
    print(sc.create_epic(name="foo", description="bar"))
