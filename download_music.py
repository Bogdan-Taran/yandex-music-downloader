#!/usr/bin/env python3
"""Скачивание трека Яндекс Музыки по полной ссылке (Python 3.9+)."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlparse


def track_id(url):
    url = url.strip()
    # При копировании из чата ссылка может иметь вид [текст](URL).
    markdown = re.fullmatch(r'\[.*\]\((https?://.*)\)', url, flags=re.DOTALL)
    if markdown:
        url = markdown.group(1)
    # Терминал и редакторы иногда экранируют ?, &, = обратным слешем.
    url = re.sub(r'\\+([?&=/#])', r'\1', url)
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in {
        'music.yandex.ru', 'music.yandex.com', 'music.yandex.by',
        'music.yandex.kz', 'music.yandex.uz',
    }:
        raise ValueError('Укажите полную ссылку на трек с music.yandex.ru.')
    match = re.fullmatch(r'/(?:album/(\d+)/)?track/(\d+)/?', parsed.path)
    if not match:
        raise ValueError('Нужна ссылка /album/123/track/456 или /track/456.')
    album, track = match.groups()
    return f'{track}:{album}' if album else track


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', help='Полная ссылка на трек')
    parser.add_argument('-o', '--output', default='music', help='Папка назначения')
    parser.add_argument('--login', action='store_true', help='Войти заново и сохранить новый аккаунт')
    args = parser.parse_args()
    identifier = track_id(args.url)
    try:
        from yandex_music import Client
    except ImportError:
        raise RuntimeError('Установите библиотеку: python3 -m pip install -U yandex-music')

    token_file = Path(__file__).resolve().parent / '.yandex_music_token.json'
    token = None if args.login else os.environ.get('YANDEX_MUSIC_TOKEN')
    if not token and not args.login and token_file.exists():
        try:
            saved = json.loads(token_file.read_text(encoding='utf-8'))
            if saved.get('expires_at', 0) > time.time() + 60:
                token = saved.get('access_token')
        except (ValueError, AttributeError):
            print('Сохранённая авторизация повреждена. Войдите заново.')
    client = Client(token) if token else Client()
    if not token:
        def on_code(code):
            print(f'Откройте {code.verification_url} и введите код: {code.user_code}', flush=True)
        credentials = client.device_auth(on_code=on_code)
        client.init()
        saved = {
            'access_token': credentials.access_token,
            'expires_at': time.time() + float(credentials.expires_in or 0),
        }
        fd, temporary_token = tempfile.mkstemp(prefix='.yandex-token-', dir=token_file.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(saved, stream)
            os.replace(temporary_token, token_file)
        finally:
            Path(temporary_token).unlink(missing_ok=True)
        print('Авторизация сохранена для следующих запусков.')
    else:
        client.init()
    tracks = client.tracks([identifier])
    if not tracks:
        raise RuntimeError('Трек не найден.')
    track = tracks[0]
    variants = [item for item in track.get_download_info() if item.codec == 'mp3']
    if not variants:
        raise RuntimeError('API не предоставил MP3 для этого трека. Проверьте доступ аккаунта и подписку.')
    best = max(variants, key=lambda item: item.bitrate_in_kbps)
    artists = ', '.join(artist.name for artist in track.artists or [])
    title = f'{artists} - {track.title}'
    title = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', title).strip(' .')[:100] or 'track'
    folder = Path(args.output).expanduser()
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
        # Не перезаписываем существующий файл даже при одновременном запуске.
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(f'Скачано: {destination.resolve()} ({best.bitrate_in_kbps} кбит/с)')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as error:
        # Ответы API могут содержать служебные данные: не выводим их целиком.
        if isinstance(error, (ValueError, RuntimeError)):
            print(f'Ошибка: {error}', file=sys.stderr)
        else:
            print(f'Ошибка: {type(error).__name__}. Проверьте сеть и доступность трека. Для повторного входа добавьте --login.', file=sys.stderr)
        sys.exit(1)
