#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Injection Trigger
Handles triggering skin injection based on countdown timer
"""

import logging
import threading
import time
from typing import Optional

from config import BASE_SKIN_VERIFICATION_WAIT_S, LOG_SEPARATOR_WIDTH
from lcu import LCU
from state import SharedState
from utils.core.issue_reporter import report_issue
from utils.core.logging import get_logger, log_action
from utils.core.junction import is_junction, safe_remove_entry, link_or_extract
from utils.core.paths import get_injection_dir
from utils.core.utilities import is_default_skin
from injection.config.base_skin_tracker import start_tracking as _start_skin_tracking
from injection.loadingname.loading_name import build as build_loading_name, parse_skin_id

log = get_logger()


class InjectionTrigger:
    """Handles triggering skin injection"""
    
    def __init__(
        self,
        lcu: LCU,
        state: SharedState,
        injection_manager=None,
        skin_scraper=None,
    ):
        self.lcu = lcu
        self.state = state
        self.injection_manager = injection_manager
        self.skin_scraper = skin_scraper

    def _skin_matches_champion(self, skin_id: Optional[int], champion_id: Optional[int]) -> bool:
        if skin_id is None or champion_id is None:
            return True
        try:
            from utils.core.utilities import get_champion_id_from_skin_id
            return get_champion_id_from_skin_id(int(skin_id)) == int(champion_id)
        except (ValueError, TypeError):
            return True

    def trigger_injection(self, name: str, ticker_id: int, cname: str = ""):
        if not name:
            log.error("=" * LOG_SEPARATOR_WIDTH)
            log.error(f"INJECTION FAILED - NO SKIN ID AVAILABLE")
            log.error(f"   Loadout Timer: #{ticker_id}")
            log.error("=" * LOG_SEPARATOR_WIDTH)
            return
        
        self.state.last_hover_written = True

        ui_skin_id = self.state.last_hovered_skin_id
        locked_champ_id = self.state.locked_champ_id or self.state.hovered_champ_id

        historic_active = getattr(self.state, 'historic_mode_active', False)
        historic_skin_id = getattr(self.state, 'historic_skin_id', None)
        random_active = getattr(self.state, 'random_mode_active', False)
        random_skin_id = getattr(self.state, 'random_skin_id', None)
        selected_chroma_id = getattr(self.state, 'selected_chroma_id', None)

        effective_skin_id = None
        if historic_active and historic_skin_id is not None:
            try:
                from utils.core.historic import is_custom_mod_path
                if not is_custom_mod_path(historic_skin_id):
                    effective_skin_id = int(historic_skin_id)
            except (ValueError, TypeError):
                pass

        if effective_skin_id is None and random_active and random_skin_id is not None:
            try:
                effective_skin_id = int(random_skin_id)
            except (ValueError, TypeError):
                pass

        if effective_skin_id is None:
            effective_skin_id = ui_skin_id
            if selected_chroma_id and ui_skin_id:
                if selected_chroma_id > ui_skin_id and selected_chroma_id < ui_skin_id + 100:
                    effective_skin_id = selected_chroma_id
                    log.debug(f"[INJECT] Using selected chroma ID {selected_chroma_id} instead of base skin {ui_skin_id}")

        if effective_skin_id is None and name:
            try:
                if name.startswith("skin_") or name.startswith("chroma_"):
                    effective_skin_id = int(name.split("_", 1)[1])
            except (IndexError, ValueError):
                pass

        if ui_skin_id is None:
            ui_skin_id = effective_skin_id

        skin_to_validate = effective_skin_id if (historic_active or random_active) else ui_skin_id
        if not self._skin_matches_champion(skin_to_validate, locked_champ_id):
            log.warning(
                "[INJECT] Refusing to inject skin %s for champion %s: champion mismatch",
                skin_to_validate,
                locked_champ_id,
            )
            return

        self.state.last_hover_written = True
        selected_custom_mod = getattr(self.state, 'selected_custom_mod', None)
        mod_name = None
        if selected_custom_mod:
            mod_name = selected_custom_mod.get("mod_name") or selected_custom_mod.get("mod_folder_name")
        
        mod_labels = []
        if mod_name:
            mod_target_skin = selected_custom_mod.get("skin_id", ui_skin_id) if selected_custom_mod else ui_skin_id
            mod_labels.append(f"{mod_name} (SKIN_{mod_target_skin})")
        else:
            mod_labels.append(name.upper())
        
        selected_map_mod = getattr(self.state, 'selected_map_mod', None)
        if selected_map_mod:
            mod_labels.append(f"MAP: {selected_map_mod.get('mod_name', 'Map')}")
        
        selected_font_mod = getattr(self.state, 'selected_font_mod', None)
        if selected_font_mod:
            mod_labels.append(f"FONT: {selected_font_mod.get('mod_name', 'Font')}")
        
        selected_announcer_mod = getattr(self.state, 'selected_announcer_mod', None)
        if selected_announcer_mod:
            mod_labels.append(f"ANNOUNCER: {selected_announcer_mod.get('mod_name', 'Announcer')}")
        
        selected_other_mods = getattr(self.state, 'selected_other_mods', None)
        if not selected_other_mods:
            selected_other_mod = getattr(self.state, 'selected_other_mod', None)
            if selected_other_mod:
                selected_other_mods = [selected_other_mod]
        
        if selected_other_mods:
            other_names = [mod.get("mod_name", "Other") for mod in selected_other_mods]
            mod_labels.append(f"OTHER: {', '.join(other_names)}")
        
        injection_label = " + ".join(mod_labels)
        
        log.info("=" * LOG_SEPARATOR_WIDTH)
        log.info(f"PREPARING INJECTION >>> {injection_label} <<<")
        log.info(f"   Loadout Timer: #{ticker_id}")
        log.info("=" * LOG_SEPARATOR_WIDTH)
        
        try:
            lcu_skin_id = self.state.selected_skin_id
            owned_skin_ids = self.state.owned_skin_ids
            
            # Auto-select custom mod from history
            historic_custom_mod_path = None
            if not selected_custom_mod:
                try:
                    from utils.core.historic import get_historic_skin_for_champion, is_custom_mod_path, get_custom_mod_path
                    champ_id = self.state.locked_champ_id or self.state.hovered_champ_id
                    historic_value = get_historic_skin_for_champion(champ_id) if champ_id else None
                    if historic_value and is_custom_mod_path(historic_value):
                        historic_custom_mod_path = get_custom_mod_path(historic_value)

                    if historic_custom_mod_path:
                        path_parts = historic_custom_mod_path.replace("\\", "/").split("/")
                        if len(path_parts) >= 2 and path_parts[0] == "skins":
                            historic_skin_id = int(path_parts[1])
                            if ui_skin_id and historic_skin_id != int(ui_skin_id):
                                historic_custom_mod_path = None
                except Exception:
                    historic_custom_mod_path = None

            if not selected_custom_mod and historic_custom_mod_path:
                try:
                    from injection.mods.storage import ModStorageService
                    mod_storage = ModStorageService()
                    path_parts = historic_custom_mod_path.replace("\\", "/").split("/")
                    if len(path_parts) >= 2 and path_parts[0] == "skins":
                        historic_storage_skin_id = int(path_parts[1])
                        champ_id = self.state.locked_champ_id or self.state.hovered_champ_id
                        
                        entries = mod_storage.list_mods_for_champion(champ_id)
                        selected_mod_entry = None
                        for entry in entries:
                            try:
                                relative_path = str(entry.path.relative_to(mod_storage.mods_root)).replace("\\", "/")
                            except Exception:
                                continue
                            if relative_path.casefold() == historic_custom_mod_path.casefold():
                                selected_mod_entry = entry
                                break

                        if selected_mod_entry:
                            target_skin_ids = ModStorageService._get_entry_target_skin_ids(selected_mod_entry)
                            current_skin_id = ui_skin_id
                            
                            historic_target_skin_id = None
                            try:
                                from utils.core.historic import get_historic_target_for_champion
                                historic_target_skin_id = get_historic_target_for_champion(int(champ_id))
                            except Exception:
                                pass

                            target_skin_id = current_skin_id
                            if historic_target_skin_id in target_skin_ids:
                                target_skin_id = int(historic_target_skin_id)
                            elif current_skin_id is not None and target_skin_ids:
                                if current_skin_id not in target_skin_ids:
                                    target_skin_id = next(iter(sorted(target_skin_ids)), int(champ_id) * 1000)

                            mod_source = Path(selected_mod_entry.path)
                            mod_folder_name = mod_source.name if mod_source.is_dir() else mod_source.stem

                            self.state.selected_custom_mod = {
                                "skin_id": int(target_skin_id) if target_skin_id else historic_storage_skin_id,
                                "storage_skin_id": selected_mod_entry.skin_id,
                                "target_skin_ids": sorted(target_skin_ids),
                                "champion_id": champ_id,
                                "mod_name": selected_mod_entry.mod_name,
                                "display_name": selected_mod_entry.display_name,
                                "mod_path": str(selected_mod_entry.path),
                                "mod_folder_name": mod_folder_name,
                                "relative_path": historic_custom_mod_path,
                            }
                            selected_custom_mod = self.state.selected_custom_mod
                            log.info(f"[HISTORIC] Auto-selected saved custom mod: {selected_mod_entry.mod_name}")
                except Exception as e:
                    log.warning(f"[HISTORIC] Failed to auto-select saved custom mod: {e}")

            has_custom_skin_mod = bool(selected_custom_mod)
            target_skin_id = selected_custom_mod.get("skin_id", effective_skin_id or ui_skin_id) if selected_custom_mod else (effective_skin_id or ui_skin_id)
            has_other_mods = selected_map_mod or selected_font_mod or selected_announcer_mod or (selected_other_mods and len(selected_other_mods) > 0)
            
            if has_custom_skin_mod:
                is_skin_owned = target_skin_id in owned_skin_ids
                if not is_skin_owned:
                    log.info(f"[INJECT] Custom mod selected for unowned skin {target_skin_id}, injecting base skin ZIP + custom mod")
                    self._inject_custom_mod(selected_custom_mod, base_skin_name=name, champion_name=cname)
                else:
                    log.info(f"[INJECT] Custom mod selected for owned skin {target_skin_id}, injecting custom mod only")
                    self._inject_custom_mod(selected_custom_mod)
                return
            
            if has_other_mods and not has_custom_skin_mod:
                target_skin_id = effective_skin_id or ui_skin_id
                dummy_custom_mod = {
                    "skin_id": target_skin_id,
                    "champion_id": self.state.locked_champ_id or self.state.hovered_champ_id,
                    "mod_name": name.upper(),
                    "mod_folder_name": None,
                }
                
                is_default = target_skin_id is not None and is_default_skin(target_skin_id)
                is_skin_owned = target_skin_id is not None and (is_default or target_skin_id in (owned_skin_ids or set()))
                base_skin_name_for_injection = None
                
                if not is_skin_owned and target_skin_id != 0 and not is_default:
                    base_skin_name_for_injection = name
                    log.info(f"[INJECT] Other mod(s) selected + unowned skin {target_skin_id}, injecting base skin ZIP + other mod(s)")
                elif is_skin_owned and not is_default:
                    self._force_owned_skin(target_skin_id)
                
                self._inject_custom_mod(dummy_custom_mod, base_skin_name=base_skin_name_for_injection, champion_name=cname)
                return
            
            historic_active = getattr(self.state, 'historic_mode_active', False)
            random_active = getattr(self.state, 'random_mode_active', False)
            is_default = effective_skin_id is not None and is_default_skin(effective_skin_id)
            if is_default and not historic_active and not random_active:
                log.info(f"[INJECT] skipping injection for default skin (skinId={effective_skin_id}) - no mods selected")
                if self.injection_manager:
                    self.injection_manager.resume_if_suspended()
                return

            elif effective_skin_id in owned_skin_ids and not is_default:
                self._force_owned_skin(effective_skin_id)
                if self.injection_manager:
                    self.injection_manager.inject_skin_immediately(
                        name,
                        champion_name=cname,
                        champion_id=self.state.locked_champ_id or self.state.hovered_champ_id,
                        localized_name=self.state.last_hovered_skin_key,
                    )
            elif (ui_skin_id in owned_skin_ids and ui_skin_id < effective_skin_id < ui_skin_id + 100 and not is_default):
                self._force_owned_skin(effective_skin_id)
                if self.injection_manager:
                    self.injection_manager.inject_skin_immediately(
                        name,
                        champion_name=cname,
                        champion_id=self.state.locked_champ_id or self.state.hovered_champ_id,
                        localized_name=self.state.last_hovered_skin_key,
                    )
            elif self.injection_manager:
                self._inject_unowned_skin(name, cname)
        
        except Exception as e:
            log.warning(f"[loadout #{ticker_id}] injection setup failed: {e}")
    
    def _force_owned_skin(self, skin_id: int):
        log.info(f"[INJECT] User owns this skin/chroma (skinId={skin_id}), forcing selection via LCU")
        champ_id = self.state.locked_champ_id or self.state.hovered_champ_id
        if champ_id and self.lcu:
            target_skin_id = skin_id
            forced_successfully = False
            try:
                sess = self.lcu.session or {}
                actions = sess.get("actions") or []
                my_cell = self.state.local_cell_id
                
                for rnd in actions:
                    for act in rnd:
                        if act.get("actorCellId") == my_cell and act.get("type") == "pick":
                            action_id = act.get("id")
                            if not act.get("completed", False) and action_id is not None:
                                if self.lcu.set_selected_skin(action_id, target_skin_id):
                                    forced_successfully = True
                            break
                    if forced_successfully:
                        break
                
                if not forced_successfully:
                    forced_successfully = self.lcu.set_my_selection_skin(target_skin_id)
                
                if forced_successfully and not getattr(self.state, 'random_mode_active', False):
                    time.sleep(BASE_SKIN_VERIFICATION_WAIT_S)
            except Exception as e:
                log.warning(f"[INJECT] Error forcing owned skin: {e}")
            
            if self.injection_manager:
                try:
                    self.injection_manager.resume_if_suspended()
                except Exception:
                    pass
    
    def _inject_unowned_skin(self, name: str, cname: str):
        try:
            champ_id = self.state.locked_champ_id or self.state.hovered_champ_id
            if champ_id:
                base_skin_id = champ_id * 1000
                actual_lcu_skin_id = None
                try:
                    sess = self.lcu.session or {}
                    my_team = sess.get("myTeam") or []
                    my_cell = self.state.local_cell_id
                    for player in my_team:
                        if player.get("cellId") == my_cell:
                            actual_lcu_skin_id = player.get("selectedSkinId")
                            if actual_lcu_skin_id is not None:
                                actual_lcu_skin_id = int(actual_lcu_skin_id)
                            break
                except Exception:
                    pass
                
                if actual_lcu_skin_id is None or actual_lcu_skin_id != base_skin_id:
                    self._force_base_skin(base_skin_id)
            
            has_been_in_progress = False

            def game_ended_callback():
                nonlocal has_been_in_progress
                phase = self.state.phase
                if phase == "InProgress":
                    has_been_in_progress = True
                    return False
                if phase in ("Reconnect", "GameStart"):
                    return False
                return has_been_in_progress and phase not in ("InProgress", "Reconnect", "GameStart")
            
            log.info(f"[INJECT] Starting injection: {name}")
            champ_id_for_history = self.state.locked_champ_id
            
            # Безопасно достаем ID скина из переданного name (например "chroma_12345" -> 12345)
            current_id = None
            try:
                if name.startswith("skin_") or name.startswith("chroma_"):
                    current_id = int(name.split("_", 1)[1])
            except Exception:
                pass

            # Гарантированно получаем имя БАЗОВОГО скина для Loading Screen (без приписок хром)
            localized_name = self.state.last_hovered_skin_key
            
            if current_id and self.skin_scraper and self.skin_scraper.cache:
                base_skin_id_for_name = current_id
                chroma_id_map = getattr(self.skin_scraper.cache, "chroma_id_map", {})
                
                if current_id in chroma_id_map:
                    base_skin_id_for_name = chroma_id_map[current_id].get('skinId', current_id)
                    
                skin_data = self.skin_scraper.cache.get_skin_by_id(base_skin_id_for_name)
                if skin_data and skin_data.get('skinName'):
                    localized_name = skin_data.get('skinName')
                    
            log.info(f"[INJECT] Localized name for Loading Screen: {localized_name}")

            def run_injection():
                try:
                    if not self.lcu.ok:
                        return
                    
                    success = self.injection_manager.inject_skin_immediately(
                        name,
                        stop_callback=game_ended_callback,
                        champion_name=cname,
                        champion_id=self.state.locked_champ_id,
                        localized_name=localized_name,
                    )
                    
                    if getattr(self.state, 'random_mode_active', False):
                        self.state.random_skin_name = None
                        self.state.random_skin_id = None
                        self.state.random_mode_active = False

                    if success:
                        try:
                            injected_id = None
                            if isinstance(name, str) and '_' in name:
                                parts = name.split('_', 1)
                                if len(parts) == 2 and parts[1].isdigit():
                                    injected_id = int(parts[1])
                            champ_id = champ_id_for_history
                            if champ_id is not None and injected_id is not None:
                                from utils.core.historic import write_historic_entry
                                write_historic_entry(int(champ_id), int(injected_id))
                        except Exception:
                            pass
                except Exception as e:
                    log.error(f"[INJECT] injection thread error: {e}")
            
            threading.Thread(target=run_injection, daemon=True, name="InjectionThread").start()
        
        except Exception as e:
            log.error(f"[INJECT] injection error: {e}")
    
    def _force_base_skin(self, base_skin_id: int):
        log.info(f"[INJECT] Forcing base skin (skinId={base_skin_id})")
        if self.state.ui_skin_thread:
            self.state.ui_skin_thread._broadcast_skip_base_skin()

        try:
            from ui.core.user_interface import get_user_interface
            user_interface = get_user_interface(self.state, self.skin_scraper)
            if user_interface.is_ui_initialized():
                user_interface._schedule_hide_all_on_main_thread()
        except Exception:
            pass
        
        base_skin_set_successfully = False
        t_force0 = time.perf_counter()
        
        try:
            sess = self.lcu.session or {}
            actions = sess.get("actions") or []
            my_cell = self.state.local_cell_id
            
            for rnd in actions:
                for act in rnd:
                    if act.get("actorCellId") == my_cell and act.get("type") == "pick":
                        action_id = act.get("id")
                        if not act.get("completed", False) and action_id is not None:
                            if self.lcu.set_selected_skin(action_id, base_skin_id):
                                base_skin_set_successfully = True
                        break
                if base_skin_set_successfully:
                    break
            
            if not base_skin_set_successfully:
                base_skin_set_successfully = self.lcu.set_my_selection_skin(base_skin_id)

            if base_skin_set_successfully:
                _start_skin_tracking(base_skin_id)
                if not getattr(self.state, 'random_mode_active', False):
                    time.sleep(BASE_SKIN_VERIFICATION_WAIT_S)
        except Exception as e:
            log.error(f"[INJECT] Error forcing base skin: {e}")
    
    def _inject_custom_mod(self, custom_mod: dict, base_skin_name: Optional[str] = None, champion_name: str = ""):
        try:
            from pathlib import Path
            
            if not self.injection_manager or not self.injection_manager.injector:
                return
            
            injector = self.injection_manager.injector
            mod_name = custom_mod.get("mod_name")
            mod_folder_name = custom_mod.get("mod_folder_name")
            mod_path = custom_mod.get("mod_path")
            champion_id = custom_mod.get("champion_id") or self.state.locked_champ_id
            
            injector._clean_mods_dir()
            injector._clean_overlay_dir()

            if self.injection_manager and not self.injection_manager._monitor_active:
                self.injection_manager._start_monitor()

            mod_folder_names = []
            mod_names_list = []

            # 1. Извлекаем базовый скин (если скин не куплен) И генерируем Loading Name
            if base_skin_name:
                log.info(f"[INJECT] Extracting base skin ZIP: {base_skin_name}")
                try:
                    zp = injector._resolve_zip(
                        base_skin_name,
                        skin_name=base_skin_name,
                        champion_name=champion_name,
                        champion_id=champion_id
                    )
                    if zp and zp.exists():
                        base_mod_folder = injector._extract_zip_to_mod(zp)
                        if base_mod_folder:
                            mod_folder_names.append(base_mod_folder.name)
                            mod_names_list.append(f"Base Skin ({base_skin_name})")
                            
                            # === ГЕНЕРАЦИЯ LOADING NAME ДЛЯ МОДОВ ===
                            try:
                                loading_name_mod = build_loading_name(
                                    injector.game_dir,
                                    injector.mods_dir,
                                    base_mod_folder,
                                    parse_skin_id(base_skin_name, champion_id),
                                    localized_name=self.state.last_hovered_skin_key,
                                )
                                if loading_name_mod:
                                    mod_folder_names.append(loading_name_mod)
                                    log.info(f"[INJECT] Added loading screen name mod: {loading_name_mod}")
                            except Exception as e:
                                log.warning(f"[INJECT] Failed to build loading name mod: {e}")
                except Exception as e:
                    log.error(f"[INJECT] Error extracting base skin ZIP: {e}")

            # 2. Извлекаем кастомный скин
            if mod_folder_name and mod_path:
                try:
                    mod_source = Path(mod_path)
                    if mod_source.exists():
                        extract_cache_dir = get_injection_dir() / ".extract_cache"
                        mod_dest = injector.mods_dir / mod_folder_name
                        if mod_dest.exists() or is_junction(mod_dest):
                            safe_remove_entry(mod_dest)
                        link_or_extract(mod_source, mod_dest, cache_dir=extract_cache_dir)
                        if mod_dest.exists() or is_junction(mod_dest):
                            mod_folder_names.append(mod_folder_name)
                            mod_names_list.append(mod_name or "Custom Mod")
                except Exception as e:
                    log.error(f"[INJECT] Error re-extracting custom mod: {e}")

            # 3. Дополнительные моды (карты, шрифты, аннонсеры)
            def re_extract_mod(mod_dict, mod_type_name):
                if not mod_dict or not mod_dict.get("mod_folder_name") or not mod_dict.get("mod_path"):
                    return None
                try:
                    mod_source = Path(mod_dict["mod_path"])
                    if not mod_source.exists():
                        return None
                    extract_cache_dir = get_injection_dir() / ".extract_cache"
                    mod_dest = injector.mods_dir / mod_dict["mod_folder_name"]
                    if mod_dest.exists() or is_junction(mod_dest):
                        safe_remove_entry(mod_dest)
                    link_or_extract(mod_source, mod_dest, cache_dir=extract_cache_dir)
                    return mod_dict["mod_folder_name"]
                except Exception:
                    return None

            selected_map_mod = getattr(self.state, 'selectf# Top-level modulesed_map_mod', None)
            if selected_map_mod:
                folder = re_extract_mod(selected_map_mod, "Map")
                if folder:
                    mod_folder_names.append(folder)
                    mod_names_list.append(selected_map_mod.get("mod_name", "Map"))

            selected_font_mod = getattr(self.state, 'selected_font_mod', None)
            if selected_font_mod:
                folder = re_extract_mod(selected_font_mod, "Font")
                if folder:
                    mod_folder_names.append(folder)
                    mod_names_list.append(selected_font_mod.get("mod_name", "Font"))

            selected_announcer_mod = getattr(self.state, 'selected_announcer_mod', None)
            if selected_announcer_mod:
                folder = re_extract_mod(selected_announcer_mod, "Announcer")
                if folder:
                    mod_folder_names.append(folder)
                    mod_names_list.append(selected_announcer_mod.get("mod_name", "Announcer"))

            selected_other_mods = getattr(self.state, 'selected_other_mods', None)
            if selected_other_mods:
                for mod in selected_other_mods:
                    folder = re_extract_mod(mod, "Other")
                    if folder:
                        mod_folder_names.append(folder)
                        mod_names_list.append(mod.get("mod_name", "Other"))

            if not mod_folder_names:
                return

            if champion_id and base_skin_name:
                self._force_base_skin(champion_id * 1000)

            has_been_in_progress = False

            def game_ended_callback():
                nonlocal has_been_in_progress
                phase = self.state.phase
                if phase == "InProgress":
                    has_been_in_progress = True
                    return False
                if phase in ("Reconnect", "GameStart"):
                    return False
                return has_been_in_progress and phase not in ("InProgress", "Reconnect", "GameStart")

            try:
                from config import get_config_float
                user_timeout = int(get_config_float("General", "monitor_auto_resume_timeout", 120.0))
            except Exception:
                user_timeout = 120

            result = injector.overlay_manager.mk_run_overlay(
                mod_folder_names,
                timeout=user_timeout,
                stop_callback=game_ended_callback,
                injection_manager=self.injection_manager
            )

            if self.injection_manager:
                self.injection_manager._stop_monitor()

            if result == 0:
                log.info("=" * LOG_SEPARATOR_WIDTH)
                log.info(f"CUSTOM MOD INJECTION COMPLETED >>> {' + '.join([m.upper() for m in mod_names_list])} <<<")
                log.info("=" * LOG_SEPARATOR_WIDTH)
        except Exception as e:
            log.error(f"[INJECT] Error injecting custom mod: {e}")