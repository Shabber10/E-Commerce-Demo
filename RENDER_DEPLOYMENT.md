# 🚀 Deploying to Render (Render.com)

This application is fully pre-configured and ready for deployment on **[Render](https://render.com/)** as a Python Web Service.

---

## 📋 What Makes This App Render-Ready?

- ✅ **`render.yaml`**: Pre-configured Blueprint specification for 1-click deployment.
- ✅ **`gunicorn.conf.py`**: Production WSGI server settings auto-tuned for Render free tier (512MB RAM, 2 workers + 2 threads, port binding to `0.0.0.0:$PORT`).
- ✅ **`Procfile`**: Standard process file recognized by Render (`web: gunicorn app:app`).
- ✅ **`.python-version` & `runtime.txt`**: Pins Python runtime to `3.11.9`.
- ✅ **`/health` & `/healthz`**: Zero-downtime deployment health check endpoint.
- ✅ **Automatic Database & Uploads Init**: Automatically seeds the SQLite database (`smartcart.db`) and verifies `uploads/` folder permissions on startup.

---

## ⚡ Deployment Methods

### Method 1: Using Render Blueprint (Recommended - 1 Click)

1. Push your latest code to your **GitHub** or **GitLab** account:
   ```bash
   git add .
   git commit -m "Configure project for Render deployment"
   git push origin main
   ```
2. Log in to [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** in the top right corner and select **Blueprint**.
4. Connect your repository (`E-Commerce-Demo`).
5. Render will automatically detect `render.yaml` and configure:
   - **Name**: `smartcart-ecommerce`
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Health Check Path**: `/health`
   - **Environment Variables**: `SECRET_KEY`, `DB_ENGINE`, etc.
6. Click **Apply**. Render will build and deploy your application automatically.

---

### Method 2: Manual Web Service Setup

If you prefer to configure the Web Service manually:

1. In the Render Dashboard, click **New +** > **Web Service**.
2. Connect your Git repository.
3. Fill in the following details:
   | Setting | Value |
   | :--- | :--- |
   | **Name** | `smartcart-ecommerce` (or your preferred name) |
   | **Region** | Choose nearest to your users (e.g. Frankfurt, Oregon, Singapore) |
   | **Branch** | `main` |
   | **Runtime** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `gunicorn app:app` |
   | **Instance Type** | `Free` |

4. Scroll down to **Advanced** > **Health Check Path**:
   - Set to: `/health`

5. Under **Environment Variables**, add:
   | Key | Value | Notes |
   | :--- | :--- | :--- |
   | `PYTHON_VERSION` | `3.11.9` | Pins Python version |
   | `SECRET_KEY` | *(Click "Generate" or enter random string)* | Session encryption |
   | `DB_ENGINE` | `sqlite` | Default portable database |
   | `FLASK_DEBUG` | `false` | Production mode |
   | `STORE_UPI_ID` | `9704039617@fam` | Direct UPI payment QR ID |

6. Click **Create Web Service**.

---

## 🔑 Default Admin Account

Once deployed, you can access the admin dashboard at `/admin/login`:
- **Email**: `shabber10343@gmail.com`
- **Password**: `Admin@123`

*(You can update your admin email and password anytime from the Admin Profile page)*.

---

## ⚙️ Environment Variables Reference

| Environment Variable | Default Value | Description |
| :--- | :--- | :--- |
| `SECRET_KEY` | *(random)* | Secret key for signing session cookies |
| `DB_ENGINE` | `sqlite` | `sqlite` (portable, recommended for Render) or `mysql` |
| `SQLITE_DB_PATH` | `./smartcart.db` | Custom path to SQLite file (useful if using Render Persistent Disk) |
| `UPLOAD_FOLDER` | `./uploads` | Custom path to uploaded product photos |
| `STORE_UPI_ID` | `9704039617@fam` | UPI ID for customer QR code payments |
| `RAZORPAY_KEY_ID` | `rzp_test_eCommerceKey` | Razorpay API key ID for online card/netbanking payments |
| `RAZORPAY_KEY_SECRET` | `eCommerceSecretKey` | Razorpay API key secret |
| `MAIL_SERVER` | `smtp.gmail.com` | SMTP host for OTP verification emails |
| `MAIL_PORT` | `587` | SMTP port (587 for TLS) |
| `MAIL_USERNAME` | `your_email@gmail.com` | Gmail address for sending OTPs |
| `MAIL_PASSWORD` | `your_app_password` | Gmail 16-character App Password |
| `MAIL_DEFAULT_SENDER` | `your_email@gmail.com` | "From" address for verification emails |
| `DB_HOST` | `localhost` | MySQL host (only if `DB_ENGINE=mysql`) |
| `DB_USER` | `root` | MySQL user (only if `DB_ENGINE=mysql`) |
| `DB_PASSWORD` | `shabber` | MySQL password (only if `DB_ENGINE=mysql`) |
| `DB_NAME` | `e_commerce` | MySQL database name (only if `DB_ENGINE=mysql`) |

---

## 💾 Data Persistence on Render

### Free Tier (Default)
Render's free tier has an ephemeral disk. The database resets to initial seed data when the web service spins down or rebuilds. This is completely functional for demos and testing.

### Persistent Storage (Optional - Paid Starter Plan)
To persist newly added products, uploaded photos, and user orders across redeployments:
1. In Render, upgrade instance to **Starter** ($7/mo).
2. Add a **Persistent Disk**:
   - Mount Path: `/var/data`
   - Size: 1 GB
3. Set these Environment Variables:
   - `SQLITE_DB_PATH` = `/var/data/smartcart.db`
   - `UPLOAD_FOLDER` = `/var/data/uploads`
The app will automatically seed the starter database and product photos into the persistent disk on first boot.

Alternatively, connect an external managed MySQL or PostgreSQL database by setting `DB_ENGINE=mysql` and your connection details.
