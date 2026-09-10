PRABHA THE BAKERS - PYTHON / FLASK

Local run:
1) pip install -r requirements.txt
2) python app.py
3) open http://127.0.0.1:5000

Render deployment:
Build command: pip install -r requirements.txt
Start command: gunicorn app:app

Razorpay:
Set these environment variables on the server (never put the secret in public code):
RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_key_secret

The website calculates the order total on the server from the product list, creates a Razorpay order, opens Standard Checkout, and verifies the returned payment signature server-side.
Contact: 8869946488


ADMIN UPLOAD PANEL
------------------
This version adds:
- /admin login page
- image/video upload
- uploaded media appears in a Daily Updates section on the home page
- delete uploaded media

Render Environment Variables to add:
- ADMIN_PASSWORD = choose a strong password (do not share it)
- FLASK_SECRET_KEY = a long random secret (optional but recommended)

IMPORTANT:
Render's local filesystem is not guaranteed to be permanent on redeploys/restarts. This admin uploader is a simple first version. For permanent media storage, connect the app to an external object-storage service such as Cloudinary or another persistent storage provider.
