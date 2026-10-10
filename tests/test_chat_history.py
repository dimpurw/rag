from app.services import chat_history


def test_append_and_get_history():
    session_id = "test-session-append"
    chat_history.clear_session(session_id)

    chat_history.append_turn(session_id, "Halo", "Hai juga!")
    history = chat_history.get_history_messages(session_id)

    assert len(history) == 2
    assert history[0].content == "Halo"
    assert history[1].content == "Hai juga!"

    chat_history.clear_session(session_id)


def test_clear_session_removes_history():
    session_id = "test-session-clear"
    chat_history.append_turn(session_id, "Q", "A")
    assert len(chat_history.get_history_messages(session_id)) == 2

    chat_history.clear_session(session_id)
    assert chat_history.get_history_messages(session_id) == []


def test_empty_session_returns_empty_list():
    assert chat_history.get_history_messages("session-belum-pernah-ada") == []
