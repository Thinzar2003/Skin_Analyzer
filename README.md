# DermaScan — Skin Type Recognition System
### Senior Research Project

A professional dual-method skin type analyzer combining:
- **Questionnaire Method** — 8 dermatologist-validated questions
- **Image Analysis** — Rule-based computer vision
- **Comparison Tab** — Side-by-side result comparison

## Skin Types Detected
- 💧 Dry
- ✨ Normal  
- 💫 Oily
- ⚡ Combination

## Project Structure
```
skin_analyzer/
├── app.py                  ← Flask backend
├── requirements.txt        ← Python dependencies
├── templates/
│   └── index.html          ← Main webpage
└── static/
    ├── css/style.css        ← Styling
    └── js/main.js           ← Frontend logic
```

## How to Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python app.py

# 3. Open browser at
http://localhost:5000
```

## How to Deploy on Render (Free)

1. Push this folder to GitHub
2. Go to render.com → New Web Service
3. Connect your GitHub repo
4. Set Start Command: `python app.py`
5. Deploy — get a free public URL

## How to Deploy on Railway (Free)

1. Push to GitHub
2. Go to railway.app → New Project
3. Deploy from GitHub repo
4. Automatic deployment

## Technologies Used
- **Backend**: Python, Flask
- **Computer Vision**: OpenCV
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Fonts**: Playfair Display, DM Sans
