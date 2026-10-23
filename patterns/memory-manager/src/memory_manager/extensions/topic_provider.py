"""Extension point: supply the domain's topic vocabulary.

Optional. Defaults to reading the versioned YAML configuration, which is what most domains want. A
domain needing topics to change without a redeploy supplies its own provider — a database-backed one,
say — without the pattern changing.

On failure: deny. A provider that cannot answer leaves every topic unknown, and an unknown topic is
rejected.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import Classification, ExtensionError, Topic, TopicField


@runtime_checkable
class TopicProvider(Protocol):
    """Supplies the topics this domain accepts.

    Called per request, so an implementation that reaches a network or a database **must** cache.
    Raise :class:`~.types.ExtensionError` rather than returning an empty set on failure: an empty
    set and a failed lookup are different, and conflating them hides an outage behind
    ``TOPIC_UNKNOWN``.
    """

    def topics(self) -> dict[str, Topic]:
        """Return the topic vocabulary, keyed by topic id."""
        ...


class YamlTopicProvider:
    """The platform default: topics from the validated configuration.

    Takes the already-parsed and schema-validated ``topics`` list, so it never re-reads or
    re-validates a file on the request path.
    """

    def __init__(self, topics_config: list[dict[str, object]]) -> None:
        self._topics = self._build(topics_config)

    @staticmethod
    def _build(topics_config: list[dict[str, object]]) -> dict[str, Topic]:
        built: dict[str, Topic] = {}
        for entry in topics_config:
            topic_id = entry.get("id")
            classification = entry.get("classification")
            if not isinstance(topic_id, str) or not isinstance(classification, str):
                raise ExtensionError("topic entry is missing 'id' or 'classification'")
            if topic_id in built:
                raise ExtensionError(f"duplicate topic id: {topic_id}")

            raw_fields = entry.get("fields") or []
            if not isinstance(raw_fields, list):
                raise ExtensionError(f"topic {topic_id}: 'fields' must be a list")

            fields: list[TopicField] = []
            for raw in raw_fields:
                if not isinstance(raw, dict):
                    raise ExtensionError(
                        f"topic {topic_id}: each field must be a mapping"
                    )
                name, value_type = raw.get("name"), raw.get("valueType")
                if not isinstance(name, str) or value_type not in (
                    "string",
                    "number",
                    "boolean",
                ):
                    raise ExtensionError(
                        f"topic {topic_id}: field needs 'name' and a valid 'valueType'"
                    )
                max_length = raw.get("maxLength")
                fields.append(
                    TopicField(
                        name=name,
                        value_type=value_type,
                        max_length=max_length if isinstance(max_length, int) else None,
                    )
                )

            built[topic_id] = Topic(
                id=topic_id,
                classification=Classification(classification),
                enabled=bool(entry.get("enabled", False)),
                allow_inferred=bool(entry.get("allowInferred", False)),
                fields=tuple(fields),
            )
        return built

    def topics(self) -> dict[str, Topic]:
        return dict(self._topics)
