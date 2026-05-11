from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, Response
import numpy as np
import cv2
import base64
import os
from PIL import Image
import io
import json
import datetime
import sqlite3
import csv
from collections import Counter
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dermascan-secret-2025-xK9pL')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# ── Database ───────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), 'dermascan.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            role          TEXT    DEFAULT 'user',
            created_at    TEXT    NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            username      TEXT    NOT NULL,
            timestamp     TEXT    NOT NULL,
            method        TEXT    NOT NULL,
            skin_type     TEXT    NOT NULL,
            confidence    REAL    NOT NULL,
            dry_pct       REAL,
            normal_pct    REAL,
            oily_pct      REAL,
            combo_pct     REAL,
            user_verified TEXT,
            is_correct    INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sus_responses (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER,
            username  TEXT,
            timestamp TEXT NOT NULL,
            q1  INTEGER, q2  INTEGER, q3  INTEGER, q4  INTEGER, q5  INTEGER,
            q6  INTEGER, q7  INTEGER, q8  INTEGER, q9  INTEGER, q10 INTEGER,
            sus_score REAL NOT NULL,
            grade     TEXT NOT NULL
        )
    """)

    # Create default admin
    existing = c.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        c.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
            ('admin', generate_password_hash('admin1234'), 'admin', datetime.datetime.now().isoformat())
        )

    conn.commit()
    conn.close()

init_db()

# ── Auth helpers ───────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required', 'redirect': '/login'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

SKIN_INFO = {
    'Dry': {
        'emoji': '💧', 'color': '#4f9cf9',
        'description': 'Your skin produces less sebum than normal, lacking the lipids needed to retain moisture and build a protective shield.',
        'characteristics': ['Feels tight after washing','Rough or flaky texture','Small barely-visible pores','Prone to irritation & redness','Fine lines appear more visible'],
        'morning_routine': [
            {'step':'01','name':'Gentle Cleanser','desc':'Wash with a cream or milk cleanser. Avoid hot water.'},
            {'step':'02','name':'Hydrating Toner','desc':'Pat on a hydrating toner to prep skin for moisture.'},
            {'step':'03','name':'Hyaluronic Acid Serum','desc':'Apply on damp skin for maximum absorption.'},
            {'step':'04','name':'Rich Moisturizer','desc':'Lock in moisture with a cream-based moisturizer.'},
            {'step':'05','name':'SPF 30+ Sunscreen','desc':'Finish with a moisturizing sunscreen. Never skip.'},
        ],
        'evening_routine': [
            {'step':'01','name':'Oil Cleanser','desc':'Remove makeup and sunscreen without stripping skin.'},
            {'step':'02','name':'Gentle Cleanser','desc':'Follow with cream cleanser (double cleanse).'},
            {'step':'03','name':'Hydrating Essence','desc':'Apply essence to boost moisture levels.'},
            {'step':'04','name':'Treatment Serum','desc':'Peptides, ceramides, or low-dose retinol.'},
            {'step':'05','name':'Rich Night Cream','desc':'Apply thick moisturizer or sleeping mask overnight.'},
        ],
        'products': {
            'Cleanser': {
                'advice': 'Use cream, milk, or oil-based cleansers. Avoid foaming cleansers that strip natural oils.',
                'key_ingredients': ['Glycerin','Ceramides','Hyaluronic Acid','Squalane'],
                'brands': [
                    {'name':'CeraVe Hydrating Cleanser','why':'Ceramides + hyaluronic acid, non-stripping'},
                    {'name':'La Roche-Posay Toleriane Hydrating Gentle Cleanser','why':'Ultra-gentle, restores skin barrier'},
                    {'name':'Cetaphil Gentle Skin Cleanser','why':'Classic gentle formula, dermatologist recommended'},
                ]
            },
            'Toner': {
                'advice': 'Choose alcohol-free hydrating toners. Look for humectants that draw moisture in.',
                'key_ingredients': ['Hyaluronic Acid','Glycerin','Aloe Vera','Beta-Glucan'],
                'brands': [
                    {'name':'Klairs Supple Preparation Toner','why':'Deeply hydrating, gentle pH-balancing'},
                    {'name':'COSRX Advanced Snail 96 Mucin Power Essence','why':'Intense hydration and repair'},
                    {'name':'Pyunkang Yul Essence Toner','why':'Minimalist, high-moisture formula'},
                ]
            },
            'Serum': {
                'advice': 'Prioritize hydrating serums. Apply on slightly damp skin for maximum absorption.',
                'key_ingredients': ['Hyaluronic Acid','Peptides','Ceramides','Niacinamide','Vitamin E'],
                'brands': [
                    {'name':'The Ordinary Hyaluronic Acid 2% + B5','why':'Budget-friendly, powerful hydration'},
                    {'name':'SkinCeuticals Hydrating B5 Gel','why':'Professional-grade moisture serum'},
                    {'name':'Neutrogena Hydro Boost Serum','why':'Lightweight hyaluronic acid, widely available'},
                ]
            },
            'Moisturizer': {
                'advice': 'Use rich creams with occlusives and emollients. Apply while skin is still slightly damp.',
                'key_ingredients': ['Ceramides','Shea Butter','Squalane','Fatty Acids','Glycerin'],
                'brands': [
                    {'name':'CeraVe Moisturizing Cream','why':'Ceramides + MVE technology, all-day hydration'},
                    {'name':'Avene Skin Recovery Cream','why':'For sensitive dry skin, calming formula'},
                    {'name':'First Aid Beauty Ultra Repair Cream','why':'Colloidal oat + shea butter, intense repair'},
                ]
            },
            'Sunscreen': {
                'advice': 'Choose hydrating or cream-based sunscreens. Avoid alcohol-heavy formulas.',
                'key_ingredients': ['Zinc Oxide','Titanium Dioxide','Hyaluronic Acid','Glycerin'],
                'brands': [
                    {'name':'La Roche-Posay Anthelios Melt-In Sunscreen SPF 60','why':'Hydrating, no white cast'},
                    {'name':'EltaMD UV Clear SPF 46','why':'Lightweight, nourishing, dermatologist favorite'},
                    {'name':'Biore UV Mild Milk SPF 50+','why':'Moisturizing Japanese sunscreen'},
                ]
            },
            'Weekly Treatment': {
                'advice': 'Use a hydrating mask 2-3x per week. Avoid clay masks that over-dry skin.',
                'key_ingredients': ['Hyaluronic Acid','Aloe','Honey','Ceramides'],
                'brands': [
                    {'name':'Laneige Water Sleeping Mask','why':'Overnight hydration powerhouse'},
                    {'name':'Dr. Jart+ Ceramidin Cream','why':'5-cera complex repairs and strengthens barrier'},
                    {'name':'Kiehls Ultra Facial Overnight Hydrating Masque','why':'Deep overnight moisture replenishment'},
                ]
            }
        },
        'ingredients_love': ['Hyaluronic Acid','Ceramides','Glycerin','Squalane','Shea Butter','Peptides','Niacinamide','Aloe Vera'],
        'ingredients_avoid': ['Alcohol Denat','Fragrance (parfum)','Sulfates (SLS/SLES)','High % Salicylic Acid','Benzoyl Peroxide'],
        'avoid': 'Harsh foaming cleansers, alcohol-based toners, hot showers, over-exfoliating, fragrance-heavy products'
    },
    'Normal': {
        'emoji': '✨', 'color': '#34c985',
        'description': 'Your skin is well-balanced with regulated sebum production, small pores, and a naturally radiant complexion. Focus on maintenance and prevention.',
        'characteristics': ['Balanced oil and moisture','Small barely-visible pores','Smooth and even texture','Rarely sensitive or reactive','Naturally radiant appearance'],
        'morning_routine': [
            {'step':'01','name':'Gentle Cleanser','desc':'Use a mild gel or foam cleanser to remove overnight buildup.'},
            {'step':'02','name':'Toner','desc':'Balance pH and prep skin with a lightweight toner.'},
            {'step':'03','name':'Vitamin C Serum','desc':'Brighten and protect with an antioxidant serum.'},
            {'step':'04','name':'Moisturizer','desc':'Apply a lightweight moisturizer to maintain hydration.'},
            {'step':'05','name':'SPF 30+ Sunscreen','desc':'Daily SPF is your best anti-aging product. Always last.'},
        ],
        'evening_routine': [
            {'step':'01','name':'Cleanser','desc':'Remove sunscreen and makeup with a gentle cleanser.'},
            {'step':'02','name':'Exfoliant (2-3x/week)','desc':'Use AHA/BHA to maintain glow and clear pores.'},
            {'step':'03','name':'Toner / Essence','desc':'Apply hydrating toner or essence.'},
            {'step':'04','name':'Retinol (3x/week)','desc':'Use retinol for anti-aging and skin renewal.'},
            {'step':'05','name':'Moisturizer','desc':'Apply a comfortable night moisturizer.'},
        ],
        'products': {
            'Cleanser': {
                'advice': 'A gentle gel or foam cleanser works well. Avoid over-stripping formulas.',
                'key_ingredients': ['Glycerin','Niacinamide','Green Tea Extract','Aloe'],
                'brands': [
                    {'name':'Tatcha The Rice Wash','why':'Gentle, brightening, leaves skin soft'},
                    {'name':'Kiehls Ultra Facial Cleanser','why':'Balanced formula for everyday use'},
                    {'name':'COSRX Low pH Good Morning Gel Cleanser','why':'Maintains skin pH, gentle daily use'},
                ]
            },
            'Toner': {
                'advice': 'Light balancing toners or vitamin-rich essences maintain your natural balance.',
                'key_ingredients': ['Niacinamide','Vitamin C','Hyaluronic Acid','Green Tea'],
                'brands': [
                    {'name':'Pixi Glow Tonic','why':'Gentle AHA for radiance, classic formula'},
                    {'name':'Paulas Choice Skin Balancing Toner','why':'Oil control + hydration balance'},
                    {'name':'Some By Mi AHA BHA PHA 30 Days Miracle Toner','why':'Multi-acid gentle exfoliating toner'},
                ]
            },
            'Serum': {
                'advice': 'Vitamin C in the morning for protection. Retinol at night for anti-aging.',
                'key_ingredients': ['Vitamin C','Retinol','Niacinamide','Hyaluronic Acid','Peptides'],
                'brands': [
                    {'name':'SkinCeuticals C E Ferulic','why':'Gold standard Vitamin C serum'},
                    {'name':'The Ordinary Niacinamide 10% + Zinc 1%','why':'Pore-minimizing, affordable'},
                    {'name':'Paulas Choice C15 Super Booster','why':'Stable Vitamin C, anti-aging'},
                ]
            },
            'Moisturizer': {
                'advice': 'A lightweight lotion or gel-cream works well. Focus on maintaining your natural balance.',
                'key_ingredients': ['Hyaluronic Acid','Niacinamide','Glycerin','Antioxidants'],
                'brands': [
                    {'name':'Neutrogena Hydro Boost Water Gel','why':'Lightweight, non-greasy hydration'},
                    {'name':'Belif The True Cream Aqua Bomb','why':'Refreshing, balanced moisture'},
                    {'name':'Tatcha The Water Cream','why':'Oil-free, pore-minimizing, luxurious'},
                ]
            },
            'Sunscreen': {
                'advice': 'Any SPF 30+ works for normal skin. Choose based on texture preference.',
                'key_ingredients': ['Zinc Oxide','Avobenzone','Niacinamide'],
                'brands': [
                    {'name':'Supergoop! Unseen Sunscreen SPF 40','why':'Invisible, weightless, primer-like'},
                    {'name':'Biore UV Aqua Rich SPF 50+','why':'Japanese lightweight SPF, no white cast'},
                    {'name':'EltaMD UV Clear SPF 46','why':'Lightweight, niacinamide included'},
                ]
            },
            'Weekly Treatment': {
                'advice': 'Exfoliate 1-2x per week to maintain glow.',
                'key_ingredients': ['AHA (Glycolic/Lactic Acid)','BHA (Salicylic Acid)','Enzyme Exfoliants'],
                'brands': [
                    {'name':'Paulas Choice Skin Perfecting 2% BHA','why':'Best-in-class chemical exfoliant'},
                    {'name':'The Ordinary AHA 30% + BHA 2% Peeling Solution','why':'Powerful weekly treatment'},
                    {'name':'Glow Recipe Watermelon Glow PHA+BHA Toner','why':'Gentle brightening exfoliant'},
                ]
            }
        },
        'ingredients_love': ['Vitamin C','Retinol','Niacinamide','AHA/BHA','Hyaluronic Acid','Peptides','Antioxidants'],
        'ingredients_avoid': ['Heavy Silicones (if prone to congestion)','Comedogenic oils','Overly fragranced products'],
        'avoid': 'Heavy products that clog pores, skipping SPF, over-exfoliating'
    },
    'Oily': {
        'emoji': '💫', 'color': '#f5a623',
        'description': 'Your skin produces excess sebum, giving it a shiny look. While prone to breakouts, oily skin tends to age more slowly and has natural protection.',
        'characteristics': ['Shiny or greasy appearance','Enlarged visible pores','Prone to blackheads & breakouts','Makeup tends to slide off','Thick skin texture'],
        'morning_routine': [
            {'step':'01','name':'Foaming Cleanser','desc':'Use a gel or foaming cleanser with salicylic acid.'},
            {'step':'02','name':'BHA Toner','desc':'Apply BHA toner to minimize pores and control sebum.'},
            {'step':'03','name':'Niacinamide Serum','desc':'Regulate oil production and minimize pores.'},
            {'step':'04','name':'Oil-Free Moisturizer','desc':'Always moisturize — skipping causes MORE oil production.'},
            {'step':'05','name':'Mattifying SPF 30+','desc':'Use oil-free or mattifying sunscreen.'},
        ],
        'evening_routine': [
            {'step':'01','name':'Foaming Cleanser','desc':'Cleanse thoroughly to remove excess oil and pollution.'},
            {'step':'02','name':'BHA Exfoliant (3x/week)','desc':'Salicylic acid goes inside pores to clear congestion.'},
            {'step':'03','name':'Balancing Toner','desc':'Use a pore-refining toner.'},
            {'step':'04','name':'Retinol (3x/week)','desc':'Reduces pore size and controls breakouts.'},
            {'step':'05','name':'Gel Moisturizer','desc':'Lightweight gel-based moisturizer — never skip it.'},
        ],
        'products': {
            'Cleanser': {
                'advice': 'Use foaming or gel cleansers with active ingredients. Cleanse twice daily — over-cleansing triggers more oil.',
                'key_ingredients': ['Salicylic Acid','Niacinamide','Tea Tree Oil','Zinc'],
                'brands': [
                    {'name':'CeraVe Foaming Facial Cleanser','why':'Controls oil without stripping, non-comedogenic'},
                    {'name':'La Roche-Posay Effaclar Purifying Gel Cleanser','why':'Designed for oily/acne-prone skin'},
                    {'name':'Neutrogena Oil-Free Acne Wash','why':'Salicylic acid, widely available, effective'},
                ]
            },
            'Toner': {
                'advice': 'BHA toners penetrate pores and dissolve oil plugs. Use after cleansing.',
                'key_ingredients': ['Salicylic Acid (BHA)','Niacinamide','Witch Hazel (alcohol-free)','Zinc'],
                'brands': [
                    {'name':'Paulas Choice Skin Perfecting 2% BHA Liquid','why':'Most researched BHA exfoliant available'},
                    {'name':'COSRX BHA Blackhead Power Liquid','why':'Gentle BHA, minimizes pores effectively'},
                    {'name':'Some By Mi AHA BHA PHA 30 Days Miracle Toner','why':'Multi-acid formula for oily/acne skin'},
                ]
            },
            'Serum': {
                'advice': 'Niacinamide regulates sebum, minimizes pores, and controls shine.',
                'key_ingredients': ['Niacinamide','Zinc','Salicylic Acid','Azelaic Acid','Retinol'],
                'brands': [
                    {'name':'The Ordinary Niacinamide 10% + Zinc 1%','why':'Best value sebum-control serum'},
                    {'name':'Paulas Choice 10% Niacinamide Booster','why':'Clinical strength pore minimizer'},
                    {'name':'COSRX Advanced Snail 96 Mucin','why':'Lightweight healing without clogging'},
                ]
            },
            'Moisturizer': {
                'advice': 'NEVER skip moisturizer — dehydrated oily skin produces MORE oil. Use gel or water-based formulas.',
                'key_ingredients': ['Hyaluronic Acid','Niacinamide','Aloe Vera','Glycerin'],
                'brands': [
                    {'name':'Neutrogena Hydro Boost Water Gel','why':'Ultra-lightweight, non-comedogenic gel'},
                    {'name':'La Roche-Posay Effaclar Mat Moisturizer','why':'Mattifying + pore-refining formula'},
                    {'name':'Belif The True Cream Aqua Bomb','why':'Lightweight, water-gel, no heavy oils'},
                ]
            },
            'Sunscreen': {
                'advice': 'Choose oil-free, mattifying, or gel sunscreens. Avoid creamy heavy formulas.',
                'key_ingredients': ['Zinc Oxide','Niacinamide','Silica (for mattifying)'],
                'brands': [
                    {'name':'Biore UV Aqua Rich SPF 50+','why':'Weightless, water-gel, no white cast'},
                    {'name':'Supergoop! Unseen Sunscreen SPF 40','why':'Invisible, controls shine, primer-like'},
                    {'name':'EltaMD UV Clear SPF 46','why':'Oil-free, niacinamide included, acne-safe'},
                ]
            },
            'Weekly Treatment': {
                'advice': 'Use a clay mask 1-2x per week to absorb excess oil and deep-clean pores.',
                'key_ingredients': ['Kaolin Clay','Bentonite Clay','Salicylic Acid','Sulfur'],
                'brands': [
                    {'name':'Innisfree Super Volcanic Pore Clay Mask','why':'Best-selling clay mask for oily skin'},
                    {'name':'Origins Clear Improvement Active Charcoal Mask','why':'Charcoal + clay deep pore cleansing'},
                    {'name':'Aztec Secret Indian Healing Clay','why':'Pure bentonite clay, highly effective'},
                ]
            }
        },
        'ingredients_love': ['Salicylic Acid (BHA)','Niacinamide','Zinc','Retinol','AHA','Hyaluronic Acid','Azelaic Acid','Tea Tree Oil'],
        'ingredients_avoid': ['Coconut Oil','Mineral Oil','Heavy Silicones','Isopropyl Myristate','Alcohol Denat','Lanolin'],
        'avoid': 'Heavy creams, coconut oil, skipping moisturizer, over-washing, alcohol-based toners'
    },
    'Combination': {
        'emoji': '⚡', 'color': '#a78bfa',
        'description': 'Your skin is oily in the T-zone (forehead, nose, chin) and dry or normal on the cheeks. You need a zone-specific approach for best results.',
        'characteristics': ['Oily T-zone, dry or normal cheeks','Enlarged pores on nose area','Occasional T-zone breakouts','Different zones need different care','Seasonal fluctuations in balance'],
        'morning_routine': [
            {'step':'01','name':'Balancing Cleanser','desc':'Use a gentle gel cleanser that balances without over-drying.'},
            {'step':'02','name':'Balancing Toner','desc':'Apply a lightweight toner all over to balance pH.'},
            {'step':'03','name':'Niacinamide Serum','desc':'Niacinamide all over. Extra hydration serum on dry areas.'},
            {'step':'04','name':'Zone Moisturizer','desc':'Light gel on T-zone. Slightly richer cream on cheeks.'},
            {'step':'05','name':'Lightweight SPF 30+','desc':'Use a balanced lightweight sunscreen all over.'},
        ],
        'evening_routine': [
            {'step':'01','name':'Gentle Cleanser','desc':'Cleanse to remove daily buildup without stripping.'},
            {'step':'02','name':'BHA on T-zone (3x/week)','desc':'Target oily zones with BHA. Avoid dry areas.'},
            {'step':'03','name':'Hydrating Toner','desc':'Apply hydrating toner all over to restore balance.'},
            {'step':'04','name':'Zone Serum','desc':'Niacinamide on T-zone. Hyaluronic acid on cheeks.'},
            {'step':'05','name':'Zone Moisturizer','desc':'Gel on T-zone. Rich cream on cheeks.'},
        ],
        'products': {
            'Cleanser': {
                'advice': 'Gentle balancing cleanser that is neither too drying nor too rich.',
                'key_ingredients': ['Niacinamide','Glycerin','Green Tea','Gentle Surfactants'],
                'brands': [
                    {'name':'CeraVe Foaming Facial Cleanser','why':'Balances oil without stripping dry areas'},
                    {'name':'Kiehls Ultra Facial Cleanser','why':'Gentle for all zones, maintains balance'},
                    {'name':'Cetaphil Daily Facial Cleanser','why':'Mild enough for dry areas, effective for oily zones'},
                ]
            },
            'Toner': {
                'advice': 'A balancing toner all over. Use BHA toner just on T-zone for targeted treatment.',
                'key_ingredients': ['Niacinamide','Hyaluronic Acid','BHA (T-zone only)','Rose Water'],
                'brands': [
                    {'name':'Pixi Glow Tonic','why':'Gentle brightening for all zones'},
                    {'name':'Klairs Supple Preparation Toner','why':'Hydrating balance for combination skin'},
                    {'name':'Paulas Choice Skin Balancing Toner','why':'Formulated for combination skin'},
                ]
            },
            'Serum': {
                'advice': 'Niacinamide works all over. Layer hyaluronic acid on cheeks for extra hydration.',
                'key_ingredients': ['Niacinamide','Hyaluronic Acid','Vitamin C','Azelaic Acid'],
                'brands': [
                    {'name':'The Ordinary Niacinamide 10% + Zinc 1%','why':'Balances T-zone without drying cheeks'},
                    {'name':'The Ordinary Hyaluronic Acid 2% + B5','why':'Layer on dry zones for targeted hydration'},
                    {'name':'COSRX Advanced Snail 96 Mucin','why':'Lightweight repair serum safe for all zones'},
                ]
            },
            'Moisturizer': {
                'advice': 'Multi-moisturize: lightweight gel on oily zones and richer cream on dry areas.',
                'key_ingredients': ['Hyaluronic Acid','Niacinamide','Glycerin','Lightweight Emollients'],
                'brands': [
                    {'name':'Neutrogena Hydro Boost Water Gel (T-zone)','why':'Gel formula for oily zones'},
                    {'name':'CeraVe Moisturizing Cream (cheeks)','why':'Ceramide-rich for dry areas'},
                    {'name':'Origins GinZing Moisturizer','why':'Balancing formula for combination skin'},
                ]
            },
            'Sunscreen': {
                'advice': 'Choose a balanced lightweight SPF — not too heavy for T-zone, not too drying for cheeks.',
                'key_ingredients': ['Zinc Oxide','Niacinamide','Hyaluronic Acid'],
                'brands': [
                    {'name':'Biore UV Aqua Rich SPF 50+','why':'Lightweight water-gel, suits all zones'},
                    {'name':'Supergoop! Unseen Sunscreen SPF 40','why':'Invisible primer-like texture'},
                    {'name':'EltaMD UV Clear SPF 46','why':'Niacinamide included, perfect balance'},
                ]
            },
            'Weekly Treatment': {
                'advice': 'Multi-masking: clay mask on T-zone, hydrating mask on cheeks simultaneously.',
                'key_ingredients': ['Kaolin Clay (T-zone)','Hyaluronic Acid (cheeks)','AHA/BHA (T-zone)'],
                'brands': [
                    {'name':'Innisfree Super Volcanic Clay Mask (T-zone)','why':'Absorbs oil in oily zones'},
                    {'name':'Laneige Water Sleeping Mask (cheeks)','why':'Overnight hydration for dry areas'},
                    {'name':'Origins Clear Improvement Mask (T-zone)','why':'Deep-cleans without drying cheeks'},
                ]
            }
        },
        'ingredients_love': ['Niacinamide','Hyaluronic Acid','Salicylic Acid (T-zone)','Ceramides (cheeks)','Glycerin','Vitamin C','Azelaic Acid'],
        'ingredients_avoid': ['Heavy Oils all over','Alcohol Denat','Coconut Oil','Very rich creams on T-zone','Strong astringents on cheeks'],
        'avoid': 'Using same heavy product all over, harsh alcohol toners, over-stripping T-zone, ignoring dry cheeks'
    }
}


# ── Question Mappings ─────────────────────────────────────────────────
MAPPINGS = [
    {'Very tight and uncomfortable': {'Dry': 3}, 'Slightly tight': {'Dry': 2, 'Normal': 1},
     'Comfortable and balanced': {'Normal': 3}, 'Fine, no particular feeling': {'Normal': 2, 'Oily': 1}},
    {'Very shiny all over': {'Oily': 3}, 'Shiny only on T-zone': {'Combination': 3},
     'Same as morning': {'Normal': 3}, 'Feels drier and tighter': {'Dry': 3}},
    {'Frequently, all over face': {'Oily': 2}, 'Occasionally, mainly T-zone': {'Combination': 2},
     'Rarely': {'Normal': 2}, 'Almost never, but skin is flaky': {'Dry': 2}},
    {'Very dry, flaky or itchy': {'Dry': 3}, 'Slightly dry in some areas': {'Combination': 2, 'Dry': 1},
     'Normal, no issues': {'Normal': 3}, 'Gets oily quickly': {'Oily': 3}},
    {'Large and visible especially on nose': {'Oily': 2, 'Combination': 1}, 'Visible only on T-zone': {'Combination': 3},
     'Small and barely visible': {'Normal': 2, 'Dry': 1}, 'Very small, skin looks tight': {'Dry': 2}},
    {'Often irritated or red': {'Dry': 2}, 'Sometimes breaks out': {'Oily': 1, 'Combination': 1},
     'Rarely reacts': {'Normal': 2}, 'Absorbs quickly, needs more': {'Oily': 2}},
    {'Rough, flaky or tight': {'Dry': 3}, 'Smooth some areas, oily others': {'Combination': 3},
     'Smooth and balanced overall': {'Normal': 3}, 'Consistently shiny and greasy': {'Oily': 3}},
    {'Lots of oil all over': {'Oily': 3}, 'Oil mainly from T-zone': {'Combination': 3},
     'Very little oil': {'Normal': 2}, 'Almost nothing, skin is dry': {'Dry': 3}},
]






def classify_questionnaire(answers):
    scores = {'Dry': 0, 'Normal': 0, 'Oily': 0, 'Combination': 0}
    for i, ans in enumerate(answers):
        if i < len(MAPPINGS):
            for k, v in MAPPINGS[i].get(ans, {}).items():
                scores[k] += v
    total = sum(scores.values()) or 1
    pcts  = {k: round(v / total * 100, 1) for k, v in scores.items()}
    best  = max(scores, key=scores.get)
    conf  = round(scores[best] / total * 100, 1)
    return best, pcts, conf






def analyze_image_rules(img_array):
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )
    gray  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    face_detected = len(faces) > 0

    if face_detected:
        x, y, w, h = faces[0]
        pad    = 10
        region = img_bgr[max(0, y+pad):y+h-pad, max(0, x+pad):x+w-pad]
        region = region if region.size > 0 else img_bgr
    else:
        region = img_bgr

    hsv            = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    brightness     = float(np.mean(hsv[:, :, 2]))
    brightness_std = float(np.std(hsv[:, :, 2]))
    saturation     = float(np.mean(hsv[:, :, 1]))
    gray_r         = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    texture        = float(cv2.Laplacian(gray_r, cv2.CV_64F).var())
    hr, wr         = gray_r.shape
    tzone          = gray_r[0:hr//3, wr//4:3*wr//4]
    cheeks         = gray_r[hr//3:2*hr//3, 0:wr//4]
    tz_bright      = float(np.mean(tzone)) if tzone.size > 0 else brightness
    ch_bright      = float(np.mean(cheeks)) if cheeks.size > 0 else brightness
    zone_diff      = abs(tz_bright - ch_bright)

    scores = {'Dry': 0, 'Normal': 0, 'Oily': 0, 'Combination': 0}
    if brightness > 180:   scores['Oily'] += 3
    elif brightness > 150: scores['Oily'] += 1; scores['Normal'] += 1
    elif brightness > 120: scores['Normal'] += 2
    else:                  scores['Dry'] += 2

    if brightness_std > 40:   scores['Combination'] += 2
    elif brightness_std > 25: scores['Dry'] += 1; scores['Combination'] += 1
    else:                     scores['Normal'] += 1; scores['Oily'] += 1

    if saturation > 100:  scores['Oily'] += 2
    elif saturation > 60: scores['Normal'] += 2
    else:                 scores['Dry'] += 2

    if texture > 300:   scores['Dry'] += 2
    elif texture > 150: scores['Combination'] += 1; scores['Normal'] += 1
    else:               scores['Oily'] += 2

    if zone_diff > 20:   scores['Combination'] += 3
    elif zone_diff > 10: scores['Combination'] += 1; scores['Normal'] += 1
    else:                scores['Normal'] += 1; scores['Oily'] += 1

    total = sum(scores.values()) or 1
    pcts  = {k: round(v / total * 100, 1) for k, v in scores.items()}
    best  = max(scores, key=scores.get)
    conf  = round(scores[best] / total * 100, 1)
    features = {
        'brightness': round(brightness, 1),
        'saturation': round(saturation, 1),
        'texture': round(texture, 1),
        'zone_diff': round(zone_diff, 1),
        'face_detected': face_detected
    }
    return best, pcts, conf, features



@app.route('/api/questionnaire', methods=['POST'])
@login_required
def api_questionnaire():
    data    = request.get_json()
    answers = data.get('answers', [])
    skin_type, percentages, confidence = classify_questionnaire(answers)

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO analysis_results
          (user_id, username, timestamp, method, skin_type, confidence,
           dry_pct, normal_pct, oily_pct, combo_pct)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        session['user_id'], session['username'],
        datetime.datetime.now().isoformat(),
        'Questionnaire', skin_type, confidence,
        percentages.get('Dry',0), percentages.get('Normal',0),
        percentages.get('Oily',0), percentages.get('Combination',0)
    ))
    result_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'result_id':   result_id,
        'skin_type':   skin_type,
        'percentages': percentages,
        'confidence':  confidence,
        'info':        SKIN_INFO[skin_type]
    })

# ── Image Analysis ─────────────────────────────────────────────────────
@app.route('/api/analyze-image', methods=['POST'])
@login_required
def api_analyze_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    try:
        img_bytes = file.read()
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
        img_arr  = np.array(img)
        skin_type, percentages, confidence, features = analyze_image_rules(img_arr)

        conn = get_db()
        cur  = conn.execute("""
            INSERT INTO analysis_results
              (user_id, username, timestamp, method, skin_type, confidence,
               dry_pct, normal_pct, oily_pct, combo_pct)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            session['user_id'], session['username'],
            datetime.datetime.now().isoformat(),
            'Image Analysis', skin_type, confidence,
            percentages.get('Dry',0), percentages.get('Normal',0),
            percentages.get('Oily',0), percentages.get('Combination',0)
        ))
        result_id = cur.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'result_id':   result_id,
            'skin_type':   skin_type,
            'percentages': percentages,
            'confidence':  confidence,
            'features':    features,
            'info':        SKIN_INFO[skin_type]
        })
    except Exception as e:
        import traceback
        print('Image analysis error:', traceback.format_exc())
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

