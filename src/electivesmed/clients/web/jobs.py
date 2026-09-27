"""Background jobs: agent runs and throttled real sends."""

from ...agent.invoker import manual_invocation
from ...builders.prompts import default_scout_prompt, generate_prompt
from ...models.entities import Campaign
from ...models.enums import AgentName
from ...services.sending import send_batch


def run_scout(
    container, invocation_id: str, instructions: str = "", campaign_id: int | None = None
) -> None:
    prompt = default_scout_prompt(container, instructions)
    container.invoker.invoke(
        AgentName.SCOUT, prompt, campaign_id=campaign_id, invocation_id=invocation_id
    )


def run_generate(
    container,
    invocation_id: str,
    campaign: Campaign,
    contacts: list,
    instructions: str = "",
) -> None:
    prompt = generate_prompt(container, campaign, contacts, instructions)
    container.invoker.invoke(
        AgentName.OUTREACH, prompt, campaign_id=campaign.id, invocation_id=invocation_id
    )


def run_regenerate(
    container,
    invocation_id: str,
    contact,
    campaign: Campaign | None = None,
    instructions: str = "",
) -> None:
    active = campaign or Campaign(
        name="regenerate",
        goal=container.profile.goal,
        tone=container.profile.tone,
        language=container.profile.language,
    )
    prompt = generate_prompt(container, active, [contact], instructions)
    container.invoker.invoke(
        AgentName.OUTREACH, prompt, campaign_id=active.id, invocation_id=invocation_id
    )


def run_send(container, invocation_id: str, draft_ids: list[int], force_window: bool) -> None:
    with manual_invocation(container, "web-send", invocation_id=invocation_id) as run:
        result = send_batch(
            container,
            draft_ids,
            limit=len(draft_ids),
            dry_run=False,
            force_window=force_window,
        )
        run.output.update(result)
