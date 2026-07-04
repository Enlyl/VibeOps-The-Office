@echo off
echo ===================================================
echo 🚀 VibeOps Multi-Agent UI Initialization
echo ===================================================

echo [1/2] Checking and installing dependencies...
python -m pip install streamlit pandas

echo [2/2] Starting Streamlit Server...
set PYTHONUTF8=1
python -m streamlit run app.py

pause
