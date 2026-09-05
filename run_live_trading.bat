@echo off
cd /d "C:\Users\PC\Documents\scalper-trading-bot"
echo. >> logs\live_trading_log.txt
echo ===== %date% %time% ===== >> logs\live_trading_log.txt
"C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe" run_live_trading.py >> logs\live_trading_log.txt 2>&1
