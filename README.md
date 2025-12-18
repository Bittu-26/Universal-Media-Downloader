# Universal Media Downloader

A lightweight, production-ready web application that allows users to download videos and audio from supported platforms using **yt-dlp**. Built with **Flask**, designed for simple UI usage, and deployable on **Render** with FFmpeg support.

---

## 🚀 Features

* 🎥 Download videos in multiple resolutions
* 🎵 Extract audio (MP3) from videos
* ⚡ Fast downloads powered by yt-dlp
* 🌐 Simple static HTML frontend
* 🐍 Flask-based backend API
* 🔊 FFmpeg support for media conversion

---

## 🗂 Project Structure

```
UniversalDownloader/
├── app.py                # Flask application entry point
├── requirements.txt      # Python dependencies
├── render.yaml           # Render deployment configuration
├── static/
│   └── index.html        # Frontend UI
├── downloads/            # Downloaded files (runtime)
```

---

## 🧰 Tech Stack

* **Backend:** Python, Flask
* **Downloader:** yt-dlp
* **Media Processing:** FFmpeg
* **Frontend:** HTML, CSS, JavaScript
* **Deployment:** Render

---

## 📦 Requirements

* Python 3.9+
* FFmpeg
* pip

All dependencies are listed in `requirements.txt`.

---

## ▶️ Running Locally

### 1️⃣ Clone the repository

```bash
git clone https://github.com/Bittu-26/Universal-Media-Downloader.git
cd Universal-Media-Downloader
```

### 2️⃣ Create virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Install FFmpeg

* **Windows:** [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
* **Linux:** `sudo apt install ffmpeg`
* **Mac:** `brew install ffmpeg`

### 5️⃣ Run the server

```bash
python app.py
```

App will be available at:

```
http://127.0.0.1:5000
```

---

## 🌍 Deployment on Render

This project is preconfigured for Render using `render.yaml`.

### Steps:

1. Push the repository to GitHub
2. Go to [https://render.com](https://render.com)
3. New → Web Service
4. Connect the GitHub repo
5. Render auto-detects `render.yaml`
6. Click **Deploy**

FFmpeg and dependencies will be installed automatically.

---

## ⚠️ Platform Limitations

* ❌ **Vercel** is not supported (no FFmpeg / yt-dlp execution)
* ❌ Not intended for heavy concurrent downloads on free plans

Recommended platform: **Render**

---

## 🔐 Legal Disclaimer

This tool is for **educational purposes only**.

Downloading copyrighted content without permission may violate the terms of service of content providers.

The author is not responsible for misuse of this application.

---

## 📄 License

MIT License

---

## 👤 Author

**Ayush (Bittu-26)**

GitHub: [https://github.com/Bittu-26](https://github.com/Bittu-26)

---

## ⭐ Support

If you find this project useful, please ⭐ star the repository.
