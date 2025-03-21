#working code for adhar pan and credence all pages and payslips and results
import os
import json
import base64
import requests
import time
from flask import Flask, request, jsonify
from pdf2image import convert_from_path
from PIL import Image


app = Flask(__name__)

# OCR API URL
API_URL = "http://172.16.11.25:11434/api/generate"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Required keys
REQUIRED_KEYS = ["documentType", "documentNumber", "dateOfBirthorIssue", "FatherGuardianName", "nameAsOnDoc", "Gender", "Address"]

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def pdf_to_images(pdf_path):
    return convert_from_path(pdf_path)

def process_file(file):
    images_base64 = []
    file_ext = file.filename.lower().split(".")[-1]
    file_path = f"temp_upload.{file_ext}"
    file.save(file_path)
    
    if file_ext == "pdf":
        images = pdf_to_images(file_path)
        for i, img in enumerate(images):
            img_path = f"temp_page_{i}.png"
            img.save(img_path, "PNG")
            images_base64.append(encode_image(img_path))
            os.remove(img_path)
    else:
        images_base64.append(encode_image(file_path))
    
    os.remove(file_path)
    return images_base64

def save_image(base64_string, filename):
    """Save a base64 string as an image file."""
    image_data = base64.b64decode(base64_string)  # Decode the base64 string
    image_path = os.path.join(UPLOAD_FOLDER, filename)
    
    with open(image_path, "wb") as f:
        f.write(image_data)  # Write image file
    
    return image_path



def make_api_request(payload):
    headers = {"Content-Type": "application/json"}
    response = requests.post(API_URL, json=payload, headers=headers, verify=False)
    return response


def crop_candidate_photo(image_path):
    image = Image.open(image_path)
    width, height = image.size
    
    left = int(width * 0.75)
    top = int(height * 0.25)
    right = int(width * 0.95)
    bottom = int(height * 0.35)
    
    cropped_image = image.crop((left, top, right, bottom))
    photo_path = os.path.join(UPLOAD_FOLDER, "candidate_photo.png")
    cropped_image.save(photo_path, "PNG")
    return photo_path


def determine_document_type(images_base64):
    if not images_base64:
        return None  # Ensure we have at least one image

    # Process only the first page for document type classification
    payload = {
        "model": "llama3.2-vision",
        "prompt": """Analyze the provided image and classify it as one of the following:
            - 'Aadhaar Card' (if Aadhaar-related words like "Aadhaar", "Unique Identification", "UIDAI" are present.
            this word can be small letters also).
            - 'PAN Card' (if words like "Income Tax Department", "Permanent Account Number", "Govt. of India" appear
            this words can be small letters also).
            - 'Credence' (if the word 'Credence' is found in the first page of text).
            If 'Credence' appears anywhere in the extracted text of the **first page**, return 'Credence' without considering other document types
            it can be all letters small case also.
            - 'Pay Slip' (if words like 'Pay Slip', 'Salary Statement', 'Net Pay Amount' appears on that document).
            - 'result' (if words like 'Marks', 'grade', 'Hall Ticket Number', 'Roll No', 'University' appears on that document)
            Always return only one of these five options.

            """,
        "images": [images_base64[0]],  # Only checking the first page
        "temperature": 0.0,
        "stream": False
    }

    response = make_api_request(payload)

    if response.status_code == 200:
        try:
            document_type_response = response.json().get("response", "").strip()
            print(document_type_response)
            if "Credence" in document_type_response:
                return "Credence Document"
            elif "Aadhaar" in document_type_response:
                return "Aadhaar Card"
            elif "PAN" in document_type_response:
                return "PAN Card"
            elif "pay slip" in document_type_response or "payslip" in document_type_response or "salary statement" in document_type_response:
                return "Pay Slip"
            elif "marks" in document_type_response or "grades" in document_type_response or "roll number" in document_type_response or "student's name" in document_type_response or "details of their academic performance" in document_type_response or "University" in document_type_response:
                return "Result"
            else:
                return "Unknown Document"  # Instead of None, return an explicit unknown type
            
        except json.JSONDecodeError:
            print("Error parsing API JSON response")

    return "Unknown Document"

