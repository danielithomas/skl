"""Package that ships JSON Schemas consumed by ``skl validate``.

Schemas are loaded via ``importlib.resources.files("skl.schemas")`` so they
travel inside the installed wheel. Do not import yaml libraries here -
schemas are JSON, not YAML.
"""
