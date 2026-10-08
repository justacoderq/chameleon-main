"""Lazy exports keep asset/shape helpers usable without the official renderer."""
from importlib import import_module


def __getattr__(name):
    modules = {"load_brand_font_manager": "brand_fonts", "convert_chameleon_to_crello": "convert",
               "render_design_to_png": "convert", "make_stub_features": "features_stub"}
    if name not in modules:
        raise AttributeError(name)
    return getattr(import_module("." + modules[name], __name__), name)

__all__ = [
    "convert_chameleon_to_crello",
    "render_design_to_png",
    "make_stub_features",
    "load_brand_font_manager",
]
