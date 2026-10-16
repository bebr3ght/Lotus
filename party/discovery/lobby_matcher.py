#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lobby Matcher
Matches connected peers to lobby/champion select members
"""

from typing import Dict, Optional, Set, Tuple

from lcu import LCU
from state import SharedState
from utils.core.logging import get_logger

log = get_logger()


class LobbyMatcher:
    """Matches connected peers to current lobby members"""

    def __init__(self, lcu: LCU, state: SharedState):
        """Initialize lobby matcher

        Args:
            lcu: LCU client instance
            state: Shared application state
        """
        self.lcu = lcu
        self.state = state

    def get_lobby_summoner_ids(self) -> Set[int]:
        """Get summoner IDs from current lobby

        Returns:
            Set of summoner IDs in the lobby
        """
        summoner_ids = set()

        try:
            # Try lobby endpoint first (pre-game lobby)
            lobby_data = self.lcu.get("/lol-lobby/v2/lobby")
            if lobby_data and isinstance(lobby_data, dict):
                members = lobby_data.get("members", [])
                if isinstance(members, list):
                    for member in members:
                        if isinstance(member, dict):
                            summoner_id = member.get("summonerId")
                            if summoner_id:
                                summoner_ids.add(int(summoner_id))

                # Also check localMember
                local_member = lobby_data.get("localMember")
                if isinstance(local_member, dict):
                    summoner_id = local_member.get("summonerId")
                    if summoner_id:
                        summoner_ids.add(int(summoner_id))

        except Exception as e:
            log.debug(f"[LOBBY] Error getting lobby members: {e}")

        return summoner_ids

    def get_champ_select_summoner_ids(self) -> Set[int]:
        """Get summoner IDs from champion select

        Returns:
            Set of summoner IDs in champion select
        """
        summoner_ids = set()

        try:
            session = self.lcu.session
            if not session or not isinstance(session, dict):
                return summoner_ids

            # Get myTeam members
            my_team = session.get("myTeam", [])
            if isinstance(my_team, list):
                for player in my_team:
                    if isinstance(player, dict):
                        summoner_id = player.get("summonerId")
                        if summoner_id:
                            summoner_ids.add(int(summoner_id))

        except Exception as e:
            log.debug(f"[LOBBY] Error getting champ select members: {e}")

        return summoner_ids

    def get_all_summoner_ids(self) -> Set[int]:
        """Get summoner IDs from lobby or champion select

        Returns:
            Set of summoner IDs from current lobby/game
        """
        phase = self.state.phase

        if phase == "ChampSelect":
            return self.get_champ_select_summoner_ids()
        elif phase in ("Lobby", "Matchmaking", "ReadyCheck"):
            return self.get_lobby_summoner_ids()
        else:
            # Try both
            ids = self.get_lobby_summoner_ids()
            if not ids:
                ids = self.get_champ_select_summoner_ids()
            return ids

    def get_my_summoner_id(self) -> Optional[int]:
        """Get our own summoner ID

        Returns:
            Our summoner ID or None
        """
        try:
            summoner = self.lcu.current_summoner
            if summoner and isinstance(summoner, dict):
                summoner_id = summoner.get("summonerId")
                if summoner_id:
                    return int(summoner_id)
        except Exception as e:
            log.debug(f"[LOBBY] Error getting own summoner ID: {e}")

        return None

    def get_my_summoner_name(self) -> str:
        """Get our own summoner name

        Returns:
            Our summoner name or "Unknown"
        """
        try:
            summoner = self.lcu.current_summoner
            if summoner and isinstance(summoner, dict):
                # Try different name fields
                name = summoner.get("displayName")
                if not name:
                    name = summoner.get("gameName")
                if not name:
                    name = summoner.get("internalName")
                if name:
                    return str(name)
        except Exception as e:
            log.debug(f"[LOBBY] Error getting own summoner name: {e}")

        return "Unknown"

    def get_team_info(self) -> Tuple[Dict[int, int], Set[int]]:
        """Get our champion select team

        Returns:
            (summoner_id -> champion_id for players whose name is visible,
             every champion ID picked on our team). Both are empty outside
             champion select.
        """
        mapping = {}
        champions = set()

        try:
            session = self.lcu.session
            if not session or not isinstance(session, dict):
                return mapping, champions

            my_team = session.get("myTeam", [])
            if isinstance(my_team, list):
                for player in my_team:
                    if not isinstance(player, dict):
                        continue
                    champion_id = int(player.get("championId") or 0)
                    if not champion_id:
                        continue
                    champions.add(champion_id)
                    # Hidden names (anonymous champ select) report summonerId 0
                    summoner_id = int(player.get("summonerId") or 0)
                    if summoner_id:
                        mapping[summoner_id] = champion_id

        except Exception as e:
            log.debug(f"[LOBBY] Error getting team champions: {e}")

        return mapping, champions
