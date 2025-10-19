# CLA-ssistant

Ez a projekt egy Flask-alapú webes felületet biztosít robotok kezeléséhez.

## Fő funkciók
- **Futtatható robotok**: Csak a már letöltött branch-ek jelennek meg, ezek közül lehet kiválasztani és futtatni.
- **Letölthető robotok**: Csak a még le nem töltött branch-ek jelennek meg, ezek közül lehet kiválasztani és letölteni.
- **Kiválasztott robotok futtatása**: A kiválasztott robotokat egy gombnyomással lehet futtatni.
- **UI**: Két tab (Futtatható/Letölthető), kártyás nézet, gombok a letöltéshez és futtatáshoz.

## Futtatás
1. Telepítsd a szükséges Python csomagokat:
   ```sh
   pip install flask
   ```
2. Indítsd el a szervert:
   ```sh
   start.bat
   ```
3. Nyisd meg a böngészőben: [http://localhost:5000](http://localhost:5000)

## Fájlok
- `flask_app.py` – Flask szerver és webes logika
- `CLA-ssistant_main.robot`, `do-selected.robot` – Robot Framework tesztek
- `fetch_github_repos.py`, `parse_repos.py` – Segédszkriptek
- `resources/`, `libraries/` – Robot Framework erőforrások és könyvtárak
- `results/` – Futtatási eredmények

## Megjegyzések
- A "Branch név" felirat nem jelenik meg a felületen.
- A tabok szűrése Python oldalon történik, a UI csak a releváns robotokat mutatja.

## Szerző
lovaszotto
