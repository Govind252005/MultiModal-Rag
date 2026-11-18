"""
Universal Transliteration Engine (Phase 6.10).
Converts Latin names and entity text into target scripts (e.g. Devanagari for Hindi queries)
with phonetic accuracy, handling both common names and arbitrary syllable combinations.
"""

from __future__ import annotations

import re
from typing import Dict

# Curated high-accuracy phonetic dictionary for names & roles in Indian academic/industry documents
_NAME_MAP: Dict[str, str] = {
    "govind": "गोविंद",
    "shree": "श्री",
    "lochan": "लोचन",
    "shreelochan": "श्रीलोचन",
    "shree_lochan": "श्रीलोचन",
    "shilajan": "शिलाजन",
    "tanisha": "तनीषा",
    "nisha": "निशा",
    "madan": "मदान",
    "charu": "चारू",
    "gupta": "गुप्ता",
    "sharma": "शर्मा",
    "verma": "वर्मा",
    "singh": "सिंह",
    "kumar": "कुमार",
    "mishra": "मिश्रा",
    "yadav": "यादव",
    "patel": "पटेल",
    "shah": "शाह",
    "jain": "जैन",
    "agarwal": "अग्रवाल",
    "aggarwal": "अग्रवाल",
    "bansal": "बंसल",
    "mittal": "मित्तल",
    "goyal": "गोयल",
    "garg": "गर्ग",
    "singhal": "सिंघल",
    "tyagi": "त्यागी",
    "choudhary": "चौधरी",
    "chaudhary": "चौधरी",
    "malik": "मलिक",
    "tomar": "तोमर",
    "chauhan": "चौहान",
    "rathore": "राठौड़",
    "rajput": "राजपूत",
    "joshi": "जोशी",
    "bhatt": "भट्ट",
    "pandey": "पांडे",
    "tiwari": "तिवारी",
    "tripathi": "त्रिपाठी",
    "shukla": "शुक्ला",
    "dubey": "दुबे",
    "chaubey": "चौबे",
    "jha": "झा",
    "thakur": "ठाकुर",
    "das": "दास",
    "bose": "बोस",
    "banerjee": "बनर्जी",
    "chatterjee": "चटर्जी",
    "mukherjee": "मुखर्जी",
    "ghosh": "घोष",
    "roy": "रॉय",
    "sen": "सेन",
    "dutta": "दत्ता",
    "biswas": "बिस्वास",
    "reddy": "रेड्डी",
    "rao": "राव",
    "nair": "नायर",
    "pillai": "पिल्लई",
    "menon": "मेनन",
    "iyer": "अय्यर",
    "iyengar": "अय्यंगर",
    "rahul": "राहुल",
    "amit": "अमित",
    "priya": "प्रिया",
    "rohit": "रोहित",
    "ananya": "अनन्या",
    "vikram": "विक्रम",
    "aditya": "आदित्य",
    "pooja": "पूजा",
    "neha": "नेहा",
    "sneha": "स्नेहा",
    "rajesh": "राजेश",
    "suresh": "सुरेश",
    "ramesh": "रमेश",
    "deepak": "दीपक",
    "manoj": "मनोज",
    "sandeep": "संदीप",
    "ashok": "अशोक",
    "ajay": "अजय",
    "vijay": "विजय",
    "sunil": "सुनील",
    "anil": "अनिल",
    "ravi": "रवि",
    "kavita": "कविता",
    "sunita": "सुनीता",
    "anita": "अनीता",
    "meena": "मीना",
    "reena": "रीना",
    "ritu": "ऋतु",
    "swati": "स्वाति",
    "divya": "दिव्या",
    "shivam": "शिवम",
    "sachin": "सचिन",
    "saurabh": "सौरभ",
    "gaurav": "गौरव",
    "harsh": "हर्ष",
    "varun": "वरुण",
    "tarun": "तरुण",
    "kunal": "कुणाल",
    "pankaj": "पंकज",
    "prateek": "प्रतीक",
    "abhishek": "अभिषेक",
    "shubham": "शुभम",
    "vishal": "विशाल",
    "mohit": "मोहित",
    "nitin": "नितिन",
    "ashish": "आशीष",
    "manish": "मनीष",
    "mayank": "मयंक",
    "ayush": "आयुष",
    "harshit": "हर्षित",
    "ankit": "अंकित",
    "nikhil": "निखिल",
    "rishabh": "ऋषभ",
    "tushar": "तुषार",
    "akash": "आकाश",
    "vikas": "विकास",
    "sahil": "साहिल",
    "yash": "यश",
    "aman": "अमन",
    "karan": "करण",
    "arjun": "अर्जुन",
}

