"""Tests for the hello module."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nqueens_recog.hello import greet


def test_greet_default():
    assert greet() == "Hello, World! Welcome to nqueens-recog."


def test_greet_custom_name():
    assert greet("Alice") == "Hello, Alice! Welcome to nqueens-recog."
