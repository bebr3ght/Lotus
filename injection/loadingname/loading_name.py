#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loading screen name
Builds a mod that makes the loading screen print the injected skin's name instead of the champion's.
"""

import json
import struct
import re
from pathlib import Path
from typing import List, Optional, Tuple

from utils.core.logging import get_logger

log = get_logger()

try:
    import zstandard
    log.info("[LOADNAME] zstandard module imported successfully")
except ImportError as e:
    log.error(f"[LOADNAME] Failed to import zstandard: {e}")
    zstandard = None

MOD_FOLDER = "ROSE-LoadingName"
RST_MASK = (1 << 38) - 1
_ZSTD_WARNED = False


def _language_wads(game_dir: Path) -> List[Path]:
    localized = Path(game_dir) / "DATA" / "FINAL" / "Localized"
    wads = sorted(localized.glob("Global.*.wad.client")) if localized.is_dir() else []
    log.info(f"[LOADNAME] Found {len(wads)} language WADs in {localized}")
    return wads


def _unzstd(chunk: bytes, size: int, single_frame: bool) -> Optional[bytes]:
    global _ZSTD_WARNED
    try:
        from compression.zstd import decompress
        return decompress(chunk)
    except ImportError:
        pass

    if zstandard is None:
        if not _ZSTD_WARNED:
            log.warning("[LOADNAME] zstandard module is not available, skipping loading screen name decompression")
            _ZSTD_WARNED = True
        return None

    try:
        if single_frame:
            return zstandard.ZstdDecompressor().decompress(chunk, max_output_size=size)
        import io
        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(chunk), read_across_frames=True) as reader:
            return reader.read(size)
    except Exception as exc:
        log.error(f"[LOADNAME] zstd decompression error: {exc}")
        return None


def _read_table(wad: Path) -> Optional[bytes]:
    """The lol.stringtable entry of a wad, decompressed."""
    try:
        data = wad.read_bytes()
    except OSError as e:
        log.error(f"[LOADNAME] Failed to read WAD {wad.name}: {e}")
        return None
        
    if len(data) < 272 or data[:2] != b"RW" or data[2] != 3:
        log.warning(f"[LOADNAME] {wad.name}: unsupported wad version or invalid signature")
        return None
        
    count = struct.unpack_from("<I", data, 268)[0]
    for i in range(count):
        at = 272 + i * 32
        if at + 32 > len(data):
            break
        path_hash, offset, packed, size = struct.unpack_from("<QIII", data, at)
        kind = data[at + 20] & 0xF
        chunk = None
        if kind == 0:
            chunk = data[offset:offset + size]
        elif kind in (3, 4):
            chunk = _unzstd(data[offset:offset + packed], size, single_frame=kind == 3)

        # RST v2 - v5 signatures
        if chunk and len(chunk) >= 4 and chunk[:3] == b"RST" and chunk[3] in (2, 3, 4, 5):
            return chunk
            
    log.warning(f"[LOADNAME] No valid RST stringtable found in {wad.name}")
    return None


def _entries(table: bytes) -> Tuple[int, int]:
    count = struct.unpack_from("<I", table, 4)[0]
    return count, 8 + count * 8


def _text_of(table: bytes, key_hash: int) -> Optional[str]:
    count, text_start = _entries(table)
    for i in range(count):
        entry = struct.unpack_from("<Q", table, 8 + i * 8)[0]
        if entry & RST_MASK != key_hash:
            continue
        at = text_start + (entry >> 38)
        end = table.find(b"\0", at)
        if end == -1:
            end = len(table)
        return table[at:end].decode("utf-8", "replace")
    return None


def _with_text(table: bytes, key_hash: int, text: str) -> bytes:
    count, text_start = _entries(table)
    entries = [struct.unpack_from("<Q", table, 8 + i * 8)[0] for i in range(count)]
    added = text.encode("utf-8") + b"\0"
    entry = key_hash | ((len(table) - text_start) << 38)

    for i, existing in enumerate(entries):
        if existing & RST_MASK == key_hash:
            entries[i] = entry
            break
    else:
        entries.append(entry)
        entries.sort(key=lambda e: e & RST_MASK)

    out = bytearray(table[:4])
    out += struct.pack("<I", len(entries))
    for e in entries:
        out += struct.pack("<Q", e)
    out += table[text_start:]
    out += added
    return bytes(out)


_SECRET = bytes.fromhex(
    "b8fe6c3923a44bbe7c01812cf721ad1cded46de9839097db7240a4a4b7b3671f"
    "cb79e64eccc0e578825ad07dccff7221b8084674f743248ee03590e6813a264c"
    "3c2852bb91c300cb88d0658b1b532ea371644897a20df94e3819ef46a9deacd8"
    "a8fa763fe39c343ff9dcbbc7c70b4f1d8a51e04bcdb45931c89f7ec9d9787364"
)
_U64 = (1 << 64) - 1


def _u64(v: int) -> int:
    return v & _U64


def _read64(data: bytes, at: int) -> int:
    return struct.unpack_from("<Q", data, at)[0]


def _mul_fold(a: int, b: int) -> int:
    product = a * b
    return _u64(product) ^ (product >> 64)


def _mix16(data: bytes, at: int, secret_at: int) -> int:
    return _mul_fold(_read64(data, at) ^ _read64(_SECRET, secret_at),
                     _read64(data, at + 8) ^ _read64(_SECRET, secret_at + 8))


def _xxh3_64(data: bytes) -> int:
    size = len(data)
    if not 17 <= size <= 128:
        raise ValueError("xxh3: only 17 to 128 bytes are supported here")
    acc = _u64(size * 0x9E3779B185EBCA87)
    if size > 32:
        if size > 64:
            if size > 96:
                acc += _mix16(data, 48, 96) + _mix16(data, size - 64, 112)
            acc += _mix16(data, 32, 64) + _mix16(data, size - 48, 80)
        acc += _mix16(data, 16, 32) + _mix16(data, size - 32, 48)
    acc = _u64(acc + _mix16(data, 0, 0) + _mix16(data, size - 16, 16))
    acc ^= acc >> 37
    acc = _u64(acc * 0x165667919E3779F9)
    return acc ^ (acc >> 32)


def _key_hash(key: str) -> int:
    return _xxh3_64(key.lower().encode("utf-8")) & RST_MASK


def champion_aliases(mod_folder: Path) -> List[str]:
    wad_dir = Path(mod_folder) / "WAD"
    if not wad_dir.is_dir():
        log.warning(f"[LOADNAME] No WAD directory found in {mod_folder}")
        return []
    aliases = []
    for wad in wad_dir.iterdir():
        name = wad.name
        if not name.lower().endswith(".wad.client"):
            continue
        alias = name[: -len(".wad.client")].split(".")[0]
        if alias.lower() != "global" and alias not in aliases:
            aliases.append(alias)
    log.info(f"[LOADNAME] Extracted champion aliases from WADs: {aliases}")
    return aliases


def parse_skin_id(skin_name: str, champion_id: Optional[int] = None) -> int:
    for token in reversed(str(skin_name or "").replace("_", " ").split()):
        if not token.isdigit():
            continue
        value = int(token)
        if value < 1000:
            continue
        if champion_id and value // 1000 != int(champion_id):
            continue
        return value
    return 0


def build(game_dir: Path, mods_dir: Path, mod_folder: Path, skin_id: int, localized_name: Optional[str] = None) -> Optional[str]:
    try:
        log.info(f"[LOADNAME] Starting build for skin_id={skin_id}, localized_name='{localized_name}'")
        if not skin_id or skin_id % 1000 == 0:
            log.info("[LOADNAME] Base skin or invalid ID, skipping.")
            return None
            
        aliases = champion_aliases(mod_folder)
        if not aliases:
            log.debug("[LOADNAME] The skin carries no champion wad, skipped")
            return None

        wads = _language_wads(Path(game_dir))
        if not wads:
            log.debug("[LOADNAME] No language wad in the game folder, skipped")
            return None

        clean_localized_name = None
        if localized_name:
            clean_localized_name = re.sub(r'\s+\d+$', '', str(localized_name)).strip()
            log.info(f"[LOADNAME] Cleaned localized name to use as fallback: '{clean_localized_name}'")

        built = False
        target = Path(mods_dir) / MOD_FOLDER

        for wad in wads:
            table = _read_table(wad)
            if not table:
                continue

            for alias in aliases:
                name_key = f"game_character_skin_displayname_{alias}_{skin_id % 1000}"
                
                # Приоритет отдаем переданному чистому имени базового скина
                if clean_localized_name:
                    name = clean_localized_name
                    log.info(f"[LOADNAME] Using provided localized name: '{name}'")
                else:
                    # Если его почему-то нет, только тогда лезем в файлы игры
                    name = _text_of(table, _key_hash(name_key))
                    if name:
                        log.info(f"[LOADNAME] Found name in stringtable: '{name}'")
                
                if not name:
                    log.warning(f"[LOADNAME] Could not find name for {name_key} and no fallback provided")
                    continue

                champion_key = _key_hash(f"game_character_displayname_{alias}")
                if _text_of(table, champion_key) is None:
                    log.warning(f"[LOADNAME] Champion key {champion_key} not found in stringtable for {alias}")
                    continue

                # КРИТИЧЕСКИЙ ФИКС ИЗ PR: Путь ВСЕГДА en_US внутри WAD, независимо от языка игры!
                table_rel_path = Path("RAW") / "DATA" / "Menu" / "en_US" / "lol.stringtable"
                
                (target / table_rel_path.parent).mkdir(parents=True, exist_ok=True)
                (target / "META").mkdir(parents=True, exist_ok=True)
                (target / "META" / "info.json").write_text(json.dumps({
                    "Author": "Rose",
                    "Description": name,
                    "Name": "Loading screen name",
                    "Version": "1.0.0",
                }), encoding="utf-8")
                
                (target / table_rel_path).write_bytes(_with_text(table, champion_key, name))
                log.info(f"[LOADNAME] Success! The loading screen will show '{name}'")
                built = True
                break # Break aliases loop, go to next WAD
                
        if built:
            return MOD_FOLDER

        log.warning(f"[LOADNAME] Failed to build mod for skin {skin_id}")
        return None
    except Exception as e:
        log.error(f"[LOADNAME] Fatal error during build: {e}", exc_info=True)
        return None