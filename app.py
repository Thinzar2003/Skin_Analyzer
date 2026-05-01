from flask import Flask, render_template, request, jsonify
import numpy as np
import cv2
import base64
import os
from PIL import Image
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# ── Comprehensive Skincare Database ──────────────────────────────────
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
                    {'name':'Kiehl's Ultra Facial Overnight Hydrating Masque','why':'Deep overnight moisture replenishment'},
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
                    {'name':'Kiehl's Ultra Facial Cleanser','why':'Balanced formula for everyday use'},
                    {'name':'COSRX Low pH Good Morning Gel Cleanser','why':'Maintains skin pH, gentle daily use'},
                ]
            },
            'Toner': {
                'advice': 'Light balancing toners or vitamin-rich essences maintain your natural balance.',
                'key_ingredients': ['Niacinamide','Vitamin C','Hyaluronic Acid','Green Tea'],
                'brands': [
                    {'name':'Pixi Glow Tonic','why':'Gentle AHA for radiance, classic formula'},
                    {'name':'Paula's Choice Skin Balancing Toner','why':'Oil control + hydration balance'},
                    {'name':'Some By Mi AHA BHA PHA 30 Days Miracle Toner','why':'Multi-acid gentle exfoliating toner'},
                ]
            },
            'Serum': {
                'advice': 'Vitamin C in the morning for protection. Retinol at night for anti-aging.',
                'key_ingredients': ['Vitamin C','Retinol','Niacinamide','Hyaluronic Acid','Peptides'],
                'brands': [
                    {'name':'SkinCeuticals C E Ferulic','why':'Gold standard Vitamin C serum'},
                    {'name':'The Ordinary Niacinamide 10% + Zinc 1%','why':'Pore-minimizing, affordable'},
                    {'name':'Paula's Choice C15 Super Booster','why':'Stable Vitamin C, anti-aging'},
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
                    {'name':'Paula's Choice Skin Perfecting 2% BHA','why':'Best-in-class chemical exfoliant'},
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
                    {'name':'Paula's Choice Skin Perfecting 2% BHA Liquid','why':'Most researched BHA exfoliant available'},
                    {'name':'COSRX BHA Blackhead Power Liquid','why':'Gentle BHA, minimizes pores effectively'},
                    {'name':'Some By Mi AHA BHA PHA 30 Days Miracle Toner','why':'Multi-acid formula for oily/acne skin'},
                ]
            },
            'Serum': {
                'advice': 'Niacinamide regulates sebum, minimizes pores, and controls shine.',
                'key_ingredients': ['Niacinamide','Zinc','Salicylic Acid','Azelaic Acid','Retinol'],
                'brands': [
                    {'name':'The Ordinary Niacinamide 10% + Zinc 1%','why':'Best value sebum-control serum'},
                    {'name':'Paula's Choice 10% Niacinamide Booster','why':'Clinical strength pore minimizer'},
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
                    {'name':'Kiehl's Ultra Facial Cleanser','why':'Gentle for all zones, maintains balance'},
                    {'name':'Cetaphil Daily Facial Cleanser','why':'Mild enough for dry areas, effective for oily zones'},
                ]
            },
            'Toner': {
                'advice': 'A balancing toner all over. Use BHA toner just on T-zone for targeted treatment.',
                'key_ingredients': ['Niacinamide','Hyaluronic Acid','BHA (T-zone only)','Rose Water'],
                'brands': [
                    {'name':'Pixi Glow Tonic','why':'Gentle brightening for all zones'},
                    {'name':'Klairs Supple Preparation Toner','why':'Hydrating balance for combination skin'},
                    {'name':'Paula's Choice Skin Balancing Toner','why':'Formulated for combination skin'},
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


# ── Routes ────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/questionnaire', methods=['POST'])
def api_questionnaire():
    data    = request.get_json()
    answers = data.get('answers', [])
    skin_type, percentages, confidence = classify_questionnaire(answers)
    return jsonify({
        'skin_type': skin_type,
        'percentages': percentages,
        'confidence': confidence,
        'info': SKIN_INFO[skin_type]
    })


@app.route('/api/analyze-image', methods=['POST'])
def api_analyze_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    try:
        img     = Image.open(file.stream).convert('RGB')
        img_arr = np.array(img)
        skin_type, percentages, confidence, features = analyze_image_rules(img_arr)
        return jsonify({
            'skin_type': skin_type,
            'percentages': percentages,
            'confidence': confidence,
            'features': features,
            'info': SKIN_INFO[skin_type]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
