"""What SportsPred covers. Edit this file to add or remove competitions."""

# First year of history pulled for ratings. More years = steadier ratings, slower first run.
SOCCER_HISTORY_FROM = 2021
TENNIS_HISTORY_FROM = "2024-01-01"

# Club competitions we predict. `format`:
#   league           - double round-robin table; winner = top of the table
#   league_phase_ko  - UEFA's 36-team league phase, then knockouts
SOCCER_COMPETITIONS = [
    {"slug": "eng.1", "name": "Premier League", "country": "England", "format": "league", "group": "domestic"},
    {"slug": "esp.1", "name": "La Liga", "country": "Spain", "format": "league", "group": "domestic"},
    {"slug": "ita.1", "name": "Serie A", "country": "Italy", "format": "league", "group": "domestic"},
    {"slug": "ger.1", "name": "Bundesliga", "country": "Germany", "format": "league", "group": "domestic"},
    {"slug": "fra.1", "name": "Ligue 1", "country": "France", "format": "league", "group": "domestic"},
    {"slug": "uefa.champions", "name": "Champions League", "country": "Europe", "format": "league_phase_ko", "group": "european"},
    {"slug": "uefa.europa", "name": "Europa League", "country": "Europe", "format": "league_phase_ko", "group": "european"},
]

# Extra leagues used only to rate clubs that turn up in Europe (Benfica, PSV, Celtic...).
SOCCER_RATING_ONLY = ["por.1", "ned.1", "sco.1", "bel.1", "tur.1", "uefa.europa.conf"]

# International tournaments. Shown only while they have fixtures in the current or next year.
#   groups_ko - group tables, then a knockout bracket
INTERNATIONAL_COMPETITIONS = [
    {"slug": "uefa.nations", "name": "UEFA Nations League", "format": "groups_ko", "group": "international",
     "group_filter": "Group A", "advance_top": 2, "two_leg_min": 8},
    {"slug": "fifa.world", "name": "FIFA World Cup", "format": "groups_ko", "group": "international",
     "advance_top": 2, "two_leg_min": 999},
    {"slug": "uefa.euro", "name": "UEFA Euro", "format": "groups_ko", "group": "international",
     "advance_top": 2, "two_leg_min": 999},
    {"slug": "conmebol.america", "name": "Copa América", "format": "groups_ko", "group": "international",
     "advance_top": 2, "two_leg_min": 999},
    {"slug": "caf.nations", "name": "Africa Cup of Nations", "format": "groups_ko", "group": "international",
     "advance_top": 2, "two_leg_min": 999},
    {"slug": "afc.asian.cup", "name": "AFC Asian Cup", "format": "groups_ko", "group": "international",
     "advance_top": 2, "two_leg_min": 999},
    {"slug": "concacaf.gold", "name": "Gold Cup", "format": "groups_ko", "group": "international",
     "advance_top": 2, "two_leg_min": 999},
]

INTERNATIONAL_RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"

# ESPN display name -> name used in the international results archive.
COUNTRY_ALIASES = {
    "Türkiye": "Turkey", "USA": "United States", "United States of America": "United States",
    "Korea Republic": "South Korea", "South Korea": "South Korea", "Korea DPR": "North Korea",
    "IR Iran": "Iran", "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast",
    "Czechia": "Czech Republic", "Republic of Ireland": "Republic of Ireland", "Ireland": "Republic of Ireland",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "North Macedonia": "North Macedonia", "FYR Macedonia": "North Macedonia", "Cape Verde Islands": "Cape Verde",
    "Cabo Verde": "Cape Verde", "China PR": "China", "Congo DR": "DR Congo", "DR Congo": "DR Congo",
    "Curacao": "Curaçao", "Kyrgyz Republic": "Kyrgyzstan", "Faroe Islands": "Faroe Islands",
    "St. Kitts and Nevis": "Saint Kitts and Nevis", "St. Lucia": "Saint Lucia",
    "St. Vincent and the Grenadines": "Saint Vincent and the Grenadines", "Chinese Taipei": "Taiwan",
    "Eswatini": "Eswatini", "The Gambia": "Gambia", "Gambia": "Gambia",
}

# Tennis: which tournaments get winner predictions (all tour matches still feed the ratings).
TENNIS_TOURS = {
    "atp": {"name": "ATP", "keywords": [
        "Australian Open", "Roland Garros", "French Open", "Wimbledon", "US Open",
        "BNP Paribas Open", "Indian Wells", "Miami Open", "Monte-Carlo", "Monte Carlo", "Mutua Madrid",
        "Internazionali", "Italian Open", "National Bank Open", "Canadian Open", "Omnium Banque",
        "Cincinnati", "Shanghai", "Paris Masters", "Rolex Paris"]},
    "wta": {"name": "WTA", "keywords": [
        "Australian Open", "Roland Garros", "French Open", "Wimbledon", "US Open",
        "Qatar", "Doha", "Dubai", "BNP Paribas Open", "Indian Wells", "Miami Open", "Mutua Madrid",
        "Internazionali", "Italian Open", "National Bank Open", "Canadian Open", "Omnium Banque",
        "Cincinnati", "China Open", "Wuhan"]},
}
GRAND_SLAMS = ["Australian Open", "Roland Garros", "French Open", "Wimbledon", "US Open"]

# ESPN doesn't publish court surfaces, so tournaments are matched by name. Anything unmatched is hard.
TENNIS_SURFACES = {
    "clay": [
        "Roland Garros", "French Open", "Monte-Carlo", "Monte Carlo", "Mutua Madrid", "Internazionali BNL",
        "Italian Open", "Barcelona Open", "BMW Open", "Estoril", "Geneva Open", "Auvergne-Rh", "Hamburg",
        "Gstaad", "Croatia Open", "Kitzb", "Generali Open", "Nordea Open", "Clay Court Championship", "Hassan II",
        "Argentina Open", "Rio Open", "Chile Open", "Tiriac Open", "Charleston Open", "Porsche Tennis Grand Prix",
        "Lalla Meryem", "Strasbourg", "Palermo", "Copa Colsanitas", "Parma Ladies", "Iasi Open",
        "Rouen", "Saint Malo", "Oeiras Open", "Oeiras Jamor Ladies", "Femminili Di Brescia", "Caldas da Rainha",
        "Figueira Da Foz", "Makarska", "Villa de Madrid", "Catalonia Open", "Lisboa Belem", "Cundinamarca",
        "Megasaray", "Istanbul Open", "ATIK Antalya", "Grand Est Open", "Trophée Clarins", "Montreux",
        "Bad Gastein", "Bastad", "Båstad", "Umag", "Marrakech", "Houston",
        "Bolivia Open", "Cordoba Open", "Tucumán Open", "Quito Open", "Cali Open", "Tolentino", "Citta di Grado",
        "Hungarian Grand Prix", "Samsun Open", "San Sebastian", "Solgironès", "Tiriac Foundation", "Open delle Puglie",
    ],
    "grass": [
        "Wimbledon", "HSBC Championships", "Terra Wortmann", "Libéma Open", "Boss Open", "Mallorca",
        "Eastbourne", "Birmingham", "Nottingham", "Ilkley", "Bad Homburg", "Berlin Tennis Open",
        "Hall of Fame Open", "Queen's", "Halle", "Veneto Open",
    ],
}

# Monte Carlo runs. "today" is the headline number; replays rebuild the odds-over-time chart.
SIMS_TODAY = 10000
SIMS_REPLAY = 2000
