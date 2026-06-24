"""
app.py — Flask 진입점
Render는 웹 서비스에 HTTP 포트가 필요하므로 Flask를 띄우고
별도 스레드에서 Discord 봇을 실행합니다.
"""

import threading
import logging

from flask import Flask, jsonify

from bot import run_bot

log = logging.getLogger("weao_app")

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify({"status": "ok", "service": "WEAO Discord Bot"})


@app.route("/health")
def health():
    """Render 헬스체크 엔드포인트"""
    return jsonify({"status": "ok"}), 200


def start_bot_thread():
    t = threading.Thread(target=run_bot, daemon=True, name="discord-bot")
    t.start()
    log.info("Discord 봇 스레드 시작")


if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    start_bot_thread()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
