"""Explicit native dependencies; the canonical runner remains hermetic."""


def pytest_addoption(parser):
    parser.addini("reaction_draw_python", "Prepared reaction-draw Python interpreter", default="")
    parser.addini("reaction_draw_browser", "Prepared Chromium executable", default="")
