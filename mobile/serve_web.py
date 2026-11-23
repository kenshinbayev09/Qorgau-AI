"""Раздаёт веб-версию приложения (mobile/dist-web) на http://localhost:8090.

Заголовки COOP/COEP нужны для SQLite в браузере (SharedArrayBuffer).
Запуск из папки mobile:  python serve_web.py
"""
import functools
import http.server
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist-web")


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()


if __name__ == "__main__":
    handler = functools.partial(Handler, directory=ROOT)
    print("Открыть: http://localhost:8090 (с других устройств — http://IP_ноутбука:8090)")
    http.server.ThreadingHTTPServer(("0.0.0.0", 8090), handler).serve_forever()
