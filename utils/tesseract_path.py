#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tesseract OCR path detection and configuration utilities
"""

import os
import sys
import platform
import shutil
from pathlib import Path
from typing import Optional, List, Tuple


def find_tesseract_executable() -> Optional[str]:
    """
    Find Tesseract executable on the system.
    
    Returns:
        Path to tesseract.exe if found, None otherwise
    """
    # Check if tesseract is in PATH
    tesseract_exe = shutil.which("tesseract")
    if tesseract_exe:
        return tesseract_exe
    
    # Common Windows installation paths (more comprehensive)
    if platform.system() == "Windows":
        username = os.getenv('USERNAME', '')
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(username),
            r"C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe".format(username),
            r"C:\Users\{}\AppData\Roaming\Tesseract-OCR\tesseract.exe".format(username),
            r"C:\Tesseract-OCR\tesseract.exe",
            r"C:\ProgramData\Tesseract-OCR\tesseract.exe",
        ]
        
        # Also check for portable installations
        for drive in ['C:', 'D:', 'E:']:
            common_paths.extend([
                f"{drive}\\Tesseract-OCR\\tesseract.exe",
                f"{drive}\\Program Files\\Tesseract-OCR\\tesseract.exe",
                f"{drive}\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
            ])
        
        for path in common_paths:
            if os.path.isfile(path):
                return path
    
    # Check common Unix paths
    elif platform.system() in ["Linux", "Darwin"]:
        common_paths = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",
            "/opt/local/bin/tesseract",
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                return path
    
    return None


def find_tessdata_directory(tesseract_exe: Optional[str] = None) -> Optional[str]:
    """
    Find the tessdata directory for Tesseract.
    
    Args:
        tesseract_exe: Path to tesseract executable (optional)
        
    Returns:
        Path to tessdata directory if found, None otherwise
    """
    # Check TESSDATA_PREFIX environment variable
    tessdata_prefix = os.environ.get("TESSDATA_PREFIX")
    if tessdata_prefix:
        # If it ends with tessdata, use it directly
        if tessdata_prefix.lower().endswith("tessdata"):
            if os.path.isdir(tessdata_prefix):
                return tessdata_prefix
        # Otherwise, check if tessdata subdirectory exists
        else:
            tessdata_path = os.path.join(tessdata_prefix, "tessdata")
            if os.path.isdir(tessdata_path):
                return tessdata_path
    
    # Try to determine from tesseract executable location
    if tesseract_exe:
        tesseract_dir = os.path.dirname(tesseract_exe)
        
        # Check tessdata in same directory as tesseract.exe
        tessdata_path = os.path.join(tesseract_dir, "tessdata")
        if os.path.isdir(tessdata_path):
            return tessdata_path
        
        # Check parent directory
        parent_dir = os.path.dirname(tesseract_dir)
        tessdata_path = os.path.join(parent_dir, "tessdata")
        if os.path.isdir(tessdata_path):
            return tessdata_path
        
        # Check sibling directories (for portable installations)
        for sibling in ["share", "tessdata"]:
            sibling_path = os.path.join(parent_dir, sibling)
            if os.path.isdir(sibling_path):
                if sibling == "tessdata":
                    return sibling_path
                else:
                    tessdata_in_sibling = os.path.join(sibling_path, "tessdata")
                    if os.path.isdir(tessdata_in_sibling):
                        return tessdata_in_sibling
    
    # Common Windows tessdata paths (more comprehensive)
    if platform.system() == "Windows":
        username = os.getenv('USERNAME', '')
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tessdata",
            r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
            r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tessdata".format(username),
            r"C:\Users\{}\AppData\Local\Tesseract-OCR\tessdata".format(username),
            r"C:\Users\{}\AppData\Roaming\Tesseract-OCR\tessdata".format(username),
            r"C:\Tesseract-OCR\tessdata",
            r"C:\ProgramData\Tesseract-OCR\tessdata",
        ]
        
        # Also check for portable installations
        for drive in ['C:', 'D:', 'E:']:
            common_paths.extend([
                f"{drive}\\Tesseract-OCR\\tessdata",
                f"{drive}\\Program Files\\Tesseract-OCR\\tessdata",
                f"{drive}\\Program Files (x86)\\Tesseract-OCR\\tessdata",
            ])
        
        for path in common_paths:
            if os.path.isdir(path):
                return path
    
    # Common Unix tessdata paths
    elif platform.system() in ["Linux", "Darwin"]:
        common_paths = [
            "/usr/share/tesseract-ocr/4.00/tessdata",
            "/usr/share/tesseract-ocr/5/tessdata",
            "/usr/share/tesseract-ocr/tessdata",
            "/usr/local/share/tesseract-ocr/tessdata",
            "/opt/homebrew/share/tesseract-ocr/5/tessdata",
            "/opt/homebrew/share/tesseract-ocr/tessdata",
        ]
        
        for path in common_paths:
            if os.path.isdir(path):
                return path
    
    return None


def validate_tesseract_installation(tesseract_exe: Optional[str] = None, tessdata_dir: Optional[str] = None) -> Tuple[bool, List[str]]:
    """
    Validate Tesseract installation and return detailed error messages.
    
    Args:
        tesseract_exe: Path to tesseract executable (optional)
        tessdata_dir: Path to tessdata directory (optional)
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []
    
    # Find tesseract executable if not provided
    if not tesseract_exe:
        tesseract_exe = find_tesseract_executable()
        if not tesseract_exe:
            errors.append("Tesseract executable not found. Please install Tesseract OCR.")
            errors.append("Download from: https://github.com/UB-Mannheim/tesseract/wiki")
            return False, errors
    
    # Validate tesseract executable
    if not os.path.isfile(tesseract_exe):
        errors.append(f"Tesseract executable not found at: {tesseract_exe}")
        return False, errors
    
    # Find tessdata directory if not provided
    if not tessdata_dir:
        tessdata_dir = find_tessdata_directory(tesseract_exe)
        if not tessdata_dir:
            errors.append("Tessdata directory not found.")
            errors.append("Try setting TESSDATA_PREFIX environment variable.")
            return False, errors
    
    # Validate tessdata directory
    if not os.path.isdir(tessdata_dir):
        errors.append(f"Tessdata directory not found at: {tessdata_dir}")
        return False, errors
    
    # Check for essential language files
    essential_files = ["eng.traineddata"]  # English is essential
    for file in essential_files:
        file_path = os.path.join(tessdata_dir, file)
        if not os.path.isfile(file_path):
            errors.append(f"Essential language file not found: {file}")
    
    if errors:
        return False, errors
    
    return True, []


