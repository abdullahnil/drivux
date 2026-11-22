<p align="center">
  <img src="docs/logo.png" width="128" alt="Drivux logosu">
</p>

<h1 align="center">Drivux</h1>

<p align="center">
  Linux için sade bir Google Drive istemcisi. Drive'ı disk olarak bağlar ve klasörlerini iki yönlü eşitler.<br>
  GTK 4 ve libadwaita ile yazıldı, arka planda <a href="https://rclone.org">rclone</a> ile çalışır.
</p>

<p align="center">
  <a href="README.md">English</a> · <b>Türkçe</b>
</p>

---

## Ne yapar?

Drivux iki iş yapar. İkisini birlikte de kullanabilirsin, yalnızca birini de:

1. **Google Drive'ı disk olarak bağlar.** Drive'ın tamamı Dosyalar'ın kenar çubuğunda "Google Drive" olarak görünür. Dosyalar açtıkça indirilir, bu yüzden diskini doldurmaz.
2. **Klasörleri iki yönlü eşitler.** Seçtiğin klasörler bilgisayarında da durur ve internet olmadan da açılır. Bir tarafta yapılan değişiklik öbür tarafa aktarılır.

## Özellikler

- **Kurulum sihirbazı.** İlk açılışta seni adım adım yönlendirir:
  - rclone'u kurar
  - Google hesabını bağlar; istersen kendi client ID'ni de kullanabilirsin
  - diskin nereye bağlanacağını ve önbelleğin ne kadar büyüyebileceğini sorar
  - eşitlenecek klasörleri seçtirir
- **rclone'u senin yerine kurar.** rclone kurulu değilse ya da çok eskiyse sihirbaz güncel sürümü resmi siteden indirir. Dosyayı rclone'un yayımladığı SHA256 özetleriyle doğrular ve yalnızca senin kullanıcın için kurar, yönetici yetkisi gerekmez.
- **Google Docs desteği.** Dokümanlar, E-Tablolar ve Slaytlar diskte küçük kısayol dosyaları olarak görünür. Birine çift tıklayınca tarayıcıda Google'ın kendi düzenleyicisinde açılır.
- **Durum tek bakışta.** Tek pencerede genel durum, eşitlenen klasörler ve her birinin son eşitleme zamanı görünür.
- **Depolamanın tamamı.** Google depolama alanın Drive, Gmail ve Google Fotoğraflar arasında paylaşılır. Drivux toplamı ve her birinin ne kadar kullandığını gösterir; sayılar Google'ın gösterdiğiyle aynı olur.
- **Üst çubuk simgesi.** Eşitleme durumunu tek bakışta gör; üst çubuktan hemen eşitle, Drivux'u ya da Drive'ını aç. Ayarlardan kapatabilirsin.
- **İngilizce ve Türkçe.** Arayüz sistem dilini izler. Ayarlardan dili kendin de seçebilirsin.
- **Otomatik eşitleme.** Eşitlenen bir klasördeki değişiklik yaklaşık 15 saniye içinde yüklenir. Drivux ayrıca düzenli aralıklarla da eşitler, varsayılan olarak 5 dakikada bir.
- **Hata bildirimleri.** Bir şey ters giderse masaüstü bildirimi alırsın. Ayrıntılar kayıt görüntüleyicide.
- **Toplu silmeye karşı koruma.** Tek bir eşitleme 50'den fazla dosya silecekse eşitleme durur ve senin onayını bekler.
- **Çakışmada veri kaybı yok.** Aynı dosya iki tarafta birden değişirse yeni sürüm kalır, öbürü numaralı bir kopya olarak saklanır.
- **Oturumla birlikte başlar.** Hem disk hem eşitleme oturum açtığında kendiliğinden başlar.

## Kurulum

### Paketle (önerilen)

