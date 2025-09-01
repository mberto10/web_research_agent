from core.state import Evidence
from tools import register_tool, get_tool, SonarAdapter, ExaAdapter


class DummyAdapter:
    name = "dummy"

    def call(self, *args, **kwargs):
        return [Evidence(url="http://example.com", tool="dummy")]


def test_registry_register_and_get():
    register_tool(DummyAdapter())
    tool = get_tool("dummy")
    result = tool.call()
    assert result[0].tool == "dummy"


def test_sonar_adapter_normalizes(monkeypatch):
    adapter = SonarAdapter(api_key="test")

    def fake_chat(messages, **params):
        return {
            "choices": [
                {
                    "message": {
                        "citations": [
                            {
                                "url": "http://example.com",
                                "title": "Example",
                                "publisher": "ExamplePub",
                                "publishedAt": "2024-01-01",
                                "snippet": "Snippet",
                            }
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(adapter, "_chat_completion", fake_chat)
    evidence = adapter.call("hello world")
    assert evidence[0].url == "http://example.com"
    assert evidence[0].tool == "sonar"


def test_exa_adapter_search_normalizes(monkeypatch):
    adapter = ExaAdapter(api_key="test")

    class FakeClient:
        def search(self, query, **params):
            return {
                "results": [
                    {
                        "url": "http://exa.example",
                        "title": "Exa",
                        "source": "ExaSource",
                        "publishedDate": "2024-02-02",
                        "snippet": "Snippet",
                        "score": 0.5,
                    }
                ]
            }

    monkeypatch.setattr(adapter, "_client", lambda: FakeClient())
    evidence = adapter.search("query")
    assert evidence[0].url == "http://exa.example"
    assert evidence[0].publisher == "ExaSource"
    assert evidence[0].tool == "exa"
