from app.Services.structured_query import StructuredQueryRouter
import pytest


def test_salary_is_scoped_and_returns_requested_field_only():
    result = StructuredQueryRouter().route("What is my net salary?", "EMP-0001")
    assert result["success"]
    assert result["data"]["records"][0] == {"net_salary": 33500}


def test_attendance_month_and_date_filters_are_parsed():
    result = StructuredQueryRouter().route(
        "meri attendance August 2026", "EMP-0001"
    )
    assert result["success"]
    assert result["data"]["filters"] == {"month": 8, "year": 2026}
    assert all(row["date"].startswith("2026-08") for row in result["data"]["records"])


def test_unknown_employee_returns_clear_missing_data():
    result = StructuredQueryRouter().route("show my projects", "EMP-9999")
    assert result["success"] is False
    assert "No projects data" in result["message"]


@pytest.mark.parametrize("query", [
    "meri attendance batao",
    "23 September ko mera checkout kya tha?",
    "23 sep ka check in?",
    "mera 23 sep ka complete attendance batao",
    "is month kitne din present tha?",
    "kitne absent tha?",
    "meri total working hours kitni hain?",
    "meri leaves kitni bachi hain?",
    "maine kitni leaves use kari?",
    "meri approved leaves batao",
    "pending leave hai?",
    "meri lifeline kitni remaining hai?",
    "maine kitni lifeline use kari?",
    "meri shift kya hai?",
    "mera branch?",
    "mera designation?",
    "company mein kitni leave milti hai?",
    "kal mera check-in kya tha?",
    "23 September ko main late tha?",
    "us din kitne hours kaam kiya?",
    "meri attendance mein absent kaunse dates hain?",
    "meri last attendance kya hai?",
    "meri July ki attendance?",
    "August mein kitne din present tha?",
    "late check-in lifeline remaining",
    "early checkout lifeline remaining",
    "meri shift timing kya hai?",
    "shifiting timing kya hai",
    "show my leave history",
    "show my salary",
    "what is my net salary?",
    "show my projects",
    "my joining date",
    "my employment status",
    "my job type",
    "half day attendance",
    "present dates this month",
    "absent dates this month",
    "total attendance count",
    "working time this month",
])
def test_real_employee_question_routes_are_generalized(query):
    result = StructuredQueryRouter().route(query, "EMP-0001")
    assert result is not None


def test_lifeline_correction_keeps_previous_lifeline_intent():
    router = StructuredQueryRouter()
    first = router.route(
        "can I see my left early cehck in lifline",
        "EMP-0001",
    )
    corrected = router.route(
        "not check in ki pooch rha hu mai",
        "EMP-0001",
    )
    assert first["data"].keys() == {"late_check_in_remaining", "period"}
    assert corrected["data"].keys() == {"late_check_in_remaining", "period"}


def test_checkout_correction_does_not_return_checkin_records():
    router = StructuredQueryRouter()
    router.route("meri late check in lifeline remaining", "EMP-0001")
    corrected = router.route(
        "nahi checkout ki pooch raha hoon",
        "EMP-0001",
    )
    assert "early_checkout_remaining" in corrected["data"]
    assert "late_check_in_remaining" not in corrected["data"]


@pytest.mark.parametrize("query", [
    "leaves kese apply karte hai",
    "how do I apply for leave",
    "leave apply kaise karu",
])
def test_leave_application_process_uses_company_knowledge(query):
    assert StructuredQueryRouter().route(query, "EMP-0001") is None


def test_leave_application_words_do_not_become_personal_leave_lookup():
    router = StructuredQueryRouter()
    for query in (
        "leaves kese apply kru",
        "how do I apply for leave",
    ):
        assert router.route(query, "EMP-0001") is None


@pytest.mark.parametrize("query", [
    "meri leaves kitni bachi hai",
    "meri leaves kitni bacchi hai",
    "leaves kitni bachi hain",
    "how many leaves are left",
])
def test_leave_balance_uses_entitlement_and_request_data(query):
    result = StructuredQueryRouter().route(query, "EMP-0001")
    assert result["tool_used"] == "get_leave_balance"
    assert "remaining_leaves" in result["data"]


@pytest.mark.parametrize("query", [
    "kon kon si leaves hai",
    "which leaves are available",
    "what leave types do we have",
    "kaun kaun si chhutti milti hai",
])
def test_leave_type_questions_use_company_leave_policy(query):
    result = StructuredQueryRouter().route(query, "EMP-0001")
    assert result["tool_used"] == "get_leave_types"
    assert result["data"]["records"]


@pytest.mark.parametrize("query", [
    "mujhe bta meri company m total kitne employee hai or sabke name",
    "company m total employee kitne hai",
    "how many employees are in my company",
    "employee count",
])
def test_company_employee_directory_uses_employee_csv(query):
    result = StructuredQueryRouter().route(query, "EMP-0001")
    assert result["tool_used"] == "get_company_employees"
    assert result["data"]["total_employees"] == 10
