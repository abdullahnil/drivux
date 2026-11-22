# Drive Bağlantı

Linux için Google Drive istemcisi. GNOME görünümünde bir arayüzü var, arka planda [rclone](https://rclone.org) ile çalışır.

İki işi birlikte yapar:

1. **Google Drive'ı disk olarak bağlar.** Drive'ın tamamı Dosyalar'ın kenar çubuğunda "Google Drive" olarak görünür. Dosyalar açıldıkça indirilir, bilgisayarda yer kaplamaz.
2. **Seçtiğin klasörleri iki yönlü eşitler.** Bu klasörler bilgisayarda da durur ve internet olmadan da açılır. Bir tarafta yapılan değişiklik öbür tarafa aktarılır.

## Özellikler

- **Kurulum sihirbazı:** ilk açılışta her şeyi adım adım sorar.
  - rclone'u kurar.
  - Google hesabını bağlar. İstersen kendi client ID'ni de girebilirsin.
  - Diskin bağlanacağı klasörü ve önbellek boyutunu sorar.
  - Eşitlenecek klasörleri seçtirir.
- **rclone dahil:** rclone kurulu değilse ya da çok eskiyse sihirbaz güncel sürümü resmi siteden indirir, SHA256 ile doğrular ve yalnızca bu kullanıcı için kurar. sudo gerekmez.
- **Google Docs desteği:** Dokümanlar, E-Tablolar ve Slaytlar diskte küçük kısayol dosyaları olarak görünür. Çift tıklayınca tarayıcıda Google'ın kendi düzenleyicisinde açılır.
- **Arayüz:** genel durum, kullanılan Drive alanı, eşitlenen klasörler ve her birinin son eşitleme zamanı tek pencerede.
- **Otomatik eşitleme:** klasörde bir değişiklik olunca yaklaşık 15 saniye içinde, bunun dışında da düzenli aralıklarla eşitler.
- **Hata bildirimi:** bir sorun çıkarsa masaüstü bildirimi gösterir.
- **Toplu silme koruması:** bir seferde 50'den fazla dosya silinecekse eşitleme durur ve senin onayını bekler.
- **Çakışmada veri kaybı yok:** aynı dosya iki tarafta birden değişirse yeni sürüm kalır, eski sürüm numaralı bir kopya olarak saklanır.

## Kurulum

### Paketle (önerilen)

[Sürümler](https://github.com/abdullahnil/drive-baglanti/releases) sayfasından dağıtımına uygun paketi indir:

```bash
# Fedora / RHEL / openSUSE
sudo dnf install ./drive-baglanti-1.1.0-1.noarch.rpm

# Ubuntu 24.04+ / Debian 13+ / Linux Mint 22+
sudo apt install ./drive-baglanti_1.1.0_all.deb
```

Sonra uygulama menüsünden **Drive Bağlantı**'yı aç. Kurulum sihirbazı kendiliğinden başlar.

### Kaynaktan

```bash
git clone https://github.com/abdullahnil/drive-baglanti.git
cd drive-baglanti
./kur.sh
```

`kur.sh` dağıtımına göre gerekli sistem paketlerini kurar (dnf, apt, pacman ya da zypper). Uygulamayı yalnızca senin kullanıcın için `~/.local` altına kurar ve sihirbazı açar. Güncellemek için `git pull` yapıp `./kur.sh`'i tekrar çalıştırman yeterli; ayarların korunur.

### Gereksinimler

- GTK 4 ve **libadwaita 1.5 veya daha yenisi**. Fedora 40 ve sonrası, Ubuntu 24.04 ve sonrası, Debian 13 ve sonrası bu koşulu karşılar.
- FUSE 3 (disk özelliği için)
- systemd kullanıcı oturumu

### Paket üretmek

```bash
./paketleme/paketle.sh   # dist/ klasörüne .rpm ve .deb üretir
```

Bunun için `rpmbuild` ve `dpkg-deb` gerekir. Fedora'da: `sudo dnf install rpm-build dpkg`.

## Kullanım

Uygulama menüsünden **Drive Bağlantı**'yı aç.

Terminalden:

```bash
drive-baglanti            # arayüz
drive-baglanti esitle     # hemen eşitle
drive-baglanti durum      # eşitleme durumu
```

## Nasıl çalışır?

| Parça | Görevi |
|---|---|
| `drive-baglanti-disk.service` | `rclone mount` ile Drive'ı `~/Google Drive` klasörüne bağlar. Tam VFS önbelleği kullanır. |
| `drive-baglanti.service` | Klasörleri `rclone bisync` ile eşitleyen Python servisi. Klasörleri izler ve zamanlamayı yönetir. |
| `drive-baglanti` | GTK4 / libadwaita arayüzü ve kurulum sihirbazı. Servisle ayar ve durum dosyaları ve sinyaller üzerinden haberleşir. |

| Dosya | Yer |
|---|---|
| Ayarlar | `~/.config/drive-baglanti/ayar.json` |
| Durum | `~/.local/state/drive-baglanti/durum.json` |
| Kayıtlar | `journalctl --user -u drive-baglanti -u drive-baglanti-disk` |

## Bilinmesi gerekenler

- **Bu bir yedek değil, ayna.** Bir dosyayı silersen ya da bozarsan değişiklik Drive'a da gider. Drive'dan silinen dosyalar 30 gün boyunca Drive'ın çöp kutusunda durur.
- **Google Docs dosyaları yalnızca diskte görünür.** Klasör eşitlemesine dahil edilmezler, çünkü bunlar gerçek dosya değil, Google'ın sunucusundaki belgelerdir.
- **Kendi client ID'ni kullan.** rclone'un herkesin kullandığı ortak Google kimliği kapatılmak üzere. Sihirbazda "Kendi Google client ID'ni kullan" seçeneğiyle kendi kimliğini girebilirsin. Nasıl oluşturulacağı için [rclone rehberine](https://rclone.org/drive/#making-your-own-client-id) bak.

## Kaldırma

```bash
./kaldir.sh
```

Paketle kurduysan `sudo dnf remove drive-baglanti` ya da `sudo apt remove drive-baglanti` kullan. Her iki yol da bilgisayardaki ve Drive'daki dosyalara dokunmaz.

## Lisans

MIT