Dağıtımına uygun paketi [Sürümler](https://github.com/abdullahnil/drivux/releases) sayfasından indir:

```bash
# Fedora / RHEL / openSUSE
sudo dnf install ./drivux-1.4.0-1.noarch.rpm

# Ubuntu 24.04+ / Debian 13+ / Linux Mint 22+
sudo apt install ./drivux_1.4.0_all.deb
```

Ardından uygulama menüsünden **Drivux**'u aç; kurulum sihirbazı başlar.

### Kaynaktan

```bash
git clone https://github.com/abdullahnil/drivux.git
cd drivux
./kur.sh
```

`kur.sh` üç iş yapar:

- gerekli sistem paketlerini paket yöneticinle kurar (dnf, apt, pacman ya da zypper)
- Drivux'u yalnızca senin kullanıcın için `~/.local` altına kurar
- kurulum sihirbazını açar

Güncellemek için `git pull` yapıp `./kur.sh`'i yeniden çalıştır. Ayarların korunur.

### Gereksinimler

- GTK 4 ve **libadwaita 1.5 ya da daha yenisi**. Fedora 40+, Ubuntu 24.04+ ve Debian 13+ bu koşulu karşılar.
- FUSE 3 (disk özelliği için)
- Üst çubuk simgesi için AppIndicator kütüphanesi (Fedora'da `libappindicator-gtk3`, Ubuntu/Debian'da `gir1.2-ayatanaappindicator3-0.1`). GNOME'da ayrıca [AppIndicator eklentisi](https://extensions.gnome.org/extension/615/appindicator-support/) gerekir; Ubuntu'da hazır gelir, Fedora'da `gnome-shell-extension-appindicator` paketidir.
- systemd kullanıcı oturumu

## Kullanım

Uygulama menüsünden **Drivux**'u aç.

Terminalden:

```bash
drivux            # uygulamayı aç
drivux sync       # hemen eşitle
drivux status     # eşitleme durumunu JSON olarak yazdır
drivux tray       # üst çubuk simgesini göster
```

## Nasıl çalışır?

| Parça | Görevi |
|---|---|
| `drivux-disk.service` | `rclone mount` ile Drive'ı `~/Google Drive` klasörüne bağlar. Tam VFS önbelleğini kullanır. |
| `drivux.service` | Klasörleri `rclone bisync` ile eşitleyen Python servisi. Klasörlerdeki değişiklikleri izler ve zamanlamayı yürütür. |
| `drivux` | GTK 4 / libadwaita uygulaması ve kurulum sihirbazı. Servisle ayar ve durum dosyaları ile Unix sinyalleri üzerinden haberleşir. |

| Ne | Nerede |
|---|---|
| Ayarlar | `~/.config/drivux/ayar.json` |
| Durum | `~/.local/state/drivux/durum.json` |
| rclone (Drivux kurduysa) | `~/.local/share/drivux/bin/rclone` |
| Kayıtlar | `journalctl --user -u drivux -u drivux-disk` |

### Paket üretmek

```bash
./paketleme/paketle.sh   # .rpm ve .deb dosyalarını dist/ klasörüne yazar
```

Bunun için `rpmbuild` ve `dpkg-deb` gerekir. Fedora'da `sudo dnf install rpm-build dpkg` ile kurabilirsin.

### Çeviriler

Arayüz İngilizce yazılır. Çeviriler `drivux/ceviri_<dil>.py` dosyalarında, İngilizce metni anahtar olarak kullanan bir sözlük halinde durur. Türkçe çeviri `drivux/ceviri_tr.py` dosyasında. Yeni bir dil eklemek için:

1. `drivux/ceviri_tr.py` dosyasını `drivux/ceviri_<kod>.py` adıyla kopyala ve değerleri çevir.
2. Dili `drivux/ceviri.py` içindeki `DILLER` ve `DIL_ADLARI` listelerine ekle.
3. `python3 paketleme/ceviri-kontrol.py` komutunu çalıştır. Eksik çevirileri ve uyuşmayan `{yer tutucuları}` gösterir; paket üretilirken de çalışır.

## Bilinmesi gerekenler

- **Eşitleme bir yedek değil, aynadır.** Bir dosyayı silersen ya da bozarsan bu değişiklik Drive'a da gider. Drive'dan silinen dosyalar 30 gün boyunca Drive'ın çöp kutusunda durur.
- **Küçük resimler dosyaları indirir.** Dosyalar uygulaması Drive diskini yerel bir disk gibi görür. Bu yüzden bir klasörü ilk açtığında küçük resim oluşturmak için fotoğrafları, videoları ve PDF'leri (varsayılan olarak 50 MB'a kadar) indirir; sonrasında önbellekten gelirler. Bağlantın yavaşsa bu sınırı `gsettings set org.gnome.nautilus.preferences thumbnail-limit 10` komutuyla (MB cinsinden) düşürebilir ya da Dosyalar → Tercihler'den küçük resimleri kapatabilirsin.
- **Google Docs dosyaları yalnızca diskte görünür.** Klasör eşitlemesine dahil değildir, çünkü bunlar gerçek dosya değil, Google'ın sunucularındaki belgelerdir.
- **Kendi client ID'ni kullan.** rclone'un bütün kullanıcılarıyla paylaştığı Google client ID'si kullanımdan kaldırılıyor. Erişimini kaybetmemek için sihirbazda "Kendi Google client ID'ni kullan" seçeneğini aç ve kendi ID'ni gir. Nasıl oluşturulacağını [rclone rehberi](https://rclone.org/drive/#making-your-own-client-id) anlatıyor.
- **Eski bir addan yükseltme.** Drivux'un adı 1.1'e kadar "Drive Bağlantı", 1.2'de "G-Drivux" idi. Drivux'u ilk çalıştırdığında ayarların, eşitleme durumun ve indirilmiş rclone yeni adlara kendiliğinden taşınır, eski servisler de kapatılır.

## Kaldırma

```bash
./kaldir.sh                  # kaynaktan kurduysan
sudo dnf remove drivux      # Fedora
sudo apt remove drivux      # Ubuntu / Debian
```

Bunların hiçbiri bilgisayardaki ya da Drive'daki dosyalarına dokunmaz.

## Lisans

[MIT](LICENSE). Drivux'un Google ile bir bağlantısı yoktur ve Google tarafından onaylanmamıştır. Google Drive, Google LLC'nin ticari markasıdır.
