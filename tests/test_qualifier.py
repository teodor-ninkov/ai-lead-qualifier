import json

import pandas as pd
import pytest

import qualifier


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(reply)


class FakeClient:
    def __init__(self, replies):
        self.models = FakeModels(replies)


def good(score="Hot"):
    return json.dumps({
        "vehicle": "2019 Honda Civic",
        "pickup_city": "Miami, FL",
        "delivery_city": "Chicago, IL",
        "desired_date": "next Monday",
        "score": score,
        "score_reason": "Clear details",
        "follow_up_email": "Hi Michael",
    })


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(qualifier.time, "sleep", lambda seconds: None)


def test_parse_response_reads_plain_json():
    result = qualifier.parse_response(good())
    assert result["vehicle"] == "2019 Honda Civic"
    assert result["score"] == "Hot"


def test_parse_response_strips_code_fences():
    result = qualifier.parse_response("```json\n" + good("Warm") + "\n```")
    assert result["score"] == "Warm"


def test_parse_response_normalises_score():
    assert qualifier.parse_response(good("hot"))["score"] == "Hot"
    assert qualifier.parse_response(good("Lukewarm"))["score"] == "Cold"


def test_parse_response_fills_missing_fields():
    result = qualifier.parse_response(json.dumps({"score": "Warm"}))
    assert set(result) == set(qualifier.OUTPUT_FIELDS)
    assert result["vehicle"] == ""


def test_validate_columns_reports_missing():
    df = pd.DataFrame({"name": ["A"], "email": ["a@x.com"]})
    assert qualifier.validate_columns(df) == ["phone", "message", "date"]


def test_retry_recovers_from_overload():
    client = FakeClient([RuntimeError("503 UNAVAILABLE"), RuntimeError("429 RESOURCE_EXHAUSTED"), good()])
    result = qualifier.qualify_with_retry(client, {"name": "M", "message": "x", "date": "d"}, "model")
    assert result["score"] == "Hot"
    assert client.models.calls == 3


def test_retry_does_not_repeat_bad_requests():
    client = FakeClient([RuntimeError("400 INVALID_ARGUMENT"), good()])
    with pytest.raises(RuntimeError):
        qualifier.qualify_with_retry(client, {"name": "M", "message": "x", "date": "d"}, "model")
    assert client.models.calls == 1


def test_one_failed_lead_does_not_stop_the_batch(monkeypatch):
    replies = [good(), RuntimeError("400 INVALID_ARGUMENT"), good("Cold")]
    monkeypatch.setattr(qualifier, "get_client", lambda api_key=None: FakeClient(replies))
    leads = pd.DataFrame({
        "name": ["A", "B", "C"], "email": [""] * 3, "phone": [""] * 3,
        "message": ["x"] * 3, "date": ["d"] * 3,
    })
    results = qualifier.qualify_leads(leads, api_key="test")
    assert list(results["score"]) == ["Hot", "Error", "Cold"]
    assert "400" in results.loc[1, "score_reason"]
