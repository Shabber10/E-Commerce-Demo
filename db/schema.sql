-- ==========================================================
-- E-Commerce Database Schema
-- Database: e_commerce
-- Roles: admin, staff, user
-- ==========================================================

CREATE DATABASE IF NOT EXISTS e_commerce 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE e_commerce;

-- ----------------------------------------------------------
-- 1. CUSTOMERS / USERS TABLE
-- Handles authentication, 3 roles (admin, staff, user), and profiles
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    customer_id INT PRIMARY KEY AUTO_INCREMENT, 
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    e_mail VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'staff', 'user') NOT NULL DEFAULT 'user',
    phone_number VARCHAR(20) NOT NULL DEFAULT '',
    status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_customer_email (e_mail),
    INDEX idx_customer_role (role)
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 2. ADDRESS TABLE
-- Customer delivery addresses (supports multiple addresses per customer)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS address (
    address_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    address_line VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    pincode VARCHAR(20) NOT NULL,
    country VARCHAR(50) NOT NULL DEFAULT 'INDIA',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 3. CATEGORIES TABLE
-- Product classifications
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT, 
    category_name VARCHAR(100) NOT NULL UNIQUE,
    category_image VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 4. PRODUCTS TABLE
-- Catalog items with details, pricing, and category reference
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    product_id INT PRIMARY KEY AUTO_INCREMENT,
    category_id INT NOT NULL,
    product_name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT NULL,
    price DECIMAL(10,2) NOT NULL,
    image_url VARCHAR(255) NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT,
    INDEX idx_product_active (is_active),
    INDEX idx_product_category (category_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 5. INVENTORY TABLE
-- Stock tracking per product (1:1 with products)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL UNIQUE,
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 6. CART TABLE
-- Active user shopping cart
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS cart (
    cart_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 7. CART_ITEMS TABLE
-- Line items inside a cart
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS cart_items (
    cart_item_id INT PRIMARY KEY AUTO_INCREMENT,
    cart_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_cart_product (cart_id, product_id),
    FOREIGN KEY (cart_id) REFERENCES cart(cart_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 8. ORDERS TABLE
-- Customer checkout orders
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    order_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    address_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_status ENUM('pending', 'processing', 'shipped', 'delivered', 'cancelled') NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address(address_id) ON DELETE RESTRICT,
    INDEX idx_order_customer (customer_id),
    INDEX idx_order_status (order_status)
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 9. ORDER_ITEMS TABLE
-- Items snapshots tied to orders
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
    price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 10. PAYMENTS TABLE
-- Payment transactions associated with orders
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    payment_status ENUM('pending', 'completed', 'failed', 'refunded') NOT NULL DEFAULT 'pending',
    amount_paid DECIMAL(10,2) NOT NULL,
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    transaction_id VARCHAR(100) NOT NULL UNIQUE,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 11. SHIPMENTS TABLE
-- Delivery shipment tracking
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    shipment_status VARCHAR(50) NOT NULL DEFAULT 'Order Placed',
    delivery_date TIMESTAMP NULL,
    address_id INT NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    tracking_number VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (address_id) REFERENCES address(address_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ----------------------------------------------------------
-- 12. PASSWORD RESETS TABLE (OTP Verification)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_resets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    otp VARCHAR(6) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_reset_email (email)
) ENGINE=InnoDB;

-- ==========================================================
-- SEED DATA: Starter Categories, Products & Inventory
-- ==========================================================

INSERT IGNORE INTO categories (category_id, category_name) VALUES
(1, 'Electronics & Gadgets'),
(2, 'Men & Women Fashion'),
(3, 'Home & Living'),
(4, 'Beauty & Personal Care');

INSERT IGNORE INTO products (product_id, category_id, product_name, description, price, is_active) VALUES
(1, 1, 'Pro Wireless Noise-Cancelling Headphones', 'Ultra-low latency audio, 40-hour battery life, memory foam cushions.', 149.99, 1),
(2, 1, 'Ultra-Slim OLED 4K Smart Monitor 27"', '144Hz refresh rate, HDR1000, USB-C single cable display setup.', 399.00, 1),
(3, 2, 'Classic Minimalist Chronograph Watch', 'Stainless steel case with genuine Italian leather strap, 50m water resistant.', 89.50, 1),
(4, 2, 'Tailored Urban Bomber Jacket', 'Water-repellent technical fabric with thermal lining, sleek black finish.', 64.99, 1),
(5, 3, 'Smart Ambient LED Desk Lamp', 'Adjustable color temperatures, wireless phone charging base, touch control.', 45.00, 1),
(6, 4, 'Organic Botanical Night Serum 50ml', 'Hydrating hyaluronic acid and cold-pressed botanical oils for radiant skin.', 29.99, 1);

INSERT IGNORE INTO inventory (product_id, quantity) VALUES
(1, 45),
(2, 20),
(3, 60),
(4, 35),
(5, 80),
(6, 100);

-- Default Admin Account (Password: Admin@123)
INSERT IGNORE INTO customers (customer_id, first_name, last_name, e_mail, password_hash, role, phone_number, status) VALUES
(1, 'Shabber', 'Hussain', 'shabber10343@gmail.com', '$2b$12$041oYgUq/oR3pWzYd6XkH.u9e6j72aK5eM0mJ2F7wZ1x4k7E8mR1G', 'admin', '9876543210', 'active');