def get_tesseract_configuration() -> dict:
    """
    Get complete Tesseract configuration including paths and validation.
    
    Returns:
        Dictionary with configuration details
    """
    tesseract_exe = find_tesseract_executable()
    tessdata_dir = find_tessdata_directory(tesseract_exe)
    
    # Auto-configure TESSDATA_PREFIX if we found a valid tessdata directory
    if tessdata_dir and os.path.isdir(tessdata_dir):
        # Temporarily set the environment variable for this session
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
    
    is_valid, errors = validate_tesseract_installation(tesseract_exe, tessdata_dir)
    
    return {
        "tesseract_exe": tesseract_exe,
        "tessdata_dir": tessdata_dir,
        "is_valid": is_valid,
        "errors": errors,
        "platform": platform.system(),
        "environment": {
            "TESSDATA_PREFIX": os.environ.get("TESSDATA_PREFIX"),
            "PATH": os.environ.get("PATH", "").split(os.pathsep)[:5],  # First 5 PATH entries
        }
    }


def print_installation_guide():
    """Print detailed installation guide for Tesseract OCR."""
    print("\n" + "="*60)
    print("TESSERACT OCR INSTALLATION GUIDE")
    print("="*60)
    
    config = get_tesseract_configuration()
    
    if config["is_valid"]:
        print("[OK] Tesseract OCR is properly installed!")
        print(f"   Executable: {config['tesseract_exe']}")
        print(f"   Tessdata: {config['tessdata_dir']}")
    else:
        print("[ERROR] Tesseract OCR installation issues detected:")
        for error in config["errors"]:
            print(f"   - {error}")
        
        print("\nINSTALLATION STEPS:")
        
        if platform.system() == "Windows":
            print("1. Download Tesseract for Windows:")
            print("   https://github.com/UB-Mannheim/tesseract/wiki")
            print("2. Run the installer (choose 'Additional language data' during installation)")
            print("3. Add Tesseract to your PATH:")
            print("   - Add 'C:\\Program Files\\Tesseract-OCR' to your system PATH")
            print("4. Set TESSDATA_PREFIX environment variable:")
            print("   - Set TESSDATA_PREFIX=C:\\Program Files\\Tesseract-OCR\\tessdata")
            print("5. Restart your command prompt/IDE")
        
        elif platform.system() == "Linux":
            print("1. Install via package manager:")
            print("   sudo apt-get install tesseract-ocr tesseract-ocr-eng")
            print("2. For additional languages:")
            print("   sudo apt-get install tesseract-ocr-[lang-code]")
        
        elif platform.system() == "Darwin":  # macOS
            print("1. Install via Homebrew:")
            print("   brew install tesseract")
            print("2. For additional languages:")
            print("   brew install tesseract-lang")
        
        print("\nTROUBLESHOOTING:")
        print("- Verify installation: tesseract --version")
        print("- Check tessdata files in: tesseract --list-langs")
        print("- Environment variables:")
        print(f"  TESSDATA_PREFIX: {config['environment']['TESSDATA_PREFIX'] or 'Not set'}")
        print("  PATH (first 5 entries):")
        for path in config["environment"]["PATH"]:
            print(f"    - {path}")
    
    print("="*60)


if __name__ == "__main__":
    print_installation_guide()
