from __future__ import annotations

import pytest
from pydantic import ValidationError

from rag_api.schemas import AskRequest


def test_empty_or_whitespace_question_rejected() -> None:
    with pytest.raises(ValidationError):
        AskRequest(question="", node_id="N-CEO")
    with pytest.raises(ValidationError):
        AskRequest(question="   ", node_id="N-CEO")


def test_question_too_long_rejected() -> None:
    with pytest.raises(ValidationError):
        AskRequest(question="x" * 2001, node_id="N-CEO")


def test_node_id_uppercased() -> None:
    request = AskRequest(question="hello", node_id="n-ceo")
    assert request.node_id == "N-CEO"


def test_bad_node_id_rejected() -> None:
    with pytest.raises(ValidationError):
        AskRequest(question="hello", node_id="CEO")


def test_top_k_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        AskRequest(question="hello", node_id="N-CEO", top_k=0)
    with pytest.raises(ValidationError):
        AskRequest(question="hello", node_id="N-CEO", top_k=11)


def test_valid_request_accepted() -> None:
    request = AskRequest(question="  hello  ", node_id="N-CEO", top_k=5)
    assert request.question == "hello"
    assert request.node_id == "N-CEO"
    assert request.top_k == 5
