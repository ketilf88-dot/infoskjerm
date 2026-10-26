# Infoskjerm

Infoskjerm for kontor-TV med Enios-logo, klokke og nyheter om offshore, subsea, Oslo Børs, Trøndelag og Norge.

- `index.html` er selve siden. Visningstid og antall saker endres øverst i skriptet.
- `scripts/fetch_news.py` henter nyhetene og skriver `news.json`. Kilder og selskaper endres øverst i filen.
- `.github/workflows/news.yml` kjører hentingen hvert 15. minutt. GitHub kan forsinke slike jobber noen minutter.

Siden publiseres med GitHub Pages: Settings → Pages → Deploy from a branch → `main` / root.
