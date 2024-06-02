"""Pythonic-ish interface to shortcut"""

import datetime
import logging

from .shortcut_client import ShortcutClient

_logger = logging.getLogger(__name__)


class Shortcut(ShortcutClient):
    """Pythonic interface to Shortcut"""

    def __init__(self, token: str):
        """_summary_

        Args:
            Args:
                token (str): Shortcut API token
        """
        super().__init__(token)
        self._refresh_metadata()

    def _config_workspace(self, config: dict):
        """INCOMPLETE: configure new or existing workspace per config files

        Args:
            config (dict): _description_
        """
        # groups
        # milestones
        # labels

        groups = [g["mention_name"] for g in self.get("groups")]
        for group_info in config["groups"]:
            mention_name = group_info["name"].lower().replace(" ", "")
            if mention_name in groups:
                continue
            body = dict(
                name=group_info["name"],
                mention_name=mention_name,
                description=group_info.get("description"),
                workflows_ids=[self.default_workflow_id],
            )
            resp = self.post("groups", body)
            _logger.info("Created group %" % (mention_name,))

        # self._refresh_metadata()

    def _refresh_metadata(self):
        custom_fields = self.get("custom-fields")

        self.teams_map = {
            e["mention_name"]: {"id": e["id"], "workflow_ids": [e["workflow_ids"]]} for e in self.get("groups")
        }

        # eg {'unstarted': 500000002, 'started': 500000003, 'done': 500000004}
        workflows = self.get("workflows")
        if len(workflows) > 1:
            _logger.warn("Multiple workflows found; using the first as the default")
        self.default_workflow_id = None  # workflows[0]["id"]

        self.workflow_id_map = {wf["name"]: wf["id"] for wf in workflows}

        self.story_state_id_map = {wfs["name"]: wfs["id"] for wfs in workflows[0]["states"]}
        self.issue_state_id_map = self.story_state_id_map  # backward compat; refactor

        # eg {'unstarted': 500000002, 'started': 500000003, 'done': 500000004}
        self.epic_state_id_map = {es["name"]: es["id"] for es in self.get("epic-workflow")["epic_states"]}

        # eg {'reece': '5fc55794-...', 'kateim': '5fcd04f2...'}
        self.member_id_map = {m["profile"]["mention_name"]: m["id"] for m in self.get("members")}

        # eg {'backend': 394, 'frontend': 393, 'high priority': 395, 'low priority': 396}
        self.labels_id_map = {lr["name"]: lr["id"] for lr in self.get("labels") if not lr["archived"]}

        # custom fields and shortcuts
        self.custom_field_map = {
            cf["name"]: {
                "id": cf["id"],
                "name": cf["name"],
                "value_id_map": {v["value"]: v["id"] for v in cf["values"]},
            }
            for cf in self.get(path="custom-fields")
        }
        self.technical_area = self.custom_field_map["Technical Area"]

        _logger.info(
            "%d issue states, %d epic states, %d members, %d labels"
            % (
                len(self.issue_state_id_map),
                len(self.epic_state_id_map),
                len(self.member_id_map),
                len(self.labels_id_map),
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
        labels: list = [],
        **kwargs,
    ) -> dict:

        owner_ids = list(filter(None, self._map_members(owners)) if owners else [])
        created_at = created_at or datetime.datetime.utcnow()
        if labels:
            labels = [{"name": l} for l in labels]
        state = state or "to do"
        body = dict(
            name=name,
            description=description,
            created_at=created_at.strftime("%FT%TZ"),
            epic_state_id=self.epic_state_id_map[state] if state else None,
            owner_ids=owner_ids,
            requested_by_id=self.member_id_map.get(requested_by),
            labels=labels,
            **kwargs,
        )
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
        return self.post(f"epics/{epic_public_id}/comments", body)

    def create_iteration(self, start_date: datetime.date, end_date: datetime.date, name: str = None, team_slug=None):
        body = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "name": name or f"{start_date} — {end_date}",
            "group_ids": [self.teams_map[team_slug]["id"]] if team_slug else []
        }
        return self.post("iterations", body)

    def create_story(
        self,
        name: str,
        description: str,
        created_at: datetime.datetime = None,
        state: str = None,
        owners: list = None,
        requested_by: str = None,
        labels: list = None,
        **kwargs,
    ) -> dict:

        owner_ids = list(filter(None, self._map_members(owners)) if owners else [])
        created_at = created_at or datetime.datetime.utcnow()
        if labels:
            labels = [{"name": l} for l in labels]
        state = state or "Unscheduled"
        body = dict(
            name=name,
            description=description,
            created_at=created_at.strftime("%FT%TZ"),
            workflow_state_id=self.issue_state_id_map[state] if state else None,
            owner_ids=owner_ids,
            requested_by_id=self.member_id_map.get(requested_by),
            labels=labels,
            **kwargs,
        )
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
        return self.post(f"stories/{id}/comments", body)

    def get_epics(self):
        return self.get("epics")
        
    def _story_find_by_external_link(self, external_link: str):
        return self.get(path="external-link/stories", data={"external_link": external_link})


if __name__ == "__main__":
    import os
    import coloredlogs

    coloredlogs.install(level="DEBUG")
    # Tip: export SHORTCUT_API_TOKEN=$(yq .shortcut.token config.yaml)
    sc = Shortcut(token=os.environ["SHORTCUT_API_TOKEN"])

    import IPython

    IPython.embed()

    # print(sc.create_epic(name="foo", description="bar"))
