"""Canned stage implementations so the pipeline runs end to end before the real modules land.

pipeline.py falls back to these per function when the real module or attribute is missing.
None of this is real logic; every stub is replaced by its owner's module.
"""
