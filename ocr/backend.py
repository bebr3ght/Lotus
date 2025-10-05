#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR backend implementation
"""

import os
from typing import Optional
import numpy as np
import cv2
from utils.tesseract_path import get_tesseract_configuration, validate_tesseract_installation, print_installation_guide


class OCR:
    """OCR backend using tesserocr"""
    
    def __init__(self, lang: str = "eng", psm: int = 7, tesseract_exe: Optional[str] = None):
        self.lang = lang
        self.psm = int(psm)
        self.backend = None
        self.api = None
        self.tessdata_dir = None
        
        try:
            from tesserocr import PyTessBaseAPI, PSM  # pyright: ignore[reportMissingImports]
            
            # Get Tesseract configuration with automatic path detection
            config = get_tesseract_configuration()
            
            # Use provided tessdata_dir if available, otherwise use auto-detected
            tessdata_dir = getattr(self, "tessdata_dir", None)
            if not tessdata_dir:
                tessdata_dir = config["tessdata_dir"]
            
            # Ensure tessdata_dir ends with 'tessdata' and exists
            if tessdata_dir and not tessdata_dir.lower().endswith("tessdata"):
                cand = os.path.join(tessdata_dir, "tessdata")
                if os.path.isdir(cand):
                    tessdata_dir = cand
            
            self.tessdata_dir = tessdata_dir
            psm_mode = PSM.SINGLE_LINE if self.psm == 7 else PSM.AUTO
            
            # Try multiple initialization strategies
            api_initialized = False
            
            # Strategy 1: Use detected tessdata path if valid
            if tessdata_dir and os.path.isdir(tessdata_dir):
                try:
                    self.api = PyTessBaseAPI(path=tessdata_dir, lang=self.lang, psm=psm_mode)
                    api_initialized = True
                except Exception:
                    pass  # Try next strategy
            
            # Strategy 2: Try with tesseract executable directory
            if not api_initialized and config.get("tesseract_exe"):
                tesseract_dir = os.path.dirname(config["tesseract_exe"])
                tessdata_candidates = [
                    os.path.join(tesseract_dir, "tessdata"),
                    os.path.join(os.path.dirname(tesseract_dir), "tessdata")
                ]
                
                for candidate in tessdata_candidates:
                    if os.path.isdir(candidate):
                        try:
                            self.api = PyTessBaseAPI(path=candidate, lang=self.lang, psm=psm_mode)
                            api_initialized = True
                            break
                        except Exception:
                            continue
            
            # Strategy 3: Try without path (let tesseract find it)
            if not api_initialized:
                try:
                    self.api = PyTessBaseAPI(lang=self.lang, psm=psm_mode)
                    api_initialized = True
                except Exception:
                    pass
            
            # Strategy 4: Try with environment variable
            if not api_initialized:
                env_tessdata = os.environ.get("TESSDATA_PREFIX")
                if env_tessdata and os.path.isdir(env_tessdata):
                    try:
                        self.api = PyTessBaseAPI(path=env_tessdata, lang=self.lang, psm=psm_mode)
                        api_initialized = True
                    except Exception:
                        pass
            
            if not api_initialized:
                # Last resort: try with minimal configuration
                try:
                    # Set environment variable temporarily if we found tessdata
                    if tessdata_dir and os.path.isdir(tessdata_dir):
                        old_env = os.environ.get("TESSDATA_PREFIX")
                        os.environ["TESSDATA_PREFIX"] = tessdata_dir
                        self.api = PyTessBaseAPI(lang=self.lang, psm=psm_mode)
                        if old_env:
                            os.environ["TESSDATA_PREFIX"] = old_env
                        else:
                            os.environ.pop("TESSDATA_PREFIX", None)
                    else:
                        self.api = PyTessBaseAPI(lang=self.lang, psm=psm_mode)
                    api_initialized = True
                except Exception:
                    raise RuntimeError("Could not initialize Tesseract OCR. Please ensure Tesseract is properly installed.")
            
            self.api.SetVariable("preserve_interword_spaces", "1")
            self.api.SetVariable("user_defined_dpi", "240")
            # Remove character whitelist to allow all Unicode characters
            # This enables recognition of Korean, Chinese, Greek, and other Unicode characters
            self.backend = "tesserocr"
            
        except ImportError:
            raise ImportError("tesserocr is required for OCR functionality. Install with: pip install -r requirements.txt")

    def recognize(self, img: np.ndarray) -> str:
        """Recognize text in image"""
        if self.backend == "tesserocr":
            from PIL import Image
            pil = Image.fromarray(img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            self.api.SetImage(pil)
            txt = self.api.GetUTF8Text() or ""
        else:
            cfg = f"-l {self.lang} --oem 3 --psm {self.psm} -c preserve_interword_spaces=1"
            txt = self.pytesseract.image_to_string(img, config=cfg)
        
        txt = txt.replace("\n", " ").strip()
        txt = txt.replace("'", "'").replace("`", "'")
        return " ".join(txt.split())
