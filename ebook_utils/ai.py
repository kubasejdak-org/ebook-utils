import json
import os
from abc import ABC, abstractmethod
from typing import Any

from .models import AiSuggestion, Confidence, EbookBundle
from .pipeline import to_jsonable


class AiResolverError(RuntimeError):
    pass


class AiResolver(ABC):
    @abstractmethod
    def resolve(self, bundle: EbookBundle) -> AiSuggestion: ...


def build_review_prompt(bundle: EbookBundle) -> str:
    payload = to_jsonable(bundle)
    return (
        "You are helping normalize ebook metadata for a local library. "
        "Return only JSON with keys: title, authors, edition_text, confidence, reasoning. "
        "Use null for unknown title or edition_text, authors as a list of strings, "
        "and confidence as high, medium, or low. Do not invent authors.\n\n"
        f"Bundle evidence:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def parse_ai_suggestion(raw: dict[str, Any]) -> AiSuggestion:
    confidence_raw = str(raw.get("confidence", "low")).casefold()
    confidence = Confidence(confidence_raw) if confidence_raw in {item.value for item in Confidence} else Confidence.LOW
    authors_raw = raw.get("authors") or []
    authors = (
        [str(author).strip() for author in authors_raw if str(author).strip()] if isinstance(authors_raw, list) else []
    )
    title = raw.get("title")
    edition_text = raw.get("edition_text")
    return AiSuggestion(
        title=str(title).strip() if title else None,
        authors=authors,
        edition_text=str(edition_text).strip() if edition_text else None,
        confidence=confidence,
        reasoning=str(raw.get("reasoning") or ""),
        raw=raw,
    )


class OpenAiResolver(AiResolver):
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("EBOOK_UTILS_OPENAI_MODEL", "gpt-4.1-mini")

    def resolve(self, bundle: EbookBundle) -> AiSuggestion:
        try:
            from openai import OpenAI
        except ImportError as error:
            raise AiResolverError("OpenAI SDK is not installed. Install ebook-utils[ai-openai].") from error

        client = OpenAI()
        response = client.responses.create(
            model=self.model,
            input=build_review_prompt(bundle),
            text={"format": {"type": "json_object"}},
        )
        try:
            raw = json.loads(response.output_text)
        except Exception as error:
            raise AiResolverError("OpenAI response was not valid JSON.") from error
        return parse_ai_suggestion(raw)


class ClaudeResolver(AiResolver):
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("EBOOK_UTILS_CLAUDE_MODEL", "claude-3-5-haiku-latest")

    def resolve(self, bundle: EbookBundle) -> AiSuggestion:
        try:
            import anthropic
        except ImportError as error:
            raise AiResolverError("Claude SDK is not installed. Install ebook-utils[ai-claude].") from error

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": build_review_prompt(bundle)}],
        )
        text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        try:
            raw = json.loads("\n".join(text_parts))
        except Exception as error:
            raise AiResolverError("Claude response was not valid JSON.") from error
        return parse_ai_suggestion(raw)


def get_resolver(provider: str, model: str | None = None) -> AiResolver:
    provider_l = provider.casefold()
    if provider_l == "openai":
        return OpenAiResolver(model=model)
    if provider_l in {"claude", "anthropic"}:
        return ClaudeResolver(model=model)
    raise AiResolverError(f"Unsupported AI provider: {provider}")
