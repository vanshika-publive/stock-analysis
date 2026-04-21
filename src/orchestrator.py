import subprocess
import json
import os

TICKERS = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN"]

def run_subagent(agent_name: str, prompt: str) -> dict:
    """Invoke a Claude Code subagent via CLI and return parsed JSON output."""
    result = subprocess.run(
        ["claude", "-p", prompt, "--subagent", agent_name],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"error": result.stdout, "stderr": result.stderr}

def process_ticker(ticker: str) -> dict:
    print(f"\n{'='*40}")
    print(f"Processing {ticker}...")

    # Step 1: Fetch raw data
    fetch_result = run_subagent(
        "stock-fetcher",
        f"Fetch historical data for ticker: {ticker}"
    )
    if fetch_result.get("status") != "ok":
        return {"ticker": ticker, "error": "fetch failed"}

    # Step 2: Find ATH/ATL
    extremes = run_subagent(
        "ath-atl-finder",
        f"Find ATH and ATL for ticker: {ticker}"
    )

    # Step 3: Compute time delta
    delta = run_subagent(
        "time-delta-calculator",
        f"Compute time delta. Input: {json.dumps(extremes)}"
    )

    # Step 4: Write analysis
    analysis_input = {**extremes, **delta}
    analysis = run_subagent(
        "stock-analyst",
        f"Analyze this stock profile: {json.dumps(analysis_input)}"
    )

    # Merge all outputs
    return {**extremes, **delta, **analysis}

def main():
    os.makedirs("src/data", exist_ok=True)
    os.makedirs("src/outputs", exist_ok=True)

    results = []
    for ticker in TICKERS:
        result = process_ticker(ticker)
        results.append(result)
        # Cache after each ticker (PostToolUse hook will also do this)
        with open(f"src/data/{ticker}_result.json", "w") as f:
            json.dump(result, f, indent=2)

    # Write aggregated result
    with open("src/outputs/aggregated.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n✓ All tickers processed. Aggregated output in src/outputs/aggregated.json")

if __name__ == "__main__":
    main()