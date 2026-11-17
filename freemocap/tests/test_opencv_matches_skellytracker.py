"""The installed OpenCV is the one skellytracker states: on another version skellytracker's model input changes
silently (warpAffine sampling differs between 4.x and 5.0) and solvePnP/undistortPoints edge cases differ."""

import importlib.metadata

import pytest
from packaging.requirements import Requirement


def test_installed_opencv_satisfies_skellytracker_requirement():
    requirements = [Requirement(text) for text in importlib.metadata.requires("skellytracker") or ()]
    opencv = [requirement for requirement in requirements if requirement.name.startswith("opencv")]
    if not opencv:
        pytest.skip("skellytracker's metadata states no OpenCV requirement")
    for requirement in opencv:
        installed = importlib.metadata.version(requirement.name)
        assert requirement.specifier.contains(installed, prereleases=True), (
            f"{requirement.name} {installed} is installed; skellytracker requires {requirement}")
