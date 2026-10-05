@echo off
REM Pull the local LLM once (needs internet ONCE, then fully offline).
ollama pull qwen3:8b
echo Done. (For a lighter model: ollama pull qwen3:4b)
pause
