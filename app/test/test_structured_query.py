from app.Services.structured_query import StructuredQueryRouter


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
