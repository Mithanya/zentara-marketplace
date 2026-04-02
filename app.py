from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, stripe, json
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'zentara-secret-key-2024'

stripe.api_key = 'sk_test_REPLACE_WITH_YOUR_STRIPE_SECRET_KEY'
STRIPE_PUB_KEY = 'pk_test_REPLACE_WITH_YOUR_STRIPE_PUBLIC_KEY'

DB = os.path.join(os.path.dirname(__file__), 'database.db')
CATEGORIES = ['All', 'Electronics', 'Fashion', 'Home', 'Accessories', 'Books', 'Gadgets', 'Kitchen', 'Sports', 'Beauty', 'Toys']

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
                  ('Admin', 'admin@zentara.com', generate_password_hash('admin123'), 1))

    c.execute("SELECT COUNT(*) as cnt FROM products")
    if c.fetchone()['cnt'] == 0:
        products = [
            # Electronics
            ('Sony WH-1000XM5 Headphones',
             'Industry-leading noise cancellation, 30h battery, multipoint Bluetooth. Foldable premium design.',
             279.99, 399.99,
             'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80&auto=format&fit=crop',
             'Electronics', 4.8, 14832, 'Best Seller'),
            ('Apple AirPods Pro 2nd Gen',
             'Active noise cancellation, Adaptive Transparency, Spatial Audio with dynamic head tracking.',
             189.99, 249.99,
             'https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?w=600&q=80&auto=format&fit=crop',
             'Electronics', 4.9, 38201, 'Best Seller'),
            ('Samsung 55 Inch 4K QLED Smart TV',
             'Quantum Dot technology, 120Hz refresh rate, built-in Alexa and Gaming Hub.',
             749.99, 1099.99,
             'https://images.unsplash.com/photo-1593784991095-a205069470b6?w=600&q=80&auto=format&fit=crop',
             'Electronics', 4.7, 9203, 'Deal'),
            ('Bose QuietComfort 45',
             'World-class noise cancellation, TriPort acoustic architecture, 24h battery life.',
             229.99, 329.99,
             'https://images.unsplash.com/photo-1583394838336-acd977736f90?w=600&q=80&auto=format&fit=crop',
             'Electronics', 4.6, 7821, ''),
            ('JBL Flip 6 Bluetooth Speaker',
             'Bold JBL Pro Sound, IP67 waterproof, 12 hours of playtime, PartyBoost compatible.',
             99.99, 149.99,
             'https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&q=80&auto=format&fit=crop',
             'Electronics', 4.5, 6542, ''),
            

            # Fashion
            ('Nike Air Max 270',
             'Large Max Air unit for all-day cushioning. Stretch mesh upper for breathability.',
             129.99, 159.99,
             'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80&auto=format&fit=crop',
             'Fashion', 4.6, 23841, 'Best Seller'),
            
            ('Ray-Ban Aviator Classic',
             'Iconic metal frame, UV400 crystal lenses, spring hinges. G-15 natural colour perception.',
             154.99, 179.99,
             'https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=600&q=80&auto=format&fit=crop',
             'Fashion', 4.7, 11293, ''),
            ('Fjallraven Kanken Backpack',
             'Classic Swedish backpack in Vinylon F fabric. 16L main compartment, padded straps.',
             89.99, 109.99,
             'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600&q=80&auto=format&fit=crop',
             'Fashion', 4.6, 9821, ''),
            ('Hamilton Khaki Field Watch',
             'Swiss-made automatic, sapphire crystal, 100m water resistant, 80h power reserve.',
             495.99, 595.99,
             'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80&auto=format&fit=crop',
             'Fashion', 4.9, 4302, 'Deal'),

            # Home
            ('Dyson Purifier Cool TP07',
             'Captures 99.97% of particles. Real-time air quality display. Oscillates 350 degrees.',
             449.99, 549.99,
             'https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=600&q=80&auto=format&fit=crop',
             'Home', 4.8, 6721, 'Best Seller'),
            ('BenQ ScreenBar LED Lamp',
             'Auto-dimming with ambient light sensor. Zero screen glare, USB powered, clips to monitor.',
             109.99, 139.99,
             'https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=600&q=80&auto=format&fit=crop',
             'Home', 4.7, 14203, "Amazon's Choice"),
            ('Govee Smart LED Strip 32ft',
             'RGBIC 16 million colors, music sync, app and voice control. Alexa and Google compatible.',
             34.99, 54.99,
             'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&q=80&auto=format&fit=crop',
             'Home', 4.5, 28942, 'Deal'),
            
            ('IKEA KALLAX Shelf Unit',
             'Versatile shelving for books, boxes and baskets. Place horizontally or vertically.',
             79.99, 99.99,
             'https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=600&q=80&auto=format&fit=crop',
             'Home', 4.4, 8932, ''),

            # Accessories
            ('Logitech MX Master 3S Mouse',
             '8000 DPI any-surface tracking, MagSpeed scroll wheel, silent clicks, USB-C charging.',
             89.99, 109.99,
             'https://images.unsplash.com/photo-1527814050087-3793815479db?w=600&q=80&auto=format&fit=crop',
             'Accessories', 4.8, 19234, "Amazon's Choice"),
            ('Keychron Q1 Mechanical Keyboard',
             'Gasket-mount TKL, QMK/VIA support, per-key RGB, CNC aluminium, hot-swappable sockets.',
             169.99, 219.99,
             'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&q=80&auto=format&fit=crop',
             'Accessories', 4.8, 10932, 'Best Seller'),
            ('MagSafe 15W Wireless Charger',
             '15W fast charging with perfect magnet alignment. Braided USB-C cable included.',
             35.99, 49.99,
             'https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=600&q=80&auto=format&fit=crop',
             'Accessories', 4.6, 12034, "Amazon's Choice"),
            

            # Books
            ('Atomic Habits by James Clear',
             'No.1 NYT bestseller. Easy proven way to build good habits and break bad ones.',
             14.99, 27.99,
             'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=600&q=80&auto=format&fit=crop',
             'Books', 4.9, 92341, 'Best Seller'),
            ('The Psychology of Money',
             'Morgan Housel on how people think about money and making better financial decisions.',
             13.99, 19.99,
             'https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=600&q=80&auto=format&fit=crop',
             'Books', 4.8, 54921, 'Best Seller'),
            ('Deep Work by Cal Newport',
             'Rules for focused success in a distracted world. How to achieve peak productivity.',
             15.99, 24.99,
             'https://images.unsplash.com/photo-1532012197267-da84d127e765?w=600&q=80&auto=format&fit=crop',
             'Books', 4.7, 31204, ''),
            ('Zero to One by Peter Thiel',
             'Notes on startups and how to build the future. Essential reading for entrepreneurs.',
             16.99, 24.99,
             'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?w=600&q=80&auto=format&fit=crop',
             'Books', 4.6, 28410, ''),

            # Gadgets
            ('DJI Mini 4 Pro Drone',
             '4K/60fps HDR video, omnidirectional obstacle sensing, 34-min flight time. Under 249g.',
             759.99, 899.99,
             'https://images.unsplash.com/photo-1508614589041-895b88991e3e?w=600&q=80&auto=format&fit=crop',
             'Gadgets', 4.8, 8921, 'New'),
            ('Ember Temperature Mug 2',
             'App-controlled heated mug. Set exact drinking temp 120-145F. 80-min battery life.',
             129.99, 149.99,
             'https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?w=600&q=80&auto=format&fit=crop',
             'Gadgets', 4.7, 12034, "Amazon's Choice"),
            
            ('Polaroid Now+ Instant Camera',
             'Bluetooth connected, 5 creative lens filters, double exposure and self-timer modes.',
             109.99, 139.99,
             'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=600&q=80&auto=format&fit=crop',
             'Gadgets', 4.6, 9203, 'New'),
            ('DJI OM 6 Gimbal Stabilizer',
             '3-axis stabilization, magnetic phone clamp, ActiveTrack 6.0 face tracking, 6h runtime.',
             119.99, 159.99,
             'https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=600&q=80&auto=format&fit=crop',
             'Gadgets', 4.5, 5421, 'New'),

            # Kitchen
            ('Fellow Stagg EKG Kettle',
             'Variable temperature control, 60-min hold mode, precision pour spout. 1L capacity.',
             165.99, 195.99,
             'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&q=80&auto=format&fit=crop',
             'Kitchen', 4.9, 8201, 'Best Seller'),
            ('Hydro Flask 32oz Wide Mouth',
             'TempShield keeps cold 24h / hot 12h. BPA-free stainless steel, leak-proof Flex Cap.',
             44.99, 54.99,
             'https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&q=80&auto=format&fit=crop',
             'Kitchen', 4.7, 38920, "Amazon's Choice"),
            ('KitchenAid Stand Mixer 5qt',
             '10 speeds, 59 touchpoints for thorough mixing. Tilt-head with dough hook and beater.',
             349.99, 449.99,
             'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=600&q=80&auto=format&fit=crop',
             'Kitchen', 4.9, 12403, 'Best Seller'),

            # Sports
            
            ('Bowflex SelectTech 552',
             'Adjusts 5 to 52.5 lbs in 15 increments. Replaces 15 sets of dumbbells. Space efficient.',
             349.99, 449.99,
             'https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&q=80&auto=format&fit=crop',
             'Sports', 4.8, 9821, 'Deal'),
           

            # Beauty
            ('The Ordinary Skincare Set',
             'Niacinamide 10% + Zinc, Hyaluronic Acid 2% + B5, Vitamin C. Clinically proven ingredients.',
             38.99, 59.99,
             'https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=600&q=80&auto=format&fit=crop',
             'Beauty', 4.7, 31204, "Amazon's Choice"),
            ('Dyson Supersonic Hair Dryer',
             'Fast drying, no extreme heat. Magnetic attachments, 3 speed and 4 heat settings.',
             399.99, 479.99,
             'https://images.unsplash.com/photo-1522338242992-e1a54906a8da?w=600&q=80&auto=format&fit=crop',
             'Beauty', 4.8, 18203, 'Deal'),

            # Toys
            ('LEGO Icons Botanical Set',
             '756-piece botanical collection. Pressed flower frame with display plants. Adults 18+.',
             49.99, 64.99,
             'https://images.unsplash.com/photo-1587654780291-39c9404d746b?w=600&q=80&auto=format&fit=crop',
             'Toys', 4.9, 15203, 'Best Seller'),
            ('Nintendo Switch OLED',
             '7-inch OLED screen, enhanced audio, 64GB storage, wired LAN port. Play anywhere.',
             349.99, 399.99,
             'https://images.unsplash.com/photo-1578303512597-81e6cc155b3e?w=600&q=80&auto=format&fit=crop',
             'Toys', 4.9, 48203, 'Best Seller'),
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
                           cat_counts=cat_counts, cart_count=cart_count())

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
    return render_template('product.html', product=product, related=related, cart_count=cart_count())

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
        try:
            stripe.PaymentIntent.create(
                amount=int(total * 100), currency='usd',
                metadata={'user_id': session['user_id']})
        except Exception:
            pass
        order_items = json.dumps([
            {'name': i['product']['name'], 'qty': i['qty'], 'price': i['product']['price']}
            for i in items])
        conn2 = get_db()
        conn2.execute(
            "INSERT INTO orders (user_id, user_email, items, total) VALUES (?,?,?,?)",
            (session['user_id'], session['user_email'], order_items, total))
        conn2.commit()
        conn2.close()
        session.pop('cart', None)
        flash('🎉 Order placed successfully!', 'success')
        return redirect(url_for('order_confirmation'))
    return render_template('checkout.html', items=items, total=total,
                           stripe_pub_key=STRIPE_PUB_KEY, cart_count=cart_count())

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
    print("👤 Admin login  → admin@zentara.com / admin123\n")
    app.run(debug=True)