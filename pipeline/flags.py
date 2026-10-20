"""Flag emoji for countries: from ESPN's three-letter tennis codes and from national-team names."""

# ESPN / Olympic-style three-letter codes -> ISO 3166 two-letter codes
CODE_TO_ISO2 = {
    "arg": "AR", "aus": "AU", "aut": "AT", "bel": "BE", "bih": "BA", "blr": "BY", "bol": "BO", "bra": "BR",
    "bul": "BG", "can": "CA", "chi": "CL", "chn": "CN", "col": "CO", "cro": "HR", "cyp": "CY", "cze": "CZ",
    "den": "DK", "dom": "DO", "ecu": "EC", "egy": "EG", "esp": "ES", "est": "EE", "fin": "FI", "fra": "FR",
    "gbr": "GB", "geo": "GE", "ger": "DE", "gre": "GR", "hkg": "HK", "hun": "HU", "ind": "IN", "ina": "ID",
    "irl": "IE", "isr": "IL", "ita": "IT", "jpn": "JP", "kaz": "KZ", "kor": "KR", "lat": "LV", "ltu": "LT",
    "lux": "LU", "mar": "MA", "mda": "MD", "mex": "MX", "mon": "MC", "mne": "ME", "ned": "NL", "nor": "NO",
    "nzl": "NZ", "par": "PY", "per": "PE", "phi": "PH", "pol": "PL", "por": "PT", "pur": "PR", "rou": "RO",
    "rsa": "ZA", "rus": "RU", "ser": "RS", "srb": "RS", "slo": "SI", "svk": "SK", "sui": "CH", "swe": "SE",
    "tha": "TH", "tpe": "TW", "tun": "TN", "tur": "TR", "ukr": "UA", "uru": "UY", "usa": "US", "uzb": "UZ",
    "ven": "VE", "lbn": "LB", "qat": "QA", "jor": "JO", "mkd": "MK", "alb": "AL", "arm": "AM", "aze": "AZ",
}

# national-team names (as used by the international results archive / ESPN) -> ISO2 or a special flag
NAME_TO_ISO2 = {
    "Albania": "AL", "Algeria": "DZ", "Andorra": "AD", "Argentina": "AR", "Armenia": "AM", "Australia": "AU",
    "Austria": "AT", "Azerbaijan": "AZ", "Bahrain": "BH", "Belarus": "BY", "Belgium": "BE", "Bolivia": "BO",
    "Bosnia and Herzegovina": "BA", "Brazil": "BR", "Bulgaria": "BG", "Burkina Faso": "BF", "Cameroon": "CM",
    "Canada": "CA", "Cape Verde": "CV", "Chile": "CL", "China": "CN", "Colombia": "CO", "Costa Rica": "CR",
    "Croatia": "HR", "Curaçao": "CW", "Cyprus": "CY", "Czech Republic": "CZ", "Czechia": "CZ", "Denmark": "DK",
    "DR Congo": "CD", "Ecuador": "EC", "Egypt": "EG", "El Salvador": "SV", "Estonia": "EE", "Faroe Islands": "FO",
    "Finland": "FI", "France": "FR", "Georgia": "GE", "Germany": "DE", "Ghana": "GH", "Gibraltar": "GI",
    "Greece": "GR", "Guatemala": "GT", "Haiti": "HT", "Honduras": "HN", "Hungary": "HU", "Iceland": "IS",
    "India": "IN", "Indonesia": "ID", "Iran": "IR", "Iraq": "IQ", "Israel": "IL", "Italy": "IT", "Ivory Coast": "CI",
    "Jamaica": "JM", "Japan": "JP", "Jordan": "JO", "Kazakhstan": "KZ", "Kosovo": "XK", "Kuwait": "KW",
    "Kyrgyzstan": "KG", "Latvia": "LV", "Lebanon": "LB", "Liechtenstein": "LI", "Lithuania": "LT",
    "Luxembourg": "LU", "Mali": "ML", "Malta": "MT", "Mexico": "MX", "Moldova": "MD", "Montenegro": "ME",
    "Morocco": "MA", "Netherlands": "NL", "New Zealand": "NZ", "Nigeria": "NG", "North Korea": "KP",
    "North Macedonia": "MK", "Norway": "NO", "Oman": "OM", "Palestine": "PS", "Panama": "PA", "Paraguay": "PY",
    "Peru": "PE", "Poland": "PL", "Portugal": "PT", "Qatar": "QA", "Republic of Ireland": "IE", "Romania": "RO",
    "Russia": "RU", "San Marino": "SM", "Saudi Arabia": "SA", "Senegal": "SN", "Serbia": "RS", "Slovakia": "SK",
    "Slovenia": "SI", "South Africa": "ZA", "South Korea": "KR", "Spain": "ES", "Suriname": "SR", "Sweden": "SE",
    "Switzerland": "CH", "Syria": "SY", "Tajikistan": "TJ", "Thailand": "TH", "Trinidad and Tobago": "TT",
    "Tunisia": "TN", "Turkey": "TR", "Türkiye": "TR", "Ukraine": "UA", "United Arab Emirates": "AE",
    "United States": "US", "USA": "US", "Uruguay": "UY", "Uzbekistan": "UZ", "Venezuela": "VE", "Vietnam": "VN",
    "Wales": "WLS", "England": "ENG", "Scotland": "SCT", "Northern Ireland": "GB",
}

# England, Scotland and Wales have their own flag sequences (black flag + tag characters)
SUBDIVISIONS = {"ENG": "gbeng", "SCT": "gbsct", "WLS": "gbwls"}


def emoji(iso2):
    if not iso2:
        return None
    if iso2 in SUBDIVISIONS:
        return "\U0001F3F4" + "".join(chr(0xE0000 + ord(ch)) for ch in SUBDIVISIONS[iso2]) + "\U000E007F"
    if len(iso2) != 2:
        return None
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in iso2.upper())


def for_code(code):
    """ESPN three-letter code (e.g. 'ser') -> flag emoji, or None."""
    return emoji(CODE_TO_ISO2.get((code or "").lower()))


def for_country(name):
    """National-team name -> flag emoji, or None."""
    return emoji(NAME_TO_ISO2.get(name or ""))
