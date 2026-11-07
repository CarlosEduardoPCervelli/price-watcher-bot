import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import watcher  # noqa: E402
from watcher import Config, PriceResult, Product, should_alert  # noqa: E402

NOW = datetime(2026, 11, 7, 12, 0, 0)
TARGET = 250.0


def last_alert(price: float, hours_ago: float) -> dict:
    return {"price": price, "alerted_at": (NOW - timedelta(hours=hours_ago)).isoformat()}


# --------------------------------------------------------------------------- #
# should_alert
# --------------------------------------------------------------------------- #

def test_never_alerts_above_target():
    assert should_alert(None, 260.0, TARGET, NOW) is False


def test_alerts_first_time_at_target():
    assert should_alert(None, 250.0, TARGET, NOW) is True


def test_no_repeat_alert_with_same_price_inside_cooldown():
    assert should_alert(last_alert(240.0, 1), 240.0, TARGET, NOW) is False


def test_alerts_again_after_cooldown():
    assert should_alert(last_alert(240.0, 25), 240.0, TARGET, NOW, cooldown_hours=24) is True


def test_alerts_on_new_low_even_inside_cooldown():
    # 240 -> 230 é uma queda de ~4,2% (> 1%)
    assert should_alert(last_alert(240.0, 1), 230.0, TARGET, NOW) is True


def test_tiny_drop_is_ignored():
    # 240 -> 239,5 é queda de ~0,2% (< 1%)
    assert should_alert(last_alert(240.0, 1), 239.5, TARGET, NOW) is False


def test_corrupted_last_alert_still_alerts():
    assert should_alert({"price": "abc"}, 240.0, TARGET, NOW) is True


# --------------------------------------------------------------------------- #
# extract_item_id / mensagens
# --------------------------------------------------------------------------- #

def test_extract_item_id_from_url():
    assert watcher.extract_item_id("https://x.com/produto/p/MLB12345678") == "MLB12345678"


def test_extract_item_id_none():
    assert watcher.extract_item_id("https://example.com/sem-id") is None


def test_email_body_escapes_html():
    product = Product(name="<script>alert(1)</script>", url="https://x.com/?a=1&b='2'", target_price=10)
    body = watcher._email_body(product, 9.0)
    assert "<script>" not in body
    assert "&lt;script&gt;" in body


# --------------------------------------------------------------------------- #
# check_all (integração com arquivos em pasta temporária)
# --------------------------------------------------------------------------- #

@pytest.fixture
def env(tmp_path, monkeypatch):
    products = tmp_path / "products.json"
    products.write_text(json.dumps([
        {"name": "Teclado", "url": "https://x.com/MLB111", "target_price": 250.0}
    ]), encoding="utf-8")
    monkeypatch.setattr(watcher, "DATA_FILE", products)
    monkeypatch.setattr(watcher, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(watcher, "ALERT_STATE_FILE", tmp_path / "alert_state.json")

    sent = []
    monkeypatch.setattr(watcher, "send_telegram", lambda s, c, p, price: sent.append(price) or True)

    def set_price(price):
        monkeypatch.setattr(watcher, "get_price", lambda s, u: PriceResult("Teclado", price, "BRL"))

    return sent, set_price, tmp_path


CFG = Config(telegram_token="t", telegram_chat_id="c")


def test_sends_only_one_alert_across_cycles(env):
    sent, set_price, _ = env
    set_price(240.0)
    for _ in range(3):
        watcher.check_all(CFG, session=None)
    assert sent == [240.0]


def test_rearms_after_price_goes_back_above_target(env):
    sent, set_price, tmp_path = env
    set_price(240.0)
    watcher.check_all(CFG, session=None)
    set_price(300.0)
    watcher.check_all(CFG, session=None)
    assert json.loads((tmp_path / "alert_state.json").read_text()) == {}
    set_price(240.0)
    watcher.check_all(CFG, session=None)
    assert sent == [240.0, 240.0]


def test_failed_delivery_is_retried_next_cycle(env, monkeypatch):
    sent, set_price, _ = env
    set_price(240.0)
    monkeypatch.setattr(watcher, "send_telegram", lambda s, c, p, price: False)
    watcher.check_all(CFG, session=None)
    monkeypatch.setattr(watcher, "send_telegram", lambda s, c, p, price: sent.append(price) or True)
    watcher.check_all(CFG, session=None)
    assert sent == [240.0]


def test_history_is_written_every_cycle(env):
    _, set_price, tmp_path = env
    set_price(240.0)
    watcher.check_all(CFG, session=None)
    watcher.check_all(CFG, session=None)
    assert len(json.loads((tmp_path / "history.json").read_text())) == 2
