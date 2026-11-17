"""Word lists for the generator: companies, places, products per business domain.

Everything is invented or generic. Names look plausible but are not tied to real
companies; identifiers are generated elsewhere and are always random.
"""

from __future__ import annotations

from typing import TypedDict

# (French, Arabic, English) -----------------------------------------------------------
STEMS = [
    ("Atlas", "أطلس", "Atlas"), ("Numidia", "نوميديا", "Numidia"),
    ("El Baraka", "البركة", "El Baraka"), ("Tassili", "طاسيلي", "Tassili"),
    ("Djurdjura", "جرجرة", "Djurdjura"), ("Hoggar", "الهقار", "Hoggar"),
    ("Mitidja", "المتيجة", "Mitidja"), ("Soummam", "الصومام", "Soummam"),
    ("Aurès", "الأوراس", "Aures"), ("El Amel", "الأمل", "El Amel"),
    ("Ibn Khaldoun", "ابن خلدون", "Ibn Khaldoun"), ("Sahara", "الصحراء", "Sahara"),
    ("Chelia", "شليا", "Chelia"), ("Medina", "المدينة", "Medina"),
    ("El Feth", "الفتح", "El Feth"), ("Rayan", "ريان", "Rayan"),
    ("Nour", "نور", "Nour"), ("Salam", "سلام", "Salam"),
    ("Rim", "ريم", "Rim"), ("Zahra", "الزهراء", "Zahra"),
]  # fmt: skip
LEGAL_FORMS = [("SARL", "ش.ذ.م.م"), ("EURL", "م.ش.ش.ذ.م.م"), ("SPA", "ش.ذ.أ"), ("Ets", "مؤسسة")]
CITIES = [
    ("Alger", "الجزائر", "Algiers", "16"), ("Oran", "وهران", "Oran", "31"),
    ("Constantine", "قسنطينة", "Constantine", "25"), ("Annaba", "عنابة", "Annaba", "23"),
    ("Sétif", "سطيف", "Setif", "19"), ("Blida", "البليدة", "Blida", "09"),
    ("Batna", "باتنة", "Batna", "05"), ("Tlemcen", "تلمسان", "Tlemcen", "13"),
    ("Béjaïa", "بجاية", "Bejaia", "06"), ("Biskra", "بسكرة", "Biskra", "07"),
]  # fmt: skip
STREETS = [
    ("Rue Didouche Mourad", "شارع ديدوش مراد", "Didouche Mourad Street"),
    ("Boulevard de l'ALN", "شارع جيش التحرير الوطني", "ALN Boulevard"),
    ("Cité des Frères", "حي الإخوة", "Freres Estate"),
    ("Zone industrielle", "المنطقة الصناعية", "Industrial Zone"),
    ("Rue de la Liberté", "شارع الحرية", "Liberty Street"),
]  # fmt: skip
# index 2 is cash: it triggers the stamp duty (droit de timbre)
PAYMENTS = {
    "fr": ["Virement", "Chèque", "Espèces", "Traite"],
    "ar": ["تحويل بنكي", "شيك", "نقدا", "كمبيالة"],
    "en": ["Bank transfer", "Cheque", "Cash", "Bill of exchange"],
}
CASH_INDEX = 2

# Extra wording that makes some descriptions long enough to wrap over two lines.
SPECS = {
    "fr": ["garantie 12 mois, livraison incluse", "conforme à la norme, emballage d'origine",
           "selon bon de commande, livraison sous 48 h"],
    "ar": ["ضمان 12 شهرا، التوصيل مشمول", "مطابق للمعايير، في التغليف الأصلي",
           "حسب سند الطلب، التسليم خلال 48 ساعة"],
    "en": ["12-month warranty, delivery included", "standards compliant, original packaging",
           "as per purchase order, delivery within 48 h"],
}  # fmt: skip


class Domain(TypedDict):
    sector: tuple[str, str, str]
    items: list[tuple[str, str, str, tuple[int, int]]]


