"""The BONUS video's config: everything the main video's `animations/config.py`
defines (colours, base scenes, the bpkfigures exports), so bonus graphics match the
main video's style without a second copy of anything.

The main config is loaded BY PATH under the name `main_config`, because this file is
itself `config` and a plain `from config import *` would import itself.
`animations/` also goes on sys.path so `from assets.<name> import ...` reaches the
main video's assets and data caches.
"""
import importlib.util
import os
import sys

_MAIN = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "animations"))
if _MAIN not in sys.path:
    sys.path.append(_MAIN)

if "main_config" not in sys.modules:
    _spec = importlib.util.spec_from_file_location("main_config",
                                                   os.path.join(_MAIN, "config.py"))
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["main_config"] = _mod
    _spec.loader.exec_module(_mod)

globals().update({k: v for k, v in vars(sys.modules["main_config"]).items()
                  if not k.startswith("_")})

from bpkfigures.table import get_table  # noqa: E402,F401  (the usual bonus graphic)
