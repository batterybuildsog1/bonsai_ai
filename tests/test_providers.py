import unittest
from unittest.mock import patch

from bonsai_ai_core.errors import ProviderError
from bonsai_ai_core.providers import OpenAIProvider, ProviderRequest


class ProviderTests(unittest.TestCase):
    @patch("bonsai_ai_core.providers.post_json")
    def test_openai_provider_extracts_output_text(self, mock_post_json):
        mock_post_json.return_value = {
            "output_text": '{"version":"1.0","units":"meters","summary":"ok","assumptions":[],"actions":[{"type":"ensure_storey","name":"Level 1","elevation":0}]}'
        }
        provider = OpenAIProvider(
            ProviderRequest(
                provider="openai",
                system_prompt="system",
                user_prompt="user",
                model="gpt-5.4",
                api_key="test-key",
                reasoning_effort="medium",
                service_tier="priority",
            )
        )
        plan = provider.generate_plan()
        self.assertEqual(plan["summary"], "ok")
        payload = mock_post_json.call_args.args[1]
        self.assertEqual(payload["model"], "gpt-5.4")
        self.assertEqual(payload["reasoning"], {"effort": "medium"})
        self.assertEqual(payload["service_tier"], "priority")

    @patch("bonsai_ai_core.providers.post_json")
    def test_openai_provider_retries_without_priority_when_rejected(self, mock_post_json):
        seen_payloads = []

        def fake_post_json(_url, payload, _headers):
            seen_payloads.append(dict(payload))
            if len(seen_payloads) == 1:
                raise ProviderError(
                    "HTTP 400 calling https://api.openai.com/v1/responses: "
                    "{\"error\":{\"message\":\"Unsupported service_tier priority\"}}"
                )
            return {
                "output_text": '{"version":"1.0","units":"meters","summary":"ok","assumptions":[],"actions":[{"type":"ensure_storey","name":"Level 1","elevation":0}]}'
            }

        mock_post_json.side_effect = fake_post_json
        provider = OpenAIProvider(
            ProviderRequest(
                provider="openai",
                system_prompt="system",
                user_prompt="user",
                model="gpt-5.4",
                api_key="test-key",
                reasoning_effort="medium",
                service_tier="priority",
            )
        )

        plan = provider.generate_plan()

        self.assertEqual(plan["summary"], "ok")
        self.assertEqual(len(seen_payloads), 2)
        self.assertEqual(seen_payloads[0]["service_tier"], "priority")
        self.assertNotIn("service_tier", seen_payloads[1])


if __name__ == "__main__":
    unittest.main()
