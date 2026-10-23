# SmartPlate: Serve Smart. Waste Less.
**PCCOE Campus Canteen Food-Demand Estimation & Food Waste Mitigation System**  
**Design Thinking (DT) FA2 SPRINT Implementation & Poster Presentation (25 Marks, CO3, CO4)**

---

## 👥 Team & Submission Details
- **Division:** Division D (SY Computer Engineering)
- **Institution:** Pimpri Chinchwad College of Engineering (PCCOE), Pune
- **Team Members:**
  - Prem Kothari (PRN: 125B1B231)
  - Aniket Jadhav (PRN: 125B1B214)
  - Prathmesh Vagshette(PRN: 125B1B254)

## 🌐 Deploying on Render

This repository includes `requirements.txt` and `render.yaml` for Render deployment.
Create a new **Web Service** connected to this repository and use:
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT`

Set an environment variable named `SECRET_KEY` to a long random value in Render (the Blueprint configuration can generate one automatically). The SQLite database on Render's free instance is ephemeral: data may reset or be lost after restarts/redeploys. Use a persistent database for real-world use.

**Demo login warning:** the project seeds `admin@pccoe.edu` with password `admin1234`. Change/remove this demo login before exposing the application beyond a controlled academic demonstration.

## 🚀 How to Run the Project

### Option A: 1-Click Launch (Recommended)
- Double-click **`Run_SmartPlate.bat`** to start the web application and automatically launch the browser at `http://127.0.0.1:5000`.
- Double-click **`View_Poster.bat`** to immediately open the FA2 Academic Poster in your browser.

### Option B: Terminal Launch
1. Open a terminal in this directory.
2. Install dependencies (Flask & QRCode):
   ```bash
   pip install flask qrcode
   ```
3. Run the application:
   ```bash
   python run_with_browser.py
   # or
   python app.py
   ```
4. Access in your browser:
   - **Main Website:** `http://127.0.0.1:5000`
   - **DT FA2 Academic Poster:** `http://127.0.0.1:5000/poster` (or open `poster.html` directly)
   - **Student Portal:** `http://127.0.0.1:5000/student`
   - **Kitchen Operations:** `http://127.0.0.1:5000/staff`
   - **Analytics & Waste Hub:** `http://127.0.0.1:5000/admin`

---

## 🔑 Login Credentials

- **Unified Admin & Canteen Operations:**  
  - Email: `admin@pccoe.edu`  
  - Password: `admin1234`
- **Student Portal Registration:**  
  - Register any student email at `http://127.0.0.1:5000/register` (Only student registrations allowed).

---

## 📄 Exporting the Academic Poster as PDF
1. Open `poster.html` or go to `http://127.0.0.1:5000/poster`.
2. Click **"Print / Save as PDF"** on the floating top toolbar (or press `Ctrl + P`).
3. Set Destination to **Save as PDF**, Orientation to **Landscape**, and Paper size to **A3**.
4. Save the file as `076_084_092_Poster.pdf` for submission in your Google Drive group folder.

---

## 🛠️ Tech Stack & Features
- **Backend:** Python (Flask), SQLite (`smartplate.db`)
- **Frontend:** HTML5, CSS3, JavaScript, Chart.js, FontAwesome
- **Design Thinking Deliverables:**
  - 8-Cluster Affinity Diagram with physical sticky note proof
  - 2 Personas (Student & Head Chef)
  - 5-Stage Google Sprint & d.school Framework implementation
  - Working dynamic demand estimation algorithm
  - Leftover waste logging and CSV audit exports
  - Aligned with UN SDG 12 (Target 12.3) and SDG 2
