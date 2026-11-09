// ~*~ RetroBot 98 / Nova 2035 - sohbet mantığı ~*~

const sohbetAlani = document.getElementById("sohbet");
const form = document.getElementById("form");
const mesajKutusu = document.getElementById("mesaj");
const gonderButonu = document.getElementById("gonder");
const durum = document.getElementById("durum");
const donemButonu = document.getElementById("donem-butonu");

// Her dönemin kendine ait metinleri
const DONEMLER = {
  "1998": {
    botAdi: "RetroBot",
    sayfaBasligi: "~*~ RetroBot 98 ~*~ Sanal Sohbet Odasi",
    placeholder: "Mesajınızı yazın...",
    karsilama: "Selaaam! Modem cızırtısı bitti, bağlandık! Ben RetroBot, 1998'in en havalı sohbet botuyum. Bana istediğini sorabilirsin! :-)",
    yaziyor: "yazıyor...",
    baglaniyor: "Bağlanıyor... (modem cızırtısı)",
    hata: "*** Bağlantı koptu! Biri telefonu açtı galiba... ",
  },
  "2035": {
    botAdi: "Nova",
    sayfaBasligi: "Nova · 2035",
    placeholder: "Nova'ya bir şey sor…",
    karsilama: "Merhaba! Ben Nova. Bugün senin için ne yapabilirim? Hava taksisi rezervasyonundan Mars'taki üsle görüntülü görüşmeye kadar her konuda yardımcı olabilirim.",
    yaziyor: "düşünüyor…",
    baglaniyor: "Nöral bağlantı kuruluyor…",
    hata: "Bağlantı kesildi. ",
  },
};

// Seçili dönem tarayıcıda saklanır, sayfa yenilense de korunur
let donem = localStorage.getItem("donem") === "2035" ? "2035" : "1998";

// Sohbet geçmişi: her istekte backend'e gönderilir, böylece bot önceki mesajları hatırlar
let gecmis = [];

// Ziyaretçi sayacı (sahte ama 90'lar ruhuna uygun - tarayıcıda saklanır)
const sayac = Number(localStorage.getItem("ziyaretci") || 1337) + 1;
localStorage.setItem("ziyaretci", sayac);
document.getElementById("sayac").textContent = String(sayac).padStart(6, "0");

function mesajEkle(sinif, isim, metin) {
  const div = document.createElement("div");
  div.className = "mesaj " + sinif;
  if (isim) {
    const b = document.createElement("b");
    // 1998'de IRC tarzı <İsim>, 2035'te sade isim etiketi
    b.textContent = donem === "1998" ? "<" + isim + "> " : isim;
    div.appendChild(b);
  }
  // textContent kullanıyoruz ki gelen metin HTML olarak çalıştırılmasın
  div.appendChild(document.createTextNode(metin));
  sohbetAlani.appendChild(div);
  sohbetAlani.scrollTop = sohbetAlani.scrollHeight;
  return div;
}

// Dönemi uygula: görünümü değiştir, sohbeti sıfırla, karşılama mesajını göster
function donemiUygula() {
  const d = DONEMLER[donem];
  document.body.classList.toggle("modern", donem === "2035");
  document.title = d.sayfaBasligi;
  mesajKutusu.placeholder = d.placeholder;
  durum.textContent = "Hazır";

  gecmis = [];
  sohbetAlani.innerHTML = "";
  mesajEkle("bot", d.botAdi, d.karsilama);
}

donemButonu.addEventListener("click", () => {
  donem = donem === "1998" ? "2035" : "1998";
  localStorage.setItem("donem", donem);
  donemiUygula();
  mesajKutusu.focus();
});

form.addEventListener("submit", async (olay) => {
  olay.preventDefault();
  const metin = mesajKutusu.value.trim();
  if (!metin) return;

  // İstek sürerken dönem değişirse cevabı yanlış sohbete yazmamak için sabitle
  const istekDonemi = donem;
  const d = DONEMLER[istekDonemi];

  mesajEkle("kullanici", "Sen", metin);
  gecmis.push({ role: "user", content: metin });
  mesajKutusu.value = "";

  gonderButonu.disabled = true;
  donemButonu.disabled = true;
  durum.textContent = d.baglaniyor;
  const bekleme = mesajEkle("bot yaziyor", d.botAdi, d.yaziyor);

  try {
    const yanit = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: gecmis, era: istekDonemi }),
    });
    const veri = await yanit.json();
    bekleme.remove();

    if (!yanit.ok) {
      throw new Error(typeof veri.detail === "string" ? veri.detail : "Bilinmeyen hata");
    }

    mesajEkle("bot", d.botAdi, veri.reply);
    gecmis.push({ role: "assistant", content: veri.reply });
    durum.textContent = "Hazır";
  } catch (hata) {
    bekleme.remove();
    gecmis.pop(); // başarısız mesajı geçmişten çıkar
    mesajEkle("hata", null, d.hata + "(" + hata.message + ")");
    durum.textContent = "Hata";
  } finally {
    gonderButonu.disabled = false;
    donemButonu.disabled = false;
    mesajKutusu.focus();
  }
});

donemiUygula();
