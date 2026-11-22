# Drive Bağlantı

Linux için Google Drive istemcisi. GNOME görünümünde bir arayüzü var, arka planda [rclone](https://rclone.org) ile çalışır.

İki işi birlikte yapar:

1. **Google Drive'ı disk olarak bağlar.** Drive'ın tamamı Dosyalar'ın kenar çubuğunda "Google Drive" olarak görünür. Dosyalar açıldıkça indirilir, bilgisayarda yer kaplamaz.
2. **Seçtiğin klasörleri iki yönlü eşitler.** Bu klasörler bilgisayarda da durur ve internet olmadan da açılır. Bir tarafta yapılan değişiklik öbür tarafa aktarılır.

## Özellikler

- **Arayüz:** genel durum, kullanılan Drive alanı, eşitlenen klasörler ve her birinin son eşitleme zamanı tek pencerede.
- **Klasör yönetimi:** tek tıkla klasör ekleyip çıkarabilirsin. Drive'da aynı adlı bir klasör varsa içerikler birleştirilir, hiçbir şey silinmez.
- **Otomatik eşitleme:** klasörde bir değişiklik olunca yaklaşık 15 saniye içinde, bunun dışında da düzenli aralıklarla (varsayılan 5 dakika) eşitler.
- **Hata bildirimi:** bir sorun çıkarsa masaüstü bildirimi gösterir. Ayrıntılar arayüzdeki kayıtlarda görünür.
- **Toplu silme koruması:** bir seferde 50'den fazla dosya silinecekse eşitleme durur ve senin onayını bekler.
- **Çakışmada veri kaybı yok:** aynı dosya iki tarafta birden değişirse yeni sürüm kalır, eski sürüm numaralı bir kopya olarak saklanır.
- **Otomatik başlama:** oturum açınca hem disk hem eşitleme kendiliğinden başlar.

## Kurulum

```bash
git clone https://github.com/abdullahnil/drive-baglanti.git
cd drive-baglanti
./kur.sh
```

Kurulum betiği gerekli paketleri kurar (rclone, GTK4, libadwaita, FUSE). Daha önce bir Google Drive bağlantısı yapılmamışsa tarayıcıda Google girişini açar. Ardından uygulamayı ve arka plan servislerini kurar.

Uygulamayı güncellemek için `git pull` yapıp `./kur.sh`'i tekrar çalıştırman yeterli. Ayarların korunur.

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
| `drive-baglanti` | GTK4 / libadwaita arayüzü. Servisle ayar ve durum dosyaları ve sinyaller üzerinden haberleşir. |

| Dosya | Yer |
|---|---|
| Ayarlar | `~/.config/drive-baglanti/ayar.json` |
| Durum | `~/.local/state/drive-baglanti/durum.json` |
| Kayıtlar | `journalctl --user -u drive-baglanti -u drive-baglanti-disk` |

## Bilinmesi gerekenler

- **Bu bir yedek değil, ayna.** Bir dosyayı silersen ya da bozarsan değişiklik Drive'a da gider. Drive'dan silinen dosyalar 30 gün boyunca Drive'ın çöp kutusunda durur.
- **Google Dokümanlar dosyaları eşitlenmez.** Diskte görünürler ama klasör eşitlemesine dahil edilmezler.
- **Kendi client ID'ni kullan.** rclone'un herkesin kullandığı ortak Google kimliği kapatılmak üzere. Kesinti yaşamamak için [kendi client ID'ni oluşturup](https://rclone.org/drive/#making-your-own-client-id) şu komutla ekle: `rclone config update gdrive client_id=... client_secret=...`

## Kaldırma

```bash
./kaldir.sh
```

Bilgisayardaki ve Drive'daki dosyalara dokunmaz.

## Lisans

MIT