@app.route("/ocr", methods=["POST"])
def ocr_extraction():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    images_base64 = process_file(file)
    document_type = determine_document_type(images_base64)
    print(document_type)
    
    if not document_type:
        return jsonify({"error": "Could not determine document type"}), 400

    if document_type in ["Aadhaar Card", "PAN Card"]:
        # Define the extraction prompt
        prompt_text = (
                "Act as an OCR assistant. Analyze the provided (PDF or image) and return the extracted fields in JSON format."
                "Extract the following details if present in the (PDF or image):"
                "Document Type(if it is aadhaar card then show Aadhaar card if it is pan card then show PAN card)"
                "Document Number(aadhard card or pan card number)"
                "Date of Birth/Issue(show in date formats it could be DOB)"
                "Name as on Document(first line of name)"
                "Father's/Guardian's Name(Father's Name line directly below the Name)"
                "Gender, and Address(show only address if it is here not any sentences and if not address"
                "then show only N/A)"
                "If any field is missing, return 'NA' for that field."
                "from extracted details I want only specific information"
        )
        
        extraction_payload = {
            "model": "llama3.2-vision",
            "prompt": prompt_text,
            "images": images_base64,
            "temperature": 0.0,
            "stream": False
        }

        valid_responses = []
        for _ in range(3):
            response = make_api_request(extraction_payload)
            print(response)
            if response.status_code == 200:
                try:
                    json_response = response.json()
                    extracted_text = json_response.get("response", "")
                    extracted_data = {}

                    for line in extracted_text.split("\n"):
                        if "**Document Type:**" in line:
                            extracted_data["documentType"] = line.split(":")[-1].lstrip("*").strip()
                        elif "**Document Number:**" in line:
                            extracted_data["documentNumber"] = line.split(":")[-1].lstrip("*").strip()
                        elif "**Date of Birth/Issue:**" in line:
                            extracted_data["dateOfBirthorIssue"] = line.split(":")[-1].lstrip("*").strip()
                        elif "**Father's/Guardian's Name:**" in line:
                            extracted_data["FatherGuardianName"] = line.split(":")[-1].lstrip("*").strip()
                        elif "**Name as on Document:**" in line:
                            extracted_data["nameAsOnDoc"] = line.split(":")[-1].lstrip("*").strip()
                        elif "**Gender:**" in line:
                            extracted_data["Gender"] = line.split(":")[-1].lstrip("*").strip()
                        elif "**Address:**" in line:
                            extracted_data["Address"] = line.split(":")[-1].lstrip("*").strip()

                    for key in REQUIRED_KEYS:
                        if key not in extracted_data or not extracted_data[key]:
                            extracted_data[key] = "NA"

                    if any(extracted_data[key] != "NA" for key in REQUIRED_KEYS):
                        valid_responses.append(extracted_data)
                except json.JSONDecodeError:
                    return jsonify({"error": "Error parsing JSON response"}), 500
            else:
                return jsonify({"error": f"API request failed with status code {response.status_code}", "message": response.text}), 500

        merged_response = {}
        for key in REQUIRED_KEYS:
            values = [resp[key] for resp in valid_responses if key in resp and resp[key] not in ["Not available", "N/A", "Not Visible"]]
            merged_response[key] = values[0] if values else "NA"

        return jsonify(merged_response), 200
    elif document_type == 'Credence Document':
        first_page_path = save_image(images_base64[0], "first_page.png")
        candidate_photo_path = crop_candidate_photo(first_page_path)
        extracted_data = []
        for i, img_base64 in enumerate(images_base64):
            img_base64 = encode_image(save_image(img_base64, f"page_{i}.png"))

            extraction_payload = {
                "model": "llama3.2-vision",
                "prompt": ( """Extract all the details from the image without describing the image.
                    Ensure the extracted data is in structured JSON format, including all fields without missing any information.
                    Do not include descriptions of sections, images, colors, or text formatting.
                    Do not include phrases like "Here is the extracted data in structured JSON format:" in the response.
                    Do not add notes, assumptions, or statements such as "from this image I got this information."
                    Do not assume it is an Aadhaar or PAN card—extract the details exactly as they appear from all pages.
                    Each page's information should be displayed only within its respective section, without mentioning "page number" or "page."
                    Use appropriate headings for each section but do not repeat the same information across multiple sections.
                    Do not include headers, footers, section or any heading texts from the document.
                    extract all the sections of the code of conduct as it is appears in the image.            
                    extract all the information from "Certification" as it is appears in the image and show it in end.
                    Do not repeat any of the information.       
                    
                    Additionally, if any section starts with the following phrases, do not include them in the response:
                    - "The image displays"
                    - "The image provides"
                    - "The image presents"
                    - "In summary, the image displays" 
                    - "The image shows a resume"
                    - "**Base64-Encoded Candidate Image Link:** Not provided"
                    - "No information is available in the image" 
                    -   "*   Section 1":"Header"
                    -   "*   Section 2":"Introduction"
                    -   "*   Section 3":"Consent Form"
                    -   "*   Section 4":"Signature"
                    -   "*   Section 5":"Witness Details" """
                    ),
                "images": [img_base64],
                "temperature": 0.0,
                "stream": False
            }
            response = make_api_request(extraction_payload)
            
            if response.status_code == 200:
                json_response = response.json()
                extracted_page_data = json_response.get("response", "")
                extracted_data.append({"page": i + 1, "data": extracted_page_data})
            
            time.sleep(1)  # Avoid API rate limits
        
        return jsonify({"documentType": "Credence Document", "extractedData": extracted_data, "candidatePhotoPath": candidate_photo_path}), 200

    elif document_type == "Pay Slip":
        payslip_prompt = """Extract structured data from the provided payslip(s).
            The extracted details should be formatted in structured JSON format.
            maintain separate heading for each month payslip.
            The following details should be extracted as per months:
            For Payslip:
            - Employee Name
            - Employee Code
            - Designation
            - PAN No.
            - Department
            - City/Facility
            - Date of Joining (DOJ)
            - Total Days
            - Payable Days
            - Loss of Pay (LOP) Days
            - Salary components:
            - BASIC
            - HRA
            - Other Allowances
            - Conveyance Allowance
            - Medical Allowance
            - Gross Earnings
            - Total Deductions
            - Net Pay Amount (both numeric value and words)

            Ensure all extracted details are formatted correctly. 
            Do not add assumptions or unnecessary descriptions.
            Maintain separate sections for each month's payslip.
            Avoid including headers, footers, or repeated details.
        """

        extracted_data = []  # Store extracted data for each page

        for i, img_base64 in enumerate(images_base64):  #  Process each image separately
            extraction_payload = {
                "model": "llama3.2-vision",
                "prompt": payslip_prompt,
                "images": [img_base64],  #  Send only ONE image at a time
                "temperature": 0.0,
                "stream": False
            }

            try:
                response = make_api_request(extraction_payload)
                print(f"Payslip API Raw Response (Page {i+1}): {response.text}")  # Debugging

                if response.status_code == 200:
                    try:
                        json_response = response.json()
                        page_data = json_response.get("response", "").strip()

                        if page_data:
                            extracted_data.append({"page": i + 1, "data": page_data})  #  Store each page separately

                    except json.JSONDecodeError:
                        return jsonify({
                            "status": "error",
                            "message": "Error decoding API JSON response"
                        }), 500

                else:
                    return jsonify({
                        "status": "error",
                        "message": f"API request failed with status code {response.status_code}"
                    }), 500

            except requests.exceptions.RequestException as e:
                return jsonify({
                    "status": "error",
                    "message": f"API request failed: {str(e)}"
                }), 500

        return jsonify({
            "status": "success",
            "message": "OCR Extraction Completed",
            "documentType": "Pay Slip",
            "extractedData": extracted_data  #  Now returns data from all pages
        }), 200

    elif document_type == "Result":
        extracted_data = []

        for i, img_base64 in enumerate(images_base64):
            extraction_payload = {
                "model": "llama3.2-vision",
                "prompt": """Extract all available details from the result, including student name,
                roll number, hall ticket number, year of admission, college name, final exam month and year,
                and class awarded. Additionally, extract all semisters data with all subjects along with their corresponding marks obtained
                as it is shown in document.
                maximum marks, grades, and result status (Pass/Fail).
                Ensure the marks is same as it shown in documents, don't change the values.
                ensure the aggregate marks also shown in json response.
                Do not add assumptions or unnecessary descriptions.
                Ensure the extracted data is formatted as a structured JSON object with clear key-value pairs.""",
                "images": [img_base64],  #  Send only ONE image at a time
                "temperature": 0.0,
                "stream": False
            }

            response = make_api_request(extraction_payload)
            print(f"API Response (Page {i+1}): {response.text}")  # Debugging

            if response.status_code == 200:
                try:
                    json_response = response.json()
                    extracted_page_data = json_response.get("response", "")

                    if extracted_page_data:
                        extracted_data.append({"page": i + 1, "data": extracted_page_data})  #  Store each page separately

                except json.JSONDecodeError:
                    return jsonify({
                        "status": "error",
                        "message": "Error decoding API JSON response"
                    }), 500

            else:
                return jsonify({
                    "status": "error",
                    "message": f"API request failed with status code {response.status_code}"
                }), 500

            time.sleep(1)  # Avoid API rate limits

        return jsonify({
            "status": "success",
            "message": "OCR Extraction Completed",
            "documentType": "Result",
            "extractedData": extracted_data  #  Now returns data from all pages
        }), 200



    else:
        return jsonify({"status": "error", "message": "Invalid document type"}), 400
        
