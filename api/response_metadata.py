def build_response_metadata(result: dict, analysis_mode: str) -> dict:
    task_results = result.get("task_results", {}) if isinstance(result, dict) else {}
    used_tools = []
    verification_status = "standard" if analysis_mode == "quick" else analysis_mode
    quality_fail_reason = None
    data_as_of = None

    for task_result in task_results.values():
        if not isinstance(task_result, dict):
            continue
        task_data = task_result.get("data", {})
        if isinstance(task_data, dict):
            used_tools.extend(task_data.get("used_tools", []))
            data_as_of = data_as_of or task_data.get("data_as_of")
            verification_status = task_data.get("verification_status", verification_status)
        quality_fail_reason = quality_fail_reason or task_result.get("quality_fail_reason")

    if quality_fail_reason:
        verification_status = "unverified"

    return {
        "analysis_mode": analysis_mode,
        "verification_status": verification_status,
        "quality_fail_reason": quality_fail_reason,
        "used_tools": sorted({tool for tool in used_tools if tool}),
        "data_as_of": data_as_of,
    }
