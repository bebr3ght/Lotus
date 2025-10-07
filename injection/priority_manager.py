#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Process Priority Management
Lowers injection process priority to increase CPU contention and slow game opening
"""

import psutil
import subprocess
from typing import Optional
from utils.logging import get_logger

log = get_logger()


class PriorityManager:
    """Manages process priorities to control CPU contention"""
    
    @staticmethod
    def lower_process_priority(proc: subprocess.Popen) -> bool:
        """
        Lower a subprocess priority to below normal
        
        This makes injection processes use less CPU, allowing game to open faster
        OR can be used to slow down game opening by making injection higher priority
        """
        try:
            p = psutil.Process(proc.pid)
            # Set to BELOW_NORMAL priority (lower than game)
            # On Windows: BELOW_NORMAL_PRIORITY_CLASS
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            log.debug(f"[Priority] Lowered process priority (PID={proc.pid})")
            return True
        except Exception as e:
            log.warning(f"[Priority] Failed to lower process priority: {e}")
            return False
    
    @staticmethod
    def raise_process_priority(proc: subprocess.Popen) -> bool:
        """
        Raise a subprocess priority to above normal
        
        This makes injection processes use MORE CPU, competing with game opening
        """
        try:
            p = psutil.Process(proc.pid)
            # Set to ABOVE_NORMAL priority (higher than game)
            p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            log.debug(f"[Priority] Raised process priority (PID={proc.pid})")
            return True
        except Exception as e:
            log.warning(f"[Priority] Failed to raise process priority: {e}")
            return False
    
    @staticmethod
    def maximize_cpu_contention() -> bool:
        """
        Maximize CPU contention during injection to slow game opening
        
        Strategy:
        - Set injection processes to HIGH priority
        - Game will get less CPU time
        - Game opening slows down naturally
        """
        try:
            # Find all mkoverlay/mod-tools processes
            current_pid = psutil.Process().pid
            
            for proc in psutil.process_iter(['name', 'pid']):
                name = proc.info['name'].lower()
                if 'mkoverlay' in name or 'mod-tools' in name or 'wad-' in name:
                    try:
                        p = psutil.Process(proc.info['pid'])
                        p.nice(psutil.HIGH_PRIORITY_CLASS)
                        log.info(f"[Priority] Set HIGH priority for {name} (PID={proc.info['pid']})")
                    except Exception as e:
                        log.debug(f"[Priority] Could not set priority for {name}: {e}")
            
            return True
        except Exception as e:
            log.error(f"[Priority] Failed to maximize CPU contention: {e}")
            return False

