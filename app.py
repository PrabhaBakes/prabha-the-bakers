from flask import Flask, jsonify, request, redirect, url_for, session, send_from_directory
import os
import re
import html
import json
try:
    import razorpay
except ImportError:
    razorpay = None

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-in-production")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
MEDIA_FILE = os.path.join(os.path.dirname(__file__), "media.json")
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "site_settings.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_IMAGE = {"png", "jpg", "jpeg", "webp", "gif"}
ALLOWED_VIDEO = {"mp4", "webm", "mov"}

def load_media():
    try:
        with open(MEDIA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_media(items):
    with open(MEDIA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def ext_ok(filename, allowed):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed

def admin_ok():
    return session.get("admin_logged_in") is True


# Contact + Razorpay configuration.
CONTACT_PHONE = "8869946488"
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "YOUR_RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "YOUR_RAZORPAY_KEY_SECRET")
razorpay_client = (
    razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    if razorpay and not RAZORPAY_KEY_ID.startswith("YOUR_") and not RAZORPAY_KEY_SECRET.startswith("YOUR_")
    else None
)


DEFAULT_SETTINGS = {
    "brand_name": "Prabha The Bakers",
    "tagline": "Freshly Baked, Always Loved",
    "phone": "8869946488",
    "hero_eyebrow": "Welcome to",
    "hero_title": "Prabha The Bakers",
    "hero_points": ["Freshly Baked", "Premium Quality", "Made with Love"],
    "hero_description": "From delicious cakes to mouth-watering pastries, cookies, breads and more — we bring happiness in every bite.",
    "hero_image": "https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=1200&q=90",
    "background_image": "https://images.unsplash.com/photo-1517433670267-08bbd4be890f?auto=format&fit=crop&w=2200&q=90",
    "story_image": "https://images.unsplash.com/photo-1556910103-1c02745aae4d?auto=format&fit=crop&w=1000&q=85",
    "story_eyebrow": "Our Story",
    "story_title": "Every celebration deserves something special.",
    "story_text": "At Prabha The Bakers, we believe every celebration deserves something special. What started as a small dream has grown into a place where love, creativity and the art of baking come together.",
    "gallery": [
        "https://images.unsplash.com/photo-1571115177098-24ec42ed204d?auto=format&fit=crop&w=500&q=80",
        "https://images.unsplash.com/photo-1621303837174-89787a7d4729?auto=format&fit=crop&w=500&q=80",
        "https://images.unsplash.com/photo-1558301211-0d8c8d6a3b0f?auto=format&fit=crop&w=500&q=80",
        "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=500&q=80"
    ],
    "video_image": "https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=1000&q=85",
    "video_title": "Cake<br>Making<br><em>Magic ♡</em>",
    "trust": ["Fresh & Natural Ingredients", "Hygienic Preparation", "On-Time Delivery", "100% Customer Satisfaction"],
    "footer_tagline": "Freshly Baked, Always Loved",
    "gold": "#f4c65d",
    "advanced_css": ""
}


def load_settings():
    data = {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data if isinstance(data, dict) else {})
    # Keep products separately editable and migrate defaults from PRODUCTS.
    default_products = [
        {"name":n,"price":p,"old_price":op,"rating":r,"reviews":rv,"tag":t,"image":u}
        for n,p,op,r,rv,t,u in PRODUCTS
    ]
    products = merged.get("products")
    if not isinstance(products, list) or len(products) != len(default_products):
        products = default_products
    merged["products"] = products
    return merged


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def esc(v):
    return html.escape(str(v or ""), quote=True)


def build_product_cards(products):
    cards=[]
    for p in products:
        name=esc(p.get("name","Product")); price=esc(p.get("price",0)); old=esc(p.get("old_price",0))
        rating=esc(p.get("rating","5.0")); reviews=esc(p.get("reviews","0")); tag=esc(p.get("tag","FRESH")); image=esc(p.get("image",""))
        cards.append(f'<article class="product-card" data-name="{name.lower()}"><div class="product-image"><img src="{image}" alt="{name}" loading="lazy"><span class="tag">{tag}</span></div><h3>{name}</h3><div class="price"><b>₹{price}</b> <del>₹{old}</del></div><div class="rating">★ {rating} <span>({reviews})</span></div><button class="add-cart" data-product="{name}" data-price="{price}">🛒 Add to Cart</button></article>')
    return "".join(cards)


def build_page(settings, media_html):
    page = PAGE
    page = page.replace('url("https://images.unsplash.com/photo-1517433670267-08bbd4be890f?auto=format&fit=crop&w=2200&q=90")', 'url("' + esc(settings.get("background_image")) + '")')
    hero_start = page.find('<section class="hero" id="home">')
    hero_end = page.find('</section>\n\n<section class="glass-panel">', hero_start)
    if hero_start >= 0 and hero_end >= 0:
        pts=settings.get("hero_points", ["Freshly Baked","Premium Quality","Made with Love"])
        pts_html = '<b>•</b>'.join(' <span>'+esc(x)+'</span> ' for x in pts)
        # Keep exactly two separators for the default, but support any count.
        pts_html = ' <b>•</b> '.join('<span>'+esc(x)+'</span>' for x in pts)
        hero = f'''<section class="hero" id="home">\n  <div class="hero-content">\n    <div class="eyebrow">{esc(settings.get("hero_eyebrow"))}</div>\n    <h1>{esc(settings.get("hero_title"))}</h1>\n    <div class="hero-points">{pts_html}</div>\n    <p>{esc(settings.get("hero_description"))}</p>\n    <div class="hero-buttons">\n      <a class="gold-btn" href="#products">▣ &nbsp; Explore Our Menu</a>\n      <a class="outline-btn" href="#videos">▶ &nbsp; Watch Our Video</a>\n    </div>\n  </div>\n  <div class="hero-cake">\n    <div class="cake-card">\n      <img src="{esc(settings.get("hero_image"))}" alt="{esc(settings.get("hero_title"))}">\n    </div>\n  </div>\n</section>'''
        page = page[:hero_start] + hero + page[hero_end:]

    # Replace product grid.
    pg_start=page.find('<div class="product-grid" id="productGrid">')
    pg_end=page.find('\n  </div>\n</section>\n\n<section class="lower-grid">', pg_start)
    if pg_start>=0 and pg_end>=0:
        page=page[:pg_start] + '<div class="product-grid" id="productGrid">' + build_product_cards(settings["products"]) + page[pg_end:]

    lower_start=page.find('<section class="lower-grid">')
    lower_end=page.find('</section>\n\n<section class="trust-bar"', lower_start)
    if lower_start>=0 and lower_end>=0:
        g=settings.get("gallery",[])
        while len(g)<4: g.append("")
        lower=f'''<section class="lower-grid">\n  <div class="story image-box">\n    <img src="{esc(settings.get("story_image"))}" alt="Baker preparing fresh dough">\n  </div>\n  <div class="story copy" id="about">\n    <div class="eyebrow small">{esc(settings.get("story_eyebrow"))}</div>\n    <h2>{esc(settings.get("story_title"))}</h2>\n    <p>{esc(settings.get("story_text"))}</p>\n    <a class="gold-btn small-btn" href="#contact">Learn More →</a>\n  </div>\n  <div class="gallery-box" id="gallery">\n    <div class="mini-head"><div><h3>Daily Gallery</h3><p>A glimpse of our fresh creations.</p></div><a href="#gallery">View All →</a></div>\n    <div class="gallery">\n      <img src="{esc(g[0])}" alt="Gallery image 1">\n      <img src="{esc(g[1])}" alt="Gallery image 2">\n      <img src="{esc(g[2])}" alt="Gallery image 3">\n      <img src="{esc(g[3])}" alt="Gallery image 4">\n    </div>\n  </div>\n  <div class="video-box" id="videos">\n    <div class="mini-head"><div><h3>Watch Our Videos</h3><p>Behind the scenes & social moments.</p></div><a href="#videos">View All →</a></div>\n    <div class="video-cover">\n      <img src="{esc(settings.get("video_image"))}" alt="Cake making">\n      <button class="play">▶</button>\n      <div class="video-title">{settings.get("video_title","")}</div>\n    </div>\n  </div>\n</section>'''
        page=page[:lower_start]+lower+page[lower_end:]

    # Trust bar and footer contact/tagline.
    trust_start=page.find('<section class="trust-bar" id="contact">')
    trust_end=page.find('</section>', trust_start)
    if trust_start>=0 and trust_end>=0:
        tr=settings.get("trust",[])
        icons=['♧','♢','▣','♡']
        trust='\n'.join(f'  <div>{icons[i%4]} <span>{esc(x)}</span></div>' for i,x in enumerate(tr))
        page=page[:trust_start]+'<section class="trust-bar" id="contact">\n'+trust+'\n'+page[trust_end:]
    page=page.replace('<b>Prabha The Bakers</b><span>Freshly Baked, Always Loved</span>', '<b>'+esc(settings.get("brand_name"))+ '</b><span>'+esc(settings.get("footer_tagline"))+ '</span>')
    phone=esc(settings.get("phone"))
    page=re.sub(r'tel:[^"\']+', 'tel:'+phone, page, count=1)
    page=re.sub(r'wa\.me/\d+', 'wa.me/91'+re.sub(r'\D','',str(settings.get("phone",""))), page, count=1)
    page=re.sub(r'📞 <a href="tel:[^"]+">[^<]+</a>', '📞 <a href="tel:'+phone+'">'+phone+'</a>', page, count=1)
    if settings.get('gold'):
        page=page.replace('--gold:#f4c65d', '--gold:'+esc(settings['gold']))
    if settings.get('advanced_css'):
        page=page.replace('</style></head>', esc(settings['advanced_css']).replace('&quot;','"') + '</style></head>')
    return page.replace("{{MEDIA_HTML}}", media_html)

# PRABHA THE BAKERS - PYTHON ONLY SOURCE
# Complete website UI is embedded in this single Python file.
# No HTML/CSS/JS/template/static source files are required.

PRODUCTS = [('Chocolate Cake', 599, 699, '4.8', '120', 'BEST SELLER', 'https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=900&q=85'), ('Red Velvet Cake', 649, 749, '4.9', '94', 'POPULAR', 'https://images.unsplash.com/photo-1586788680434-30d324b2d46f?auto=format&fit=crop&w=900&q=85'), ('Cupcakes (Box of 6)', 399, 499, '4.8', '73', 'FRESH', 'https://images.unsplash.com/photo-1587668178277-295251f900ce?auto=format&fit=crop&w=900&q=85'), ('Mix Pastry Box', 449, 549, '4.7', '110', 'FAVOURITE', 'https://images.unsplash.com/photo-1614707267537-2b9f7a9d1c43?auto=format&fit=crop&w=900&q=85'), ('Chocolate Chip Cookies', 199, 249, '4.8', '160', 'CRUNCHY', 'https://images.unsplash.com/photo-1499636136210-6f4ee915583e?auto=format&fit=crop&w=900&q=85'), ('Fresh Bread Loaf', 149, 189, '4.9', '81', 'DAILY FRESH', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=900&q=85')]

PAGE = '<!DOCTYPE html><html lang="en"><head><meta name="google-site-verification" content="H6__emlVfLp-sRDgdajHuP_9Lvrkl1qgzrYIxJo8u-c" /><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Prabha The Bakers — Freshly Baked, Always Loved</title><meta name="description" content="Prabha The Bakers — premium cakes, pastries, cookies, breads and desserts."><style>\n:root{\n  --gold:#f4c65d; --gold2:#ffe7a1; --cream:#fffaf0; --bg:#090705; --panel:rgba(18,14,10,.86);\n  --line:rgba(255,220,150,.16); --muted:#c7c0b4;\n}\n*{box-sizing:border-box} html{scroll-behavior:smooth}\nbody{margin:0;background:#080605;color:#fff;font-family:Inter,Arial,sans-serif;overflow-x:hidden}\nbody:before{content:"";position:fixed;inset:0;background:linear-gradient(90deg,rgba(0,0,0,.78),rgba(0,0,0,.34),rgba(0,0,0,.72)),url("https://images.unsplash.com/photo-1517433670267-08bbd4be890f?auto=format&fit=crop&w=2200&q=90") center/cover;filter:saturate(.9);z-index:-3}\nbody:after{content:"";position:fixed;inset:0;background:radial-gradient(circle at 70% 35%,rgba(255,174,52,.14),transparent 32%),rgba(0,0,0,.2);z-index:-2}\na{text-decoration:none;color:inherit}.navbar{height:78px;position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;padding:0 7%;background:rgba(5,4,3,.72);backdrop-filter:blur(15px);border-bottom:1px solid rgba(255,255,255,.08)}\n.brand{display:flex;align-items:center;gap:9px}.chef{font-size:31px;color:var(--gold);transform:rotate(-12deg)}.brand-script{font-family:"Cormorant Garamond",serif;font-size:35px;line-height:25px;color:var(--gold);font-style:italic}.brand-sub{font-size:12px;letter-spacing:4px;text-align:center}.brand small{display:block;font-size:7px;color:#ddd;text-align:center}\nnav{display:flex;gap:32px;font-size:13px;font-weight:600}nav a{padding:29px 0;color:#eee}nav a.active,nav a:hover{color:var(--gold);border-bottom:2px solid var(--gold)}\n.nav-actions{display:flex;align-items:center;gap:14px}.icon-btn,.cart-btn{background:none;border:0;color:#fff;font-size:25px;cursor:pointer}.cart-btn{font-size:18px;position:relative}.cart-btn span{position:absolute;right:-7px;top:-8px;background:#e34a3f;border-radius:50%;font-size:9px;padding:2px 5px}.order-btn,.gold-btn{background:linear-gradient(135deg,#ffe7a0,#f1bd4e);color:#171109;padding:12px 20px;border-radius:28px;font-weight:700;font-size:12px;display:inline-block;box-shadow:0 6px 24px rgba(244,198,93,.16)}\n.search-panel{display:none;position:fixed;right:7%;top:82px;z-index:25;background:#17110b;border:1px solid var(--line);padding:10px;border-radius:13px}.search-panel.show{display:block}.search-panel input{width:280px;background:#0b0907;color:#fff;border:1px solid #4d3c24;padding:12px;border-radius:9px;outline:none}\n.hero{min-height:390px;display:flex;align-items:center;padding:45px 12% 35px;position:relative}.hero-content{width:52%;z-index:2}.eyebrow{font-family:"Cormorant Garamond",serif;color:var(--gold);font-size:48px;font-style:italic;line-height:.9}.hero h1{font-family:"Playfair Display",serif;font-size:49px;margin:4px 0 8px;line-height:1.05}.hero-points{display:flex;gap:10px;align-items:center;font-size:15px}.hero-points b{color:var(--gold)}.hero p{font-size:14px;line-height:1.65;color:#eee;max-width:580px}.hero-buttons{display:flex;gap:18px;margin-top:20px}.outline-btn{border:1px solid #eee;padding:12px 20px;border-radius:28px;font-size:12px;font-weight:600}.hero-cake{width:48%;position:relative}.cake-card{width:min(540px,100%);margin-left:auto;border-radius:26px;overflow:hidden;box-shadow:0 25px 80px rgba(0,0,0,.7);transform:rotate(1deg)}.cake-card img{display:block;width:100%;height:330px;object-fit:cover}\n.glass-panel{margin:0 11%;padding:14px 28px 18px;background:linear-gradient(145deg,rgba(27,20,13,.88),rgba(10,8,6,.9));border:1px solid rgba(255,255,255,.07);border-radius:18px;box-shadow:0 20px 60px #0008;backdrop-filter:blur(10px)}.category-row{display:grid;grid-template-columns:repeat(6,1fr);border-bottom:1px solid var(--line)}.category{text-align:center;padding:10px 5px 16px;border-right:1px solid var(--line);transition:.2s}.category:last-child{border:0}.category:hover{background:rgba(244,198,93,.05)}.cat-icon{width:47px;height:47px;border:1px solid var(--gold);border-radius:50%;display:grid;place-items:center;margin:0 auto 7px;color:var(--gold);font-size:23px}.category strong{display:block;font-family:"Playfair Display",serif;font-size:14px}.category span{font-size:9px;color:#ddd}\n.section-head{display:flex;justify-content:space-between;align-items:end;padding:12px 0 8px}.section-head h2{font-family:"Playfair Display",serif;margin:0;font-size:19px}.section-head p{margin:3px 0 0;color:#ddd;font-size:11px}.section-head>a{font-size:10px;color:#eee}.product-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}.product-card{background:linear-gradient(160deg,#211b15,#0d0c0b);border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:7px;overflow:hidden;transition:.25s}.product-card:hover{transform:translateY(-4px);border-color:rgba(244,198,93,.45)}.product-image{height:108px;position:relative;border-radius:8px;overflow:hidden}.product-image img{width:100%;height:100%;object-fit:cover}.tag{position:absolute;left:6px;bottom:5px;background:#0a0908cc;color:var(--gold2);font-size:6px;padding:3px 5px;border-radius:4px}.product-card h3{font-size:10px;margin:8px 3px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.price{margin:0 3px;font-size:10px}.price b{font-size:13px}.price del{color:#777;margin-left:4px}.rating{font-size:8px;color:var(--gold);margin:5px 3px}.rating span{color:#aaa}.add-cart{width:100%;border:0;background:linear-gradient(135deg,#ffe39a,#eebc51);border-radius:6px;padding:7px;font-size:9px;font-weight:800;cursor:pointer;margin-top:3px}\n.lower-grid{display:grid;grid-template-columns:1.15fr .9fr 1.25fr 1.2fr;gap:16px;margin:12px 0;padding:0 11%}.story,.gallery-box,.video-box{background:rgba(17,13,9,.88);border:1px solid rgba(255,255,255,.07);border-radius:15px;overflow:hidden;min-height:150px}.image-box img{width:100%;height:100%;min-height:170px;object-fit:cover}.copy{padding:16px}.eyebrow.small{font-size:28px}.copy h2{font-family:"Playfair Display",serif;font-size:16px;margin:4px 0 8px}.copy p{font-size:9px;line-height:1.55;color:#ddd}.small-btn{padding:8px 14px;font-size:9px}.mini-head{display:flex;justify-content:space-between;align-items:start;padding:12px}.mini-head h3{font-family:"Playfair Display",serif;font-size:13px;margin:0}.mini-head p,.mini-head a{font-size:8px;color:#ccc;margin:3px 0}.gallery{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;padding:0 10px 10px}.gallery img{width:100%;height:73px;object-fit:cover;border-radius:7px}.video-cover{margin:0 10px 10px;height:110px;border-radius:9px;overflow:hidden;position:relative}.video-cover img{width:100%;height:100%;object-fit:cover;filter:brightness(.65)}.play{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:42px;height:42px;border:0;border-radius:50%;background:#ef4761;color:#fff;cursor:pointer}.video-title{position:absolute;right:12px;top:18px;font-family:"Cormorant Garamond",serif;font-size:22px;font-style:italic}.video-title em{font-size:15px;color:var(--gold)}\n.trust-bar{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:12px 11%;display:flex;justify-content:space-between;background:rgba(8,7,5,.9);font-size:11px}.trust-bar div{display:flex;gap:8px;align-items:center;color:var(--gold)}.trust-bar span{color:#eee;font-size:9px}\nfooter{padding:22px 11%;display:flex;justify-content:space-between;color:#aaa;font-size:9px}footer b{color:#fff;display:block;font-family:"Playfair Display",serif;font-size:14px}footer span{color:#777}\n.cart-drawer{position:fixed;right:-390px;top:0;width:370px;height:100vh;background:#100c08;z-index:50;padding:22px;transition:.3s;box-shadow:-20px 0 70px #000;display:flex;flex-direction:column}.cart-drawer.open{right:0}.cart-head{display:flex;justify-content:space-between}.cart-head h2{font-family:"Playfair Display",serif}.cart-head button{background:none;border:0;color:#fff;font-size:30px;cursor:pointer}.cart-items{flex:1;overflow:auto}.cart-item{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding:12px 0;font-size:12px}.cart-item button{background:none;border:0;color:#ff9b8f;cursor:pointer}.empty{color:#999;text-align:center;margin-top:80px}.cart-total{border-top:1px solid var(--line);padding:18px 0;display:flex;justify-content:space-between}.checkout{border:0;padding:13px;background:linear-gradient(135deg,#ffe39a,#eebc51);font-weight:800;border-radius:10px;cursor:pointer}.overlay{display:none;position:fixed;inset:0;background:#0009;z-index:40}.overlay.show{display:block}\n@media(max-width:1100px){nav{gap:15px}.product-grid{grid-template-columns:repeat(3,1fr)}.lower-grid{grid-template-columns:1fr 1fr}.hero{padding-left:7%;padding-right:7%}.glass-panel{margin:0 6%}.lower-grid{padding:0 6%}.trust-bar{padding:12px 6%}}\n@media(max-width:760px){.navbar{padding:10px 5%;height:auto;flex-wrap:wrap;gap:8px}.brand{transform:scale(.9);transform-origin:left}nav{order:3;width:100%;overflow:auto;gap:20px}nav a{padding:10px 0}.nav-actions{margin-left:auto}.order-btn{display:none}.hero{padding:35px 6%;display:block}.hero-content{width:100%}.hero h1{font-size:40px}.hero-cake{width:100%;margin-top:25px}.cake-card img{height:250px}.glass-panel{margin:0 4%;padding:10px}.category-row{grid-template-columns:repeat(3,1fr)}.category:nth-child(3){border-right:0}.category:nth-child(n+4){border-top:1px solid var(--line)}.product-grid{grid-template-columns:repeat(2,1fr)}.lower-grid{padding:0 4%;grid-template-columns:1fr}.trust-bar{padding:14px 5%;display:grid;grid-template-columns:1fr 1fr;gap:12px}.hero-points{font-size:11px}.cart-drawer{width:min(370px,92vw)}footer{padding:20px 5%;display:block}footer p{margin-top:12px}}\n</style></head><body>\n\n<div class="page-glow"></div>\n\n<header class="navbar">\n  <a class="brand" href="#home">\n    <div class="chef">♨</div>\n    <div>\n      <div class="brand-script">Prabha</div>\n      <div class="brand-sub">THE BAKERS</div>\n      <small>Freshly Baked, Always Loved</small>\n    </div>\n  </a>\n\n  <nav>\n    <a class="active" href="#home">Home</a>\n    <a href="#products">Products</a>\n    <a href="#gallery">Gallery</a>\n    <a href="#videos">Videos</a>\n    <a href="#about">About Us</a>\n    <a href="#contact">Contact</a>\n  </nav>\n\n  <div class="nav-actions">\n    <button class="icon-btn" id="searchBtn" aria-label="Search">⌕</button>\n    <button class="cart-btn" id="cartBtn">🛒 <span id="cartCount">0</span></button>\n    <a class="order-btn" href="#products">◉ &nbsp; Order Now</a>\n  </div>\n</header>\n\n<div class="search-panel" id="searchPanel">\n  <input id="searchInput" type="search" placeholder="Search cakes, pastries, cookies...">\n</div>\n\n<main>\n<section class="hero" id="home">\n  <div class="hero-content">\n    <div class="eyebrow">Welcome to</div>\n    <h1>Prabha The Bakers</h1>\n    <div class="hero-points"><span>Freshly Baked</span><b>•</b><span>Premium Quality</span><b>•</b><span>Made with Love</span></div>\n    <p>From delicious cakes to mouth-watering pastries, cookies, breads and more — we bring happiness in every bite.</p>\n    <div class="hero-buttons">\n      <a class="gold-btn" href="#products">▣ &nbsp; Explore Our Menu</a>\n      <a class="outline-btn" href="#videos">▶ &nbsp; Watch Our Video</a>\n    </div>\n  </div>\n  <div class="hero-cake">\n    <div class="cake-card">\n      <img src="https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=1200&q=90" alt="Chocolate cake">\n    </div>\n  </div>\n</section>\n\n<section class="glass-panel">\n  <div class="category-row">\n    <a class="category" href="#products" data-category="Cakes"><div class="cat-icon">♨</div><strong>Cakes</strong><span>Celebrate Every Moment</span></a><a class="category" href="#products" data-category="Pastries"><div class="cat-icon">⌁</div><strong>Pastries</strong><span>Small Bites, Big Happiness</span></a><a class="category" href="#products" data-category="Cookies"><div class="cat-icon">◉</div><strong>Cookies</strong><span>Crunchy &amp; Delicious</span></a><a class="category" href="#products" data-category="Breads"><div class="cat-icon">⌁</div><strong>Breads</strong><span>Freshly Baked Daily</span></a><a class="category" href="#products" data-category="Cupcakes"><div class="cat-icon">♨</div><strong>Cupcakes</strong><span>Little Cakes, Big Smiles</span></a><a class="category" href="#products" data-category="Desserts"><div class="cat-icon">♡</div><strong>Desserts</strong><span>Sweetness in Every Spoon</span></a>\n  </div>\n\n  <div class="section-head" id="products">\n    <div><h2>Featured Products</h2><p>Our most loved treats, freshly baked for you.</p></div>\n    <a href="#products">View All Products →</a>\n  </div>\n\n  <div class="product-grid" id="productGrid">\n    <article class="product-card" data-name="chocolate cake"><div class="product-image"><img src="https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=900&q=85" alt="Chocolate Cake" loading="lazy"><span class="tag">BEST SELLER</span></div><h3>Chocolate Cake</h3><div class="price"><b>₹599</b> <del>₹699</del></div><div class="rating">★ 4.8 <span>(120)</span></div><button class="add-cart" data-product="Chocolate Cake" data-price="599">🛒 Add to Cart</button></article><article class="product-card" data-name="red velvet cake"><div class="product-image"><img src="https://images.unsplash.com/photo-1586788680434-30d324b2d46f?auto=format&fit=crop&w=900&q=85" alt="Red Velvet Cake" loading="lazy"><span class="tag">POPULAR</span></div><h3>Red Velvet Cake</h3><div class="price"><b>₹649</b> <del>₹749</del></div><div class="rating">★ 4.9 <span>(94)</span></div><button class="add-cart" data-product="Red Velvet Cake" data-price="649">🛒 Add to Cart</button></article><article class="product-card" data-name="cupcakes (box of 6)"><div class="product-image"><img src="https://images.unsplash.com/photo-1587668178277-295251f900ce?auto=format&fit=crop&w=900&q=85" alt="Cupcakes (Box of 6)" loading="lazy"><span class="tag">FRESH</span></div><h3>Cupcakes (Box of 6)</h3><div class="price"><b>₹399</b> <del>₹499</del></div><div class="rating">★ 4.8 <span>(73)</span></div><button class="add-cart" data-product="Cupcakes (Box of 6)" data-price="399">🛒 Add to Cart</button></article><article class="product-card" data-name="mix pastry box"><div class="product-image"><img src="https://images.unsplash.com/photo-1614707267537-2b9f7a9d1c43?auto=format&fit=crop&w=900&q=85" alt="Mix Pastry Box" loading="lazy"><span class="tag">FAVOURITE</span></div><h3>Mix Pastry Box</h3><div class="price"><b>₹449</b> <del>₹549</del></div><div class="rating">★ 4.7 <span>(110)</span></div><button class="add-cart" data-product="Mix Pastry Box" data-price="449">🛒 Add to Cart</button></article><article class="product-card" data-name="chocolate chip cookies"><div class="product-image"><img src="https://images.unsplash.com/photo-1499636136210-6f4ee915583e?auto=format&fit=crop&w=900&q=85" alt="Chocolate Chip Cookies" loading="lazy"><span class="tag">CRUNCHY</span></div><h3>Chocolate Chip Cookies</h3><div class="price"><b>₹199</b> <del>₹249</del></div><div class="rating">★ 4.8 <span>(160)</span></div><button class="add-cart" data-product="Chocolate Chip Cookies" data-price="199">🛒 Add to Cart</button></article><article class="product-card" data-name="fresh bread loaf"><div class="product-image"><img src="https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=900&q=85" alt="Fresh Bread Loaf" loading="lazy"><span class="tag">DAILY FRESH</span></div><h3>Fresh Bread Loaf</h3><div class="price"><b>₹149</b> <del>₹189</del></div><div class="rating">★ 4.9 <span>(81)</span></div><button class="add-cart" data-product="Fresh Bread Loaf" data-price="149">🛒 Add to Cart</button></article>\n  </div>\n</section>\n\n<section class="lower-grid">\n  <div class="story image-box">\n    <img src="https://images.unsplash.com/photo-1556910103-1c02745aae4d?auto=format&fit=crop&w=1000&q=85" alt="Baker preparing fresh dough">\n  </div>\n  <div class="story copy" id="about">\n    <div class="eyebrow small">Our Story</div>\n    <h2>Every celebration deserves something special.</h2>\n    <p>At Prabha The Bakers, we believe every celebration deserves something special. What started as a small dream has grown into a place where love, creativity and the art of baking come together.</p>\n    <a class="gold-btn small-btn" href="#contact">Learn More →</a>\n  </div>\n\n  <div class="gallery-box" id="gallery">\n    <div class="mini-head"><div><h3>Daily Gallery</h3><p>A glimpse of our fresh creations.</p></div><a href="#gallery">View All →</a></div>\n    <div class="gallery">\n      <img src="https://images.unsplash.com/photo-1571115177098-24ec42ed204d?auto=format&fit=crop&w=500&q=80" alt="Cake">\n      <img src="https://images.unsplash.com/photo-1621303837174-89787a7d4729?auto=format&fit=crop&w=500&q=80" alt="Cupcakes">\n      <img src="https://images.unsplash.com/photo-1558301211-0d8c8d6a3b0f?auto=format&fit=crop&w=500&q=80" alt="Desserts">\n      <img src="https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=500&q=80" alt="Bread">\n    </div>\n  </div>\n\n  <div class="video-box" id="videos">\n    <div class="mini-head"><div><h3>Watch Our Videos</h3><p>Behind the scenes & social moments.</p></div><a href="#videos">View All →</a></div>\n    <div class="video-cover">\n      <img src="https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=1000&q=85" alt="Cake making">\n      <button class="play">▶</button>\n      <div class="video-title">Cake<br>Making<br><em>Magic ♡</em></div>\n    </div>\n  </div>\n</section>\n\n<section class="trust-bar" id="contact">\n  <div>♧ <span>Fresh & Natural Ingredients</span></div>\n  <div>♢ <span>Hygienic Preparation</span></div>\n  <div>▣ <span>On-Time Delivery</span></div>\n  <div>♡ <span>100% Customer Satisfaction</span></div>\n</section>\n\n<section class="section" style="padding-top:20px">\n  <div class="section-title"><span>Daily Updates</span><h2>Fresh from Prabha</h2><p>Latest photos and videos from our bakery.</p></div>\n  <div id="dailyMedia" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px">{{MEDIA_HTML}}</div>\n</section>\n\n\n</main>\n\n<aside class="cart-drawer" id="cartDrawer">\n  <div class="cart-head"><h2>Your Cart</h2><button id="closeCart">×</button></div>\n  <div id="cartItems" class="cart-items"><p class="empty">Your cart is empty 🍰</p></div>\n  <div class="cart-total"><span>Total</span><b id="cartTotal">₹0</b></div>\n  <button class="checkout" id="checkoutBtn">Place Order</button>\n</aside>\n<div class="overlay" id="overlay"></div>\n\n<footer>\n  <div><b>Prabha The Bakers</b><span>Freshly Baked, Always Loved</span></div>\n  <p>© 2026 Prabha The Bakers. All rights reserved.<br>📞 <a href="tel:8869946488">8869946488</a> &nbsp;|&nbsp; <a href="https://wa.me/918869946488" target="_blank" rel="noopener">WhatsApp</a></p>\n</footer>\n\n\n<script src="https://checkout.razorpay.com/v1/checkout.js"></script><script>\nconst cart = [];\nconst cartDrawer = document.getElementById("cartDrawer");\nconst overlay = document.getElementById("overlay");\nconst cartItems = document.getElementById("cartItems");\nconst cartCount = document.getElementById("cartCount");\nconst cartTotal = document.getElementById("cartTotal");\n\nfunction money(n){ return "₹" + n.toLocaleString("en-IN"); }\n\nfunction renderCart(){\n  cartCount.textContent = cart.reduce((s,i)=>s+i.qty,0);\n  if(!cart.length){\n    cartItems.innerHTML = \'<p class="empty">Your cart is empty 🍰</p>\';\n  } else {\n    cartItems.innerHTML = cart.map((i,idx)=>`\n      <div class="cart-item">\n        <div><b>${i.name}</b><br><small>${money(i.price)} × ${i.qty}</small></div>\n        <button onclick="removeItem(${idx})">Remove</button>\n      </div>`).join("");\n  }\n  cartTotal.textContent = money(cart.reduce((s,i)=>s+i.price*i.qty,0));\n}\nwindow.removeItem = function(idx){ cart.splice(idx,1); renderCart(); };\n\ndocument.querySelectorAll(".add-cart").forEach(btn=>{\n  btn.addEventListener("click",()=>{\n    const name = btn.dataset.product, price = Number(btn.dataset.price);\n    const existing = cart.find(i=>i.name===name);\n    if(existing) existing.qty++;\n    else cart.push({name,price,qty:1});\n    renderCart();\n    cartDrawer.classList.add("open"); overlay.classList.add("show");\n  });\n});\n\ndocument.getElementById("cartBtn").onclick=()=>{cartDrawer.classList.add("open");overlay.classList.add("show")};\ndocument.getElementById("closeCart").onclick=()=>{cartDrawer.classList.remove("open");overlay.classList.remove("show")};\noverlay.onclick=()=>{cartDrawer.classList.remove("open");overlay.classList.remove("show")};\n\ndocument.getElementById("searchBtn").onclick=()=>{\n  const p=document.getElementById("searchPanel"); p.classList.toggle("show");\n  if(p.classList.contains("show")) document.getElementById("searchInput").focus();\n};\ndocument.getElementById("searchInput").addEventListener("input",(e)=>{\n  const q=e.target.value.toLowerCase();\n  document.querySelectorAll(".product-card").forEach(card=>{\n    card.style.display = card.dataset.name.includes(q) ? "" : "none";\n  });\n});\n\ndocument.querySelectorAll(".category").forEach(cat=>{\n  cat.addEventListener("click",()=>{\n    const term=cat.dataset.category.toLowerCase().slice(0,-1);\n    document.querySelectorAll(".product-card").forEach(card=>{\n      card.style.display = card.dataset.name.includes(term) || term==="cake" && card.dataset.name.includes("cake") ? "" : "";\n    });\n  });\n});\n\ndocument.getElementById("checkoutBtn").onclick=async()=>{\n  if(!cart.length){ alert("Please add something delicious to your cart first 😊"); return; }\n  const btn=document.getElementById("checkoutBtn");\n  btn.disabled=true; btn.textContent="Opening payment…";\n  try {\n    const res=await fetch("/api/create-order",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({items:cart.map(i=>({name:i.name,qty:i.qty}))})});\n    const data=await res.json();\n    if(!res.ok) throw new Error(data.error||"Could not create order");\n    const options={key:data.key_id,amount:data.amount,currency:"INR",name:"Prabha The Bakers",description:"Bakery order",order_id:data.order_id,prefill:{contact:"8869946488"},theme:{color:"#f4c65d"},handler:async function(response){\n      const vr=await fetch("/api/verify-payment",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(response)});\n      const vd=await vr.json();\n      if(vr.ok && vd.ok){ alert("Payment successful! Thank you for ordering from Prabha The Bakers 🎂"); cart.length=0; renderCart(); cartDrawer.classList.remove("open"); overlay.classList.remove("show"); }\n      else alert("Payment could not be verified. Please contact us at 8869946488.");\n      btn.disabled=false; btn.textContent="Place Order";\n    },modal:{ondismiss:function(){btn.disabled=false;btn.textContent="Place Order";}}};\n    const rzp=new Razorpay(options);\n    rzp.on("payment.failed",function(){alert("Payment failed. Please try again.");btn.disabled=false;btn.textContent="Place Order";});\n    rzp.open();\n  } catch(err){ alert(err.message); btn.disabled=false; btn.textContent="Place Order"; }\n};\nrenderCart();\n</script></body>'

@app.route("/")
def home():
    media = load_media()
    cards = []
    for item in media:
        url = "/uploads/" + item["filename"]
        title = item.get("title", "")
        if item["type"] == "video":
            cards.append('<div style="background:#111;border-radius:18px;overflow:hidden"><video src="' + url + '" controls style="width:100%;display:block;max-height:420px"></video><div style="padding:12px;color:#fff">' + esc(title) + '</div></div>')
        else:
            cards.append('<div style="background:#111;border-radius:18px;overflow:hidden"><img src="' + url + '" alt="' + esc(title) + '" style="width:100%;display:block;max-height:420px;object-fit:cover"><div style="padding:12px;color:#fff">' + esc(title) + '</div></div>')
    media_html = "".join(cards) if cards else "<p style='opacity:.7'>No daily updates yet.</p>"
    return build_page(load_settings(), media_html)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        return "<h2>Admin password is not configured.</h2><p>Set ADMIN_PASSWORD in Render Environment.</p>", 503
    if request.method == "POST":
        if request.form.get("password") == password:
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))
        return "<h2>Wrong password</h2><p><a href='/admin'>Try again</a></p>", 401
    if not admin_ok():
        return '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Login</title>
        <style>body{font-family:Arial;background:#111;color:#fff;display:grid;place-items:center;min-height:100vh}.box{background:#1d1d1d;padding:30px;border-radius:18px;width:min(90%,420px)}input,button{width:100%;padding:14px;margin-top:12px;border-radius:10px;border:0}button{background:#f4c65d;cursor:pointer;font-weight:700}</style></head>
        <body><div class="box"><h1>Prabha The Bakers</h1><p>Admin Login</p><form method="post"><input type="password" name="password" placeholder="Admin password" required><button>Login</button></form></div></body></html>'''
    st=load_settings()
    media=load_media()
    products=st["products"]
    product_forms=[]
    for i,p in enumerate(products):
        product_forms.append(f'''<div class="product"><h3>Product {i+1}</h3>
        <label>Name<input name="p_name_{i}" value="{esc(p.get('name'))}"></label>
        <div class="two"><label>Price<input name="p_price_{i}" value="{esc(p.get('price'))}" type="number"></label><label>Old price<input name="p_old_{i}" value="{esc(p.get('old_price'))}" type="number"></label></div>
        <div class="two"><label>Rating<input name="p_rating_{i}" value="{esc(p.get('rating'))}"></label><label>Reviews<input name="p_reviews_{i}" value="{esc(p.get('reviews'))}"></label></div>
        <label>Badge<input name="p_tag_{i}" value="{esc(p.get('tag'))}"></label>
        <label>Image URL<input name="p_image_{i}" value="{esc(p.get('image'))}"></label>
        <p class="hint">For a local uploaded image, use the product image upload button below.</p>
        <form method="post" action="/admin/product-image/{i}" enctype="multipart/form-data"><input type="file" name="media" accept="image/*" required><button>Upload & use this image</button></form>
        </div>''')
    media_rows=[]
    for idx,item in enumerate(media):
        media_rows.append(f'<div class="item"><b>{esc(item.get("title") or "Untitled")}</b> — {esc(item.get("type"))} <form method="post" action="/admin/delete/{idx}" style="display:inline"><button class="danger">Delete</button></form></div>')
    return f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prabha The Bakers — Website Manager</title>
    <style>
    body{{font-family:Arial,sans-serif;background:#0c0a08;color:#fff;margin:0;padding:24px}}.wrap{{max-width:1100px;margin:auto}}h1,h2,h3{{font-family:Georgia,serif}}.box{{background:#18130e;border:1px solid #3a2b1a;padding:22px;border-radius:18px;margin:18px 0}}label{{display:block;font-size:13px;color:#ddd;margin:10px 0}}input,textarea{{width:100%;box-sizing:border-box;padding:11px;border-radius:9px;border:1px solid #493820;background:#0d0b09;color:#fff;margin-top:6px}}textarea{{min-height:90px;resize:vertical}}button{{padding:11px 15px;border:0;border-radius:9px;background:#f4c65d;color:#15100a;font-weight:700;cursor:pointer;margin-top:8px}}.danger{{background:#9d3f35;color:#fff}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.products{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}.product{{background:#0f0c09;padding:15px;border:1px solid #3a2b1a;border-radius:14px}}.hint{{font-size:11px;color:#aaa}}.item{{padding:12px 0;border-bottom:1px solid #33291e}}.links a{{color:#f4c65d;margin-right:15px}}small{{color:#aaa}}@media(max-width:700px){{.products,.two{{grid-template-columns:1fr}}}}
    </style></head><body><div class="wrap"><h1>Prabha The Bakers — Website Manager</h1><p><small>Change website content, product details, images, gallery, theme and daily uploads without editing Python code.</small></p>
    <div class="box"><h2>1. Main website</h2><form method="post" action="/admin/settings">
    <div class="two"><label>Brand name<input name="brand_name" value="{esc(st.get('brand_name'))}"></label><label>Footer tagline<input name="footer_tagline" value="{esc(st.get('footer_tagline'))}"></label></div>
    <div class="two"><label>Phone<input name="phone" value="{esc(st.get('phone'))}"></label><label>Gold/theme color<input name="gold" value="{esc(st.get('gold'))}"></label></div>
    <div class="two"><label>Hero small heading<input name="hero_eyebrow" value="{esc(st.get('hero_eyebrow'))}"></label><label>Hero main heading<input name="hero_title" value="{esc(st.get('hero_title'))}"></label></div>
    <label>Hero points — separate with |<input name="hero_points" value="{esc(' | '.join(st.get('hero_points',[])))}"></label>
    <label>Hero description<textarea name="hero_description">{esc(st.get('hero_description'))}</textarea></label>
    <label>Hero image URL<input name="hero_image" value="{esc(st.get('hero_image'))}"></label>
    <form method="post" action="/admin/single-image/hero_image" enctype="multipart/form-data"><label>Or upload new hero image<input type="file" name="media" accept="image/*" required></label><button>Upload hero image</button></form>
    <label>Website background image URL<input name="background_image" value="{esc(st.get('background_image'))}"></label>
    <form method="post" action="/admin/single-image/background_image" enctype="multipart/form-data"><label>Or upload new background image<input type="file" name="media" accept="image/*" required></label><button>Upload background</button></form>
    <button type="submit">Save main website changes</button></form></div>

    <div class="box"><h2>2. Products — edit image, name, price, badge, rating</h2><form method="post" action="/admin/products"><div class="products">{''.join(product_forms)}</div><button>Save all product changes</button></form></div>

    <div class="box"><h2>3. Our Story</h2><form method="post" action="/admin/story"><label>Heading<input name="story_eyebrow" value="{esc(st.get('story_eyebrow'))}"></label><label>Title<input name="story_title" value="{esc(st.get('story_title'))}"></label><label>Story text<textarea name="story_text">{esc(st.get('story_text'))}</textarea></label><label>Image URL<input name="story_image" value="{esc(st.get('story_image'))}"></label><button>Save story</button></form><form method="post" action="/admin/single-image/story_image" enctype="multipart/form-data"><input type="file" name="media" accept="image/*" required><button>Upload & use story image</button></form></div>

    <div class="box"><h2>4. Gallery</h2><form method="post" action="/admin/gallery">{''.join(f'<label>Gallery image {i+1} URL<input name="g{i}" value="{esc(st.get("gallery",["","","",""])[i])}"></label>' for i in range(4))}<button>Save gallery</button></form></div>

    <div class="box"><h2>5. Video section</h2><form method="post" action="/admin/video"><label>Video cover image URL<input name="video_image" value="{esc(st.get('video_image'))}"></label><label>Video title (HTML allowed for line breaks/emphasis)<input name="video_title" value="{esc(st.get('video_title'))}"></label><button>Save video section</button></form><form method="post" action="/admin/single-image/video_image" enctype="multipart/form-data"><input type="file" name="media" accept="image/*" required><button>Upload & use video cover</button></form></div>

    <div class="box"><h2>6. Trust bar</h2><form method="post" action="/admin/trust">{''.join(f'<label>Item {i+1}<input name="t{i}" value="{esc(st.get("trust",["","","",""])[i])}"></label>' for i in range(4))}<button>Save trust bar</button></form></div>

    <div class="box"><h2>7. Daily photos/videos</h2><form method="post" action="/admin/upload" enctype="multipart/form-data"><label>Title<input type="text" name="title" placeholder="Title (optional)"></label><input type="file" name="media" accept="image/*,video/*" required><button>Upload daily image/video</button></form><p><small>Images: PNG/JPG/JPEG/WEBP/GIF — Videos: MP4/WEBM/MOV</small></p>{''.join(media_rows) if media_rows else '<p>No uploads yet.</p>'}</div>

    <div class="box links"><a href="/" target="_blank">View website</a><a href="/admin/logout">Logout</a></div>
    </div></body></html>'''
def require_admin():
    return admin_ok()


def save_uploaded_image(slot, f):
    if not f or not f.filename:
        return None
    original = f.filename.replace("\\","/").split("/")[-1]
    if not ext_ok(original, ALLOWED_IMAGE):
        return None
    import uuid
    filename = "site_" + slot + "_" + uuid.uuid4().hex + "_" + re.sub(r"[^A-Za-z0-9._-]", "_", original)
    f.save(os.path.join(UPLOAD_DIR, filename))
    return "/uploads/" + filename


@app.route("/admin/settings", methods=["POST"])
def admin_settings():
    if not require_admin(): return redirect(url_for("admin"))
    st=load_settings()
    for k in ["brand_name","tagline","phone","hero_eyebrow","hero_title","hero_description","hero_image","background_image","footer_tagline","gold"]:
        st[k]=request.form.get(k, st.get(k,"" )).strip()
    st["hero_points"]=[x.strip() for x in request.form.get("hero_points","").split("|") if x.strip()]
    save_settings(st)
    return redirect(url_for("admin"))


@app.route("/admin/products", methods=["POST"])
def admin_products():
    if not require_admin(): return redirect(url_for("admin"))
    st=load_settings()
    products=st["products"]
    for i,p in enumerate(products):
        p["name"]=request.form.get(f"p_name_{i}",p.get("name","")).strip()
        p["price"]=request.form.get(f"p_price_{i}",p.get("price",0)).strip()
        p["old_price"]=request.form.get(f"p_old_{i}",p.get("old_price",0)).strip()
        p["rating"]=request.form.get(f"p_rating_{i}",p.get("rating","5.0")).strip()
        p["reviews"]=request.form.get(f"p_reviews_{i}",p.get("reviews","0")).strip()
        p["tag"]=request.form.get(f"p_tag_{i}",p.get("tag","FRESH")).strip()
        p["image"]=request.form.get(f"p_image_{i}",p.get("image","")).strip()
    st["products"]=products
    save_settings(st)
    return redirect(url_for("admin"))


@app.route("/admin/product-image/<int:index>", methods=["POST"])
def admin_product_image(index):
    if not require_admin(): return redirect(url_for("admin"))
    st=load_settings()
    if not (0 <= index < len(st["products"])): return "Invalid product", 400
    url=save_uploaded_image(f"product_{index}", request.files.get("media"))
    if not url: return "Invalid image file. Use PNG/JPG/JPEG/WEBP/GIF.", 400
    st["products"][index]["image"]=url
    save_settings(st)
    return redirect(url_for("admin"))


@app.route("/admin/single-image/<slot>", methods=["POST"])
def admin_single_image(slot):
    if not require_admin(): return redirect(url_for("admin"))
    allowed={"hero_image","background_image","story_image","video_image"}
    if slot not in allowed: return "Invalid image slot", 400
    st=load_settings()
    url=save_uploaded_image(slot, request.files.get("media"))
    if not url: return "Invalid image file. Use PNG/JPG/JPEG/WEBP/GIF.", 400
    st[slot]=url
    save_settings(st)
    return redirect(url_for("admin"))


@app.route("/admin/story", methods=["POST"])
def admin_story():
    if not require_admin(): return redirect(url_for("admin"))
    st=load_settings()
    for k in ["story_eyebrow","story_title","story_text","story_image"]: st[k]=request.form.get(k,st.get(k,"")).strip()
    save_settings(st); return redirect(url_for("admin"))


@app.route("/admin/gallery", methods=["POST"])
def admin_gallery():
    if not require_admin(): return redirect(url_for("admin"))
    st=load_settings(); st["gallery"]=[request.form.get(f"g{i}","").strip() for i in range(4)]; save_settings(st); return redirect(url_for("admin"))


@app.route("/admin/video", methods=["POST"])
def admin_video():
    if not require_admin(): return redirect(url_for("admin"))
    st=load_settings(); st["video_image"]=request.form.get("video_image",st.get("video_image","")).strip(); st["video_title"]=request.form.get("video_title",st.get("video_title","")).strip(); save_settings(st); return redirect(url_for("admin"))


@app.route("/admin/trust", methods=["POST"])
def admin_trust():
    if not require_admin(): return redirect(url_for("admin"))
    st=load_settings(); st["trust"]=[request.form.get(f"t{i}","").strip() for i in range(4)]; save_settings(st); return redirect(url_for("admin"))


@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if not admin_ok():
        return redirect(url_for("admin"))
    f = request.files.get("media")
    if not f or not f.filename:
        return "No file selected", 400
    original = f.filename.replace("\\","/").split("/")[-1]
    if ext_ok(original, ALLOWED_IMAGE):
        kind = "image"
    elif ext_ok(original, ALLOWED_VIDEO):
        kind = "video"
    else:
        return "Unsupported file type.", 400
    import uuid
    filename = uuid.uuid4().hex + "_" + re.sub(r"[^A-Za-z0-9._-]", "_", original)
    f.save(os.path.join(UPLOAD_DIR, filename))
    media = load_media()
    media.append({"filename": filename, "type": kind, "title": request.form.get("title","").strip()})
    save_media(media)
    return redirect(url_for("admin"))

@app.route("/admin/delete/<int:index>", methods=["POST"])
def admin_delete(index):
    if not admin_ok():
        return redirect(url_for("admin"))
    media = load_media()
    if 0 <= index < len(media):
        item = media.pop(index)
        try:
            os.remove(os.path.join(UPLOAD_DIR, item["filename"]))
        except OSError:
            pass
        save_media(media)
    return redirect(url_for("admin"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin"))

@app.route("/api/create-order", methods=["POST"])
def create_order():
    if razorpay_client is None:
        return jsonify({"error": "Razorpay is not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET first."}), 503
    data = request.get_json(silent=True) or {}
    try:
        amount = int(round(float(data.get("amount", 0)) * 100))
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        return jsonify({"error": "Invalid order amount."}), 400
    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "receipt": "prabha_" + str(__import__("time").time_ns())[-12:],
        "payment_capture": 1
    })
    return jsonify({"order_id": order["id"], "amount": amount, "key_id": RAZORPAY_KEY_ID})

@app.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    if razorpay_client is None:
        return jsonify({"ok": False, "error": "Razorpay is not configured."}), 503
    data = request.get_json(silent=True) or {}
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": data["razorpay_order_id"],
            "razorpay_payment_id": data["razorpay_payment_id"],
            "razorpay_signature": data["razorpay_signature"]
        })
        return jsonify({"ok": True})
    except Exception:
        return jsonify({"ok": False}), 400

@app.route("/api/products")
def api_products():
    return jsonify([
        {"name": n, "price": p, "old_price": op, "rating": r, "reviews": rv, "tag": t, "image": u}
        for n, p, op, r, rv, t, u in PRODUCTS
    ])

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
