-- ==========================================================
-- E-Commerce Database Schema for SQLite
-- Database: smartcart.db
-- Roles: admin, staff, user
-- ==========================================================

-- 1. CUSTOMERS / USERS TABLE
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT, 
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    e_mail TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    phone_number TEXT NOT NULL DEFAULT '',
    profile_image TEXT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. ADDRESS TABLE
CREATE TABLE IF NOT EXISTS address (
    address_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    address_line TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    pincode TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT 'INDIA',
    phone_number TEXT NULL,
    is_default BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
);

-- 3. CATEGORIES TABLE
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT, 
    category_name TEXT NOT NULL UNIQUE,
    category_image TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. PRODUCTS TABLE
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    product_name TEXT NOT NULL UNIQUE,
    description TEXT NULL,
    price REAL NOT NULL,
    image_url TEXT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT
);

-- 5. INVENTORY TABLE
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE,
    quantity INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

-- 6. CART TABLE
CREATE TABLE IF NOT EXISTS cart (
    cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
);

-- 7. CART_ITEMS TABLE
CREATE TABLE IF NOT EXISTS cart_items (
    cart_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (cart_id, product_id),
    FOREIGN KEY (cart_id) REFERENCES cart(cart_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

-- 8. ORDERS TABLE
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    address_id INTEGER NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_status TEXT NOT NULL DEFAULT 'pending',
    total_amount REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address(address_id) ON DELETE RESTRICT
);

-- 9. ORDER_ITEMS TABLE
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE RESTRICT
);

-- 10. PAYMENTS TABLE
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    payment_method TEXT NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'pending',
    amount_paid REAL NOT NULL,
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    transaction_id TEXT NOT NULL UNIQUE,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- 11. SHIPMENTS TABLE
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    shipment_status TEXT NOT NULL DEFAULT 'Order Placed',
    delivery_date TIMESTAMP NULL,
    address_id INTEGER NOT NULL,
    phone_number TEXT NOT NULL,
    tracking_number TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (address_id) REFERENCES address(address_id) ON DELETE RESTRICT
);

-- 12. PASSWORD RESETS TABLE
CREATE TABLE IF NOT EXISTS password_resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    otp TEXT NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- SEED DATA: Starter Categories, Products & Inventory
-- ==========================================================

INSERT OR IGNORE INTO categories (category_id, category_name) VALUES
(1, 'Electronics & Gadgets'),
(2, 'Men & Women Fashion'),
(3, 'Home & Living'),
(4, 'Beauty & Personal Care');

INSERT OR IGNORE INTO products (product_id, category_id, product_name, description, price, image_url, is_active) VALUES
(1, 1, 'Pro Wireless Noise-Cancelling Headphones', 'Ultra-low latency audio, 40-hour battery life, memory foam cushions.', 149.99, '10a9f5304d7fe524.webp', 1),
(2, 1, 'Ultra-Slim OLED 4K Smart Monitor 27"', '144Hz refresh rate, HDR1000, USB-C single cable display setup.', 399.00, '1f8eb1db3d1d7dc7.webp', 1),
(3, 2, 'Classic Minimalist Chronograph Watch', 'Stainless steel case with genuine Italian leather strap, 50m water resistant.', 89.50, '20f980e8caa2f8f9.webp', 1),
(4, 2, 'Tailored Urban Bomber Jacket', 'Water-repellent technical fabric with thermal lining, sleek black finish.', 64.99, '25c86ddc7fa9df53.webp', 1),
(5, 3, 'Smart Ambient LED Desk Lamp', 'Adjustable color temperatures, wireless phone charging base, touch control.', 45.00, '30d55bba8a118a58.webp', 1),
(6, 4, 'Organic Botanical Night Serum 50ml', 'Hydrating hyaluronic acid and cold-pressed botanical oils for radiant skin.', 29.99, '342c770f9e49cc7b.webp', 1);

INSERT OR IGNORE INTO inventory (product_id, quantity) VALUES
(1, 45),
(2, 20),
(3, 60),
(4, 35),
(5, 80),
(6, 100);

-- Default Admin Account (Password: Admin@123)
INSERT OR IGNORE INTO customers (customer_id, first_name, last_name, e_mail, password_hash, role, phone_number, status) VALUES
(1, 'Shabber', 'Hussain', 'shabber10343@gmail.com', '$2b$12$041oYgUq/oR3pWzYd6XkH.u9e6j72aK5eM0mJ2F7wZ1x4k7E8mR1G', 'admin', '9876543210', 'active');
