from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import fitz
import io
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

@app.route('/')
def home():
    return jsonify({"message": "PDF Editor API", "status": "running"})

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "message": "PDF Editor API is running"})

@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    try:
        pdf_bytes = file.read()
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_data = []
        
        for page_num in range(len(pdf_doc)):
            page = pdf_doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            text_elements = []
            
            for block in blocks:
                if block['type'] == 0:
                    for line in block.get('lines', []):
                        for span in line.get('spans', []):
                            text_elements.append({
                                "text": span['text'],
                                "x": span['bbox'][0],
                                "y": span['bbox'][1],
                                "width": span['bbox'][2] - span['bbox'][0],
                                "height": span['bbox'][3] - span['bbox'][1],
                                "size": span['size']
                            })
            
            pages_data.append({
                "page_number": page_num,
                "width": page.rect.width,
                "height": page.rect.height,
                "text_elements": text_elements
            })
        
        pdf_doc.close()
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)
        
        return jsonify({
            "success": True,
            "filename": filename,
            "pages": pages_data,
            "total_pages": len(pages_data)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/edit', methods=['POST'])
def edit():
    try:
        data = request.get_json()
        filename = data.get('filename')
        edits = data.get('edits')
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        pdf_doc = fitz.open(filepath)
        
        for edit in edits:
            page = pdf_doc[edit['page']]
            instances = page.search_for(edit['old_text'])
            
            for inst in instances:
                page.draw_rect(inst, color=(1, 1, 1), fill=(1, 1, 1))
                page.insert_text((inst.x0, inst.y1), edit['new_text'], 
                               fontsize=edit.get('size', 12))
        
        output = io.BytesIO()
        pdf_doc.save(output)
        pdf_doc.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/pdf', 
                        as_attachment=True, download_name=f'edited_{filename}')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/render-page/<filename>/<int:page_num>')
def render(filename, page_num):
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        pdf_doc = fitz.open(filepath)
        page = pdf_doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = io.BytesIO(pix.tobytes("png"))
        img.seek(0)
        pdf_doc.close()
        return send_file(img, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
