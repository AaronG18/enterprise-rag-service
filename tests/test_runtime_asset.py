"""The bundled runtime must follow the platform, not hard-code Windows (issue #148).

Hard-coding the Windows asset meant a reviewer on macOS or Linux never got a model: `--setup`
reported MISSING and the service silently ran the deterministic backend, so the headline feature of
the deliverable was unavailable on the machine they actually use.
"""
from __future__ import annotations

import platform
import unittest

from ragserve.cli import setup as setup_mod


class RuntimeAssetTest(unittest.TestCase):
    def _asset(self, system: str, machine: str) -> str:
        original = (platform.system, platform.machine)
        platform.system = lambda: system
        platform.machine = lambda: machine
        try:
            return setup_mod.runtime_asset()
        finally:
            platform.system, platform.machine = original

    def test_each_platform_picks_its_own_asset(self):
        cases = [
            ("Windows", "AMD64", "win-cpu-x64"),
            ("Linux", "x86_64", "ubuntu-x64"),
            ("Darwin", "arm64", "macos-arm64"),
            ("Darwin", "x86_64", "macos-x64"),
        ]
        for system, machine, expected in cases:
            asset = self._asset(system, machine)
            self.assertIn(expected, asset, "%s/%s must download %s" % (system, machine, expected))
            self.assertIn(setup_mod.LLAMA_BUILD, asset)

    def test_an_unknown_platform_is_reported_not_guessed(self):
        self.assertEqual(self._asset("Plan9", "vax"), "",
                         "an unsupported platform must not silently download a wrong binary")
        self.assertEqual(setup_mod.runtime_sources(""), [],
                         "no asset means no download attempt")

    def test_sources_point_at_the_chosen_asset(self):
        asset = setup_mod.runtime_asset()
        for url in setup_mod.runtime_sources(asset):
            self.assertTrue(url.endswith(asset), url)


if __name__ == "__main__":
    unittest.main()
