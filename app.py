from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import mysql.connector
from PIL import Image
import io
import re
import cv2
import numpy as np
from openbharatocr.ocr.aadhaar import extract_front_aadhaar_details, extract_back_aadhaar_details
from openbharatocr.ocr.pan import extract_pan_details

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# MySQL Configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "aadhaar_details"
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        print("Database Connection Successful")
        return conn
    except Exception as e:
        print(f"Database Connection Error: {str(e)}")
        return None

def format_date(dob):
    try:
        return datetime.strptime(dob, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

def clean_address(address):
    cleaned_address = re.sub(r'[^\w\s,/-]', '', address)
    cleaned_address = re.sub(r'\s+', ' ', cleaned_address).strip()
    return cleaned_address

def extract_father_name_from_address(address):
    match = re.search(r'C/O[:\s]+([\w\s]+),', address, re.IGNORECASE)
    return match.group(1).strip() if match else "Not Available"

def preprocess_aadhaar_back(image_path):
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    processed_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    kernel = np.ones((1, 1), np.uint8)
    processed_img = cv2.morphologyEx(processed_img, cv2.MORPH_CLOSE, kernel)
    
    temp_filename = "temp_processed_back.png"
    cv2.imwrite(temp_filename, processed_img)
    
    return temp_filename

#function to extract aadhar details
def extract_aadhaar_details(front_image, back_image=None):
    try:
        temp_front = io.BytesIO()
        front_image.save(temp_front, format="PNG")
        temp_front.seek(0)

        extracted_text_front = extract_front_aadhaar_details(temp_front)
        extracted_text_back = {}
        
        if back_image:
            temp_back_path = "aadhaar_back.png"
            back_image.save(temp_back_path, format="PNG")
            processed_image_path = preprocess_aadhaar_back(temp_back_path)
            extracted_text_back = extract_back_aadhaar_details(processed_image_path)

        details = {
            "name": extracted_text_front.get("Full Name", "").strip(),
            "gender": extracted_text_front.get("Gender", "").strip(),
            "date_of_birth": format_date(extracted_text_front.get("Date/Year of Birth", "").strip()),
            "fathers_name": extract_father_name_from_address(extracted_text_back.get("Address", "")) if extracted_text_back else "Not Available",
            "aadhar_no": extracted_text_front.get("Aadhaar Number", "").strip(),
            "street_address": clean_address(extracted_text_back.get("Address", "")) if extracted_text_back else "Not Available"
        }

        #check if any key has an empty value
        if any(value in ["", "Not Available", None] for value in details.values()):
            return{"error":"Failed to extract Aadhaar details. Please check the image quality."}

        return details
    except Exception as e:
        return {"error": f"Failed to extract Aadhaar details: {str(e)}"}

def extract_pan_data(image):
    try:
        if image.mode == "RGBA":
            image = image.convert("RGB")
        temp_pan_path = "temp_pan.png"
        image.save(temp_pan_path, format="PNG") 
        with open(temp_pan_path, "rb") as pan_file:
            extracted_text_pan = extract_pan_details(pan_file)
        details = {
            "name": extracted_text_pan.get("Full Name", "").strip(),
            "fathers_name": extracted_text_pan.get("Parent's Name", "").strip(),
            "date_of_birth": format_date(extracted_text_pan.get("Date of Birth", "").strip()),
            "pan_no": extracted_text_pan.get("PAN Number", "").strip()
        } 

        #check if any key has an empty value
        if any(value in ["", "Not Available", None] for value in details.values()):
            return{"error":"Failed to extract PAN details. Please check the image quality."}

        return details      
    except Exception as e:
        return {"error": f"failed to extract pan details: {str(e)}"}

@app.route('/upload_aadhaar', methods=['POST'])
def upload_aadhaar():
    if 'file_front' not in request.files:
        return jsonify({"error": "Front side of Aadhaar is required"}), 400

    file_front = request.files['file_front']
    file_back = request.files.get('file_back')

    try:
        front_image = Image.open(io.BytesIO(file_front.read()))
        back_image = Image.open(io.BytesIO(file_back.read())) if file_back else None
        extracted_data = extract_aadhaar_details(front_image, back_image)

        # Ensure extracted_data is not empty or None before returning it
        if not extracted_data:
            return jsonify({"error": "Failed to extract Aadhaar details"}), 400

        return jsonify({"message": "Success", "data": extracted_data}), 200

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500


@app.route('/upload_pan', methods=['POST'])
def upload_pan():
    if 'file' not in request.files:
        return jsonify({"error": "PAN card image is required"}), 400
    
    file = request.files['file']
    
    try:
        image = Image.open(io.BytesIO(file.read()))
        extracted_data = extract_pan_data(image)
        
        return jsonify({"message": "Success", "data": extracted_data}), 200

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

def save_to_database(data):
    try:
        connection = get_db_connection()
        if not connection:
            return {"error": "Database connection failed"}
        
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM candidates WHERE aadhar_no = %s", (data.get("aadhar_no"),))
        (record_exists,) = cursor.fetchone()

        if record_exists:
            update_query = """
            UPDATE candidates SET name=%s, gender=%s, date_of_birth=%s, fathers_name=%s, street_address=%s
            WHERE aadhar_no=%s
            """
            values = (
                data.get("name"), data.get("gender"), data.get("date_of_birth"),
                data.get("fathers_name"), data.get("street_address"), data.get("aadhar_no")
            )
            cursor.execute(update_query, values)
            message = "Data updated successfully!"
        else:
            insert_query = """
            INSERT INTO candidates (name, gender, date_of_birth, aadhar_no, fathers_name, street_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            values = (
                data.get("name"), data.get("gender"), data.get("date_of_birth"),
                data.get("aadhar_no"), data.get("fathers_name"), data.get("street_address")
            )
            cursor.execute(insert_query, values)
            message = "Data saved successfully!"

        connection.commit()
        cursor.close()
        connection.close()
        return {"message": message}

    except Exception as e:
        return {"error": str(e)}

@app.route('/save_aadhaar', methods=['POST'])
def save_aadhaar():
    data = request.json
    result = save_to_database(data)
    return jsonify(result), 200 if "message" in result else 500

def save_pan_to_database(data):
    try:
        connection = get_db_connection()
        if not connection:
            return {"error": "Database connection failed"}
        
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM candidates WHERE pan_no = %s", (data.get("pan_no"),))
        (record_exists,) = cursor.fetchone()

        if record_exists:
            update_query = """
            UPDATE candidates SET name=%s, fathers_name=%s, date_of_birth=%s
            WHERE pan_no=%s
            """
            values = (
                data.get("name"), data.get("fathers_name"), data.get("date_of_birth"), data.get("pan_no")
            )
            cursor.execute(update_query, values)
            message = "PAN data updated successfully!"
        else:
            insert_query = """
            INSERT INTO candidates (name, fathers_name, date_of_birth, pan_no)
            VALUES (%s, %s, %s, %s)
            """
            values = (
                data.get("name"), data.get("fathers_name"), data.get("date_of_birth"), data.get("pan_no")
            )
            cursor.execute(insert_query, values)
            message = "PAN data saved successfully!"

        connection.commit()
        cursor.close()
        connection.close()
        return {"message": message}

    except Exception as e:
        return {"error": str(e)}

@app.route('/save_pan', methods=['POST'])
def save_pan():
    data = request.json
    result = save_pan_to_database(data)
    return jsonify(result), 200 if "message" in result else 500

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
