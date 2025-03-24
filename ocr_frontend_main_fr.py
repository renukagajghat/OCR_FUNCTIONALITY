#working code for editable json response and json response for aadhar pan credence and payslips
import streamlit as st
import requests
import json
import re

# API Endpoint
BACKEND_URL = "http://127.0.0.1:5000/ocr"

# Streamlit UI
st.title("OCR Document Upload")
st.write("Upload an Aadhaar, PAN card image, or PDF for OCR processing.")

# File uploader
uploaded_file = st.file_uploader("Choose a file...", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file is not None:
    file_extension = uploaded_file.name.split(".")[-1].lower()

    # Display the uploaded file
    if file_extension in ["png", "jpg", "jpeg"]:
        st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
    elif file_extension == "pdf":
        st.write("PDF file uploaded successfully!")

    # Submit button
    if st.button("Extract Text"):
        with st.spinner("Processing OCR..."):
            files = {"file": (uploaded_file.name if uploaded_file.name else "uploaded_file", uploaded_file, "application/octet-stream")}
            try:
                response = requests.post(BACKEND_URL, files=files, timeout=150)
                response.raise_for_status()  # Raise error for HTTP failure

                if response.status_code == 200:
                    extracted_data = response.json()

                    if "error" in extracted_data:
                        st.error(f"Error: {extracted_data['error']}")
                    else:
                        document_type = extracted_data.get("documentType", "Unknown")

                        if document_type in ["Aadhaar Card", "PAN Card"]:
                            # Structured JSON response
                            structured_response = {
                                "status": "success",
                                "message": "OCR Extraction Completed",
                                "data": {
                                    "documentType": extracted_data.get("documentType", "Unknown"),
                                    "documentNumber": extracted_data.get("documentNumber", ""),
                                    "dateOfBirthorIssue": extracted_data.get("dateOfBirthorIssue", ""),
                                    "nameAsOnDoc": extracted_data.get("nameAsOnDoc", ""),
                                    "FatherGuardianName": extracted_data.get("FatherGuardianName", ""),
                                    "Gender": extracted_data.get("Gender", ""),
                                    "Address": extracted_data.get("Address", "")
                                }
                            }
                        elif document_type == 'Credence Document':
                            # Process Credence Document Data
                            extracted_text_list = extracted_data.get("extractedData", [])
                            structured_data = {}

                            candidate_photo = extracted_data.get("candidatePhotoPath", "")

                            if extracted_text_list:
                                for page_data in extracted_text_list:
                                    raw_text = page_data.get("data", "")

                                    # **Improved Parsing Logic**
                                    lines = raw_text.split("\n")
                                    current_section = None

                                    for line in lines:
                                        line = line.strip()
                                        if not line:
                                            continue  # Skip empty lines

                                        if "**" in line:  # Detect section headers or key-value pairs
                                            line = line.replace("**", "").strip()
                                            if ":" in line:
                                                key, value = map(str.strip, line.split(":", 1))
                                                structured_data[key] = value
                                            else:
                                                current_section = line
                                                structured_data.setdefault(current_section, "")  # Initialize if not exists

                                        elif current_section:
                                            structured_data[current_section] += f" {line}".strip()

                                # Final JSON structure
                                structured_response = {
                                    "status": "success",
                                    "message": "OCR Extraction Completed",
                                    "documentType": "Credence Document",
                                    "candidatePhotoPath": candidate_photo,  # Only from first page
                                    "data": structured_data
                                }
                            else:
                                structured_response = {
                                    "status": "error",
                                    "message": "No extracted text found"
                                }

                         # Payslip Handling (Multi-Page Support)
                        elif document_type == "Pay Slip":
                            extracted_text_list = extracted_data.get("extractedData", [])

                            if extracted_text_list:
                                structured_response = {
                                    "status": "success",
                                    "message": "OCR Extraction Completed",
                                    "documentType": "Pay Slip",
                                    "pages": []
                                }

                                # Process each page separately
                                for page in extracted_text_list:
                                    page_number = page.get("page", "Unknown Page")
                                    page_data = page.get("data", "No Data Found")

                                    structured_response["pages"].append({
                                        "page": page_number,
                                        "text": page_data
                                    })
                            else:
                                structured_response = {
                                    "status": "error",
                                    "message": "No extracted text found"
                                }

                        elif document_type == "Result":
                            extracted_text_list = extracted_data.get("extractedData", [])
                            structured_response = {
                                "status": "success",
                                "message": "OCR Extraction Completed",
                                "documentType": "Result",
                                "data": extracted_text_list if extracted_text_list else {"status": "error", "message": "No extracted text found"}
                            }
                  
                        # Convert JSON to string for editing
                        json_str = json.dumps(structured_response, indent=4, ensure_ascii=False)

                        # Editable text area for JSON
                        # Unique key for each document type
                        key_value = f"{document_type}_json"
                        
                        # Editable text area for JSON
                        edited_json_str = st.text_area(f"Edit Extracted JSON ({document_type})", json_str, height=600, key=key_value)
                        # Parse the edited JSON
                        try:
                            edited_json = json.loads(edited_json_str)
                            st.success("Valid JSON format!")
                            st.json(edited_json)  # Display edited JSON
                        except json.JSONDecodeError:
                            st.error("Invalid JSON format! Please check your edits.")

                        # Handle Unknown Documents
                        else:
                            structured_response = {
                                "status": "error",
                                "message": "Could not determine the document type"
                            }


                else:
                    st.error(f"API request failed: {response.status_code}\n{response.text}")

            except requests.exceptions.RequestException as e:
                st.error(f"API request failed: {e}")



















































































































# #working code for editable json response and json response for aadhar pan credence and payslips
# import streamlit as st
# import requests
# import json
# import re

# # API Endpoint
# BACKEND_URL = "http://127.0.0.1:5000/ocr"

# # Streamlit UI
# st.title("OCR Document Upload")
# st.write("Upload an Aadhaar, PAN card image, or PDF for OCR processing.")

# # File uploader
# uploaded_file = st.file_uploader("Choose a file...", type=["png", "jpg", "jpeg", "pdf"])

# if uploaded_file is not None:
#     file_extension = uploaded_file.name.split(".")[-1].lower()

#     # Display the uploaded file
#     if file_extension in ["png", "jpg", "jpeg"]:
#         st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
#     elif file_extension == "pdf":
#         st.write("PDF file uploaded successfully!")

#     # Submit button
#     if st.button("Extract Text"):
#         with st.spinner("Processing OCR..."):
#             files = {"file": (uploaded_file.name if uploaded_file.name else "uploaded_file", uploaded_file, "application/octet-stream")}
#             try:
#                 response = requests.post(BACKEND_URL, files=files, timeout=150)
#                 response.raise_for_status()  # Raise error for HTTP failure

#                 if response.status_code == 200:
#                     extracted_data = response.json()

#                     if "error" in extracted_data:
#                         st.error(f"Error: {extracted_data['error']}")
#                     else:
#                         document_type = extracted_data.get("documentType", "Unknown")

#                         if document_type in ["Aadhaar Card", "PAN Card"]:
#                             # Structured JSON response
#                             structured_response = {
#                                 "status": "success",
#                                 "message": "OCR Extraction Completed",
#                                 "data": {
#                                     "documentType": extracted_data.get("documentType", "Unknown"),
#                                     "documentNumber": extracted_data.get("documentNumber", ""),
#                                     "dateOfBirthorIssue": extracted_data.get("dateOfBirthorIssue", ""),
#                                     "nameAsOnDoc": extracted_data.get("nameAsOnDoc", ""),
#                                     "FatherGuardianName": extracted_data.get("FatherGuardianName", ""),
#                                     "Gender": extracted_data.get("Gender", ""),
#                                     "Address": extracted_data.get("Address", "")
#                                 }
#                             }

#                             # Convert JSON to string for editing
#                             json_str = json.dumps(structured_response, indent=4, ensure_ascii=False)

#                             # Editable text area for JSON
#                             edited_json_str = st.text_area("Edit Extracted JSON", json_str, height=300)

#                             # Parse the edited JSON
#                             try:
#                                 edited_json = json.loads(edited_json_str)
#                                 st.success("Valid JSON format!")
#                                 st.json(edited_json)  # Display edited JSON
#                             except json.JSONDecodeError:
#                                 st.error("Invalid JSON format! Please check your edits.")

#                         elif document_type == 'Credence Document':
#                             # Process Credence Document Data
#                             extracted_text_list = extracted_data.get("extractedData", [])
#                             structured_data = {}

#                             candidate_photo = extracted_data.get("candidatePhotoPath", "")

#                             if extracted_text_list:
#                                 for page_data in extracted_text_list:
#                                     raw_text = page_data.get("data", "")

#                                     # **Improved Parsing Logic**
#                                     lines = raw_text.split("\n")
#                                     current_section = None

#                                     for line in lines:
#                                         line = line.strip()
#                                         if not line:
#                                             continue  # Skip empty lines

#                                         if "**" in line:  # Detect section headers or key-value pairs
#                                             line = line.replace("**", "").strip()
#                                             if ":" in line:
#                                                 key, value = map(str.strip, line.split(":", 1))
#                                                 structured_data[key] = value
#                                             else:
#                                                 current_section = line
#                                                 structured_data.setdefault(current_section, "")  # Initialize if not exists

#                                         elif current_section:
#                                             structured_data[current_section] += f" {line}".strip()

#                                 # Final JSON structure
#                                 structured_response = {
#                                     "status": "success",
#                                     "message": "OCR Extraction Completed",
#                                     "candidatePhotoPath": candidate_photo,  # Only from first page
#                                     "data": structured_data
#                                 }
#                             else:
#                                 structured_response = {
#                                     "status": "error",
#                                     "message": "No extracted text found"
#                                 }

#                             # Convert JSON to string for editing
#                             json_str = json.dumps(structured_response, indent=4, ensure_ascii=False)

#                             # Editable text area for JSON
#                             edited_json_str = st.text_area("Edit Extracted JSON", json_str, height=600)

#                             # Parse the edited JSON
#                             try:
#                                 edited_json = json.loads(edited_json_str)
#                                 st.success("Valid JSON format!")
#                                 st.json(edited_json)  # Display edited JSON
#                             except json.JSONDecodeError:
#                                 st.error("Invalid JSON format! Please check your edits.")

#                          # Payslip Handling (Multi-Page Support)
#                         elif document_type == "Pay Slip":
#                             extracted_text_list = extracted_data.get("extractedData", [])

#                             if extracted_text_list:
#                                 structured_response = {
#                                     "status": "success",
#                                     "message": "OCR Extraction Completed",
#                                     "documentType": "Pay Slip",
#                                     "pages": []
#                                 }

#                                 # Process each page separately
#                                 for page in extracted_text_list:
#                                     page_number = page.get("page", "Unknown Page")
#                                     page_data = page.get("data", "No Data Found")

#                                     structured_response["pages"].append({
#                                         "page": page_number,
#                                         "text": page_data
#                                     })
#                             else:
#                                 structured_response = {
#                                     "status": "error",
#                                     "message": "No extracted text found"
#                                 }

#                         # Handle Unknown Documents
#                         else:
#                             structured_response = {
#                                 "status": "error",
#                                 "message": "Could not determine the document type"
#                             }

#                         # Convert JSON to string for editing
#                         json_str = json.dumps(structured_response, indent=4, ensure_ascii=False)

#                         # Editable text area for JSON
#                         edited_json_str = st.text_area("Edit Extracted JSON", json_str, height=600)

#                         # Parse the edited JSON
#                         try:
#                             edited_json = json.loads(edited_json_str)
#                             st.success("Valid JSON format!")
#                             st.json(edited_json)  # Display edited JSON
#                         except json.JSONDecodeError:
#                             st.error("Invalid JSON format! Please check your edits.")

#                 else:
#                     st.error(f"API request failed: {response.status_code}\n{response.text}")

#             except requests.exceptions.RequestException as e:
#                 st.error(f"API request failed: {e}")