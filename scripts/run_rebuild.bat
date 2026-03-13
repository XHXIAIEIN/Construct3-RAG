@echo off
cd /d D:\Users\Administrator\Documents\GitHub\Construct3-RAG
echo === Regenerate Schema ===
node scripts\generate-schema.js
echo.
echo === Rebuild Index ===
C:\Users\test\AppData\Local\Python\bin\python.exe -m src.ingest.indexer --rebuild
echo.
echo === Done ===
pause