if __name__ == "__main__":
    # app.run(host="172.16.11.39", port=5002, debug=True)
    app.run(debug=True)












































































































































# #working code for adhar pan and credence all pages and payslips
# import os
# import json
# import base64
# import requests
# import time
# from flask import Flask, request, jsonify
# from pdf2image import convert_from_path
# from PIL import Image


# app = Flask(__name__)

# # OCR API URL
# API_URL = "http://172.16.11.25:11434/api/generate"

# UPLOAD_FOLDER = "uploads"
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# # Required keys
# REQUIRED_KEYS = ["documentType", "documentNumber", "dateOfBirthorIssue", "FatherGuardianName", "nameAsOnDoc", "Gender", "Address"]

# def encode_image(image_path):
#     with open(image_path, "rb") as image_file:
#         return base64.b64encode(image_file.read()).decode("utf-8")

# def pdf_to_images(pdf_path):
#     return convert_from_path(pdf_path)

# def process_file(file):
#     images_base64 = []
#     file_ext = file.filename.lower().split(".")[-1]
#     file_path = f"temp_upload.{file_ext}"
#     file.save(file_path)
    
#     if file_ext == "pdf":
#         images = pdf_to_images(file_path)
#         for i, img in enumerate(images):
#             img_path = f"temp_page_{i}.png"
#             img.save(img_path, "PNG")
#             images_base64.append(encode_image(img_path))
#             os.remove(img_path)
#     else:
#         images_base64.append(encode_image(file_path))
    
