import sys
from unittest.mock import MagicMock

import pytest

# Pillow (PIL) doesn't support Python 3.14 yet.
# Mock it only when it is unavailable so normal CI can exercise the real
# card generator.
try:
    from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    PILLOW_AVAILABLE = True
except Exception:
    PILLOW_AVAILABLE = False
    for _mod in ('PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont'):
        sys.modules.setdefault(_mod, MagicMock())
    sys.modules.setdefault('card_generator', MagicMock())


def pytest_collection_modifyitems(config, items):
    if PILLOW_AVAILABLE:
        return

    skip_progress_card = pytest.mark.skip(reason="Pillow is unavailable")
    for item in items:
        if item.nodeid.startswith("tests/test_progress_card.py"):
            item.add_marker(skip_progress_card)
