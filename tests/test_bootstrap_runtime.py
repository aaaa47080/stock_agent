from unittest.mock import MagicMock

from langchain_core.messages import SystemMessage, HumanMessage

from core.agents.bootstrap import (
    LanguageAwareLLM,
    bootstrap,
    get_manager_instance,
    invalidate_manager_cache,
)


def make_mock_llm(content="ok"):
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=content)
    llm.ainvoke = MagicMock(return_value=MagicMock(content=content))
    return llm


def test_bootstrap_isolates_managers_by_session():
    user_id = "bootstrap-test-user"
    invalidate_manager_cache(user_id)

    manager_a = bootstrap(make_mock_llm("a"), web_mode=False, user_id=user_id, session_id="session-a")
    manager_a_reused = bootstrap(make_mock_llm("a2"), web_mode=False, user_id=user_id, session_id="session-a")
    manager_b = bootstrap(make_mock_llm("b"), web_mode=False, user_id=user_id, session_id="session-b")

    assert manager_a_reused is manager_a
    assert manager_a is not manager_b
    assert get_manager_instance(user_id, "session-a") is manager_a
    assert get_manager_instance(user_id, "session-b") is manager_b

    invalidate_manager_cache(user_id)


async def test_language_aware_llm_ainvoke_injects_system_message():
    class DummyLLM:
        def __init__(self):
            self.last_messages = None

        async def ainvoke(self, messages, **kwargs):
            self.last_messages = list(messages)
            return MagicMock(content="done")

    dummy = DummyLLM()
    wrapped = LanguageAwareLLM(dummy, language="zh-TW")

    response = await wrapped.ainvoke([HumanMessage(content="測試訊息")])

    assert response.content == "done"
    assert isinstance(dummy.last_messages[0], SystemMessage)
    assert "請以繁體中文回覆所有回應" in dummy.last_messages[0].content
    assert dummy.last_messages[1].content == "測試訊息"
