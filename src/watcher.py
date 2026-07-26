"""
price-watcher — Bot de monitoramento de preços via API do Mercado Livre

Otimizações em relação à versão original:
  1. requests.Session() reutilizada com retry/backoff automático (menos
     conexões TCP/TLS novas, resiliência a falhas transitórias da API).
  2. Checagem de produtos em paralelo (ThreadPoolExecutor) em vez de
     sequencial com time.sleep(2) fixo entre cada um.
  3. Histórico lido e escrito UMA vez por ciclo (antes era 1 leitura +
     1 escrita do arquivo inteiro por produto → O(n²) de I/O conforme
     o histórico cresce).
  4. Credenciais podem vir de variáveis de ambiente (.env) além de
     argumentos de linha de comando — evita senha em texto puro no
     histórico do shell / processos visíveis.
  5. Dataclasses e type hints para deixar o fluxo de dados explícito.
  6. Uma única conexão SMTP reaproveitada quando várias notificações
     ocorrem no mesmo ciclo.
"""

from __future__ import annotations

import json
import logging
import os
import re
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("price-watcher")

DATA_FILE = Path(__file__).parent.parent / "data" / "products.json"
HISTORY_FILE = Path(__file__).parent.parent / "data" / "history.json"

ITEM_ID_RE = re.compile(r"(MLB\d+)")
FALLBACK_ID_RE = re.compile(r"/([a-z]+-)*(\d{8,12})")


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #

@dataclass
class Product:
    name: str
    url: str
    target_price: float

    @classmethod
    def from_dict(cls, d: dict) -> "Product":
        return cls(name=d["name"], url=d["url"], target_price=float(d["target_price"]))


@dataclass
class PriceResult:
    title: str
    price: float
    currency: str


@dataclass
class Config:
    email_from: str = ""
    email_to: str = ""
    email_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    telegram_token: str = ""
    telegram_chat_id: str = ""
    max_workers: int = 5


# --------------------------------------------------------------------------- #
# Sessão HTTP com retry/backoff (reaproveitada em todo o ciclo de vida)
# --------------------------------------------------------------------------- #

def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"Accept": "application/json"})
    return session


# --------------------------------------------------------------------------- #
# Persistência
# --------------------------------------------------------------------------- #

def load_products() -> list[Product]:
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    return [Product.from_dict(p) for p in raw]


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        return json.load(f)


def append_history(entries: list[dict]) -> None:
    """Lê o histórico uma única vez, acrescenta todas as entradas do
    ciclo e grava uma única vez — em vez de 1 leitura+escrita por produto."""
    if not entries:
        return
    history = load_history()
    history.extend(entries)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# Consulta de preço
# --------------------------------------------------------------------------- #

def extract_item_id(url: str) -> Optional[str]:
    """Extrai o ID do item da URL do Mercado Livre. Ex: MLB123456789"""
    match = ITEM_ID_RE.search(url.upper())
    if match:
        return match.group(1)
    match = FALLBACK_ID_RE.search(url)
    if match:
        return "MLB" + match.group(2)
    return None


def get_price(session: requests.Session, url: str) -> Optional[PriceResult]:
    """Busca o preço usando a API pública do Mercado Livre."""
    item_id = extract_item_id(url)
    if not item_id:
        log.error(f"Não foi possível extrair o ID do item da URL: {url}")
        return None

    api_url = f"https://api.mercadolibre.com/items/{item_id}"

    try:
        resp = session.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        price = data.get("price")
        if price is None:
            log.warning(f"  [{item_id}] API retornou sem preço.")
            return None

        return PriceResult(
            title=data.get("title", "Produto sem nome"),
            price=float(price),
            currency=data.get("currency_id", "BRL"),
        )

    except requests.exceptions.HTTPError as e:
        log.error(f"  [{item_id}] Erro HTTP {e.response.status_code} na API do ML")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"  [{item_id}] Erro de conexão: {e}")
        return None


# --------------------------------------------------------------------------- #
# Notificações
# --------------------------------------------------------------------------- #

def _email_body(product: Product, current_price: float) -> str:
    return (
        f"<h2>🔔 Alerta de Preço!</h2>"
        f"<p>O produto <b>{product.name}</b> atingiu o preço desejado!</p>"
        f"<ul>"
        f"<li>💰 Preço atual: <b>R$ {current_price:.2f}</b></li>"
        f"<li>🎯 Preço alvo: <b>R$ {product.target_price:.2f}</b></li>"
        f"<li>🔗 <a href='{product.url}'>Ver produto no Mercado Livre</a></li>"
        f"</ul>"
        f"<p><small>Verificado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</small></p>"
    )