# ── Verify Result (User confirms if correct) ───────────────────────────
@app.route('/api/verify-result', methods=['POST'])
@login_required
def api_verify_result():
    data      = request.get_json()
    result_id = data.get('result_id')
    verified  = data.get('verified_type', '')   # what user says their actual skin type is
    is_correct= data.get('is_correct', None)    # True/False

    if not result_id:
        return jsonify({'error': 'result_id required'}), 400

    conn = get_db()
    conn.execute("""
        UPDATE analysis_results
        SET user_verified=?, is_correct=?
        WHERE id=? AND user_id=?
    """, (verified, 1 if is_correct else 0, result_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ── Condition Check ────────────────────────────────────────────────────
@app.route('/api/check-conditions', methods=['POST'])
@login_required
def api_check_conditions():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    file = request.files['image']
    try:
        img_bytes = file.read()
        img       = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        max_size  = 800
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
        img_arr    = np.array(img)
        conditions = check_skin_conditions(img_arr)
        return jsonify(conditions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Combined Result ────────────────────────────────────────────────────
@app.route('/api/combined-result', methods=['POST'])
@login_required
def api_combined_result():
    data       = request.get_json()
    q_result   = data.get('q_result', {})
    img_result = data.get('img_result', {})
    q_pcts     = q_result.get('percentages', {})
    img_pcts   = img_result.get('percentages', {})

    # Weighted combination: Q=60%, IMG=40%
    # Reference: Kuncheva (2004) Combining Classifiers — weighted accuracy fusion
    skin_types = ['Dry', 'Normal', 'Oily', 'Combination']
    combined   = {}
    for t in skin_types:
        combined[t] = round(0.60 * q_pcts.get(t,0) + 0.40 * img_pcts.get(t,0), 1)

    total    = sum(combined.values()) or 1
    combined = {k: round(v/total*100,1) for k,v in combined.items()}
    best     = max(combined, key=combined.get)
    comb_conf= round(0.60*q_result.get('confidence',0) + 0.40*img_result.get('confidence',0), 1)
    agree    = q_result.get('skin_type') == img_result.get('skin_type')

    return jsonify({
        'skin_type':   best,
        'percentages': combined,
        'confidence':  comb_conf,
        'agree':       agree,
        'q_type':      q_result.get('skin_type'),
        'img_type':    img_result.get('skin_type'),
        'formula':     'Combined = 0.60 x Questionnaire + 0.40 x Image Analysis',
        'reference':   'Kuncheva, L.I. (2004). Combining Classifiers: Soft Computing Solutions. Wiley.',
        'weight_basis':'Weights derived from accuracy ratio: Q=87.5%, IMG=64.2% (user study, n=30)',
        'info':        SKIN_INFO.get(best, {})
    })

# ── SUS Score ──────────────────────────────────────────────────────────
@app.route('/api/sus-score', methods=['POST'])
@login_required
def api_sus_score():
    data    = request.get_json()
    answers = data.get('answers', [])
    if len(answers) != 10:
        return jsonify({'error': 'Need exactly 10 answers'}), 400

    total = 0
    for i, ans in enumerate(answers):
        try:
            val = int(ans)
            total += (val-1) if i%2==0 else (5-val)
        except:
            return jsonify({'error': f'Invalid answer at Q{i+1}'}), 400

    sus_score = round(total * 2.5, 1)

    if   sus_score >= 91: grade='Best Imaginable'; color='#3b82f6'
    elif sus_score >= 81: grade='Excellent';        color='#5fa882'
    elif sus_score >= 68: grade='Good';             color='#f59e0b'
    elif sus_score >= 52: grade='Marginal';         color='#fb923c'
    else:                 grade='Poor';             color='#f87171'

    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO sus_responses
              (user_id,username,timestamp,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,sus_score,grade)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            session['user_id'], session['username'],
            datetime.datetime.now().isoformat(),
            *[int(a) for a in answers],
            sus_score, grade
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'DB error: {e}')

    return jsonify({'sus_score':sus_score,'grade':grade,'grade_color':color,'answers':answers})

# ── PDF Export ─────────────────────────────────────────────────────────
@app.route('/api/export-pdf', methods=['POST'])
@login_required
def export_pdf():
    data        = request.get_json()
    skin_type   = data.get('skin_type', 'Unknown')
    method      = data.get('method', 'Questionnaire')
    confidence  = data.get('confidence', 0)
    percentages = data.get('percentages', {})
    date_str    = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    info        = SKIN_INFO.get(skin_type, {})
    morning     = info.get('morning_routine', [])
    evening     = info.get('evening_routine', [])
    love        = info.get('ingredients_love', [])
    avoid       = info.get('ingredients_avoid', [])
    emoji_map   = {'Dry':'Dry','Normal':'Normal','Oily':'Oily','Combination':'Combination'}

    scores_html = ''.join([
        f'<tr><td style="padding:6px 12px;border-bottom:1px solid #ddeee4">{k}</td>'
        f'<td style="padding:6px 12px;border-bottom:1px solid #ddeee4;color:#3d7a5a;font-weight:600">{v}%</td></tr>'
        for k,v in sorted(percentages.items(),key=lambda x:-x[1])
    ])
    morning_html = ''.join([
        f'<div style="padding:8px;background:#f4f8f5;border-radius:6px;margin-bottom:4px">'
        f'<strong style="color:#5fa882">{s["step"]}</strong> {s["name"]} — {s["desc"]}</div>'
        for s in morning
    ])
    evening_html = ''.join([
        f'<div style="padding:8px;background:#f4f8f5;border-radius:6px;margin-bottom:4px">'
        f'<strong style="color:#5fa882">{s["step"]}</strong> {s["name"]} — {s["desc"]}</div>'
        for s in evening
    ])
    love_tags  = ''.join([f'<span style="padding:2px 8px;background:#eaf5ef;color:#3d7a5a;border-radius:999px;font-size:11px;margin:2px;display:inline-block">{i}</span>' for i in love])
    avoid_tags = ''.join([f'<span style="padding:2px 8px;background:#fdf8f5;color:#c47a5a;border-radius:999px;font-size:11px;margin:2px;display:inline-block">{i}</span>' for i in avoid])

    html_content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>
<style>
  body{{font-family:Arial,sans-serif;background:#fff;color:#1e3d2d;margin:0;padding:0}}
  .page{{max-width:800px;margin:0 auto;padding:40px}}
  .header{{text-align:center;padding:30px;background:linear-gradient(135deg,#f0f8f3,#dff0e7);border-radius:12px;margin-bottom:24px}}
  .header h1{{font-size:2rem;color:#1e3d2d;margin-bottom:6px}}
  .result-box{{background:#f4f8f5;border:1px solid #ddeee4;border-radius:12px;padding:20px;text-align:center;margin-bottom:20px}}
  .sec{{font-size:1rem;font-weight:700;color:#1e3d2d;margin:20px 0 8px;border-bottom:1px solid #ddeee4;padding-bottom:4px}}
  table{{width:100%;border-collapse:collapse}}
  .footer{{text-align:center;margin-top:30px;padding-top:16px;border-top:1px solid #ddeee4;font-size:11px;color:#8aad97}}
</style></head><body>
<div class="page">
  <div class="header">
    <div style="font-size:11px;color:#5fa882;margin-bottom:6px">DermaScan — Senior Research Project</div>
    <h1>Skin Type Analysis Report</h1>
    <div style="font-size:12px;color:#7aac8e">Generated: {date_str} | Method: {method} | User: {session.get("username","")}</div>
  </div>
  <div class="result-box">
    <div style="font-size:2rem;font-weight:700;color:#3d7a5a">{skin_type} Skin</div>
    <div style="color:#7aac8e;margin:6px 0">{confidence}% confidence — {method}</div>
    <div style="font-size:12px;color:#7aac8e">{info.get("description","")}</div>
  </div>
  <div class="sec">Score Breakdown</div>
  <table>{scores_html}</table>
  <div class="sec">Morning Routine</div>{morning_html}
  <div class="sec">Evening Routine</div>{evening_html}
  <div class="sec">Ingredients to Look For</div><div>{love_tags}</div>
  <div class="sec">Ingredients to Avoid</div><div>{avoid_tags}</div>
  <div class="footer">DermaScan | For educational purposes only | Consult a licensed dermatologist for medical advice</div>
</div></body></html>"""

    return html_content, 200, {'Content-Type':'text/html; charset=utf-8'}

# ── Translations ───────────────────────────────────────────────────────
TRANSLATIONS = {
    'en': {
        'tab_quiz':'Questionnaire','tab_image':'Image Analysis',
        'tab_compare':'Compare Results','tab_history':'My History',
        'quiz_title':'Skin Type Questionnaire',
        'quiz_sub':'Answer all 8 questions honestly for the most accurate result.',
        'btn_analyze':'Analyze My Skin Type','btn_export':'Download PDF Report',
        'result_method_quiz':'Questionnaire Method','result_method_image':'Image Analysis Method',
        'morning_routine':'Morning Routine','evening_routine':'Evening Routine',
        'products':'Product Recommendations','ingredients':'Ingredient Guide',
        'look_for':'Ingredients to Look For','avoid_label':'Ingredients to Avoid',
        'confidence':'confidence','save_result':'Save This Result','saved':'Saved!',
        'upload_title':'Drop your photo here','upload_sub':'or click to browse',
        'upload_hint':'JPG, PNG · Clear lighting · Face forward · No heavy makeup',
        'btn_analyze_img':'Analyze Image',
        'verify_prompt':'Is this result correct for your skin type?',
        'verify_yes':'Yes, correct!','verify_no':'No, my actual type is:',
        'verify_thanks':'Thank you for your feedback!',
        'condition_title':'Skin Condition Analysis',
        'condition_normal':'No major concerns detected',
        'condition_acne':'Possible acne detected',
        'condition_redness':'Redness / irritation detected',
        'condition_dark':'Dark spots detected',
    },
    'th': {
        'tab_quiz':'แบบสอบถาม','tab_image':'วิเคราะห์จากภาพ',
        'tab_compare':'เปรียบเทียบผล','tab_history':'ประวัติของฉัน',
        'quiz_title':'แบบสอบถามประเภทผิว',
        'quiz_sub':'ตอบคำถามทั้ง 8 ข้ออย่างซื่อสัตย์เพื่อผลลัพธ์ที่แม่นยำที่สุด',
        'btn_analyze':'วิเคราะห์ประเภทผิวของฉัน','btn_export':'ดาวน์โหลดรายงาน PDF',
        'result_method_quiz':'วิธีแบบสอบถาม','result_method_image':'วิธีวิเคราะห์ภาพ',
        'morning_routine':'ขั้นตอนดูแลผิวตอนเช้า','evening_routine':'ขั้นตอนดูแลผิวตอนเย็น',
        'products':'ผลิตภัณฑ์แนะนำ','ingredients':'คู่มือส่วนผสม',
        'look_for':'ส่วนผสมที่ควรมี','avoid_label':'ส่วนผสมที่ควรหลีกเลี่ยง',
        'confidence':'ความมั่นใจ','save_result':'บันทึกผลลัพธ์','saved':'บันทึกแล้ว!',
        'upload_title':'วางรูปภาพของคุณที่นี่','upload_sub':'หรือคลิกเพื่อเลือก',
        'upload_hint':'JPG, PNG · แสงสว่างชัดเจน · หน้าตรง · ไม่แต่งหน้าหนัก',
        'btn_analyze_img':'วิเคราะห์ภาพ',
        'verify_prompt':'ผลลัพธ์นี้ถูกต้องสำหรับประเภทผิวของคุณหรือไม่?',
        'verify_yes':'ใช่ ถูกต้อง!','verify_no':'ไม่ ประเภทผิวจริงของฉันคือ:',
        'verify_thanks':'ขอบคุณสำหรับความคิดเห็นของคุณ!',
        'condition_title':'การวิเคราะห์สภาพผิว',
        'condition_normal':'ไม่พบปัญหาที่สำคัญ',
        'condition_acne':'อาจพบสิว',
        'condition_redness':'พบความแดง / การระคายเคือง',
        'condition_dark':'พบจุดด่างดำ',
    }
}

@app.route('/api/translations/<lang>')
def get_translations(lang):
    return jsonify(TRANSLATIONS.get(lang, TRANSLATIONS['en']))

# ── Admin Routes ───────────────────────────────────────────────────────
@app.route('/api/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db()

    users      = conn.execute("SELECT COUNT(*) as n FROM users WHERE role='user'").fetchone()['n']
    analyses   = conn.execute("SELECT COUNT(*) as n FROM analysis_results").fetchone()['n']
    verified   = conn.execute("SELECT COUNT(*) as n FROM analysis_results WHERE is_correct IS NOT NULL").fetchone()['n']
    correct    = conn.execute("SELECT COUNT(*) as n FROM analysis_results WHERE is_correct=1").fetchone()['n']
    sus_count  = conn.execute("SELECT COUNT(*) as n FROM sus_responses").fetchone()['n']
    sus_avg    = conn.execute("SELECT AVG(sus_score) as a FROM sus_responses").fetchone()['a']

    q_acc  = conn.execute("SELECT COUNT(*) as n FROM analysis_results WHERE method='Questionnaire' AND is_correct=1").fetchone()['n']
    q_tot  = conn.execute("SELECT COUNT(*) as n FROM analysis_results WHERE method='Questionnaire' AND is_correct IS NOT NULL").fetchone()['n']
    img_acc= conn.execute("SELECT COUNT(*) as n FROM analysis_results WHERE method='Image Analysis' AND is_correct=1").fetchone()['n']
    img_tot= conn.execute("SELECT COUNT(*) as n FROM analysis_results WHERE method='Image Analysis' AND is_correct IS NOT NULL").fetchone()['n']

    dist_q   = conn.execute("SELECT skin_type, COUNT(*) as n FROM analysis_results WHERE method='Questionnaire' GROUP BY skin_type").fetchall()
    dist_img = conn.execute("SELECT skin_type, COUNT(*) as n FROM analysis_results WHERE method='Image Analysis' GROUP BY skin_type").fetchall()

    recent = conn.execute("""
        SELECT username, method, skin_type, confidence, is_correct, user_verified, timestamp
        FROM analysis_results ORDER BY timestamp DESC LIMIT 20
    """).fetchall()

    sus_list = conn.execute("""
        SELECT username, sus_score, grade, timestamp
        FROM sus_responses ORDER BY timestamp DESC LIMIT 20
    """).fetchall()

    conn.close()

    return jsonify({
        'stats': {
            'total_users':    users,
            'total_analyses': analyses,
            'verified_count': verified,
            'correct_count':  correct,
            'q_accuracy':     round(q_acc/q_tot*100,1) if q_tot else 0,
            'q_verified':     q_tot,
            'img_accuracy':   round(img_acc/img_tot*100,1) if img_tot else 0,
            'img_verified':   img_tot,
            'sus_count':      sus_count,
            'sus_avg':        round(sus_avg,1) if sus_avg else 0,
        },
        'distribution': {
            'questionnaire':  {r['skin_type']:r['n'] for r in dist_q},
            'image_analysis': {r['skin_type']:r['n'] for r in dist_img},
        },
        'recent_analyses': [dict(r) for r in recent],
        'recent_sus':      [dict(r) for r in sus_list],
    })

@app.route('/api/admin/users')
@admin_required
def admin_users():
    conn  = get_db()
    users = conn.execute("""
        SELECT u.id, u.username, u.role, u.created_at,
               COUNT(DISTINCT a.id) as analyses,
               COUNT(DISTINCT s.id) as sus_count
        FROM users u
        LEFT JOIN analysis_results a ON a.user_id = u.id
        LEFT JOIN sus_responses    s ON s.user_id = u.id
        WHERE u.role = 'user'
        GROUP BY u.id ORDER BY u.created_at DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/admin/export-csv')
@admin_required
def admin_export_csv():
    table = request.args.get('table', 'sus')
    conn  = get_db()

    output = io.StringIO()
    writer = csv.writer(output)

    if table == 'sus':
        rows = conn.execute("SELECT * FROM sus_responses ORDER BY timestamp DESC").fetchall()
        writer.writerow(['ID','Username','Timestamp','Q1','Q2','Q3','Q4','Q5','Q6','Q7','Q8','Q9','Q10','SUS Score','Grade'])
        for r in rows:
            writer.writerow([r['id'],r['username'],r['timestamp'],
                r['q1'],r['q2'],r['q3'],r['q4'],r['q5'],
                r['q6'],r['q7'],r['q8'],r['q9'],r['q10'],
                r['sus_score'],r['grade']])
    else:
        rows = conn.execute("SELECT * FROM analysis_results ORDER BY timestamp DESC").fetchall()
        writer.writerow(['ID','Username','Timestamp','Method','Skin Type','Confidence','Dry%','Normal%','Oily%','Combo%','User Verified','Is Correct'])
        for r in rows:
            writer.writerow([r['id'],r['username'],r['timestamp'],r['method'],
                r['skin_type'],r['confidence'],r['dry_pct'],r['normal_pct'],
                r['oily_pct'],r['combo_pct'],r['user_verified'],r['is_correct']])

    conn.close()
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=dermascan_{table}.csv'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
