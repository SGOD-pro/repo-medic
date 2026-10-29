import pytest
from src.cli.terminal import get_banner_width, format_banner


def test_get_banner_width():
    width = get_banner_width()
    assert isinstance(width, int)
    assert width >= 40


def test_format_banner():
    banner = format_banner("RepoMedic Engine")
    assert "RepoMedic Engine" in banner
    lines = banner.strip().split("\n")
    assert len(lines) == 3
    assert lines[0] == lines[2]