#     os.remove(file_path)
#     return images_base64

# def save_image(base64_string, filename):
#     """Save a base64 string as an image file."""
#     image_data = base64.b64decode(base64_string)  # Decode the base64 string
#     image_path = os.path.join(UPLOAD_FOLDER, filename)
    
#     with open(image_path, "wb") as f:
#         f.write(image_data)  # Write image file
    
#     return image_path



# def make_api_request(payload):
#     headers = {"Content-Type": "application/json"}
#     response = requests.post(API_URL, json=payload, headers=headers, verify=False)
#     return response


# def crop_candidate_photo(image_path):
#     image = Image.open(image_path)
#     width, height = image.size
    
#     left = int(width * 0.75)
#     top = int(height * 0.25)
#     right = int(width * 0.95)
#     bottom = int(height * 0.35)
    
#     cropped_image = image.crop((left, top, right, bottom))
#     photo_path = os.path.join(UPLOAD_FOLDER, "candidate_photo.png")
#     cropped_image.save(photo_path, "PNG")
#     return photo_path


# def determine_document_type(images_base64):
#     if not images_base64:
#         return None  # Ensure we have at least one image

#     # Process only the first page for document type classification
#     payload = {
#         "model": "llama3.2-vision",
#         "prompt": """Analyze the provided image and classify it as one of the following:
#             - 'Aadhaar Card' (if Aadhaar-related words like "Aadhaar", "Unique Identification", "UIDAI" are present.
#             this word can be small letters also).
#             - 'PAN Card' (if words like "Income Tax Department", "Permanent Account Number", "Govt. of India" appear
#             this words can be small letters also).
#             - 'Credence' (if the word 'Credence' is found in the first page of text).
#             If 'Credence' appears anywhere in the extracted text of the **first page**, return 'Credence' without considering other document types
#             it can be all letters small case also.
#             - 'Pay Slip' (if words like 'Pay Slip', 'Salary Statement', 'Net Pay Amount' appears on that document).
#             Always return only one of these four options.

#             """,
#         "images": [images_base64[0]],  # Only checking the first page
#         "temperature": 0.0,
#         "stream": False
#     }

#     response = make_api_request(payload)

