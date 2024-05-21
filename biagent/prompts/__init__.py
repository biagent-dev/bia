import sys

from jinja2 import Environment, PackageLoader

thismodule = sys.modules[__name__]

_NINJA_FILE_SUFFIX = ".jinja"


def get_templates():
    """Loads Jinja templates from the current package directory."""
    env = Environment(
        loader=PackageLoader("biagent", "prompts")
    )  # Load from current package
    templates = {}
    for name in env.loader.list_templates():
        if name.endswith(_NINJA_FILE_SUFFIX):
            templates[name.replace(_NINJA_FILE_SUFFIX, "")] = env.get_template(name)
    return templates


templates = get_templates()

for name, template in templates.items():
    setattr(thismodule, name, template)

__all__ = list(templates.keys())
