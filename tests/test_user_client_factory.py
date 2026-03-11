import socket

from utils.user_client_factory import explain_llm_exception


def test_explain_llm_exception_for_dns_failure():
    exc = RuntimeError("Connection error.")
    exc.__cause__ = socket.gaierror(8, "nodename nor servname provided, or not known")

    message = explain_llm_exception(exc)

    assert "DNS" in message
    assert "可連外網" in message


def test_explain_llm_exception_for_auth_failure():
    message = explain_llm_exception(RuntimeError("401 Unauthorized"))
    assert message == "API Key 無效或已過期"
