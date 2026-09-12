"""Convert untrusted messages and images into bounded, provenance-carrying facts."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol, Sequence

from .loaders import DatasetIndex
from .models import EvidenceCandidate, EvidenceFact, FinancialEvent, ImageReference, Message


ALLOWED_FACT_TYPES = frozenset({
    "event_cancelled",
    "event_amount_amended",
    "event_amount",
    "payment_delayed",
    "income_confirmed",
})
CURRENCIES = frozenset({"INR", "ZAR", "IDR", "USD", "EUR"})
_CURRENCY_AMOUNT = re.compile(r"\b(INR|ZAR|IDR|USD|EUR)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b", re.I)
_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


class EvidenceValidationError(ValueError):
    """Untrusted extraction output violates the bounded evidence schema."""


class ModelAdapter(Protocol):
    """Provider-neutral future extension point; it may return facts, never instructions."""

    def extract_message(self, message: Message) -> Sequence[EvidenceCandidate]: ...

    def extract_image(self, image_path: Path, linked_event: FinancialEvent) -> Sequence[EvidenceCandidate]: ...


class DisabledModelAdapter:
    """Safe default: no external model is called and no fact is fabricated."""

    def extract_message(self, message: Message) -> Sequence[EvidenceCandidate]:
        return ()

    def extract_image(self, image_path: Path, linked_event: FinancialEvent) -> Sequence[EvidenceCandidate]:
        return ()


def model_adapter_from_environment() -> ModelAdapter:
    """Return the safe default unless a future provider integration is installed explicitly."""
    provider = os.getenv("EVIDENCE_MODEL_PROVIDER", "").strip()
    if not provider:
        return DisabledModelAdapter()
    raise RuntimeError(
        f"No model adapter is installed for EVIDENCE_MODEL_PROVIDER={provider!r}; "
        "install a provider-specific adapter without changing evidence validation."
    )


def _amount_and_currency(text: str) -> tuple[Decimal, str] | None:
    match = _CURRENCY_AMOUNT.search(text)
    if match is None:
        return None
    return Decimal(match.group(2).replace(",", "")), match.group(1).upper()


def _date_from_text(text: str) -> date | None:
    match = _ISO_DATE.search(text)
    return date.fromisoformat(match.group(1)) if match else None


def deterministic_message_candidates(message: Message) -> tuple[EvidenceCandidate, ...]:
    """Small conservative parser for explicit facts; arbitrary instructions produce no candidate."""
    text = message.message_text.lower()
    candidates: list[EvidenceCandidate] = []
    if message.related_event_id and ("cancelled" in text or "canceled" in text):
        candidates.append(EvidenceCandidate("event_cancelled", message.related_event_id, confidence=Decimal("0.90"), rationale="explicit cancellation wording"))
    amount = _amount_and_currency(message.message_text)
    if message.related_event_id and amount and any(word in text for word in ("amended", "updated", "revised", "changed")):
        candidates.append(EvidenceCandidate("event_amount_amended", message.related_event_id, amount[0], amount[1], confidence=Decimal("0.80"), rationale="explicit amended amount"))
    delayed_date = _date_from_text(message.message_text)
    if message.related_event_id and delayed_date and any(word in text for word in ("delayed", "expected", "rescheduled", "replaces")):
        candidates.append(EvidenceCandidate("payment_delayed", message.related_event_id, effective_date=delayed_date, confidence=Decimal("0.80"), rationale="explicit revised date"))
    if amount and "confirmed" in text and any(word in text for word in ("salary", "payroll", "income")):
        candidates.append(EvidenceCandidate("income_confirmed", message.related_event_id, amount[0], amount[1], delayed_date, Decimal("0.80"), "explicit confirmed income"))
    return tuple(candidates)


def _validate_candidate(
    candidate: EvidenceCandidate,
    *,
    source_id: str,
    source_kind: str,
    user_id: str,
    request_id: str | None,
    source_timestamp: object,
    allowed_event_id: str | None,
    index: DatasetIndex,
) -> EvidenceFact:
    if candidate.fact_type not in ALLOWED_FACT_TYPES:
        raise EvidenceValidationError(f"Unsupported evidence fact type: {candidate.fact_type}")
    if not (Decimal("0") <= candidate.confidence <= Decimal("1")):
        raise EvidenceValidationError("Evidence confidence must be between 0 and 1")
    if candidate.currency is not None and candidate.currency not in CURRENCIES:
        raise EvidenceValidationError(f"Unsupported evidence currency: {candidate.currency}")
    if candidate.amount is not None and candidate.currency is None:
        raise EvidenceValidationError("An evidence amount requires a currency")
    if candidate.fact_type in {"event_amount", "event_amount_amended"} and candidate.amount is None:
        raise EvidenceValidationError(f"{candidate.fact_type} requires an amount")
    if candidate.fact_type in {"event_cancelled", "event_amount", "event_amount_amended", "payment_delayed"} and candidate.related_event_id is None:
        raise EvidenceValidationError(f"{candidate.fact_type} requires related_event_id")
    if allowed_event_id is not None and candidate.related_event_id not in {None, allowed_event_id}:
        raise EvidenceValidationError("Image candidate cannot target an event other than its linked event")
    if candidate.related_event_id is not None:
        event = index.events_by_id.get(candidate.related_event_id)
        if event is None or event.user_id != user_id:
            raise EvidenceValidationError("Evidence candidate references an unrelated event")
    return EvidenceFact(
        fact_type=candidate.fact_type,
        user_id=user_id,
        source_id=source_id,
        source_kind=source_kind,
        source_timestamp=source_timestamp if hasattr(source_timestamp, "tzinfo") else None,
        related_event_id=candidate.related_event_id,
        related_request_id=request_id,
        amount=candidate.amount,
        currency=candidate.currency,
        effective_date=candidate.effective_date,
        confidence=candidate.confidence,
        rationale=candidate.rationale,
    )


def extract_message_facts(
    message: Message, index: DatasetIndex, adapter: ModelAdapter | None = None
) -> tuple[EvidenceFact, ...]:
    """Extract and validate message facts; message text never acts as executable policy."""
    candidates = list(deterministic_message_candidates(message))
    if adapter is not None:
        candidates.extend(adapter.extract_message(message))
    return tuple(_validate_candidate(
        candidate, source_id=message.message_id, source_kind="message", user_id=message.user_id,
        request_id=message.request_id, source_timestamp=message.sent_at, allowed_event_id=None, index=index,
    ) for candidate in candidates)


def extract_image_facts(
    image: ImageReference, linked_event: FinancialEvent, index: DatasetIndex, adapter: ModelAdapter | None = None
) -> tuple[EvidenceFact, ...]:
    """Extract linked image facts through an adapter; no image/OCR provider is assumed."""
    if image.related_event_id != linked_event.event_id:
        raise EvidenceValidationError("Image must be processed with its related event")
    if not image.path.is_file():
        raise EvidenceValidationError(f"Image file is absent: {image.path}")
    candidates = () if adapter is None else adapter.extract_image(image.path, linked_event)
    return tuple(_validate_candidate(
        candidate, source_id=image.image_id, source_kind="image", user_id=image.user_id,
        request_id=image.request_id, source_timestamp=None, allowed_event_id=linked_event.event_id, index=index,
    ) for candidate in candidates)


@dataclass(frozen=True)
class EvidenceProcessor:
    index: DatasetIndex
    adapter: ModelAdapter | None = None

    def find_image_for_event(self, event_id: str) -> ImageReference | None:
        images = self.index.images_by_related_event_id.get(event_id, ())
        return images[0] if images else None

    def extract_facts_for_request(self, request_id: str) -> tuple[EvidenceFact, ...]:
        context = self.index.get_request_context(request_id)
        facts: list[EvidenceFact] = []
        for message in context.messages:
            facts.extend(extract_message_facts(message, self.index, self.adapter))
        for event in context.events:
            # A blank source amount remains unknown unless an image adapter returns event_amount.
            if event.amount is None:
                image = self.find_image_for_event(event.event_id)
                if image is not None:
                    facts.extend(extract_image_facts(image, event, self.index, self.adapter))
        return tuple(facts)
