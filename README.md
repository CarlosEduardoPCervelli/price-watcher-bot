#  Price Watcher

 Bot de monitoramento de preços com alertas por **e-mail** e **Telegram**.

Monitora produtos no **Mercado Livre** e te avisa automaticamente quando o preço atingir a sua meta — sem precisar ficar verificando manualmente.

---

##  Funcionalidades

- 🔍 Monitoramento automático de múltiplos produtos
- 📧 Alertas por e-mail (Gmail / SMTP)
- ✈️ Alertas pelo Telegram
- 📊 Histórico de preços salvo em JSON
- ⏱️ Intervalo configurável entre verificações
- 🛒 Suporte ao Mercado Livre (extensível para outras lojas)

---

##  Como usar

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/price-watcher.git
cd price-watcher
```

### 2. Instale as dependências
```bash
pip install -r requirements.txt
```

### 3. Cadastre os produtos
Edite o arquivo `data/products.json`:
```json
[
  {
    "name": "Teclado Mecânico Redragon",
    "url": "https://www.mercadolivre.com.br/...",
    "target_price": 250.00
  }
]
```

### 4. Execute o bot

**Verificação única (para testar):**
```bash
python src/watcher.py --once
```

**Monitoramento contínuo (a cada 30 minutos):**
```bash
python src/watcher.py --interval 30
```

**Com alertas por e-mail (Gmail):**
```bash
python src/watcher.py \
  --email-from seuemail@gmail.com \
  --email-to destino@gmail.com \
  --email-password sua_senha_de_app \
  --interval 60
```

**Com alertas pelo Telegram:**
```bash
python src/watcher.py \
  --telegram-token SEU_BOT_TOKEN \
  --telegram-chat-id SEU_CHAT_ID \
  --interval 30
```

---

##  Estrutura do projeto

```
price-watcher/
├── src/
│   └── watcher.py        # Script principal
├── data/
│   ├── products.json     # Produtos monitorados
│   └── history.json      # Histórico de preços (gerado automaticamente)
├── requirements.txt
└── README.md
```

---

##  Como configurar o Telegram

1. Crie um bot conversando com [@BotFather](https://t.me/BotFather) no Telegram
2. Copie o **token** gerado
3. Envie uma mensagem para o bot e acesse:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Copie o `chat_id` retornado

---

##  Como configurar o Gmail

1. Acesse [myaccount.google.com](https://myaccount.google.com)
2. Ative a **verificação em duas etapas**
3. Gere uma **Senha de App** (Segurança → Senhas de app)
4. Use essa senha no argumento `--email-password`

---

##  Como adicionar suporte a outras lojas

Basta criar uma nova função `scrape_nomeloja(url)` em `watcher.py` e registrá-la na função `get_price()`:

```python
def get_price(url: str) -> dict | None:
    if "mercadolivre.com.br" in url:
        return scrape_mercadolivre(url)
    if "amazon.com.br" in url:
        return scrape_amazon(url)  # implemente aqui
```

---

##  Exemplo de saída no terminal

```
2025-01-15 10:30:00  INFO      Price Watcher iniciado — verificando a cada 30 min
2025-01-15 10:30:01  INFO     Verificando: Teclado Mecânico Redragon
2025-01-15 10:30:02  INFO        Preço atual: R$ 279.90 | Meta: R$ 250.00
2025-01-15 10:30:02  INFO        Ainda R$ 29.90 acima da meta.
2025-01-15 10:30:04  INFO      Verificando: Monitor LG 24' Full HD
2025-01-15 10:30:05  INFO        Preço atual: R$ 899.00 | Meta: R$ 900.00
2025-01-15 10:30:05  INFO        Preço atingiu a meta! Enviando notificação...
2025-01-15 10:30:05  INFO       E-mail de alerta enviado!
```

---

##  Tecnologias

- **Python 3.11+**
- `requests` — requisições HTTP
- `BeautifulSoup4` — parsing de HTML
- `smtplib` — envio de e-mail (nativo)

---

##  Licença

MIT — fique à vontade para usar, modificar e distribuir.
