# OBS Not Bildirimi

Fırat Üniversitesi OBS'yi izler, yeni harf notu açıklandığında Telegram'a bildirim gönderir.

## Özellikler

- Saatte bir OBS'ye giriş yapıp not tablosunu kontrol eder
- Yeni harf notu (AA/BA/BB...) açıklandığında anında Telegram mesajı gönderir
- 5 saatte bir "henüz not yok" hatırlatması
- `/kontrol` komutuyla anlık not durumu

## Kurulum

### 1. Telegram Bot Oluştur

1. Telegram'da [@BotFather](https://t.me/BotFather)'a yaz → `/newbot`
2. Bot token'ı kopyala
3. Bota bir mesaj gönder, ardından şu adresten chat ID'ni öğren:  
   `https://api.telegram.org/bot<TOKEN>/getUpdates`

### 2. Bağımlılıkları Yükle

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. .env Dosyası Oluştur

```bash
cp .env.example .env
```

`.env` dosyasını düzenle:

```env
OBS_USERNAME=ogrenci_numarasi
OBS_PASSWORD=sifre
TELEGRAM_BOT_TOKEN=bot_token
TELEGRAM_CHAT_ID=chat_id
```

### 4. Çalıştır

```bash
python bot.py
```

İlk çalıştırmada mevcut notlar baseline olarak kaydedilir, bildirim gelmez.

## Otomatik Çalıştırma

### GitHub Actions ile (Önerilen — Bilgisayar Açık Olmak Zorunda Değil)

Repo fork'lanarak GitHub'ın sunucularında ücretsiz çalıştırılabilir.

**1. Repo'yu Fork'la**

Sağ üstten **Fork** butonuna bas.

**2. Secrets Ekle**

Fork'ladığın repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Adı | Değer |
|---|---|
| `OBS_USERNAME` | Öğrenci numarası |
| `OBS_PASSWORD` | OBS şifresi |
| `TELEGRAM_BOT_TOKEN` | Bot token |
| `TELEGRAM_CHAT_ID` | Chat ID |

**3. Actions'ı Etkinleştir**

Repo → **Actions** sekmesi → **I understand my workflows, enable them** butonuna bas.

Hepsi bu. Her 30 dakikada bir otomatik çalışır. **Actions** sekmesinden logları takip edebilirsin. İstersen **Run workflow** butonuyla manuel de tetikleyebilirsin.

---

### Kendi Bilgisayarında (Linux/Mac)

```bash
crontab -e
# Her 30 dakikada bir çalıştır:
*/30 * * * * cd /path/to/obs-not-bildirimi && python bot.py
```

### Kendi Bilgisayarında (Windows)

- Görev Zamanlayıcı → Temel Görev Oluştur
- Tetikleyici: Günlük, her 1 saatte bir tekrarla
- Eylem: `python bot.py` (proje klasöründe)

## Bildirim Formatı

```
📢 Yeni Not Açıklandı!

BMÜ260 — NESNE TABANLI PROGRAMLAMA
🔢 Vize : 90     Final : 55
Not: BA  |  Ort: 69  |  Geçti
```

## Telegram Komutları

| Komut | Açıklama |
|-------|----------|
| `/kontrol` | Tüm derslerin güncel not durumunu gösterir |

## Gereksinimler

- Python 3.11+
- Playwright (Chromium)
- Telegram Bot Token
