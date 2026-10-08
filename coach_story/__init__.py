"""EFOS Coach Story package."""
from .principles import detect_principles
from .story_builder import build_coach_story
from .report_generator import render_coach_story_md

__all__ = ["detect_principles", "build_coach_story", "render_coach_story_md"]
