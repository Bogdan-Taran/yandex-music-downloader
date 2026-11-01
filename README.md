# multi-music-downloader

Установите библиотеку и зависимости:
```bash
python3 -m pip install -U yandex-music
python3 -m pip install -U "yt-dlp[default]" yandex-music
```
ля macOS с Homebrew использует FFmpeg для преобразования аудио и JavaScript-движок для поддержки YouTube
```bash
brew install ffmpeg deno
```
Д

ЧТобы скачать музыку с Яндекса, перейдите в папку проекта в терминале и введите 
```bash
python3 download_music.py "https://music.yandex.ru/album/5600810/track/38816585"
```

Чтобы скачать музыку с ютуба, пришлите ссылку на видео, скрипт сам преобразует в аудио:
```bash
python3 download_music.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"
```

Скрипт пришлёт ссылку на авторизацию, введите там код для подключения API

Чтобы сменить аккаунт, введите
```bash
python3 download_music.py "ССЫЛКА" --login
```
