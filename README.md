# E-Commerce Demo - Flask Web Application

E-Commerce Demo is a complete full-stack E-Commerce web application developed using **Python Flask**, **SQLite / MySQL**, **HTML5/CSS3**, and **Vanilla JavaScript**.

---

## 🚀 Features

### 🛒 Customer Storefront
- **Catalog & Search:** Browse products by categories, search items by keywords, and filter by price.
- **Single Product Details:** View high-resolution photos, descriptions, inventory status, and price.
- **Shopping Cart:** Add items to cart with **Amazon-style instant AJAX updates** (no page reload), increase/decrease quantities, and auto-calculate totals.
- **Checkout & Razorpay Payment:** Shipping address management and seamless online payment integration with Razorpay.
- **Order Tracking & Tax Invoice:** View order history, order status, and download/print computer-generated PDF tax invoices (`xhtml2pdf`).
- **User Authentication:** Registration, Login with bcrypt password hashing, and user dashboard.

### 🛡️ Administrator Panel
- **Admin Authentication:** Dedicated Admin Sign-up with 6-digit email OTP verification and secure bcrypt login.
- **Protected Admin Dashboard:** Overview metrics including total active products, categories, customer orders, and registered users.
- **Product Management (CRUD):** Add products with image uploads, edit product information, upload replacement photos, and delete products.
- **Category Management:** Create, manage, and delete product classifications.
- **Order Management:** View incoming customer orders, check transaction IDs, and update dispatch/delivery status.
- **Admin Profile & Settings:** Update admin personal details, change admin password, and update profile avatar.

---

## 🛠️ Tech Stack
- **Backend:** Python 3, Flask
- **Database:** MySQL (using `mysql-connector-python`)
- **Security:** `bcrypt` password hashing, session-based route protection
- **PDF Generation:** `xhtml2pdf`
- **Email / OTP:** Python SMTP / Gmail App Password
- **Payment Gateway:** Razorpay API
- **Frontend:** HTML5, Vanilla CSS3 (responsive design), JavaScript Fetch API

---

## 💻 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Shabber10/E-Commerce-Demo.git
   cd E-Commerce-Demo
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Mac/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Database Configuration:**
   - Ensure MySQL is running on `localhost`.
   - Update database credentials in `config.py` if needed:
     ```python
     DB_HOST = "localhost"
     DB_USER = "root"
     DB_PASSWORD = "your_password"
     DB_NAME = "e_commerce"
     ```
   - On first run, `init_db()` will automatically create the database and required tables from `db/schema.sql`.

5. **Run the Application:**
   ```bash
   python app.py
   ```
   Open your browser and navigate to: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)

---

## 📌 Project Structure
```text
E-Commerce-Demo/
├── app.py                  # Main Flask routes and controllers
├── config.py               # Database and application configuration
├── email_utils.py          # SMTP email and OTP delivery utilities
├── requirements.txt        # Python package dependencies
├── .gitignore              # Files excluded from version control
├── README.md               # Project documentation
│
├── db/
│   └── schema.sql          # MySQL database schema and initial data
│
├── static/
│   ├── css/
│   │   └── style.css       # Responsive custom CSS stylesheets
│   └── js/
│
├── templates/
│   ├── base.html           # Base layout template with responsive navbar
│   ├── admin/              # Admin dashboard, product CRUD, and profile
│   ├── landing/            # Store catalog and search filtering
│   ├── login/              # Login, register, OTP verification
│   └── website/            # Cart, checkout, orders, invoices
│
├── uploads/                # User uploaded product photos & avatars
└── utils/
    └── pdf_generator.py    # HTML to PDF conversion utility (xhtml2pdf)
```
