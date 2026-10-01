@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo [%date% %time%] >> paylasim.log
"C:\Users\90546\AppData\Local\Programs\Python\Python311\python.exe" youtube_yukle.py --adet 1 >> paylasim.log 2>&1
