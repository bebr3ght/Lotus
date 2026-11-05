#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LCU.get passes its cache switch through.

The reconnect after a late overlay polls the gameflow phase and must not read a
cached answer. LCU.get did not accept use_cache at all, so every poll raised
TypeError, the caller's broad except turned that into "no phase", and the poll
timed out even while the client was sitting in Reconnect.
"""

import unittest
from unittest import mock

from lcu.core.client import LCU


class ClientGetTests(unittest.TestCase):
    def _client(self):
        with mock.patch.object(LCU, "_connection", create=True), \
                mock.patch("lcu.core.client.LCUConnection"), \
                mock.patch("lcu.core.client.LCUAPI") as api, \
                mock.patch("lcu.core.client.LCUProperties"), \
                mock.patch("lcu.core.client.LCUSkinSelection"), \
                mock.patch("lcu.core.client.LCUGameMode"), \
                mock.patch("lcu.core.client.LCUSwiftplay"):
            client = LCU()
            client._api = api.return_value
            return client, api.return_value

    def test_the_cache_switch_is_forwarded(self):
        client, api = self._client()
        client.get("/lol-gameflow/v1/gameflow-phase", timeout=1.0, use_cache=False)
        api.get.assert_called_once_with(
            "/lol-gameflow/v1/gameflow-phase", 1.0, use_cache=False)

    def test_the_default_keeps_the_cache(self):
        client, api = self._client()
        client.get("/any")
        api.get.assert_called_once_with("/any", 1.0, use_cache=True)


if __name__ == "__main__":
    unittest.main()
