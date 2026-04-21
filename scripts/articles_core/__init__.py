"""Focused submodules for the article build pipeline.

The main entry point lives in ``scripts/build_articles.py``. This package
holds the narrow, well-tested pieces that the build pipeline uses --
Markdown-to-HTML rendering, frontmatter parsing, and filesystem-safe
path helpers. Extracting them makes the module graph shallower and the
individual pieces easier to test and review.

The main module re-exports the public names from these submodules so
existing callers (tests, CI, local preview) keep importing from
``scripts.build_articles`` unchanged.
"""
