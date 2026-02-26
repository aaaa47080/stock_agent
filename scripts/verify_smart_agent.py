import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.smart_agents import SmartTechnicalAnalyst
from utils.llm_client import create_llm_client_from_config
from core.config import DEEP_THINKING_MODEL, FAST_THINKING_MODEL


def main():
    print("🚀 Starting Smart Agent Verification...")

    # 1. Create LLM Client
    try:
        # Use FAST_THINKING_MODEL for speed, or DEEP_THINKING_MODEL for better reasoning
        print(f"Initializing Client with model: {FAST_THINKING_MODEL.get('model')}...")
        client, model_name = create_llm_client_from_config(FAST_THINKING_MODEL)
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return

    # 2. Instantiate SmartTechnicalAnalyst
    try:
        analyst = SmartTechnicalAnalyst(client)
        print("✅ SmartTechnicalAnalyst instantiated.")
    except Exception as e:
        print(f"❌ Failed to instantiate analyst: {e}")
        return

    # 3. Prepare Test Data (Minimal)
    # Note: We don't provide pre-fetched indicators. We expect the agent to fetch them.
    market_data = {
        "symbol": "BTC-USDT",
        "interval": "1h",
        "market_type": "spot",
        "exchange": "okx",
    }

    print(f"\n📊 Requesting analysis for {market_data['symbol']}...")

    # 4. Run Analysis
    try:
        report = analyst.analyze(market_data)

        print("\n✅ Analysis Complete!")
        print("=" * 40)
        print(f"Type: {report.analyst_type}")
        print(f"Confidence: {report.confidence}")
        print(f"Summary: {report.summary}")
        print("-" * 20)
        print("Key Findings:")
        for f in report.key_findings:
            print(f"- {f}")
        print("=" * 40)

    except Exception as e:
        print(f"\n❌ Analysis Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
