#!/usr/bin/env python3
"""Скачать трек Яндекс Музыки или аудио YouTube в MP3."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse, parse_qs


def normalize_url(value):
    value = value.strip()
    match = re.fullmatch(r'\[.*\]\((https?://.*)\)', value, re.DOTALL)
    if match:
        value = match.group(1)
    return re.sub(r'\\+([?&=/#])', r'\1', value)


def youtube_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return None
    host = parsed.hostname
    if host not in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be', 'www.youtu.be'}:
        return None
    parts = parsed.path.strip('/').split('/')
    video = None
    if host in {'youtu.be', 'www.youtu.be'}:
        video = parts[0]
    elif parsed.path == '/watch':
        video = parse_qs(parsed.query).get('v', [None])[0]
    elif len(parts) == 2 and parts[0] in {'shorts', 'embed', 'live'}:
        video = parts[1]
    if not video or not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('Нужна ссылка на конкретное видео YouTube.')
    return f'https://www.youtube.com/watch?v={video}'


def download_youtube(url, folder):
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise RuntimeError('Установите: python3 -m pip install -U "yt-dlp[default]"')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('Нужен FFmpeg. На macOS с Homebrew: brew install ffmpeg')
    folder.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
               '--no-overwrites', '-f', 'bestaudio/best', '-x', '--audio-format', 'mp3',
               '--audio-quality', '0', '--embed-metadata', '-P', str(folder),
               '-o', '%(title).150B [%(id)s].%(ext)s', '--', url]
    if subprocess.run(command).returncode:
        raise RuntimeError('YouTube: скачивание не завершено. См. сообщение выше; попробуйте обновить yt-dlp.')
    print(f'Аудио сохранено в: {folder.resolve()}')


def track_id(url):
    parsed = urlparse(normalize_url(url))
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in {
        'music.yandex.ru', 'music.yandex.com', 'music.yandex.by', 'music.yandex.kz', 'music.yandex.uz',
    }:
        raise ValueError('Поддерживаются ссылки Яндекс Музыки и YouTube.')
    match = re.fullmatch(r'/(?:album/(\d+)/)?track/(\d+)/?', parsed.path)
    if not match:
        raise ValueError('Нужна ссылка /album/123/track/456 или /track/456.')
    album, track = match.groups()
    return f'{track}:{album}' if album else track


def save_token(path, credentials):
    fd, temporary = tempfile.mkstemp(prefix='.yandex-token-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump({'access_token': credentials.access_token,
                       'expires_at': time.time() + float(credentials.expires_in or 0)}, stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def download_yandex(identifier, folder, login):
    try:
        from yandex_music import Client
    except ImportError:
        raise RuntimeError('Установите: python3 -m pip install -U yandex-music')
    token_file = Path(__file__).resolve().parent / '.yandex_music_token.json'
    token = None if login else os.environ.get('YANDEX_MUSIC_TOKEN')
    if not token and not login and token_file.exists():
        try:
            saved = json.loads(token_file.read_text(encoding='utf-8'))
            if saved.get('expires_at', 0) > time.time() + 60:
                token = saved.get('access_token')
        except (ValueError, TypeError, AttributeError):
            print('Сохранённая авторизация повреждена. Войдите заново.')
    client = Client(token) if token else Client()
    if not token:
        def on_code(code):
            print(f'Откройте {code.verification_url} и введите код: {code.user_code}', flush=True)
        credentials = client.device_auth(on_code=on_code)
        client.init()
        save_token(token_file, credentials)
        print('Авторизация сохранена для следующих запусков.')
    else:
        client.init()
    tracks = client.tracks([identifier])
    if not tracks:
        raise RuntimeError('Трек не найден.')
    track = tracks[0]
    variants = [item for item in track.get_download_info() if item.codec == 'mp3']
    if not variants:
        raise RuntimeError('API не предоставил MP3. Проверьте доступ аккаунта и подписку.')
    best = max(variants, key=lambda item: item.bitrate_in_kbps)
    artists = ', '.join(artist.name for artist in track.artists or [])
    title = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', f'{artists} - {track.title}').strip(' .')[:100] or 'track'
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f'{title} [{track.id}].mp3'
    if destination.exists():
        print(f'Файл уже существует: {destination.resolve()}')
        return
    fd, temporary = tempfile.mkstemp(prefix='.download-', suffix='.part', dir=folder)
    os.close(fd)
    try:
        track.download(temporary, codec='mp3', bitrate_in_kbps=best.bitrate_in_kbps)
        if Path(temporary).stat().st_size == 0:
            raise RuntimeError('Сервис вернул пустой файл.')
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(f'Скачано: {destination.resolve()}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', help='Ссылка на трек или видео')
    parser.add_argument('-o', '--output', default='music', help='Папка назначения')
    parser.add_argument('--login', action='store_true', help='Войти заново в Яндекс')
    args = parser.parse_args()
    url = normalize_url(args.url)
    folder = Path(args.output).expanduser().resolve()
    video = youtube_url(url)
    if video:
        download_youtube(video, folder)
    else:
        download_yandex(track_id(url), folder, args.login)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as error:
        if isinstance(error, (ValueError, RuntimeError)):
            print(f'Ошибка: {error}', file=sys.stderr)
        else:
            print(f'Ошибка: {type(error).__name__}. Проверьте сеть и доступность трека. Для повторного входа в Яндекс добавьте --login.', file=sys.stderr)
        sys.exit(1)
