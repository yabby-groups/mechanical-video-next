"""Choose an explicit test face for layout fixtures that do not verify typography."""
import os
from pathlib import Path
from unittest import SkipTest

from PIL import ImageFont


def test_font():
    for candidate in (os.environ.get('MVN_TEST_FONT_PATH'), 'DejaVuSans.ttf',
                      '/System/Library/Fonts/Supplemental/Arial.ttf'):
        if candidate:
            try:
                return str(Path(os.fsdecode(ImageFont.truetype(candidate, 64).path)).resolve())
            except OSError:
                continue
    raise SkipTest('Layout fixture needs a test font (set MVN_TEST_FONT_PATH or install DejaVu Sans)')


def require_approved_font():
    from mechanical_video_next.text_layout import resolved_font_family
    try:
        return resolved_font_family()
    except ValueError as error:
        if 'font unavailable' not in str(error):
            raise
        raise SkipTest('Optional approved typography integration requires PingFang SC Medium') from error
