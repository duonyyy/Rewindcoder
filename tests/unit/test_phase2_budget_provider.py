import os
import time
import unittest
from unittest.mock import patch

from rewindcoder.contracts.task import TaskBudget
from rewindcoder.providers.factory import create_provider
from rewindcoder.providers.mock import MockProvider
from rewindcoder.runtime.budget import BudgetExceeded, BudgetMeter
from rewindcoder.tools.policy import Permission, fixture_bootstrap_permission


class Phase2BudgetProviderTests(unittest.TestCase):
    def test_each_budget_limit(self):
        limits = TaskBudget(max_agent_steps=1, max_rewinds=0, max_tokens=1, max_tool_calls=1, timeout_seconds=1)
        meter = BudgetMeter(limits)
        meter.step()
        with self.assertRaisesRegex(BudgetExceeded, "max_agent_steps"):
            meter.step()
        meter.tool()
        with self.assertRaisesRegex(BudgetExceeded, "max_tool_calls"):
            meter.tool()
        with self.assertRaisesRegex(BudgetExceeded, "max_tokens"):
            meter.charge_text("more than four bytes")
        expired = BudgetMeter(limits, started=time.monotonic() - 2)
        with self.assertRaisesRegex(BudgetExceeded, "timeout"):
            expired.remaining_seconds()

    def test_provider_factory_defaults_to_mock_and_external_is_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(create_provider(), MockProvider)
        with patch.dict(os.environ, {"REWINDCODER_PROVIDER": "external"}, clear=True):
            with self.assertRaisesRegex(ValueError, "trusted"):
                create_provider()
        with patch.dict(os.environ, {"REWINDCODER_PROVIDER": "unknown"}, clear=True):
            with self.assertRaisesRegex(ValueError, "unsupported"):
                create_provider()

    def test_fixture_bootstrap_policy_is_exact(self):
        self.assertEqual(fixture_bootstrap_permission("git add --all"), Permission.AUTO)
        self.assertEqual(fixture_bootstrap_permission("git add ../secret"), Permission.DENY)
