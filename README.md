# yandex-music-downloader

Установите библиотеку:
```bash
python3 -m pip install -U yandex-music
```

ЧТобы скачать музыку с Яндекса, перейдите в папку проекта в терминале и введите 

```bash
python3 download_music.py "https://music.yandex.ru/album/5600810/track/38816585"
```

Скрипт пришлёт ссылку на авторизацию, введите там код для подключения API

Чтобы сменить аккаунт, введите
```bash
python3 download_music.py "ССЫЛКА" --login
```
