from api.response_metadata import build_response_metadata


def test_build_response_metadata_collects_tools_and_verified_status():
    result = {
        "task_results": {
            "task_1": {
                "data": {
                    "used_tools": ["tw_stock_price"],
                    "verification_status": "verified",
                    "data_as_of": "2026-03-13T10:00:00Z",
                },
                "quality_fail_reason": None,
            }
        }
    }

    metadata = build_response_metadata(result, "verified")

    assert metadata["analysis_mode"] == "verified"
    assert metadata["verification_status"] == "verified"
    assert metadata["used_tools"] == ["tw_stock_price"]
    assert metadata["data_as_of"] == "2026-03-13T10:00:00Z"


def test_build_response_metadata_marks_unverified_on_quality_failure():
    result = {
        "task_results": {
            "task_1": {
                "data": {
                    "verification_status": "verified",
                },
                "quality_fail_reason": "verified_tool_unavailable",
            }
        }
    }

    metadata = build_response_metadata(result, "verified")

    assert metadata["verification_status"] == "unverified"
    assert metadata["quality_fail_reason"] == "verified_tool_unavailable"
