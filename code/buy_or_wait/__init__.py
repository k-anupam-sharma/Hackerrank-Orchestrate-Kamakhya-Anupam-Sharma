"""Typed, deterministic data access for the Buy or Wait challenge."""

from .loaders import DatasetIndex, DatasetValidationError, RequestContext, load_dataset
from .normalization import normalize_user_events, print_normalized_timeline
from .evidence import EvidenceProcessor, extract_image_facts, extract_message_facts, local_ocr_from_environment
from .forecast import forecast_balance, get_minimum_projected_balance, is_plan_safe
from .capacity import calculate_amount_safe_to_pay, find_earliest_safe_full_payment_date
from .plans import PlanGenerator, PlanValidator
from .spending_changes import SpendingChangeEngine
from .ranking import choose_best_plan, map_plan_to_recommendation
from .solver import solve_all_requests, solve_dataset, solve_request, validate_output_csv
from .reconciliation import reconcile_evidence_facts
from .explanations import build_explanation_facts, deterministic_explanation, generate_explanation, validate_explanation

__all__ = [
    "DatasetIndex", "DatasetValidationError", "RequestContext", "load_dataset",
    "normalize_user_events", "print_normalized_timeline",
    "EvidenceProcessor", "extract_image_facts", "extract_message_facts", "local_ocr_from_environment",
    "forecast_balance", "get_minimum_projected_balance", "is_plan_safe",
    "calculate_amount_safe_to_pay", "find_earliest_safe_full_payment_date",
    "PlanGenerator", "PlanValidator",
    "SpendingChangeEngine",
    "choose_best_plan", "map_plan_to_recommendation",
    "solve_request", "solve_all_requests", "solve_dataset", "validate_output_csv",
    "reconcile_evidence_facts",
    "build_explanation_facts", "deterministic_explanation", "generate_explanation", "validate_explanation",
]
