"""Load, validate, index, and retrieve challenge data without financial decisions."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Mapping, TypeVar

from .models import (
    ExchangeRate, FinancialEvent, ImageReference, Message, OutputTemplateRow,
    PaymentOption, Request, UserProfile,
)
from .parsing import (
    ParseError, optional_date, optional_decimal, optional_int, optional_text,
    pipe_list, required_bool, required_date, required_datetime, required_decimal,
    required_int, required_text,
)


class DatasetValidationError(ValueError):
    """The supplied dataset is structurally invalid or has broken relationships."""


PROFILE_COLUMNS = frozenset({
    "user_id", "home_currency", "current_available_balance", "minimum_balance_to_keep",
    "financial_priorities", "expense_categories_to_protect",
    "expense_categories_user_is_willing_to_reduce", "expense_categories_user_is_willing_to_stop",
    "payment_methods_user_will_consider", "max_installment_months",
})
EVENT_COLUMNS = frozenset({
    "event_id", "user_id", "event_type", "description", "category", "direction", "amount",
    "currency", "event_date", "settlement_date", "status", "linked_event_id", "flexibility",
    "minimum_allowed_amount",
})
REQUEST_COLUMNS = frozenset({
    "request_id", "user_id", "request_date", "request_type", "requested_amount",
    "desired_completion_date", "allows_partial_payment", "request_text",
})
OPTION_COLUMNS = frozenset({
    "payment_option_id", "request_id", "payment_method", "payment_amount", "number_of_payments",
    "first_payment_date", "payment_frequency_days", "financing_fee", "total_payable_amount",
})
MESSAGE_COLUMNS = frozenset({
    "message_id", "user_id", "request_id", "related_event_id", "sent_at", "source_type", "message_text",
})
IMAGE_COLUMNS = frozenset({"image_id", "user_id", "request_id", "related_event_id"})
RATE_COLUMNS = frozenset({"rate_date", "from_currency", "to_currency", "rate"})
OUTPUT_COLUMNS = (
    "request_id", "amount_safe_to_pay", "affordability_status", "recommended_payment_method",
    "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed", "decision_explanation",
)


def _rows(dataset_dir: Path, filename: str, required_columns: Iterable[str]) -> list[dict[str, str]]:
    path = dataset_dir / filename
    if not path.is_file():
        raise DatasetValidationError(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DatasetValidationError(f"{filename} has no header")
        missing = set(required_columns) - set(reader.fieldnames)
        if missing:
            raise DatasetValidationError(f"{filename} missing required columns: {sorted(missing)}")
        return list(reader)


T = TypeVar("T")


def _unique_index(records: Iterable[T], id_getter: Callable[[T], str], label: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for record in records:
        record_id = id_getter(record)
        if record_id in result:
            raise DatasetValidationError(f"Duplicate {label}: {record_id}")
        result[record_id] = record
    return result


def _group(records: Iterable[T], key_getter: Callable[[T], str | None]) -> dict[str, tuple[T, ...]]:
    grouped: defaultdict[str, list[T]] = defaultdict(list)
    for record in records:
        key = key_getter(record)
        if key is not None:
            grouped[key].append(record)
    return {key: tuple(value) for key, value in grouped.items()}


@dataclass(frozen=True)
class RequestContext:
    request: Request
    profile: UserProfile
    events: tuple[FinancialEvent, ...]
    payment_options: tuple[PaymentOption, ...]
    messages: tuple[Message, ...]
    images: tuple[ImageReference, ...]
    linked_messages_by_event_id: Mapping[str, tuple[Message, ...]]
    linked_images_by_event_id: Mapping[str, tuple[ImageReference, ...]]
    exchange_rates: tuple[ExchangeRate, ...]


@dataclass(frozen=True)
class DatasetIndex:
    profiles_by_user_id: Mapping[str, UserProfile]
    evaluation_requests_by_id: Mapping[str, Request]
    sample_requests_by_id: Mapping[str, Request]
    requests_by_id: Mapping[str, Request]
    events_by_id: Mapping[str, FinancialEvent]
    events_by_user_id: Mapping[str, tuple[FinancialEvent, ...]]
    payment_options_by_id: Mapping[str, PaymentOption]
    payment_options_by_request_id: Mapping[str, tuple[PaymentOption, ...]]
    messages_by_id: Mapping[str, Message]
    messages_by_user_id: Mapping[str, tuple[Message, ...]]
    messages_by_request_id: Mapping[str, tuple[Message, ...]]
    messages_by_related_event_id: Mapping[str, tuple[Message, ...]]
    images_by_id: Mapping[str, ImageReference]
    images_by_user_id: Mapping[str, tuple[ImageReference, ...]]
    images_by_request_id: Mapping[str, tuple[ImageReference, ...]]
    images_by_related_event_id: Mapping[str, tuple[ImageReference, ...]]
    exchange_rates_by_key: Mapping[tuple[date, str, str], ExchangeRate]
    output_template_rows: tuple[OutputTemplateRow, ...]

    def get_request_context(self, request_id: str) -> RequestContext:
        try:
            request = self.requests_by_id[request_id]
        except KeyError as exc:
            raise KeyError(f"Unknown request_id: {request_id}") from exc
        return RequestContext(
            request=request,
            profile=self.profiles_by_user_id[request.user_id],
            events=self.events_by_user_id.get(request.user_id, ()),
            payment_options=self.payment_options_by_request_id.get(request_id, ()),
            messages=tuple(
                dict.fromkeys(
                    self.messages_by_user_id.get(request.user_id, ())
                    + self.messages_by_request_id.get(request_id, ())
                )
            ),
            images=tuple(
                dict.fromkeys(
                    self.images_by_user_id.get(request.user_id, ())
                    + self.images_by_request_id.get(request_id, ())
                )
            ),
            linked_messages_by_event_id={
                event.event_id: self.messages_by_related_event_id.get(event.event_id, ())
                for event in self.events_by_user_id.get(request.user_id, ())
            },
            linked_images_by_event_id={
                event.event_id: self.images_by_related_event_id.get(event.event_id, ())
                for event in self.events_by_user_id.get(request.user_id, ())
            },
            exchange_rates=tuple(self.exchange_rates_by_key.values()),
        )


def _convert(filename: str, row_number: int, convert: Callable[[], T]) -> T:
    try:
        return convert()
    except ParseError as exc:
        raise DatasetValidationError(f"{filename} row {row_number}: {exc}") from exc


def _load_profiles(dataset_dir: Path) -> list[UserProfile]:
    return [_convert("financial_profiles.csv", i, lambda row=row: UserProfile(
        required_text(row["user_id"], "user_id"), required_text(row["home_currency"], "home_currency"),
        required_decimal(row["current_available_balance"], "current_available_balance"),
        required_decimal(row["minimum_balance_to_keep"], "minimum_balance_to_keep"),
        pipe_list(row["financial_priorities"]), pipe_list(row["expense_categories_to_protect"]),
        pipe_list(row["expense_categories_user_is_willing_to_reduce"]),
        pipe_list(row["expense_categories_user_is_willing_to_stop"]),
        pipe_list(row["payment_methods_user_will_consider"]), optional_int(row["max_installment_months"], "max_installment_months"),
    )) for i, row in enumerate(_rows(dataset_dir, "financial_profiles.csv", PROFILE_COLUMNS), start=2)]


def _load_events(dataset_dir: Path) -> list[FinancialEvent]:
    return [_convert("financial_events.csv", i, lambda row=row: FinancialEvent(
        required_text(row["event_id"], "event_id"), required_text(row["user_id"], "user_id"),
        required_text(row["event_type"], "event_type"), required_text(row["description"], "description"),
        required_text(row["category"], "category"), required_text(row["direction"], "direction"),
        optional_decimal(row["amount"], "amount"), required_text(row["currency"], "currency"),
        required_date(row["event_date"], "event_date"), optional_date(row["settlement_date"], "settlement_date"),
        required_text(row["status"], "status"), optional_text(row["linked_event_id"]),
        required_text(row["flexibility"], "flexibility"), optional_decimal(row["minimum_allowed_amount"], "minimum_allowed_amount"),
    )) for i, row in enumerate(_rows(dataset_dir, "financial_events.csv", EVENT_COLUMNS), start=2)]


def _load_requests(dataset_dir: Path, filename: str) -> list[Request]:
    return [_convert(filename, i, lambda row=row: Request(
        required_text(row["request_id"], "request_id"), required_text(row["user_id"], "user_id"),
        required_date(row["request_date"], "request_date"), required_text(row["request_type"], "request_type"),
        required_decimal(row["requested_amount"], "requested_amount"),
        required_date(row["desired_completion_date"], "desired_completion_date"),
        required_bool(row["allows_partial_payment"], "allows_partial_payment"), required_text(row["request_text"], "request_text"),
    )) for i, row in enumerate(_rows(dataset_dir, filename, REQUEST_COLUMNS), start=2)]


def _load_options(dataset_dir: Path) -> list[PaymentOption]:
    return [_convert("request_payment_options.csv", i, lambda row=row: PaymentOption(
        required_text(row["payment_option_id"], "payment_option_id"), required_text(row["request_id"], "request_id"),
        required_text(row["payment_method"], "payment_method"), required_decimal(row["payment_amount"], "payment_amount"),
        required_int(row["number_of_payments"], "number_of_payments"),
        required_date(row["first_payment_date"], "first_payment_date"),
        optional_int(row["payment_frequency_days"], "payment_frequency_days"),
        required_decimal(row["financing_fee"], "financing_fee"), required_decimal(row["total_payable_amount"], "total_payable_amount"),
    )) for i, row in enumerate(_rows(dataset_dir, "request_payment_options.csv", OPTION_COLUMNS), start=2)]


def _load_messages(dataset_dir: Path) -> list[Message]:
    return [_convert("messages.csv", i, lambda row=row: Message(
        required_text(row["message_id"], "message_id"), required_text(row["user_id"], "user_id"),
        optional_text(row["request_id"]), optional_text(row["related_event_id"]),
        required_datetime(row["sent_at"], "sent_at"), required_text(row["source_type"], "source_type"),
        required_text(row["message_text"], "message_text"),
    )) for i, row in enumerate(_rows(dataset_dir, "messages.csv", MESSAGE_COLUMNS), start=2)]


def _load_images(dataset_dir: Path) -> list[ImageReference]:
    return [_convert("images.csv", i, lambda row=row: ImageReference(
        required_text(row["image_id"], "image_id"), required_text(row["user_id"], "user_id"),
        optional_text(row["request_id"]), optional_text(row["related_event_id"]),
        dataset_dir / "media" / "images" / f"{required_text(row['image_id'], 'image_id')}.png",
    )) for i, row in enumerate(_rows(dataset_dir, "images.csv", IMAGE_COLUMNS), start=2)]


def _load_rates(dataset_dir: Path) -> list[ExchangeRate]:
    return [_convert("exchange_rates.csv", i, lambda row=row: ExchangeRate(
        required_date(row["rate_date"], "rate_date"), required_text(row["from_currency"], "from_currency"),
        required_text(row["to_currency"], "to_currency"), required_decimal(row["rate"], "rate"),
    )) for i, row in enumerate(_rows(dataset_dir, "exchange_rates.csv", RATE_COLUMNS), start=2)]


def _load_output_template(dataset_dir: Path) -> list[OutputTemplateRow]:
    rows = _rows(dataset_dir, "output.csv", OUTPUT_COLUMNS)
    return [_convert("output.csv", i, lambda row=row: OutputTemplateRow(required_text(row["request_id"], "request_id")))
            for i, row in enumerate(rows, start=2)]


def _validate_foreign_keys(index: DatasetIndex) -> None:
    users = index.profiles_by_user_id
    requests = index.requests_by_id
    events = index.events_by_id
    for request in requests.values():
        if request.user_id not in users:
            raise DatasetValidationError(f"Request {request.request_id} references unknown user {request.user_id}")
    for event in events.values():
        if event.user_id not in users:
            raise DatasetValidationError(f"Event {event.event_id} references unknown user {event.user_id}")
        if event.linked_event_id is not None and event.linked_event_id not in events:
            raise DatasetValidationError(f"Event {event.event_id} links unknown event {event.linked_event_id}")
    for option in index.payment_options_by_id.values():
        if option.request_id not in requests:
            raise DatasetValidationError(f"Payment option {option.payment_option_id} references unknown request {option.request_id}")
    for message in index.messages_by_id.values():
        _validate_evidence_links("Message", message.message_id, message.user_id, message.request_id, message.related_event_id, users, requests, events)
    for image in index.images_by_id.values():
        _validate_evidence_links("Image", image.image_id, image.user_id, image.request_id, image.related_event_id, users, requests, events)
        if not image.path.is_file():
            raise DatasetValidationError(f"Image {image.image_id} is missing media file {image.path}")
    template_ids = [row.request_id for row in index.output_template_rows]
    if len(template_ids) != len(set(template_ids)):
        raise DatasetValidationError("output.csv contains duplicate request_id values")
    if set(template_ids) != set(index.evaluation_requests_by_id):
        raise DatasetValidationError("output.csv request IDs do not exactly match requests.csv")


def _validate_evidence_links(
    label: str, record_id: str, user_id: str, request_id: str | None, event_id: str | None,
    users: Mapping[str, UserProfile], requests: Mapping[str, Request], events: Mapping[str, FinancialEvent],
) -> None:
    if user_id not in users:
        raise DatasetValidationError(f"{label} {record_id} references unknown user {user_id}")
    if request_id is not None:
        request = requests.get(request_id)
        if request is None:
            raise DatasetValidationError(f"{label} {record_id} references unknown request {request_id}")
        if request.user_id != user_id:
            raise DatasetValidationError(f"{label} {record_id} user does not match request {request_id}")
    if event_id is not None:
        event = events.get(event_id)
        if event is None:
            raise DatasetValidationError(f"{label} {record_id} references unknown event {event_id}")
        if event.user_id != user_id:
            raise DatasetValidationError(f"{label} {record_id} user does not match event {event_id}")


def load_dataset(dataset_dir: str | Path) -> DatasetIndex:
    """Load all required CSV files and return validated indexes for request-level access."""
    root = Path(dataset_dir)
    profiles = _load_profiles(root)
    events = _load_events(root)
    evaluation_requests = _load_requests(root, "requests.csv")
    sample_requests = _load_requests(root, "sample_requests.csv")
    all_requests = evaluation_requests + sample_requests
    options = _load_options(root)
    messages = _load_messages(root)
    images = _load_images(root)
    rates = _load_rates(root)
    template = _load_output_template(root)
    profiles_by_id = _unique_index(profiles, lambda item: item.user_id, "user_id")
    events_by_id = _unique_index(events, lambda item: item.event_id, "event_id")
    evaluation_by_id = _unique_index(evaluation_requests, lambda item: item.request_id, "evaluation request_id")
    sample_by_id = _unique_index(sample_requests, lambda item: item.request_id, "sample request_id")
    all_by_id = _unique_index(all_requests, lambda item: item.request_id, "request_id")
    options_by_id = _unique_index(options, lambda item: item.payment_option_id, "payment_option_id")
    messages_by_id = _unique_index(messages, lambda item: item.message_id, "message_id")
    images_by_id = _unique_index(images, lambda item: item.image_id, "image_id")
    rates_by_key = _unique_index(rates, lambda item: (item.rate_date, item.from_currency, item.to_currency), "exchange-rate key")
    index = DatasetIndex(
        profiles_by_user_id=profiles_by_id,
        evaluation_requests_by_id=evaluation_by_id,
        sample_requests_by_id=sample_by_id,
        requests_by_id=all_by_id,
        events_by_id=events_by_id,
        events_by_user_id=_group(events, lambda item: item.user_id),
        payment_options_by_id=options_by_id,
        payment_options_by_request_id=_group(options, lambda item: item.request_id),
        messages_by_id=messages_by_id,
        messages_by_user_id=_group(messages, lambda item: item.user_id),
        messages_by_request_id=_group(messages, lambda item: item.request_id),
        messages_by_related_event_id=_group(messages, lambda item: item.related_event_id),
        images_by_id=images_by_id,
        images_by_user_id=_group(images, lambda item: item.user_id),
        images_by_request_id=_group(images, lambda item: item.request_id),
        images_by_related_event_id=_group(images, lambda item: item.related_event_id),
        exchange_rates_by_key=rates_by_key,
        output_template_rows=tuple(template),
    )
    _validate_foreign_keys(index)
    return index
