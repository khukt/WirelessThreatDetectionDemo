import unittest
from unittest.mock import patch

import numpy as np

from wireless_demo.helpers import conformal_pvalue
from wireless_demo.persistence import hydrate_model_artifacts
from wireless_demo.training import suggest_threshold


class CalibrationTests(unittest.TestCase):
    def test_high_anomaly_score_has_lower_pvalue(self):
        scores = np.array([0.1, 0.2, 0.4, 0.6])
        with patch("wireless_demo.helpers.st.session_state", {"conformal_scores": scores}):
            self.assertAlmostEqual(conformal_pvalue(0.15), 0.8)
            self.assertAlmostEqual(conformal_pvalue(0.9), 0.2)

    def test_threshold_uses_calibration_labels(self):
        labels = np.array([0, 0, 1, 1])
        scores = np.array([0.1, 0.4, 0.6, 0.9])
        self.assertAlmostEqual(suggest_threshold(labels, scores), 0.41)

    def test_legacy_cache_disables_incompatible_calibration(self):
        legacy = hydrate_model_artifacts({"conformal_scores": np.array([0.3])})
        self.assertIsNone(legacy["conformal_scores"])

        current = hydrate_model_artifacts({
            "calibration_method": "normal_anomaly_score",
            "conformal_scores": np.array([0.3]),
        })
        np.testing.assert_array_equal(current["conformal_scores"], [0.3])


if __name__ == "__main__":
    unittest.main()