#     if response.status_code == 200:
#         try:
#             document_type_response = response.json().get("response", "").strip()
#             if "Credence" in document_type_response:
#                 return "Credence Document"
#             elif "Aadhaar" in document_type_response:
#                 return "Aadhaar Card"
#             elif "PAN" in document_type_response:
#                 return "PAN Card"
#             elif "pay slip" in document_type_response or "payslip" in document_type_response or "salary statement" in document_type_response:
#                 return "Pay Slip"
#             else:
#                 return "Unknown Document"  # Instead of None, return an explicit unknown type


#         except json.JSONDecodeError:
#             print("Error parsing API JSON response")

#     return "Unknown Document"

# @app.route("/ocr", methods=["POST"])
# def ocr_extraction():
#     if "file" not in request.files:
#         return jsonify({"error": "No file provided"}), 400

#     file = request.files["file"]
#     images_base64 = process_file(file)
#     document_type = determine_document_type(images_base64)
#     print(document_type)
    
#     if not document_type:
#         return jsonify({"error": "Could not determine document type"}), 400

#     if document_type in ["Aadhaar Card", "PAN Card"]:
#         # Define the extraction prompt
#         prompt_text = (
#                 "Act as an OCR assistant. Analyze the provided (PDF or image) and return the extracted fields in JSON format."
#                 "Extract the following details if present in the (PDF or image):"
#                 "Document Type(if it is aadhaar card then show Aadhaar card if it is pan card then show PAN card)"
#                 "Document Number(aadhard card or pan card number)"
#                 "Date of Birth/Issue(show in date formats it could be DOB)"
#                 "Name as on Document(first line of name)"
#                 "Father's/Guardian's Name(Father's Name line directly below the Name)"
#                 "Gender, and Address(show only address if it is here not any sentences and if not address"
#                 "then show only N/A)"
#                 "If any field is missing, return 'NA' for that field."
#                 "from extracted details I want only specific information"
#         )
        
#         extraction_payload = {
#             "model": "llama3.2-vision",
#             "prompt": prompt_text,
#             "images": images_base64,
#             "temperature": 0.0,
#             "stream": False
#         }

#         valid_responses = []
#         for _ in range(3):
#             response = make_api_request(extraction_payload)
#             print(response)
#             if response.status_code == 200:
#                 try:
#                     json_response = response.json()
#                     extracted_text = json_response.get("response", "")
#                     extracted_data = {}

#                     for line in extracted_text.split("\n"):
#                         if "**Document Type:**" in line:
#                             extracted_data["documentType"] = line.split(":")[-1].lstrip("*").strip()
#                         elif "**Document Number:**" in line:
#                             extracted_data["documentNumber"] = line.split(":")[-1].lstrip("*").strip()
#                         elif "**Date of Birth/Issue:**" in line:
#                             extracted_data["dateOfBirthorIssue"] = line.split(":")[-1].lstrip("*").strip()
#                         elif "**Father's/Guardian's Name:**" in line:
#                             extracted_data["FatherGuardianName"] = line.split(":")[-1].lstrip("*").strip()
#                         elif "**Name as on Document:**" in line:
#                             extracted_data["nameAsOnDoc"] = line.split(":")[-1].lstrip("*").strip()
#                         elif "**Gender:**" in line:
#                             extracted_data["Gender"] = line.split(":")[-1].lstrip("*").strip()
#                         elif "**Address:**" in line:
#                             extracted_data["Address"] = line.split(":")[-1].lstrip("*").strip()

#                     for key in REQUIRED_KEYS:
#                         if key not in extracted_data or not extracted_data[key]:
#                             extracted_data[key] = "NA"

#                     if any(extracted_data[key] != "NA" for key in REQUIRED_KEYS):
#                         valid_responses.append(extracted_data)
#                 except json.JSONDecodeError:
#                     return jsonify({"error": "Error parsing JSON response"}), 500
#             else:
#                 return jsonify({"error": f"API request failed with status code {response.status_code}", "message": response.text}), 500

#         merged_response = {}
#         for key in REQUIRED_KEYS:
#             values = [resp[key] for resp in valid_responses if key in resp and resp[key] not in ["Not available", "N/A", "Not Visible"]]
#             merged_response[key] = values[0] if values else "NA"

#         return jsonify(merged_response), 200
#     elif document_type == 'Credence Document':
#         first_page_path = save_image(images_base64[0], "first_page.png")
#         candidate_photo_path = crop_candidate_photo(first_page_path)
#         extracted_data = []
#         for i, img_base64 in enumerate(images_base64):
#             img_base64 = encode_image(save_image(img_base64, f"page_{i}.png"))

