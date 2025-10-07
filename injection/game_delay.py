#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Game Launch Delay System
Provides mechanism to delay game client opening during late injection
"""

import time
import psutil
from typing import Optional
from utils.logging import get_logger

log = get_logger()


class GameDelayManager:
    """Manages delaying game client opening during injection"""
    
    def __init__(self):
        self.suspended_process = None
        self.delay_active = False
    
    def find_game_process(self) -> Optional[psutil.Process]:
        """Find the League of Legends game process"""
        try:
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'] in ['League of Legends.exe', 'LeagueClient.exe']:
                    return proc
        except Exception as e:
            log.error(f"[GameDelay] Error finding game process: {e}")
        return None
    
    def suspend_game(self, max_delay: float = 5.0) -> bool:
        """
        Suspend game process to delay opening
        
        Args:
            max_delay: Maximum time to keep suspended (seconds)
        
        Returns:
            True if successfully suspended
        """
        try:
            proc = self.find_game_process()
            if not proc:
                log.warning("[GameDelay] Game process not found, cannot suspend")
                return False
            
            log.info(f"[GameDelay] Suspending game process (PID={proc.pid}) for up to {max_delay}s")
            proc.suspend()
            self.suspended_process = proc
            self.delay_active = True
            
            # Auto-resume after max_delay as safety
            time.sleep(max_delay)
            if self.delay_active:
                self.resume_game()
            
            return True
            
        except Exception as e:
            log.error(f"[GameDelay] Failed to suspend game: {e}")
            return False
    
    def resume_game(self):
        """Resume suspended game process"""
        if not self.suspended_process or not self.delay_active:
            return
        
        try:
            log.info(f"[GameDelay] Resuming game process (PID={self.suspended_process.pid})")
            self.suspended_process.resume()
            self.delay_active = False
            self.suspended_process = None
        except Exception as e:
            log.error(f"[GameDelay] Failed to resume game: {e}")
    
    def delay_game_for_injection(self, injection_callback, estimated_time: float = 3.0):
        """
        Delay game opening while injection completes
        
        Args:
            injection_callback: Function to call that performs injection
            estimated_time: Estimated injection time (seconds)
        """
        import threading
        
        # Start suspension in background
        def suspend_loop():
            time.sleep(0.5)  # Give game a moment to start
            self.suspend_game(max_delay=estimated_time + 1.0)
        
        suspend_thread = threading.Thread(target=suspend_loop, daemon=True)
        suspend_thread.start()
        
        # Perform injection
        try:
            injection_callback()
        finally:
            # Resume game after injection
            self.resume_game()

