from app import _within_preset


def test_within_preset_basic():
    preset = {"min_valence": 0.5, "max_energy": 0.7}
    features = {"valence": 0.6, "energy": 0.6}
    assert _within_preset(features, preset) is True


def test_within_preset_fail_min():
    preset = {"min_valence": 0.8}
    features = {"valence": 0.6}
    assert _within_preset(features, preset) is False


def test_within_preset_fail_max():
    preset = {"max_energy": 0.5}
    features = {"energy": 0.6}
    assert _within_preset(features, preset) is False