# Phoneme syllable replacement table for arbitrary names
_PHONEMES = [
    ("shree", "श्री"), ("shri", "श्री"),
    ("ksha", "क्ष"), ("kshi", "क्षि"), ("kshu", "क्षु"), ("ksho", "क्षो"), ("ksh", "क्ष"),
    ("tra", "त्र"), ("tri", "त्रि"), ("tru", "त्रु"), ("tro", "त्रो"), ("tr", "त्र"),
    ("gya", "ज्ञा"), ("gy", "ज्ञ"),
    ("chha", "छा"), ("chhi", "छि"), ("chhu", "छु"), ("chhe", "छे"), ("chho", "छो"), ("chh", "छ"),
    ("cha", "चा"), ("chi", "चि"), ("chu", "चु"), ("che", "चे"), ("cho", "चो"), ("ch", "च"),
    ("sha", "शा"), ("shi", "शि"), ("shu", "शु"), ("she", "शे"), ("sho", "शो"), ("sh", "श"),
    ("kha", "खा"), ("khi", "खि"), ("khu", "खु"), ("khe", "खे"), ("kho", "खो"), ("kh", "ख"),
    ("gha", "घा"), ("ghi", "घि"), ("ghu", "घु"), ("ghe", "घे"), ("gho", "घो"), ("gh", "घ"),
    ("jha", "झा"), ("jhi", "झि"), ("jhu", "झु"), ("jhe", "झे"), ("jho", "झो"), ("jh", "झ"),
    ("tha", "था"), ("thi", "थि"), ("thu", "थु"), ("the", "थे"), ("tho", "थो"), ("th", "थ"),
    ("dha", "धा"), ("dhi", "धि"), ("dhu", "धु"), ("dhe", "धे"), ("dho", "धो"), ("dh", "ध"),
    ("pha", "फा"), ("phi", "फि"), ("phu", "फु"), ("phe", "फे"), ("pho", "फो"), ("ph", "फ"),
    ("bha", "भा"), ("bhi", "भि"), ("bhu", "भु"), ("bhe", "भे"), ("bho", "भो"), ("bh", "भ"),
    ("ka", "क"), ("ki", "कि"), ("ku", "कु"), ("ke", "के"), ("ko", "को"), ("k", "क"),
    ("ga", "ग"), ("gi", "गि"), ("gu", "गु"), ("ge", "गे"), ("go", "गो"), ("g", "ग"),
    ("ja", "ज"), ("ji", "जि"), ("ju", "जु"), ("je", "जे"), ("jo", "जो"), ("j", "ज"),
    ("ta", "त"), ("ti", "ति"), ("tu", "तु"), ("te", "ते"), ("to", "तो"), ("t", "त"),
    ("da", "द"), ("di", "दि"), ("du", "दु"), ("de", "दे"), ("do", "दो"), ("d", "द"),
    ("na", "न"), ("ni", "नि"), ("nu", "नु"), ("ne", "ने"), ("no", "नो"), ("n", "न"),
    ("pa", "प"), ("pi", "पि"), ("pu", "पु"), ("pe", "पे"), ("po", "पो"), ("p", "प"),
    ("ba", "ब"), ("bi", "बि"), ("bu", "बु"), ("be", "बे"), ("bo", "बो"), ("b", "ब"),
    ("ma", "म"), ("mi", "मि"), ("mu", "मु"), ("me", "मे"), ("mo", "मो"), ("m", "म"),
    ("ya", "य"), ("yi", "यि"), ("yu", "यु"), ("ye", "ये"), ("yo", "यो"), ("y", "य"),
    ("ra", "र"), ("ri", "रि"), ("ru", "रु"), ("re", "रे"), ("ro", "रो"), ("r", "र"),
    ("la", "ल"), ("li", "लि"), ("lu", "लु"), ("le", "ले"), ("lo", "लो"), ("l", "ल"),
    ("va", "व"), ("vi", "वि"), ("vu", "वु"), ("ve", "वे"), ("vo", "वो"), ("v", "व"),
    ("wa", "व"), ("wi", "वि"), ("wu", "वु"), ("we", "वे"), ("wo", "वो"), ("w", "व"),
    ("sa", "स"), ("si", "सि"), ("su", "सु"), ("se", "से"), ("so", "सो"), ("s", "स"),
    ("ha", "ह"), ("hi", "हि"), ("hu", "हु"), ("he", "हे"), ("ho", "हो"), ("h", "ह"),
    ("aa", "आ"), ("a", "अ"), ("ee", "ई"), ("i", "इ"), ("oo", "ऊ"), ("u", "उ"),
    ("e", "ए"), ("ai", "ऐ"), ("o", "ओ"), ("au", "औ"),
]


def transliterate_name_to_hindi(name_str: str) -> str:
    """Transliterate an English/Latin name to Devanagari Hindi while preserving numbers & brackets."""
    if not name_str or not name_str.strip():
        return name_str

    # Extract any parenthesized numbers or IDs at the end, e.g. "(00720802723)"
    suffix = ""
    clean_name = name_str.strip()
    id_match = re.search(r"(\s*\([0-9A-Za-z_-]+\))\s*$", clean_name)
    if id_match:
        suffix = id_match.group(1)
        clean_name = clean_name[:id_match.start()].strip()

    tokens = clean_name.split()
    translated_tokens = []
    for tok in tokens:
        clean_tok = tok.lower().strip(".,()[]-_")
        if clean_tok in _NAME_MAP:
            translated_tokens.append(_NAME_MAP[clean_tok])
        else:
            # Algorithmic fallback
            res = clean_tok
            for pat, rep in _PHONEMES:
                res = res.replace(pat, rep)
            translated_tokens.append(res if res else tok)

    transliterated = " ".join(translated_tokens)
    return f"{transliterated}{suffix}".strip()

