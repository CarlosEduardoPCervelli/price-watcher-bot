"""
price-watcher — Bot de monitoramento de preços
Monitora produtos e envia alertas por e-mail ou Telegram.
"""

import json
import smtplib
import logging
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Configuração de log ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("price-watcher")

DATA_FILE = Path(__file__).parent.parent / "data" / "products.json"
HISTORY_FILE = Path(__file__).parent.parent / "data" / "history.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}


# ── Carrega / salva dados ──────────────────────────────────────────────────────

def load_products() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_products(products: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def save_history(entry: dict) -> None:
    history = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)
    history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ── Scrapers ───────────────────────────────────────────────────────────────────

def scrape_mercadolivre(url: str) -> dict | None:
    """Extrai nome e preço de uma página do Mercado Livre."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Título
        title_tag = soup.find("h1", class_=lambda c: c and "ui-pdp-title" in c)
        title = title_tag.get_text(strip=True) if title_tag else "Produto sem nome"

        # Preço (parte inteira + centavos)
        fraction = soup.find("span", class_=lambda c: c and "andes-money-amount__fraction" in c)
        cents = soup.find("span", class_=lambda c: c and "andes-money-amount__cents" in c)

        if not fraction:
            return None

        price_str = fraction.get_text(strip=True).replace(".", "").replace(",", "")
        cents_str = cents.get_text(strip=True) if cents else "00"
        price = float(f"{price_str}.{cents_str}")

        return {"title": title, "price": price, "currency": "BRL"}

    except Exception as e:
        log.error(f"Erro ao scraper Mercado Livre: {e}")
        return None


def get_price(url: str) -> dict | None:
    """Detecta a loja e chama o scraper correto."""
    if "mercadolivre.com.br" in url or "mercadolibre.com" in url:
        return scrape_mercadolivre(url)
    log.warning(f"Loja não suportada para URL: {url}")
    return None


# ── Notificações ───────────────────────────────────────────────────────────────

def send_email(config: dict, subject: str, body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["email_from"]
    msg["To"] = config["email_to"]
    msg.attach(MIMEText(body, "html", "utf-8"))

    with smtplib.SMTP_SSL(config["smtp_host"], config.get("smtp_port", 465)) as server:
        server.login(config["email_from"], config["email_password"])
        server.sendmail(config["email_from"], config["email_to"], msg.as_string())
    log.info("📧  E-mail de alerta enviado!")


def send_telegram(config: dict, message: str) -> None:
    url = f"https://api.telegram.org/bot{config['telegram_token']}/sendMessage"
    payload = {"chat_id": config["telegram_chat_id"], "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    log.info("✈️  Mensagem Telegram enviada!")


def notify(config: dict, product: dict, current_price: float) -> None:
    subject = f"🔔 Alerta de Preço: {product['name']}"
    body = (
        f"<h2>Alerta de Preço!</h2>"
        f"<p>O produto <b>{product['name']}</b> atingiu o preço desejado.</p>"
        f"<ul>"
        f"<li>💰 Preço atual: <b>R$ {current_price:.2f}</b></li>"
        f"<li>🎯 Preço alvo: <b>R$ {product['target_price']:.2f}</b></li>"
        f"<li>🔗 <a href='{product['url']}'>Ver produto</a></li>"
        f"</ul>"
        f"<p><small>Verificado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</small></p>"
    )
    telegram_msg = (
        f"🔔 <b>Alerta de Preço!</b>\n\n"
        f"📦 {product['name']}\n"
        f"💰 Preço atual: R$ {current_price:.2f}\n"
        f"🎯 Meta: R$ {product['target_price']:.2f}\n"
        f"🔗 {product['url']}"
    )

    if config.get("email_from"):
        try:
            send_email(config, subject, body)
        except Exception as e:
            log.error(f"Falha no e-mail: {e}")

    if config.get("telegram_token"):
        try:
            send_telegram(config, telegram_msg)
        except Exception as e:
            log.error(f"Falha no Telegram: {e}")


# ── Loop principal ─────────────────────────────────────────────────────────────

def check_all(config: dict) -> None:
    products = load_products()
    if not products:
        log.warning("Nenhum produto cadastrado. Adicione em data/products.json")
        return

    for product in products:
        log.info(f"🔍 Verificando: {product['name']}")
        result = get_price(product["url"])

        if not result:
            log.warning(f"  ⚠️  Não foi possível obter o preço.")
            continue

        current_price = result["price"]
        log.info(f"  💲 Preço atual: R$ {current_price:.2f} | Meta: R$ {product['target_price']:.2f}")

        # Salva histórico
        save_history({
            "product": product["name"],
            "url": product["url"],
            "price": current_price,
            "checked_at": datetime.now().isoformat(),
        })

        if current_price <= product["target_price"]:
            log.info("  ✅ Preço atingiu a meta! Enviando notificação...")
            notify(config, product, current_price)
        else:
            diff = current_price - product["target_price"]
            log.info(f"  ⏳ Ainda R$ {diff:.2f} acima da meta.")

        time.sleep(2)  # respeitar o servidor


def run(interval_minutes: int = 30, config: dict = None) -> None:
    config = config or {}
    log.info(f"🚀 Price Watcher iniciado — verificando a cada {interval_minutes} min")
    while True:
        check_all(config)
        log.info(f"😴 Aguardando {interval_minutes} minutos...\n")
        time.sleep(interval_minutes * 60)


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="Price Watcher — Bot de monitoramento de preços")
    parser.add_argument("--interval", type=int, default=30, help="Intervalo em minutos (padrão: 30)")
    parser.add_argument("--once", action="store_true", help="Executa apenas uma verificação e sai")
    parser.add_argument("--email-from", default="")
    parser.add_argument("--email-to", default="")
    parser.add_argument("--email-password", default="")
    parser.add_argument("--smtp-host", default="smtp.gmail.com")
    parser.add_argument("--telegram-token", default="")
    parser.add_argument("--telegram-chat-id", default="")
    args = parser.parse_args()

    cfg = {
        "email_from": args.email_from,
        "email_to": args.email_to,
        "email_password": args.email_password,
        "smtp_host": args.smtp_host,
        "telegram_token": args.telegram_token,
        "telegram_chat_id": args.telegram_chat_id,
    }

    if args.once:
        check_all(cfg)
        sys.exit(0)

    run(interval_minutes=args.interval, config=cfg)
