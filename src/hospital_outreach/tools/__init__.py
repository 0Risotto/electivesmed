"""Tool layer: thin agent-facing wrappers over activities and side-effect actions.

build_read_tools() is safe for any agent; build_action_tools() exposes
policy-gated write actions and should only be given to the outreach agent.
"""

from . import actions as action_tools
from . import extract, fetch, lookup, score, sources


def build_read_tools(container) -> list:
    return [
        *sources.build(container),
        *fetch.build(container),
        *extract.build(container),
        *score.build(container),
        *lookup.build(container),
    ]


def build_action_tools(container) -> list:
    return action_tools.build(container)
