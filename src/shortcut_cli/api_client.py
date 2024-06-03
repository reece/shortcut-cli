"""Shortcut API Client

This module provides a thin wrapper for the Shortcut REST API, primarily to
support ratelimiting required by their API and to consolidate authentication.

"""

import logging

import ratelimit
import requests

_logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, token):
        session = requests.Session()
        session.headers = {"Shortcut-Token": token}
        self.session = session
        self.base_url = "https://api.app.shortcut.com/api/v3"

    @ratelimit.sleep_and_retry
    @ratelimit.limits(calls=25, period=10)
    def get(self, path, data=None):
        url = self.base_url + "/" + path
        try:
            resp = self.session.get(url=url, json=data or {})
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            e.args = (e.args[0], resp.json()["message"])
            raise(e)
        return resp.json()

    @ratelimit.sleep_and_retry
    @ratelimit.limits(calls=25, period=10)
    def post(self, path, data):
        url = self.base_url + "/" + path
        # The SC API chokes on keys w/ null values; remove them
        data = {k: v for k, v in data.items() if v is not None}
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

