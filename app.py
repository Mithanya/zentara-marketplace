from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3, os, stripe, json
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-only-change-this-secret')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', '0') == '1',
)

stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_REPLACE_WITH_YOUR_STRIPE_SECRET_KEY')
STRIPE_PUB_KEY = os.getenv('STRIPE_PUBLIC_KEY', 'pk_test_REPLACE_WITH_YOUR_STRIPE_PUBLIC_KEY')
STRIPE_ENABLED = not stripe.api_key.endswith('REPLACE_WITH_YOUR_STRIPE_SECRET_KEY')

DB = os.path.join(os.path.dirname(__file__), 'database.db')
CATEGORIES = ['All', 'Electronics', 'Fashion', 'Home', 'Accessories', 'Books', 'Gadgets', 'Kitchen', 'Sports', 'Beauty', 'Toys']
CATEGORY_IMAGE_FALLBACKS = {
    'Electronics': 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=800&q=85&auto=format&fit=crop',
    'Fashion': 'https://images.unsplash.com/photo-1483985988355-763728e1935b?w=800&q=85&auto=format&fit=crop',
    'Home': 'https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=800&q=85&auto=format&fit=crop',
    'Accessories': 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800&q=85&auto=format&fit=crop',
    'Books': 'https://images.unsplash.com/photo-1495446815901-a7297e633e8d?w=800&q=85&auto=format&fit=crop',
    'Gadgets': 'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=800&q=85&auto=format&fit=crop',
    'Kitchen': 'https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=800&q=85&auto=format&fit=crop',
    'Sports': 'https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=800&q=85&auto=format&fit=crop',
    'Beauty': 'https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=800&q=85&auto=format&fit=crop',
    'Toys': 'https://images.unsplash.com/photo-1594787318286-3d835c1d207f?w=800&q=85&auto=format&fit=crop',
}

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            email    TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS products (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            description    TEXT,
            price          REAL NOT NULL,
            original_price REAL DEFAULT 0,
            image_url      TEXT,
            category       TEXT,
            rating         REAL DEFAULT 4.0,
            review_count   INTEGER DEFAULT 0,
            badge          TEXT DEFAULT '',
            in_stock       INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            user_email TEXT,
            items      TEXT,
            total      REAL,
            status     TEXT DEFAULT 'paid',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    c.execute("SELECT id FROM users WHERE email='admin@zentara.com'")
    if not c.fetchone():
        c.execute("INSERT INTO users (name, email, password, is_admin) VALUES (?,?,?,?)",
                  ('Admin', 'admin@zentara.com',
                   generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123')), 1))

    c.execute("SELECT COUNT(*) as cnt FROM products")
    if c.fetchone()['cnt'] == 0:
        products = [
            ('Biba Printed Kurta Set',
             'Elegant festive kurta set with breathable fabric and polished tailoring for everyday wear.',
             2499.00, 3299.00,
             'https://images.unsplash.com/photo-1529139574466-a303027c1d8b?w=600&q=80&auto=format&fit=crop',
             'Fashion', 4.6, 2140, 'Best Seller'),

            ('Philips Air Fryer',
             'Crispy, healthy cooking with rapid air circulation, digital controls, and easy cleanup.',
             7999.00, 9499.00,
             'https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcREEYVha1imfZPMuozJaIy4Ab7SehIPKZ1lQZeRJyFut8EXox9vauty0AS7ppbJN4hYs6we5EnL7zrCbT8QgjvojipPKAS1PI5J6kkQljyH',
             'Home', 4.8, 3412, 'Best Seller'),

            ('Noise Buds X Pro',
             'Deep bass, ENC noise cancelling, and 40-hour battery life for all-day listening.',
             2999.00, 3999.00,
             'https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=600&q=80&auto=format&fit=crop',
             'Accessories', 4.7, 6200, 'Deal'),
            ('Zebronics RGB Keyboard',
             'Full-size keyboard with tactile switches, RGB lighting, and durable aluminum body.',
             4499.00, 5499.00,
             'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&q=80&auto=format&fit=crop',
             'Accessories', 4.8, 4100, 'Best Seller'),

            ('The Monk Who Sold His Ferrari',
             'A practical guide to success, purpose, and mindful living through powerful habits.',
             699.00, 999.00,
             'https://images.unsplash.com/photo-1512820790803-83ca734da794?w=600&q=80&auto=format&fit=crop',
             'Books', 4.9, 12300, 'Best Seller'),

            ('Mi Smart Watch 3',
             'AMOLED display, heart-rate tracking, sports modes, and 7-day battery backup.',
             6999.00, 8999.00,
             'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80&auto=format&fit=crop',
             'Gadgets', 4.6, 8900, 'New'),

            ('Prestige Mixer Grinder',
             'High-speed stainless steel jars for smooth grinding, blending, and chutney prep.',
             4299.00, 5299.00,
             'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=600&q=80&auto=format&fit=crop',
             'Kitchen', 4.8, 2870, 'Best Seller'),
            ('Borosil Casserole Set',
             'Set of two premium casserole dishes for everyday cooking and serving convenience.',
             1799.00, 2199.00,
             'https://images.unsplash.com/photo-1556911220-dabc1f02913a?w=600&q=80&auto=format&fit=crop',
             'Kitchen', 4.7, 1945, 'Deal'),

            ('Decathlon Yoga Mat',
             'Non-slip support, extra cushioning, and a lightweight design for home workouts.',
             899.00, 1299.00,
             'https://images.unsplash.com/photo-1575052814086-f385e2e2ad1b?w=600&q=85&auto=format&fit=crop',
             'Sports', 4.7, 2860, 'Deal'),
            ('Adidas Training Dumbbells',
             'Hex dumbbells with ergonomic grip for strength training and home gym sessions.',
             2199.00, 2899.00,
             'https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=600&q=80&auto=format&fit=crop',
             'Sports', 4.8, 3310, 'Best Seller'),
            ('Under Armour Sports Bottle',
             'Leak-proof insulated bottle that keeps drinks cool for hours on the go.',
             1099.00, 1499.00,
             'https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&q=80&auto=format&fit=crop',
             'Sports', 4.5, 2300, ''),
            ('Nike Running Cap',
             'Performance cap with sweat-wicking fabric, adjustable fit, and breathable comfort.',
             1499.00, 1999.00,
             'https://images.unsplash.com/photo-1521369909029-2afed882baee?w=600&q=85&auto=format&fit=crop',
             'Sports', 4.6, 2705, 'Deal'),

            ('Lakme Serum Foundation',
             'Weightless skin tint with natural finish and SPF protection for daily use.',
             1249.00, 1699.00,
             'https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?w=600&q=80&auto=format&fit=crop',
             'Beauty', 4.5, 5400, "Amazon's Choice"),
            ('Sunsilk Vitamin C Face Serum',
             'Brightening serum with antioxidants to boost glow and improve skin texture.',
             999.00, 1399.00,
             'https://images.unsplash.com/photo-1556228578-8c89e6adf883?w=600&q=80&auto=format&fit=crop',
             'Beauty', 4.7, 4100, 'Best Seller'),
            ('Nykaa Lip Balm Set',
             'Hydrating lip balm trio with rich nourishment and a smooth glossy finish.',
             799.00, 1199.00,
             'https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?w=600&q=80&auto=format&fit=crop',
             'Beauty', 4.4, 3650, ''),

            ('LEGO Classic Bricks',
             'Creative building set with durable bricks for imaginative play and display builds.',
             2599.00, 3299.00,
             'https://images.unsplash.com/photo-1587654780291-39c9404d746b?w=600&q=80&auto=format&fit=crop',
             'Toys', 4.9, 5200, 'Best Seller'),
            ('Barbie Dream House',
             'Multi-room playhouse with modern furniture, pink detailing, and fun accessories.',
             3499.00, 4599.00,
             'https://images.unsplash.com/photo-1511512578047-dfb367046420?w=600&q=80&auto=format&fit=crop',
             'Toys', 4.8, 6030, 'New'),
            ('Hot Wheels Track Set',
             'Dual-lane racing set with loops and launch pads for exciting toy car action.',
             2299.00, 2999.00,
             'https://images.unsplash.com/photo-1516627145497-ae6968895b74?w=600&q=80&auto=format&fit=crop',
             'Toys', 4.6, 4920, 'Deal'),

              ('Samsung Galaxy S24', 'Flagship smartphone with AMOLED display and pro camera.', 74999.00, 84999.00, 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&q=80&auto=format&fit=crop', 'Electronics', 4.7, 8200, 'Best Seller'),
              ('OnePlus 12R 5G', 'Fast 5G phone with smooth display and rapid charging.', 39999.00, 45999.00, 'https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=600&q=80&auto=format&fit=crop', 'Electronics', 4.6, 6100, 'Deal'),
              ('Sony Bravia 55-inch 4K TV', 'Cinematic picture quality with smart streaming and voice control.', 54999.00, 69999.00, 'https://images.unsplash.com/photo-1593784991095-a205069470b6?w=600&q=80&auto=format&fit=crop', 'Electronics', 4.8, 4300, 'Best Seller'),
              ('Canon EOS 1500D Camera', 'Beginner-friendly DSLR with detailed images and Wi-Fi sharing.', 35999.00, 42999.00, 'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=600&q=80&auto=format&fit=crop', 'Electronics', 4.5, 2700, ''),
              ('JBL Bar 500 Soundbar', 'Powerful home cinema sound with wireless subwoofer.', 32999.00, 39999.00, 'https://images.unsplash.com/photo-1545454675-3531b543be5d?w=600&q=80&auto=format&fit=crop', 'Electronics', 4.6, 1900, 'New'),

              ('W for Woman Cotton Dress', 'Comfortable printed cotton dress for workdays and weekends.', 1899.00, 2499.00, 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&q=80&auto=format&fit=crop', 'Fashion', 4.5, 1850, 'Deal'),
              ('Levis 511 Slim Jeans', 'Classic slim-fit denim with stretch comfort.', 2499.00, 3499.00, 'https://images.unsplash.com/photo-1542272604-787c3835535d?w=600&q=80&auto=format&fit=crop', 'Fashion', 4.6, 3200, ''),
              ('Manyavar Nehru Jacket', 'Textured ethnic jacket for celebrations and weddings.', 2799.00, 3999.00, 'https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=600&q=80&auto=format&fit=crop', 'Fashion', 4.4, 1100, 'New'),
              ('Puma Everyday Sneakers', 'Lightweight casual sneakers with cushioned soles.', 2999.00, 4499.00, 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80&auto=format&fit=crop', 'Fashion', 4.7, 2600, 'Best Seller'),

              ('Wakefit Memory Foam Pillow', 'Ergonomic memory foam support with washable cover.', 999.00, 1499.00, 'https://images.unsplash.com/photo-1584100936595-c0654b55a2e2?w=600&q=80&auto=format&fit=crop', 'Home', 4.6, 4800, 'Best Seller'),
              ('Nilkamal Storage Cabinet', 'Compact cabinet for organized home storage.', 3299.00, 4499.00, 'https://images.unsplash.com/photo-1595428774223-ef52624120d2?w=600&q=80&auto=format&fit=crop', 'Home', 4.4, 1720, ''),
              ('Atomberg Ceiling Fan', 'Energy-efficient quiet fan with remote control.', 3699.00, 4999.00, 'https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=600&q=80&auto=format&fit=crop', 'Home', 4.7, 2300, 'Deal'),
              ('SleepyCat Mattress Topper', 'Breathable topper that adds comfort to any mattress.', 3999.00, 5999.00, 'https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&q=80&auto=format&fit=crop', 'Home', 4.5, 2100, 'New'),

              ('Portronics USB-C Hub', 'Seven-port hub with HDMI and USB 3.0.', 1499.00, 2199.00, 'https://images.unsplash.com/photo-1625842268584-8f3296236761?w=600&q=80&auto=format&fit=crop', 'Accessories', 4.5, 3500, 'Deal'),
              ('Tukzer Laptop Stand', 'Adjustable aluminum stand for better desk ergonomics.', 1299.00, 1999.00, 'https://images.unsplash.com/photo-1524758631624-e2822e304c36?w=600&q=80&auto=format&fit=crop', 'Accessories', 4.6, 2400, ''),
              ('DailyObjects Laptop Sleeve', 'Padded water-resistant sleeve with accessory pocket.', 899.00, 1299.00, 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=600&q=80&auto=format&fit=crop', 'Accessories', 4.4, 1600, 'New'),

              ('Ikigai', 'A guide to finding purpose, balance, and meaning.', 299.00, 499.00, 'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?w=600&q=80&auto=format&fit=crop', 'Books', 4.7, 18600, 'Best Seller'),
              ('The Alchemist', 'A modern classic about dreams, courage, and destiny.', 249.00, 399.00, 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=600&q=80&auto=format&fit=crop', 'Books', 4.8, 22400, 'Best Seller'),
              ('Rich Dad Poor Dad', 'Personal finance classic about investing and financial freedom.', 349.00, 599.00, 'https://images.unsplash.com/photo-1495446815901-a7297e633e8d?w=600&q=85&auto=format&fit=crop', 'Books', 4.6, 14200, ''),
              ('Wings of Fire', 'The inspiring autobiography of Dr. A.P.J. Abdul Kalam.', 199.00, 299.00, 'https://images.unsplash.com/photo-1532012197267-da84d127e765?w=600&q=80&auto=format&fit=crop', 'Books', 4.9, 9800, 'Deal'),

              ('Fire-Boltt Smartwatch', 'Smartwatch with calling, health tracking, and sports modes.', 1799.00, 2999.00, 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80&auto=format&fit=crop', 'Gadgets', 4.4, 7400, 'Deal'),
              ('Amazon Echo Dot', 'Compact Alexa speaker with smart-home control.', 2499.00, 4499.00, 'https://images.unsplash.com/photo-1543512214-318c7553f230?w=600&q=80&auto=format&fit=crop', 'Gadgets', 4.6, 12300, 'Best Seller'),
              ('GoPro HERO Action Camera', 'Rugged waterproof camera with stabilized 4K video.', 28999.00, 34999.00, 'https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80&auto=format&fit=crop', 'Gadgets', 4.7, 2800, 'New'),
              ('Portronics Sound Drum', 'Portable Bluetooth speaker with all-day battery.', 1299.00, 1999.00, 'https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80&auto=format&fit=crop', 'Gadgets', 4.5, 4200, ''),

              ('Hawkins Pressure Cooker', 'Durable pressure cooker for quick Indian cooking.', 2199.00, 2799.00, 'https://images.unsplash.com/photo-1585518419759-7fe2e0fbf8a6?w=600&q=80&auto=format&fit=crop', 'Kitchen', 4.8, 5300, 'Best Seller'),
              ('Milton Thermosteel Flask', 'Leak-proof insulated flask for hot or cold beverages.', 999.00, 1399.00, 'https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&q=80&auto=format&fit=crop', 'Kitchen', 4.6, 4600, ''),
              ('Pigeon Induction Cooktop', 'Fast induction cooking with preset menus.', 1799.00, 2499.00, 'https://images.unsplash.com/photo-1556911220-dabc1f02913a?w=600&q=80&auto=format&fit=crop', 'Kitchen', 4.5, 3900, 'Deal'),

              ('Nivia Football', 'Durable machine-stitched football for training and matches.', 799.00, 1199.00, 'https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=600&q=80&auto=format&fit=crop', 'Sports', 4.6, 2800, 'Best Seller'),

              ('Mamaearth Face Wash', 'Gentle daily face wash with natural ingredients.', 399.00, 499.00, 'https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?w=600&q=85&auto=format&fit=crop', 'Beauty', 4.4, 7200, 'Best Seller'),
              ('Maybelline Mascara', 'Volumizing mascara with a smooth clump-free formula.', 499.00, 699.00, 'https://images.unsplash.com/photo-1631214524020-7e18db9a8f92?w=600&q=80&auto=format&fit=crop', 'Beauty', 4.5, 5100, 'Deal'),

              ('Funskool Learning Blocks', 'Colorful construction blocks for creative early learning.', 699.00, 999.00, 'https://images.unsplash.com/photo-1596461404969-9ae70f2830c1?w=600&q=80&auto=format&fit=crop', 'Toys', 4.7, 3400, 'Best Seller'),
              ('Remote Control Car', 'Rechargeable stunt car with lights and easy controls.', 1299.00, 1999.00, 'https://images.unsplash.com/photo-1594787318286-3d835c1d207f?w=600&q=80&auto=format&fit=crop', 'Toys', 4.5, 2800, 'Deal'),
        ]
        c.executemany(
            "INSERT INTO products (name, description, price, original_price, image_url, category, rating, review_count, badge) VALUES (?,?,?,?,?,?,?,?,?)",
            products)
    conn.commit()
    conn.close()

def logged_in():  return 'user_id' in session
def is_admin():   return session.get('is_admin', False)
def cart_count(): return sum(session.get('cart', {}).values())

@app.route('/')
def index():
    q   = request.args.get('q', '').strip()
    cat = request.args.get('cat', 'All').strip()
    conn = get_db()
    qry    = "SELECT * FROM products WHERE 1=1"
    params = []
    if q:
        qry   += " AND (name LIKE ? OR description LIKE ? OR category LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if cat and cat != 'All':
        qry   += " AND category = ?"
        params.append(cat)
    products = conn.execute(qry, params).fetchall()
    deals    = conn.execute("SELECT * FROM products WHERE badge IN ('Deal','Best Seller') LIMIT 5").fetchall()
    cat_counts = {}
    for row in conn.execute("SELECT category, COUNT(*) as n FROM products GROUP BY category"):
        cat_counts[row['category']] = row['n']
    conn.close()
    return render_template('index.html', products=products, q=q, cat=cat,
                           categories=CATEGORIES, deals=deals,
                           cat_counts=cat_counts, cart_count=cart_count(),
                           category_image_fallbacks=CATEGORY_IMAGE_FALLBACKS)

@app.route('/product/<int:pid>')
def product_detail(pid):
    conn    = get_db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not product:
        conn.close()
        return redirect(url_for('index'))
    related = conn.execute(
        "SELECT * FROM products WHERE category=? AND id!=? LIMIT 4",
        (product['category'], pid)).fetchall()
    conn.close()
    return render_template('product.html', product=product, related=related, cart_count=cart_count(),
                           category_image_fallbacks=CATEGORY_IMAGE_FALLBACKS)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (name, email, password) VALUES (?,?,?)",
                         (name, email, generate_password_hash(password)))
            conn.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered.', 'danger')
        finally:
            conn.close()
    return render_template('register.html', cart_count=cart_count())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id']    = user['id']
            session['user_name']  = user['name']
            session['user_email'] = user['email']
            session['is_admin']   = bool(user['is_admin'])
            flash(f'Welcome back, {user["name"]}! 👋', 'success')
            return redirect(url_for('index'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', cart_count=cart_count())

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/cart/add/<int:pid>')
def add_to_cart(pid):
    if not logged_in():
        flash('Please log in to add items to cart.', 'warning')
        return redirect(url_for('login'))
    cart = session.get('cart', {})
    cart[str(pid)] = cart.get(str(pid), 0) + 1
    session['cart'] = cart
    flash('Item added to cart!', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/buy-now/<int:pid>', methods=['POST'])
def buy_now(pid):
    if not logged_in():
        flash('Please log in to buy this item.', 'warning')
        return redirect(url_for('login'))
    quantity = request.form.get('quantity', '1', type=int)
    quantity = max(1, min(quantity, 10))
    conn = get_db()
    product = conn.execute("SELECT id FROM products WHERE id=? AND in_stock=1", (pid,)).fetchone()
    conn.close()
    if not product:
        flash('This product is currently unavailable.', 'warning')
        return redirect(url_for('index'))
    session['cart'] = {str(pid): quantity}
    return redirect(url_for('checkout'))

@app.route('/cart/remove/<int:pid>')
def remove_from_cart(pid):
    cart = session.get('cart', {})
    cart.pop(str(pid), None)
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    if not logged_in():
        return redirect(url_for('login'))
    cart  = session.get('cart', {})
    items, total = [], 0
    if cart:
        conn = get_db()
        for pid, qty in cart.items():
            p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if p:
                subtotal = p['price'] * qty
                total   += subtotal
                items.append({'product': p, 'qty': qty, 'subtotal': subtotal})
        conn.close()
    return render_template('cart.html', items=items, total=round(total, 2), cart_count=cart_count())

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if not logged_in():
        return redirect(url_for('login'))
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart'))
    conn = get_db()
    items, total = [], 0
    for pid, qty in cart.items():
        p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            subtotal = p['price'] * qty
            total   += subtotal
            items.append({'product': p, 'qty': qty, 'subtotal': subtotal})
    conn.close()
    total = round(total, 2)
    if request.method == 'POST':
        payment_status = 'demo_paid'
        if STRIPE_ENABLED:
            try:
                stripe.PaymentIntent.create(
                    amount=int(total * 100), currency='inr',
                    metadata={'user_id': session['user_id']})
                payment_status = 'paid'
            except stripe.error.StripeError:
                flash('Payment could not be completed. Please check your payment details and try again.', 'danger')
                return render_template('checkout.html', items=items, total=total,
                                       stripe_pub_key=STRIPE_PUB_KEY,
                                       stripe_enabled=STRIPE_ENABLED,
                                       cart_count=cart_count()), 402
        order_items = json.dumps([
            {'name': i['product']['name'], 'qty': i['qty'], 'price': i['product']['price']}
            for i in items])
        conn2 = get_db()
        conn2.execute(
            "INSERT INTO orders (user_id, user_email, items, total, status) VALUES (?,?,?,?,?)",
            (session['user_id'], session['user_email'], order_items, total, payment_status))
        conn2.commit()
        conn2.close()
        session.pop('cart', None)
        if payment_status == 'demo_paid':
            flash('Demo order placed. Add Stripe test keys to enable real payment processing.', 'info')
        else:
            flash('🎉 Order placed successfully!', 'success')
        return redirect(url_for('order_confirmation'))
    return render_template('checkout.html', items=items, total=total,
                           stripe_pub_key=STRIPE_PUB_KEY,
                           stripe_enabled=STRIPE_ENABLED, cart_count=cart_count())

@app.route('/order-confirmation')
def order_confirmation():
    return render_template('order_confirmation.html', cart_count=0)

@app.route('/admin')
def admin():
    if not is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('index'))
    conn     = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    orders   = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template('admin.html', products=products, orders=orders,
                           categories=CATEGORIES[1:], cart_count=cart_count())

@app.route('/admin/add', methods=['POST'])
def admin_add():
    if not is_admin(): return redirect(url_for('index'))
    f = request.form
    conn = get_db()
    conn.execute(
        "INSERT INTO products (name, description, price, original_price, image_url, category, rating, review_count, badge) VALUES (?,?,?,?,?,?,?,?,?)",
        (f['name'].strip(), f['description'].strip(), float(f['price']),
         float(f.get('original_price') or 0), f['image_url'].strip(),
         f['category'], float(f.get('rating', 4.0)),
         int(f.get('review_count', 0)), f.get('badge', '')))
    conn.commit()
    conn.close()
    flash('Product added!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:pid>')
def admin_delete(pid):
    if not is_admin(): return redirect(url_for('index'))
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash('Product deleted.', 'info')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db()
    print("\n✅ Zentara is running → http://127.0.0.1:5000")
    print("👤 Admin login  → admin@zentara.com\n")
    app.run(debug=os.getenv('FLASK_DEBUG', '0') == '1')

# ---------- React SPA serving ----------
# Serve React built files from frontend/dist
@app.route('/react')
def serve_react():
    """Serve the React single-page application entry point."""
    return send_from_directory('frontend/dist', 'index.html')

@app.route('/static/react/<path:filename>')
def serve_react_static(filename):
    """Serve static assets (JS, CSS, media) for the React app."""
    return send_from_directory('frontend/dist', filename)