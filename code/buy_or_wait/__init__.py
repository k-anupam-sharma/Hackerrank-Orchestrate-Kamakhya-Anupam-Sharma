"""Typed, deterministic data access for the Buy or Wait challenge."""

from .loaders import DatasetIndex, DatasetValidationError, RequestContext, load_dataset
from .normalization import normalize_user_events, print_normalized_timeline
from .evidence import EvidenceProcessor, extract_image_facts, extract_message_facts
from .forecast import forecast_balance, get_minimum_projected_balance, is_plan_safe
from .capacity import calculate_amount_safe_to_pay, find_earliest_safe_full_payment_date
from .plans import PlanGenerator, PlanValidator
from .spending_changes import SpendingChangeEngine
from .ranking import choose_best_plan, map_plan_to_recommendation

__all__ = [
    "DatasetIndex", "DatasetValidationError", "RequestContext", "load_dataset",
    "normalize_user_events", "print_normalized_timeline",
    "EvidenceProcessor", "extract_image_facts", "extract_message_facts",
    "forecast_balance", "get_minimum_projected_balance", "is_plan_safe",
    "calculate_amount_safe_to_pay", "find_earliest_safe_full_payment_date",
    "PlanGenerator", "PlanValidator",
    "SpendingChangeEngine",
    "choose_best_plan", "map_plan_to_recommendation",
]
