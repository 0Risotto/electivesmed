"""Container: the single composition point handed to clients."""

from dataclasses import dataclass

from ..accessors import (
    FetchAccessor,
    LlmAccessor,
    MailAccessor,
    ReplyAccessor,
)
from ..agent.invoker import Invoker
from ..components.policy import PolicyGate
from ..dao import Dao
from ..models.config import Profile, Settings


@dataclass
class Container:
    settings: Settings
    profile: Profile
    dao: Dao
    mail: MailAccessor
    http: FetchAccessor
    llm: LlmAccessor
    inbox: ReplyAccessor
    policy: PolicyGate
    invoker: Invoker | None = None

    def close(self) -> None:
        for resource in (self.dao, self.mail, self.http, self.inbox):
            try:
                resource.close()
            except Exception:
                pass

    def __enter__(self) -> "Container":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
