# CLA-ssistant – Felhasználói kézikönyv

## 1. Mi ez?
A CLA-ssistant egy Flask alapú webes felület Robot Framework robotok kezeléséhez:
- robotok letöltése / telepítése
- robotok futtatása
- futások megszakítása (STOP)
- futási eredmények, logok megnyitása
- (fejlesztői módban) GitHub kiadás (Release) készítése

A felületet böngészőből éred el: `http://localhost:5000`.

---

## 2. Előfeltételek
- Windows
- Internet elérés (GitHub lekérésekhez)
- Git telepítve (Setup script klónozáshoz)

Ajánlott:
- GitHub token a rate-limit elkerüléséhez (lásd lejjebb)

---

## 3. Telepítés (ajánlott út)
1. Futtasd a telepítőt:
   - `Setup-CLAssistant.bat`
2. A telepítő létrehozza a szükséges mappákat a következő helyen (felhasználónév függő):
   - `C:\Users\<felhasználó>\MyRobotFramework\`
   - fontosabb alkönyvtárak: `DownloadedRobots`, `SandboxRobots`, `Kuka`
3. A telepítő GitHub-ról letölti a projektet a telepített helyre, majd lefuttatja a `telepito.bat`-ot (virtuális környezet és csomagok).

---

## 4. Indítás
Két tipikus indítási mód:

### A) Telepített indítás
- `Run-CLAssistant.bat`
  - megkeresi a telepített CLA-ssistant mappát a `DownloadedRobots` alatt,
  - majd meghívja a `start.bat`-ot.

### B) Közvetlen indítás a projekt mappájából
- `start.bat`
  - ellenőrzi a `.venv` meglétét,
  - (ha kell) betölti a `github_token.txt`-t,
  - frissíti a repo adatokat,
  - elindítja a Flask szervert,
  - és megnyitja a böngészőt.

Leállítás:
- a szervert futtató konzolban `CTRL + C`

---

## 5. Módok: Normál mód vs. Fejlesztői mód
A felület két „üzemmódban” tud működni:

### Normál mód
- **Alapértelmezett mód** (ha nem kapcsolod be külön a Fejlesztői módot)
- telepített robotok a `DownloadedRobots` alatt
- Letölthető robotok jellemzően csak akkor látszanak, ha van hozzájuk release/tag információ

### Fejlesztői mód
- telepített robotok a `SandboxRobots` könyvtárból listázódnak
- a UI megnevezései fejlesztői fókuszúak (pl. Robot műtő / Robot raktár)
- extra funkció: GitHub „Kiadás készítése” (Release) modal
- a telepített verzió megjelenik és GitHub linkként működik

Megjegyzés:
- A UI-ban „Robot” felirat szerepel, de technikailag ez a `branch`.

---

## 6. Fő felületi elemek és használat

### 6.1. Globális szűrő
Felül található egy szűrő mező (pl. „Robot szűrése…”), ami az éppen aktív tab robotjait szűri.

### 6.2. Telepített robotok (Robot műtő)
Itt a már telepített robotok jelennek meg kártyákon.

Kártya fejléc (repo név):
- a repo név mellett megjelenhet egy számláló `(x)`
- ez az adott kártyán belül megjelenített robotok (branchek) darabszáma

Egy robot sorában tipikusan:
- **Futtatás** gomb (▶) – az adott robot futtatása
- **Release/Verziók** info gomb (i / hammer / bell) – verzió/release információk
  - `i` (info): van release információ
  - `hammer` (kalapács): nincs release információ
  - `bell` (harang): új verzió elérhető (**csak Normál módban**, Fejlesztői módban nem jelez)
- **Környezet beállítás** gomb (sliders) – a robothoz tartozó `*.config` fájl(ok) megtekintése/szerkesztése
  - a modalban legördülőből választható ki a kívánt `*.config` fájl
  - ha csak 1 db `*.config` van, automatikusan kiválasztódik
- **(Fejlesztői módban)** **Új kiadás készítése** gomb (box-seam) – GitHub release létrehozása
- **Telepített verzió badge** – világoskék háttérrel, sötétkék szöveggel
  - kattintható GitHub link (release tag oldal)
  - tooltip: „Részletes verzió információk”
- **Törlés** (kuka ikon) – az adott telepített robot eltávolítása a telepített listából

Megszakítás (STOP):
- A futó robot megszakítható a STOP funkcióval (ha elérhető a felületen).

### 6.3. Letölthető robotok (Robot raktár)
Itt a letölthető robotok jelennek meg.

Kártya fejléc (repo név):
- a repo név mellett megjelenhet egy számláló `(x)`, ami a listázott robotok darabszáma.

Egy robot sorában:
- **Letöltés** gomb (⬇)
  - az ikon **mindig letöltés ikon**
  - tooltip/title **mindig „Azonnali letöltés”**
  - ezen a gombon nincs ikon/tooltip csere logika
- **Verziók / release infó** gomb (i/hammer)

### 6.4. Futási eredmények
A Futási eredmények tab a korábbi futások listáját/megnyitható logjait kezeli.

### 6.5. Log
A Log tab a szerver logját és keresési segédeket tartalmazhat.

---

## 7. GitHub integráció (token)
A GitHub API hívásokhoz (repo lista, release, issue) ajánlott token.

Lehetséges módok:
- környezeti változó: `GITHUB_TOKEN` vagy `GH_TOKEN`
- fájl: `github_token.txt` a projekt gyökérben (az első sor a token)

Token nélkül:
- egyes műveletek limitáltak lehetnek (rate limit),
- Release/Issue létrehozás jellemzően tiltott.

---

## 8. Fejlesztői mód: „Kiadás készítése” (GitHub Release)
A Robot műtőben (fejlesztői módban) a box-seam gombra kattintva feljön a modal:
- **TagName** (szöveg)
- **ReleaseTitle** (szöveg)
- **ReleaseNotes** (többsoros)

Megjegyzés:
- A **TagName** mező alapértelmezés szerint a jelenlegi „latest” release tag-et próbálja felajánlani (ha elérhető).

Gombok:
- **Mégsem**
- **Kiadás készítése**

Siker esetén:
- toast üzenet + GitHub link
- a Robot műtő tab frissül

Hiba esetén:
- Ha a GitHub `422`-vel jelez (pl. már létező tag), a hibaüzenet erre külön felhívja a figyelmet (pl. „Ilyen verziószámú kiadás már létezik”).

---

## 9. Hibaelhárítás (gyors tippek)

### 9.1. `start.bat` Exit Code 1
Gyakori okok:
- nincs `.venv` (előbb futtasd a `telepito.bat`-ot vagy a Setup scriptet)
- hiányzó Python csomagok
- GitHub lekérés hibázik és nincs korábbi `repos_response.json`

Mit próbálj:
- futtasd újra a telepítést: `Setup-CLAssistant.bat`
- indítsd a telepített módon: `Run-CLAssistant.bat`
- nézd meg a konzolban a hibaüzenetet és a logot

### 9.2. Nem jelenik meg tooltip
- frissítés után a tooltipek csak akkor aktívak, ha a Bootstrap tooltip inicializálás lefut.
- ha kell, frissíts rá a tabra / oldalt, vagy várj pár másodpercet.

---

## 10. Fogalmak
- **Repo**: GitHub repository
- **Robot**: a UI-ban a branch (Robot Framework csomag/robot variáns)
- **Telepített verzió**: az utoljára letöltött/telepített tag

---

## 11. Verzió
A felületen megjelenő verzió a Beállítások/fejléc részen látszódhat (projektfüggő).