def send_email_batch(config: Config, alerts: list[tuple[Product, float]]) -> None:
    """Abre uma única conexão SMTP e envia todos os alertas do ciclo."""
    if not alerts:
        return
    try:
        with smtplib.SMTP_SSL(config.smtp_host, 465) as server:
            server.login(config.email_from, config.email_password)
            for product, price in alerts:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"🔔 Alerta de Preço: {product.name}"
                msg["From"] = config.email_from
                msg["To"] = config.email_to
                msg.attach(MIMEText(_email_body(product, price), "html", "utf-8"))
                server.sendmail(config.email_from, config.email_to, msg.as_string())
                log.info(f"📧  E-mail enviado: {product.name}")
    except Exception as e:
        log.error(f"Falha no envio de e-mail: {e}")


def send_telegram(session: requests.Session, config: Config, product: Product, price: float) -> None:
    text = (
        f"🔔 <b>Alerta de Preço!</b>\n\n"
        f"📦 {product.name}\n"
        f"💰 Preço atual: R$ {price:.2f}\n"
        f"🎯 Meta: R$ {product.target_price:.2f}\n"
        f"🔗 {product.url}"
    )
    url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
    payload = {"chat_id": config.telegram_chat_id, "text": text, "parse_mode": "HTML"}
    try:
        resp = session.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        log.info(f"✈️  Telegram enviado: {product.name}")
    except requests.exceptions.RequestException as e:
        log.error(f"Falha no Telegram: {e}")


# --------------------------------------------------------------------------- #
# Ciclo de verificação
# --------------------------------------------------------------------------- #

def _check_one(session: requests.Session, product: Product) -> tuple[Product, Optional[PriceResult]]:
    log.info(f"🔍 Verificando: {product.name}")
    return product, get_price(session, product.url)


def check_all(config: Config, session: requests.Session) -> None:
    products = load_products()
    if not products:
        log.warning("Nenhum produto cadastrado. Adicione em data/products.json")
        return

    history_entries: list[dict] = []
    email_alerts: list[tuple[Product, float]] = []

    with ThreadPoolExecutor(max_workers=min(config.max_workers, len(products))) as pool:
        futures = [pool.submit(_check_one, session, p) for p in products]

        for future in as_completed(futures):
            product, result = future.result()

            if not result:
                log.warning(f"  ⚠️  [{product.name}] Não foi possível obter o preço.")
                continue

            log.info(
                f"  💲 {product.name}: R$ {result.price:.2f} | Meta: R$ {product.target_price:.2f}"
            )

            history_entries.append({
                "product": product.name,
                "url": product.url,
                "price": result.price,
                "checked_at": datetime.now().isoformat(),
            })

            if result.price <= product.target_price:
                log.info(f"  ✅ [{product.name}] Preço atingiu a meta!")
                email_alerts.append((product, result.price))
                if config.telegram_token:
                    send_telegram(session, config, product, result.price)
            else:
                diff = result.price - product.target_price
                log.info(f"  ⏳ [{product.name}] Ainda R$ {diff:.2f} acima da meta.")

    append_history(history_entries)
    if config.email_from:
        send_email_batch(config, email_alerts)


def run(interval_minutes: int = 30, config: Optional[Config] = None) -> None:
    config = config or Config()
    session = build_session()
    log.info(f"🚀 Price Watcher iniciado — verificando a cada {interval_minutes} min")
    try:
        while True:
            check_all(config, session)
            log.info(f"😴 Aguardando {interval_minutes} minutos...\n")
            time.sleep(interval_minutes * 60)
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _config_from_env_and_args(args) -> Config:
    """Prioriza argumentos de linha de comando; usa variáveis de ambiente
    como fallback (permite não expor senha em texto puro no shell)."""
    return Config(
        email_from=args.email_from or os.getenv("PW_EMAIL_FROM", ""),
        email_to=args.email_to or os.getenv("PW_EMAIL_TO", ""),
        email_password=args.email_password or os.getenv("PW_EMAIL_PASSWORD", ""),
        smtp_host=args.smtp_host or os.getenv("PW_SMTP_HOST", "smtp.gmail.com"),
        telegram_token=args.telegram_token or os.getenv("PW_TELEGRAM_TOKEN", ""),
        telegram_chat_id=args.telegram_chat_id or os.getenv("PW_TELEGRAM_CHAT_ID", ""),
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Price Watcher")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--email-from", default="")
    parser.add_argument("--email-to", default="")
    parser.add_argument("--email-password", default="")
    parser.add_argument("--smtp-host", default="")
    parser.add_argument("--telegram-token", default="")
    parser.add_argument("--telegram-chat-id", default="")
    parser.add_argument("--max-workers", type=int, default=5,
                         help="Nº de produtos verificados em paralelo (padrão: 5)")
    args = parser.parse_args()

    cfg = _config_from_env_and_args(args)
    http_session = build_session()

    try:
        if args.once:
            check_all(cfg, http_session)
            sys.exit(0)
        run(interval_minutes=args.interval, config=cfg)
    finally:
        http_session.close()