# domain -> (sector FR, AR, EN), items [(fr, ar, en, (low, high) unit price in DZD)]
DOMAINS: dict[str, Domain] = {
    "it": {
        "sector": ("Informatique", "المعلوماتية", "Computing"),
        "items": [
            ("Clavier USB", "لوحة مفاتيح USB", "USB keyboard", (1200, 4500)),
            ("Souris sans fil", "فأرة لاسلكية", "Wireless mouse", (900, 3500)),
            ("Écran 24 pouces", "شاشة 24 بوصة", "24-inch monitor", (22000, 48000)),
            ("Câble réseau 10 m", "كابل شبكة 10 م", "Network cable 10 m", (700, 2200)),
            ("Cartouche toner noir", "خرطوشة حبر أسود", "Black toner cartridge", (6000, 18000)),
            (
                "Disque dur externe 1 To",
                "قرص صلب خارجي 1 تيرا",
                "External hard drive 1 TB",
                (9000, 16000),
            ),
            ("Routeur Wi-Fi", "جهاز توجيه واي فاي", "Wi-Fi router", (4500, 14000)),
            ("Onduleur 650 VA", "مولد احتياطي 650 فا", "UPS 650 VA", (7000, 15000)),
            ("Imprimante laser", "طابعة ليزر", "Laser printer", (25000, 60000)),
            ("Switch 8 ports", "موزع شبكة 8 منافذ", "8-port switch", (3500, 9000)),
            (
                "Licence logiciel annuelle",
                "رخصة برنامج سنوية",
                "Annual software licence",
                (12000, 90000),
            ),
            ("Webcam HD", "كاميرا ويب عالية الدقة", "HD webcam", (2500, 8000)),
        ],
    },
    "office": {
        "sector": ("Fournitures", "اللوازم المكتبية", "Office Supplies"),
        "items": [
            ("Ramette papier A4", "رزمة ورق A4", "A4 paper ream", (450, 900)),
            ("Classeur à levier", "ملف أرشيف", "Lever arch file", (150, 450)),
            (
                "Stylo bille (boîte de 50)",
                "قلم حبر جاف (علبة 50)",
                "Ballpoint pens (box of 50)",
                (600, 1500),
            ),
            ("Agrafeuse", "دباسة", "Stapler", (350, 1200)),
            ("Cahier 200 pages", "دفتر 200 صفحة", "Notebook 200 pages", (120, 400)),
            ("Marqueur permanent", "قلم تعليم دائم", "Permanent marker", (80, 250)),
            ("Chemise cartonnée", "مجلد كرتوني", "Card folder", (30, 90)),
            ("Rouleau papier thermique", "لفافة ورق حراري", "Thermal paper roll", (60, 160)),
            ("Enveloppes (carton)", "أظرفة (كرتون)", "Envelopes (carton)", (1500, 4000)),
            ("Calculatrice de bureau", "آلة حاسبة مكتبية", "Desk calculator", (800, 3000)),
        ],
    },
    "construction": {
        "sector": ("Bâtiment", "البناء", "Construction"),
        "items": [
            ("Ciment 50 kg", "إسمنت 50 كغ", "Cement 50 kg", (700, 1100)),
            ("Peinture 20 L", "طلاء 20 لتر", "Paint 20 L", (5500, 14000)),
            ("Sable (m³)", "رمل (م³)", "Sand (m³)", (1800, 3200)),
            ("Fer à béton 12 mm", "حديد البناء 12 مم", "Rebar 12 mm", (900, 1600)),
            ("Brique creuse (palette)", "آجر مجوف (منصة)", "Hollow brick (pallet)", (14000, 26000)),
            ("Carrelage 60x60 (m²)", "بلاط 60×60 (م²)", "Tiles 60x60 (m²)", (1400, 3800)),
            ("Colle carrelage 25 kg", "غراء بلاط 25 كغ", "Tile adhesive 25 kg", (900, 1700)),
            ("Tuyau PVC 100 mm", "أنبوب بي في سي 100 مم", "PVC pipe 100 mm", (600, 1500)),
            (
                "Câble électrique 2,5 mm",
                "سلك كهربائي 2.5 مم",
                "Electric cable 2.5 mm",
                (6000, 11000),
            ),
            ("Porte intérieure", "باب داخلي", "Interior door", (9000, 28000)),
            ("Gravier (m³)", "حصى (م³)", "Gravel (m³)", (2000, 3500)),
        ],
    },
    "food": {
        "sector": ("Alimentaire", "المواد الغذائية", "Foods"),
        "items": [
            ("Farine 25 kg", "دقيق 25 كغ", "Flour 25 kg", (1700, 2600)),
            ("Huile de table 5 L", "زيت المائدة 5 لتر", "Cooking oil 5 L", (800, 1100)),
            ("Sucre 50 kg", "سكر 50 كغ", "Sugar 50 kg", (5500, 8000)),
            ("Semoule 25 kg", "سميد 25 كغ", "Semolina 25 kg", (1800, 2800)),
            ("Lait en poudre 25 kg", "حليب مجفف 25 كغ", "Milk powder 25 kg", (22000, 36000)),
            ("Café (kg)", "قهوة (كغ)", "Coffee (kg)", (1800, 3500)),
            ("Eau minérale (pack)", "ماء معدني (علبة)", "Mineral water (pack)", (200, 450)),
            ("Dattes Deglet Nour (kg)", "تمر دقلة نور (كغ)", "Deglet Nour dates (kg)", (700, 1500)),
            (
                "Concentré de tomate (carton)",
                "معجون الطماطم (كرتون)",
                "Tomato paste (carton)",
                (3000, 5500),
            ),
            ("Pâtes alimentaires (carton)", "عجائن غذائية (كرتون)", "Pasta (carton)", (1500, 2600)),
            ("Thé vert (carton)", "شاي أخضر (كرتون)", "Green tea (carton)", (2500, 5200)),
        ],
    },
    "medical": {
        "sector": ("Médical", "الطبية", "Medical"),
        "items": [
            (
                "Gants d'examen (boîte)",
                "قفازات فحص (علبة)",
                "Examination gloves (box)",
                (700, 1400),
            ),
            (
                "Masques chirurgicaux (boîte de 50)",
                "كمامات جراحية (علبة 50)",
                "Surgical masks (box of 50)",
                (300, 800),
            ),
            ("Gel hydroalcoolique 500 ml", "جل مطهر 500 مل", "Hand sanitizer 500 ml", (250, 600)),
            ("Thermomètre digital", "ميزان حرارة رقمي", "Digital thermometer", (500, 1800)),
            ("Tensiomètre", "جهاز قياس الضغط", "Blood pressure monitor", (3500, 9500)),
            ("Seringues 5 ml (boîte)", "حقن 5 مل (علبة)", "Syringes 5 ml (box)", (600, 1500)),
            ("Compresses stériles", "ضمادات معقمة", "Sterile gauze pads", (150, 500)),
            ("Désinfectant 5 L", "مطهر 5 لتر", "Disinfectant 5 L", (900, 2400)),
            ("Oxymètre de pouls", "جهاز قياس الأكسجين", "Pulse oximeter", (2500, 7000)),
            ("Bandes de gaze", "لفائف شاش", "Gauze bandages", (60, 220)),
        ],
    },
    "services": {
        "sector": ("Services", "الخدمات", "Services"),
        "items": [
            ("Maintenance mensuelle", "صيانة شهرية", "Monthly maintenance", (15000, 60000)),
            ("Formation (jour)", "تكوين (يوم)", "Training (day)", (20000, 55000)),
            ("Transport de marchandises", "نقل بضائع", "Freight transport", (8000, 30000)),
            ("Audit comptable", "تدقيق محاسبي", "Accounting audit", (40000, 150000)),
            ("Conception site web", "تصميم موقع إلكتروني", "Website design", (60000, 250000)),
            (
                "Nettoyage de locaux (mois)",
                "تنظيف المحلات (شهر)",
                "Office cleaning (month)",
                (25000, 70000),
            ),
            ("Gardiennage (mois)", "حراسة (شهر)", "Security guard (month)", (45000, 110000)),
            (
                "Location de véhicule (jour)",
                "كراء مركبة (يوم)",
                "Vehicle rental (day)",
                (6000, 18000),
            ),
            (
                "Assistance technique (heure)",
                "مساعدة تقنية (ساعة)",
                "Technical support (hour)",
                (2500, 9000),
            ),
            ("Impression et reliure", "طباعة وتجليد", "Printing and binding", (3000, 25000)),
            ("Hébergement web annuel", "استضافة موقع سنوية", "Annual web hosting", (9000, 40000)),
        ],
    },
}
