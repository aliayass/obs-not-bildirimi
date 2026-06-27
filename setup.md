# Kurulum

## 1. Gereksinimler

```bash
pip install -r requirements.txt
```

## 2. .env dosyası oluştur

```bash
cp .env.example .env
```

`.env` içini doldur:

```
OBS_USERNAME=21XXXXXXX        # öğrenci numaranız
OBS_PASSWORD=şifreniz
TELEGRAM_BOT_TOKEN=123456:ABC...   # @BotFather'dan al
TELEGRAM_CHAT_ID=123456789         # aşağıya bak
```

### Telegram Bot Token alma
1. Telegram'da @BotFather'a mesaj at
2. `/newbot` yaz, isim ver
3. Token kopyala → `TELEGRAM_BOT_TOKEN`

### Chat ID alma
1. Bota `/start` mesajı at
2. Tarayıcıda şu URL'yi aç:
   `https://api.telegram.org/botTOKEN/getUpdates`
3. `"chat":{"id": BURASI}` → `TELEGRAM_CHAT_ID`

## 3. Test et

```bash
python bot.py
```

`bot.log` dosyasına bak.

## 4. VPS'te cron kurulumu

```bash
crontab -e
```

Her 15 dakikada çalıştır:

```
*/15 * * * * /usr/bin/python3 /home/user/not-bildirimi/bot.py >> /home/user/not-bildirimi/cron.log 2>&1
```

Her saat başı çalıştır:

```
0 * * * * /usr/bin/python3 /home/user/not-bildirimi/bot.py >> /home/user/not-bildirimi/cron.log 2>&1
```

## Notlar

- İlk çalışmada `state.json` oluşur, mevcut notları "görülmüş" kaydeder — ilk çalışmada bildirim gelmez.
- Sonraki çalışmalarda yalnızca **yeni + harfli** notlar bildirim gönderir.
- OBS tablo yapısı değişirse `bot.py` → `fetch_grades()` fonksiyonunu düzenle.
