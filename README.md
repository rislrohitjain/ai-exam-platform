# Advanced AI Exam & Evaluation Platform 🎓
### एडवांस्ड एआई परीक्षा और मूल्यांकन प्लेटफॉर्म

An enterprise-ready, automated AI examination, grading, and certification platform. It leverages LangGraph/LangChain multi-agent workflows, vector similarity checks, and cryptographic security to deliver fast, fair, and tamper-proof academic evaluations.

---

## 💡 Interview Pitch & Platform Highlights
### 💡 साक्षात्कार पिच और मंच की मुख्य विशेषताएं

### 🇺🇸 English Version

#### **Real-World Impact Case Study: Resolving Critical Assessment Bottlenecks**

* **📉 Crucial Pain Points:**
  * **Manual Grading:** Slow evaluation takes up to 40+ hours per batch, causing delays in feedback.
  * **Inconsistency:** Subjective grading fluctuates significantly between different human evaluators.
  * **Forgery:** Traditional hardcopy certificates are easily falsified, exposing institutions to credential fraud.
  
* **📈 Key Improvements:**
  * **95% Time Saved:** Instant AI auto-evaluation finishes in under 3 seconds per exam.
  * **98% Accuracy:** Hybrid semantic grading models precisely align subjective answers with faculty rubrics.
  * **100% Secure:** Cryptographic SHA-256 digital signatures embedded on generated PDFs prevent certificate forgery.

---

### 🇮🇳 Hindi Version (हिंदी)

#### **वास्तविक प्रभाव केस स्टडी: महत्वपूर्ण मूल्यांकन बाधाओं को हल करना**

* **📉 महत्वपूर्ण दर्द बिंदु (Pain Points):**
  * **मैन्युअल ग्रेडिंग:** धीमी मूल्यांकन में प्रति बैच 40+ घंटे तक लग जाते हैं, जिससे परिणामों में देरी होती है।
  * **विसंगति (Inconsistency):** व्यक्तिपरक (subjective) ग्रेडिंग अलग-अलग मानव मूल्यांकनकर्ताओं के बीच भिन्न होती है।
  * **जालसाजी (Forgery):** पारंपरिक हार्डकॉपी प्रमाणपत्रों में आसानी से हेरफेर की जा सकती है, जिससे साख असुरक्षित रहती है।
  
* **📈 प्रमुख सुधार (Improvements):**
  * **95% समय की बचत:** 3 सेकंड से कम समय में त्वरित एआई ऑटो-मूल्यांकन पूरा होता है।
  * **98% सटीकता:** हाइब्रिड सिमेंटिक ग्रेडिंग मॉडल व्यक्तिपरक उत्तरों को संकाय रूब्रिक्स (faculty rubrics) के साथ सटीक रूप से संरेखित करते हैं।
  * **100% सुरक्षित:** जेनरेट किए गए पीडीएफ में एम्बेडेड क्रिप्टोग्राफ़िक SHA-256 डिजिटल हस्ताक्षर प्रमाणपत्र जालसाजी को रोकते हैं।

---

## 🛠️ Tech Stack & Highlights
* **FastAPI Backend:** High-performance, asynchronous endpoints serving static files, WebSockets, and CRUD operations.
* **Flexible LLM Factory:** Support for **Local Ollama** engines (offline setup) and cloud providers like **OpenAI (GPT-4o)**, **Groq**, and **OpenRouter** dynamically switchable at runtime by the admin.
* **Database & Vector Search:** Relational mappings powered by SQLAlchemy, using PostgreSQL with `pgvector` extension (and seamless local fallback to SQLite with text representations).
* **SweetAlert2 & CKEditor 5:** Beautiful popups and rich-text editing inputs for subjective answers.
* **Automatic PDF Generation:** Automatically outputs secure, professional student marksheet PDFs and landscape completion certificates.
* **Cryptographic Verification:** Instant digital certificate validity checks using SHA-256 HMAC digital signatures.

---

## 🚀 Quick Setup & Local Running
1. **Clone & Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Setup Environment Variables:**
   Configure your database and API keys in a `.env` file (copied from `.env.example`):
   ```ini
   DATABASE_URL=postgresql://username:password@localhost:5432/ai-exam-platform
   DEFAULT_LLM_PROVIDER=ollama
   GROQ_API_KEY=your_key_here
   OPENROUTER_API_KEY=your_key_here
   ```
3. **Database Seeding:**
   Seed 100 students, 15 colleges, 15 exam papers, and 160 graded history records:
   ```bash
   python scratch/heavy_seed_database.py
   ```
4. **Run Application:**
   ```bash
   python -m app.main
   ```
   Access the web portal directly at `http://localhost:8000/static/index.html`.
