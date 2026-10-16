#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Party Mode Message Types
Protocol message definitions for P2P communication
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class SkinSelection:
    """Skin selection data for a single champion"""

    summoner_id: int
    summoner_name: str
    champion_id: int
    skin_id: int
    chroma_id: Optional[int] = None
    custom_mod_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for message payload"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkinSelection":
        """Create from dictionary"""
        return cls(
            summoner_id=data["summoner_id"],
            summoner_name=data.get("summoner_name", "Unknown"),
            champion_id=data["champion_id"],
            skin_id=data["skin_id"],
            chroma_id=data.get("chroma_id"),
            custom_mod_path=data.get("custom_mod_path"),
        )
