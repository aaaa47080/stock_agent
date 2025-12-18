#!/bin/bash

# This script runs the backend crypto analyzer with auto-trading in the background.
# All output will be redirected to 'trading_analysis.log'.

# You can customize the parameters below:
# --batch: Run batch analysis on all symbols from the config file.
# --async-batch: Run async batch analysis on all symbols (parallel analysis for faster execution).
# --symbol <SYMBOL>: Analyze a single crypto symbol (e.g., BTC). (Remove --batch if using --symbol)
# --exchange okx: The exchange to use (e.g., okx).
# --interval 5m,15m,30m: Comma-separated list of intervals for short, medium, and long term analysis.
#                        The last one is the main interval for data fetching.
# --auto-trade: Enable live auto-trading after analysis. (USE WITH CAUTION IN LIVE ENVIRONMENTS!)

# Example commands:
# nohup python3 -u analysis/backend_analyzer.py --batch --exchange okx --interval 5m,15m,30m --auto-trade > trading_analysis.log 2>&1 &
# nohup python3 -u analysis/async_backend_analyzer.py --async-batch --exchange okx --interval 5m,15m,30m --auto-trade > trading_analysis.log 2>&1 &

# Command to execute (default: using async version for better performance)
nohup python3 -u analysis/async_backend_analyzer.py --async-batch --exchange okx --interval 5m,15m,30m --auto-trade > trading_analysis.log 2>&1 &

echo "Backend analyzer started in the background."
echo "Output is logged to trading_analysis.log"
echo "To check the log: tail -f trading_analysis.log"
echo "To stop the process, find its PID: ps aux | grep backend_analyzer.py, then kill <PID>"
