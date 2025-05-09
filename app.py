from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
import os
from dxf_to_gcode import dxf_to_gcode, simulate_gcode, DEFAULT_FEED_RATE_XY, DEFAULT_FEED_RATE_Z, DEFAULT_SAFE_Z, DEFAULT_CUT_Z

# Configuration
global UPLOAD_FOLDER, OUTPUT_FOLDER, ALLOWED_EXTENSIONS
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'dxf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Utility to check file extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    # Determine DXF source: upload or refresh
    if 'file' in request.files and request.files['file'].filename:
        file = request.files['file']
        if not allowed_file(file.filename):
            return 'File type not allowed', 400
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        dxf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(dxf_path)
        base = os.path.splitext(filename)[0]
    elif 'filename' in request.form:
        base = request.form['filename']
        dxf_path = os.path.join(app.config['UPLOAD_FOLDER'], base + '.dxf')
    else:
        return 'No file provided', 400
    # Prepare G-code output path
    gcode_filename = f"{base}.gcode"
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    gcode_path = os.path.join(app.config['OUTPUT_FOLDER'], gcode_filename)
    # Read offsets
    offset_x = float(request.form.get('offset_x', 0))
    offset_y = float(request.form.get('offset_y', 0))
    # Read custom start point
    start_x = float(request.form.get('start_x', 0))
    start_y = float(request.form.get('start_y', 0))
    # Read custom end point
    end_x = float(request.form.get('end_x', 0))
    end_y = float(request.form.get('end_y', 0))
    # Generate and simulate
    dxf_to_gcode(dxf_path, gcode_path, DEFAULT_FEED_RATE_XY, DEFAULT_FEED_RATE_Z, DEFAULT_SAFE_Z, DEFAULT_CUT_Z, offset_x, offset_y, start_x, start_y, end_x, end_y)
    simulate_gcode(gcode_path, offset_x, offset_y, start_x, start_y, end_x, end_y)
    return send_file(os.path.join(os.getcwd(), 'simulation_plot.html'))

@app.route('/download', methods=['GET'])
def download_gcode():
    fname = request.args.get('filename')
    if not fname:
        return 'Filename required', 400
    path = os.path.join(app.config['OUTPUT_FOLDER'], fname + '.gcode')
    if not os.path.exists(path):
        return 'Not found', 404
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
