#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LCU API Request Handler
Handles HTTP requests to LCU API
"""

from typing import Any, Optional

import copy
import threading
import time
import requests

from config import LCU_GET_CACHE_TTL_S
from utils.core.logging import get_logger

log = get_logger()

_CACHE_MISS = object()

#: Returned by :meth:`LCUAPI.get` for 404/405 when the caller asked for it,
#: so "the client does not expose this endpoint" is distinguishable from
#: "the request failed".
LCU_ENDPOINT_ABSENT = object()


class LCUAPI:
    """Handles HTTP requests to LCU API"""

    def __init__(self, connection):
        """Initialize API handler

        Args:
            connection: LCUConnection instance
        """
        self.connection = connection
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()

    def _cache_get(self, path: str, now: float) -> Any:
        with self._cache_lock:
            entry = self._cache.get(path)
            if entry is None:
                return _CACHE_MISS
            expiry, value = entry
            if expiry <= now:
                self._cache.pop(path, None)
                return _CACHE_MISS
            # Hand out a private copy: callers edit what they get (e.g. Swiftplay
            # rewrites playerSlots[*].skinId), and mutating the cached object made
            # every other reader of that endpoint inside the TTL see the edit.
            return copy.deepcopy(value)

    def _cache_put(self, path: str, value: Any, ttl: float) -> None:
        if ttl <= 0:
            return
        with self._cache_lock:
            self._cache[path] = (time.monotonic() + ttl, copy.deepcopy(value))

    def invalidate(self, path_prefix: str = "") -> None:
        """Invalidate cached GET responses.

        Clears any cache entry whose path starts with ``path_prefix`` AND any
        ancestor of ``path_prefix`` (since a PATCH/PUT on a child resource
        logically mutates its parents too). Passing an empty string clears the
        entire cache.
        """
        with self._cache_lock:
            if not path_prefix:
                self._cache.clear()
                return
            ancestors = set()
            segments = path_prefix.rstrip("/").split("/")
            for i in range(1, len(segments)):
                ancestor = "/".join(segments[:i])
                if ancestor:
                    ancestors.add(ancestor)
            for key in list(self._cache):
                if key.startswith(path_prefix) or key in ancestors:
                    self._cache.pop(key, None)

    def get(self, path: str, timeout: float = 1.0,
            cache_ttl: Optional[float] = None, use_cache: bool = True,
            absent_sentinel: bool = False) -> Optional[dict]:
        """Make GET request to LCU API.

        Responses are cached for ``cache_ttl`` seconds (default
        ``LCU_GET_CACHE_TTL_S``) to de-duplicate bursty polls from multiple
        threads hitting the same endpoint. Pass ``use_cache=False`` to bypass.

        An endpoint the client does not expose answers 404/405. That is normally
        folded into ``None``, which hides "this build has no such endpoint" behind
        "the client is down". Pass ``absent_sentinel=True`` to get
        ``LCU_ENDPOINT_ABSENT`` for those instead, and keep ``None`` for real
        transport failures.

        Args:
            path: API endpoint path
            timeout: Request timeout in seconds
            cache_ttl: Override cache TTL in seconds (<= 0 disables caching for
                this call)
            use_cache: If False, skip the cache entirely (neither read nor write)

        Returns:
            JSON response as dict, or None if failed
        """
        ttl = LCU_GET_CACHE_TTL_S if cache_ttl is None else cache_ttl

        if use_cache and ttl > 0:
            cached = self._cache_get(path, time.monotonic())
            if cached is not _CACHE_MISS:
                return cached

        if not self.connection.ok:
            self.connection.refresh_if_needed()
        target = self.connection.request_target()
        if target is None:
            return None
        base, session = target

        def _store(value):
            if use_cache:
                self._cache_put(path, value, ttl)
            return value

        try:
            r = session.get(base + path, timeout=timeout)
            if r.status_code in (404, 405):
                return _store(LCU_ENDPOINT_ABSENT if absent_sentinel else None)
            r.raise_for_status()
            try:
                return _store(r.json())
            except (ValueError, requests.exceptions.JSONDecodeError) as e:
                # A body that is not JSON is not an answer: caching it would make
                # every reader inside the TTL see "no data" for a working endpoint.
                log.debug(f"Failed to decode JSON response for {path}: {e}")
                return None
        except requests.exceptions.RequestException:
            self.connection.refresh_if_needed(force=True)
            target = self.connection.request_target()
            if target is None:
                return None
            base, session = target
            try:
                r = session.get(base + path, timeout=timeout)
                if r.status_code in (404, 405):
                    return _store(LCU_ENDPOINT_ABSENT if absent_sentinel else None)
                r.raise_for_status()
                return _store(r.json())
            except (ValueError, requests.exceptions.JSONDecodeError) as e:
                log.debug(f"Failed to decode JSON response for {path} after reconnecting: {e}")
                return None
            except requests.exceptions.RequestException as e:
                log.debug(f"[LCU] GET {path} failed after reconnecting: {e}")
                return None
    
    def put(self, path: str, json_data, timeout: float, headers: Optional[dict] = None) -> Optional[requests.Response]:
        """Make PUT request to LCU API

        Args:
            path: API endpoint path
            json_data: JSON-serializable data to send (dict or list)
            timeout: Request timeout in seconds
            headers: Optional extra headers to merge into the request

        Returns:
            Response object or None if failed
        """
        if not self.connection.ok:
            self.connection.refresh_if_needed()
            if not self.connection.ok:
                return None

        target = self.connection.request_target()
        if target is None:
            return None
        base, session = target
        url = base + path
        self.invalidate(path)

        try:
            t0 = time.perf_counter()
            resp = session.put(
                url,
                json=json_data,
                timeout=timeout,
                headers=headers,
            )
            dt_ms = (time.perf_counter() - t0) * 1000.0
            log.info(f"[LCU] PUT {path} -> {getattr(resp, 'status_code', 'None')} in {dt_ms:.1f}ms")
            return resp
        except requests.exceptions.RequestException as exc:
            # A transport failure may or may not have reached the client, but it is
            # the only kind worth replaying: a serialise error or a decode failure
            # says nothing about the connection and would repeat the write blind.
            log.warning(f"[LCU] PUT {path} failed ({type(exc).__name__}): {exc}")
            self.connection.refresh_if_needed(force=True)
            retry_target = self.connection.request_target()
            if retry_target is None:
                log.warning(f"[LCU] PUT {path} - connection lost after refresh")
                return None
            retry_base, retry_session = retry_target
            try:
                t0 = time.perf_counter()
                resp = retry_session.put(
                    retry_base + path,
                    json=json_data,
                    timeout=timeout,
                    headers=headers,
                )
                dt_ms = (time.perf_counter() - t0) * 1000.0
                log.info(f"[LCU] PUT(retry) {path} -> {getattr(resp, 'status_code', 'None')} in {dt_ms:.1f}ms")
                return resp
            except requests.exceptions.RequestException as exc2:
                log.warning(f"[LCU] PUT(retry) {path} also failed ({type(exc2).__name__}): {exc2}")
                return None
        except Exception as exc:
            # Never replay a non-idempotent write that failed for a local reason
            log.warning(f"[LCU] PUT {path} failed before reaching the client ({type(exc).__name__}): {exc}")
            return None

    def patch(self, path: str, json_data: dict, timeout: float) -> Optional[requests.Response]:
        """Make PATCH request to LCU API
        
        Args:
            path: API endpoint path
            json_data: JSON data to send
            timeout: Request timeout in seconds
            
        Returns:
            Response object or None if failed
        """
        if not self.connection.ok:
            self.connection.refresh_if_needed()
        target = self.connection.request_target()
        if target is None:
            return None
        base, session = target

        self.invalidate(path)

        try:
            t0 = time.perf_counter()
            resp = session.patch(
                base + path,
                json=json_data,
                timeout=timeout,
            )
            dt_ms = (time.perf_counter() - t0) * 1000.0
            try:
                log.debug(f"[LCU] PATCH {path} -> {getattr(resp, 'status_code', 'None')} in {dt_ms:.1f}ms")
            except Exception:
                pass
            return resp
        except requests.exceptions.RequestException:
            self.connection.refresh_if_needed(force=True)
            retry_target = self.connection.request_target()
            if retry_target is None:
                return None
            retry_base, retry_session = retry_target
            try:
                t0 = time.perf_counter()
                resp = retry_session.patch(
                    retry_base + path,
                    json=json_data,
                    timeout=timeout,
                )
                dt_ms = (time.perf_counter() - t0) * 1000.0
                try:
                    log.debug(f"[LCU] PATCH(retry) {path} -> {getattr(resp, 'status_code', 'None')} in {dt_ms:.1f}ms")
                except Exception:
                    pass
                return resp
            except requests.exceptions.RequestException as e:
                log.debug(f"[LCU] PATCH {path} failed after reconnecting: {e}")
                return None

