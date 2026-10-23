"""Request and response shapes.

Pydantic models mirroring `contracts/openapi.yaml`. Two properties matter more than the field list:

* ``extra="forbid"`` everywhere, so an unexpected key is rejected rather than ignored. A request
  that tries to set a scope is refused by the schema, before any code runs.
* ``max_length=5`` on ``facts``, the provider's verified limit. The contract caps it rather than
  splitting a larger batch across provider calls, which would reintroduce the partial-failure
  semantics the synchronous design exists to avoid.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_FACTS = 5

TopicId = Field(pattern=r"^[a-z][a-z0-9_]{2,48}$")


class FactIn(BaseModel):
    """One fact as submitted."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(pattern=r"^[a-z][a-z0-9_]{2,48}$")
    value: str | float | bool
    fact: str = Field(min_length=3, max_length=1024)
    field_name: str | None = Field(
        default=None, alias="field", pattern=r"^[a-z][a-z0-9_]{1,48}$"
    )
    basis: Literal["stated", "inferred"] = "stated"


class RememberRequest(BaseModel):
    """The whole request body.

    Only ``facts``. There is deliberately no scope field: scope is derived server-side from the
    authenticated caller, and a body that supplies one is refused.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    facts: list[FactIn] = Field(min_length=1, max_length=MAX_FACTS)


class FactResultOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    topic: str
    reasonCode: str  # noqa: N815 - the contract's wire name
    memoryId: str | None = None  # noqa: N815


class RememberResponse(BaseModel):
    """Always a 200 when the request itself was acceptable.

    ``outcome`` distinguishes stored, stored-but-unverified, and nothing-qualified. A fully
    filtered request is ``noop`` rather than an error: the agent did nothing wrong by offering a
    fact the domain does not accept.
    """

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["written", "written_unverified", "noop"]
    stored: int = Field(ge=0, le=MAX_FACTS)
    results: list[FactResultOut]


class RecalledValueOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    field: str | None = None
    value: str | float | bool
    fact: str


class RecallResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[RecalledValueOut]
    withheld: int = Field(ge=0)
