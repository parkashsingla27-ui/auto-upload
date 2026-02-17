@echo off
echo Installing PyInstaller...
python -m pip install pyinstaller

echo Building EXE...
python -m PyInstaller --noconfirm --onefile --console --name "TelegramBot" --hidden-import="moviepy" --hidden-import="pydub" --hidden-import="imageio" --copy-metadata="imageio" --collect-all="moviepy" bot.py

echo Done! Check the dist folder.
pause
