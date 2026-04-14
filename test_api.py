"""
Test script for the Crypto Trading API.
Run this to verify the API is working correctly.
"""
import requests
import json

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    print("\n=== Testing Health Check ===")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ Health check passed")


def test_get_signal():
    """Test signal generation."""
    print("\n=== Testing Signal Generation ===")
    response = requests.get(f"{BASE_URL}/signal/BTC")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Token: {data.get('token')}")
    print(f"Action: {data.get('action')}")
    print(f"Confidence: {data.get('confidence')}")
    print(f"Reason: {data.get('reason')}")
    assert response.status_code == 200
    assert "confidence" in data
    print("✅ Signal generation passed")


def test_get_multiple_signals():
    """Test multiple signals."""
    print("\n=== Testing Multiple Signals ===")
    response = requests.post(
        f"{BASE_URL}/signals",
        params={"use_ai": True},
        json=["BTC", "ETH", "CAKE"]
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Generated {len(data)} signals")
    for signal in data:
        print(f"  - {signal['token']}: {signal['action']} (conf: {signal['confidence']})")
    assert response.status_code == 200
    assert len(data) == 3
    print("✅ Multiple signals passed")


def test_simulate_trade():
    """Test trade simulation."""
    print("\n=== Testing Trade Simulation ===")
    response = requests.post(
        f"{BASE_URL}/trade/simulate",
        json={
            "token": "CAKE",
            "action": "BUY",
            "entry_price": 2.50,
            "position_size": 0.01,
            "confidence": 0.75
        }
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Trade ID: {data.get('id')}")
    print(f"Token: {data.get('token')}")
    print(f"Status: {data.get('status')}")
    assert response.status_code == 200
    assert data["status"] == "OPEN"
    print("✅ Trade simulation passed")
    return data["id"]


def test_get_performance():
    """Test performance endpoint."""
    print("\n=== Testing Performance Metrics ===")
    response = requests.get(f"{BASE_URL}/performance")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Total Trades: {data.get('total_trades')}")
    print(f"Win Rate: {data.get('win_rate')}%")
    print(f"Total PnL: {data.get('total_pnl')}")
    assert response.status_code == 200
    print("✅ Performance metrics passed")


def test_get_history():
    """Test history endpoint."""
    print("\n=== Testing Trade History ===")
    response = requests.get(f"{BASE_URL}/history", params={"limit": 10})
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Total Trades: {data.get('total')}")
    print(f"Returned: {len(data.get('trades', []))}")
    assert response.status_code == 200
    print("✅ Trade history passed")


def test_close_trade(trade_id: int):
    """Test closing a trade."""
    print(f"\n=== Testing Close Trade (ID: {trade_id}) ===")
    response = requests.post(
        f"{BASE_URL}/trade/close/{trade_id}",
        params={"exit_price": 2.75}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Trade ID: {data.get('id')}")
    print(f"Status: {data.get('status')}")
    print(f"PnL: {data.get('pnl')}")
    assert response.status_code == 200
    assert data["status"] == "CLOSED"
    print("✅ Close trade passed")


def test_get_config():
    """Test config endpoint."""
    print("\n=== Testing Configuration ===")
    response = requests.get(f"{BASE_URL}/config")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Testnet Mode: {data.get('testnet_mode')}")
    print(f"Copy Trading: {data.get('copy_trading_enabled')}")
    print(f"Confidence Threshold: {data.get('ai_confidence_threshold')}")
    assert response.status_code == 200
    print("✅ Configuration passed")


def run_all_tests():
    """Run all tests in sequence."""
    print("\n" + "="*50)
    print("CRYPTO TRADING API - TEST SUITE")
    print("="*50)
    
    try:
        test_health()
        test_get_signal()
        test_get_multiple_signals()
        trade_id = test_simulate_trade()
        test_get_performance()
        test_get_history()
        test_close_trade(trade_id)
        test_get_config()
        
        print("\n" + "="*50)
        print("ALL TESTS PASSED ✅")
        print("="*50)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except requests.ConnectionError:
        print("\n❌ Cannot connect to API. Is the server running?")
        print("   Start with: uvicorn main:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    run_all_tests()