#             extraction_payload = {
#                 "model": "llama3.2-vision",
#                 "prompt": ( """Extract all the details from the image without describing the image.
#                     Ensure the extracted data is in structured JSON format, including all fields without missing any information.
#                     Do not include descriptions of sections, images, colors, or text formatting.
#                     Do not include phrases like "Here is the extracted data in structured JSON format:" in the response.
#                     Do not add notes, assumptions, or statements such as "from this image I got this information."
#                     Do not assume it is an Aadhaar or PAN card—extract the details exactly as they appear from all pages.
#                     Each page's information should be displayed only within its respective section, without mentioning "page number" or "page."
#                     Use appropriate headings for each section but do not repeat the same information across multiple sections.
#                     Do not include headers, footers, or any heading texts from the document and give all information of certification.
                    
#                     Additionally, if any section starts with the following phrases, do not include them in the response:
#                     - "The image displays"
#                     - "The image provides"
#                     - "The image presents"
#                     - "In summary, the image displays" 
#                     - "The image shows a resume"
#                     - "**Base64-Encoded Candidate Image Link:** Not provided" """
#                 ),
#                 "images": [img_base64],
#                 "temperature": 0.0,
#                 "stream": False
#             }
#             response = make_api_request(extraction_payload)
            
#             if response.status_code == 200:
#                 json_response = response.json()
#                 extracted_page_data = json_response.get("response", "")
#                 extracted_data.append({"page": i + 1, "data": extracted_page_data})
            
#             time.sleep(1)  # Avoid API rate limits
        
#         return jsonify({"extractedData": extracted_data, "candidatePhotoPath": candidate_photo_path}), 200

#     elif document_type == "Pay Slip":
#         payslip_prompt = """Extract structured data from the provided payslip(s) and relieving letter.
#             The extracted details should be formatted in structured JSON format.
#             The following details should be extracted:

#             For Payslip:
#             - Employee Name
#             - Employee Code
#             - Designation
#             - PAN No.
#             - Department
#             - City/Facility
#             - Date of Joining (DOJ)
#             - Total Days
#             - Payable Days
#             - Loss of Pay (LOP) Days
#             - Salary components:
#             - BASIC
#             - HRA
#             - Other Allowances
#             - Conveyance Allowance
#             - Medical Allowance
#             - Gross Earnings
#             - Total Deductions
#             - Net Pay Amount (both numeric value and words)

#             Ensure all extracted details are formatted correctly. 
#             Do not add assumptions or unnecessary descriptions.
#             Maintain separate sections for each month's payslip.
#             extract the reliveing letter.
#             Avoid including headers, footers, or repeated details.
#         """

#         extracted_data = []  # Store extracted data for each page

#         for i, img_base64 in enumerate(images_base64):  #  Process each image separately
#             extraction_payload = {
#                 "model": "llama3.2-vision",
#                 "prompt": payslip_prompt,
#                 "images": [img_base64],  #  Send only ONE image at a time
#                 "temperature": 0.0,
#                 "stream": False
#             }

#             try:
#                 response = make_api_request(extraction_payload)
#                 print(f"Payslip API Raw Response (Page {i+1}): {response.text}")  # Debugging

#                 if response.status_code == 200:
#                     try:
#                         json_response = response.json()
#                         page_data = json_response.get("response", "").strip()

#                         if page_data:
#                             extracted_data.append({"page": i + 1, "data": page_data})  #  Store each page separately

#                     except json.JSONDecodeError:
#                         return jsonify({
#                             "status": "error",
#                             "message": "Error decoding API JSON response"
#                         }), 500

#                 else:
#                     return jsonify({
#                         "status": "error",
#                         "message": f"API request failed with status code {response.status_code}"
#                     }), 500

#             except requests.exceptions.RequestException as e:
#                 return jsonify({
#                     "status": "error",
#                     "message": f"API request failed: {str(e)}"
#                 }), 500

#         return jsonify({
#             "status": "success",
#             "message": "OCR Extraction Completed",
#             "documentType": "Pay Slip",
#             "extractedData": extracted_data  #  Now returns data from all pages
#         }), 200


#     else:
#         return jsonify({"status": "error", "message": "Invalid document type"}), 400
        
# if __name__ == "__main__":
#     # app.run(host="172.16.11.39", port=5002, debug=True)
#     app.run(debug=True)









































































































