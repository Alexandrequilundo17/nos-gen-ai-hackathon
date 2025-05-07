from flask import Flask, request, send_file, render_template_string, redirect, url_for
import os
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
import requests
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

API_KEY = "AIzaSyDM_C8QeGffbN2UV_1UEGedzk_AesiaVqY"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

def generate_content(prompt_text: str, temperature: float) -> str:
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": temperature}
    }
    response = requests.post(API_URL, headers=headers, json=body)
    if response.status_code == 200:
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text']
    else:
        return "Error: Unable to generate content."

class PDFTextExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    def extract_text(self):
        text_list = []
        with fitz.open(self.pdf_path) as doc:
            for page in doc:
                text_list.append(page.get_text())
        return ''.join(text_list)

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Medical PDF Anonymizer</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
        <style>
            body { background-color: #f8f9fa; }
            .container { max-width: 800px; margin-top: 50px; }
            .card { box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card p-4">
                <h1 class="text-center mb-4">Medical PDF Anonymizer</h1>
                <p class="text-muted text-center mb-4">Upload your medical PDF to anonymize and analyze its content.</p>
                <form action="/upload" method="post" enctype="multipart/form-data">
                    <div class="form-group">
                        <label for="file">Select PDF File:</label>
                        <input type="file" class="form-control-file" id="file" name="file" accept=".pdf" required>
                    </div>
                    <button type="submit" class="btn btn-primary btn-block">Upload and Anonymize</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    ''')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    if file and file.filename.endswith('.pdf'):
        unique_id = str(uuid.uuid4())
        pdf_filename = f"{unique_id}.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
        file.save(pdf_path)
        
        extractor = PDFTextExtractor(pdf_path)
        raw_text = extractor.extract_text()
        
        anonymize_prompt = (
            "You are an expert in medical data privacy. Anonymize the following medical text by removing or replacing all personally identifiable information "
            "(such as names, dates of birth, medical record numbers, addresses, etc.) while preserving the medical content for analysis: \n\n" + raw_text
        )
        anonymized_text = generate_content(anonymize_prompt, 0.0)
        
        txt_filename = f"{unique_id}.txt"
        txt_path = os.path.join(app.config['UPLOAD_FOLDER'], txt_filename)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(anonymized_text)
        
        return redirect(url_for('report', id=unique_id))
    else:
        return "Invalid file type. Please upload a PDF.", 400

@app.route('/report/<id>', methods=['GET', 'POST'])
def report(id):
    txt_filename = f"{id}.txt"
    txt_path = os.path.join(app.config['UPLOAD_FOLDER'], txt_filename)
    if not os.path.exists(txt_path):
        return "Report not found", 404
    
    answer = None
    if request.method == 'POST':
        question = request.form.get('question')
        if question:
            with open(txt_path, 'r', encoding='utf-8') as f:
                anonymized_text = f.read()
            answer_prompt = (
                "You are a highly experienced medical professional. Based on the following anonymized medical report: \n\n" + anonymized_text + 
                "\n\nProvide a detailed and accurate answer to this question: " + question
            )
            answer = generate_content(answer_prompt, 0.0)
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Anonymized Medical Report</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
        <style>
            body { background-color: #f8f9fa; }
            .container { max-width: 800px; margin-top: 50px; }
            .card { box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            .answer-box { background-color: #e9ecef; padding: 15px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card p-4">
                <h1 class="text-center mb-4">Anonymized Medical Report</h1>
                <p class="text-muted text-center mb-4">
                    Your report has been anonymized. Download it below or ask questions about its content.
                </p>
                <div class="text-center mb-4">
                    <a href="{{ url_for('download', id=id) }}" class="btn btn-success">Download Anonymized Report</a>
                </div>
                <h2>Ask a Medical Question</h2>
                <form method="post">
                    <div class="form-group">
                        <label for="question">Your Question:</label>
                        <input type="text" class="form-control" id="question" name="question" placeholder="E.g., What is the diagnosis?" required>
                    </div>
                    <button type="submit" class="btn btn-primary btn-block">Submit Question</button>
                </form>
                {% if answer %}
                <h2 class="mt-4">Answer</h2>
                <div class="answer-box">
                    <p>{{ answer }}</p>
                </div>
                {% endif %}
            </div>
        </div>
    </body>
    </html>
    ''', id=id, answer=answer)

@app.route('/download/<id>')
def download(id):
    txt_filename = f"{id}.txt"
    txt_path = os.path.join(app.config['UPLOAD_FOLDER'], txt_filename)
    if os.path.exists(txt_path):
        return send_file(txt_path, as_attachment=True, download_name="anonymized_report.txt")
    else:
        return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True)
