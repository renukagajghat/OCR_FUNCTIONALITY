import streamlit as st
import requests
from PIL import Image
import io
import json  

st.set_page_config(page_title="OCR Processor", layout="centered")

st.title("OCR Processing for Documents")

# Initialize session state for extracted data
if "aadhaar_data" not in st.session_state:
    st.session_state.aadhaar_data = {}

if "pan_data" not in st.session_state:
    st.session_state.pan_data = {}

# Tabs for Aadhaar and PAN
tab1, tab2 = st.tabs(["📄 Aadhaar OCR", "🆔 PAN OCR"])

with tab1:
    st.subheader("Upload Aadhaar Card")

    uploaded_front = st.file_uploader("📄 Upload Aadhaar Front Side", type=["png", "jpg", "jpeg"])
    uploaded_back = st.file_uploader("📄 Upload Aadhaar Back Side (Optional)", type=["png", "jpg", "jpeg"])

    if uploaded_front:
        st.image(uploaded_front, caption="Aadhaar Front Side", use_container_width=True)

    if uploaded_back:
        st.image(uploaded_back, caption="Aadhaar Back Side", use_container_width=True)

    if uploaded_front and st.button("Extract Aadhaar Data"):
        st.info("Extracting Aadhaar data... Please wait.")

        files = {"file_front": ("front.png", uploaded_front.getvalue(), "image/png")}
        if uploaded_back:
            files["file_back"] = ("back.png", uploaded_back.getvalue(), "image/png")

        try:
            response = requests.post("http://127.0.0.1:5000/upload_aadhaar", files=files)

            if response.status_code == 200:
                extracted_data = response.json()

                if "error" in extracted_data:
                    st.error(f"Extraction Failed: {extracted_data['error']}")
                else:
                    aadhaar_details = extracted_data.get("data", {})

                    # Check if all required fields have valid data
                    required_fields = ["name", "gender", "date_of_birth", "fathers_name", "aadhar_no", "street_address"]
                    if all(aadhaar_details.get(field) for field in required_fields):
                        st.session_state.aadhaar_data = aadhaar_details
                        st.success("Aadhaar Data Extracted Successfully!")
                    else:
                        st.error("Failed to extract Aadhaar details. Please check the image quality.")

            else:
                st.error(f"Extraction Failed: {response.json().get('error', 'Unknown error')}")

        except Exception as e:
            st.error(f"Server Error: {str(e)}")


    if st.session_state.aadhaar_data:
        st.subheader("Edit Extracted Aadhaar Details")

        extracted_data = st.session_state.aadhaar_data

        name = st.text_input("Full Name", extracted_data.get("name", ""))
        gender = st.selectbox("Gender", ["Male", "Female", "Other"], 
                              index=0 if extracted_data.get("gender") == "Male" else 1)
        date_of_birth = st.text_input("Date of Birth", extracted_data.get("date_of_birth", ""))
        aadhar_no = st.text_input("Aadhaar Number", extracted_data.get("aadhar_no", ""))
        fathers_name = st.text_input("Father's Name", extracted_data.get("fathers_name", ""))
        street_address = st.text_area("Address", extracted_data.get("street_address", ""))

        if st.button("Save Aadhaar Data"):
            save_payload = {
                "name": name.strip(),
                "gender": gender.strip(),
                "date_of_birth": date_of_birth.strip(),
                "aadhar_no": aadhar_no.strip(),
                "fathers_name": fathers_name.strip(),
                "street_address": street_address.strip()
            }

            headers = {"Content-Type": "application/json"}

            try:
                save_response = requests.post("http://127.0.0.1:5000/save_aadhaar",
                                              data=json.dumps(save_payload),
                                              headers=headers)

                if save_response.status_code == 200:
                    st.success("Aadhaar Data Saved Successfully!")
                else:
                    st.error(f"Error: {save_response.json().get('error', 'Unknown error')}")

            except Exception as e:
                st.error(f"Request Error: {str(e)}")


with tab2:
    st.subheader("Upload PAN Card")

    uploaded_pan = st.file_uploader("🆔 Upload PAN Card", type=["png", "jpg", "jpeg"])

    if "pan_data" not in st.session_state:
        st.session_state.pan_data = {}

    if uploaded_pan and st.button("Extract PAN Data"):
        st.info("Extracting PAN data... Please wait.")

        files = {"file": ("pan.png", uploaded_pan.getvalue(), "image/png")}

        try:
            response = requests.post("http://127.0.0.1:5000/upload_pan", files=files)

            if response.status_code == 200:
                extracted_pan_data = response.json()

                if "error" in extracted_pan_data:
                    st.error(f"Extraction Failed: {extracted_pan_data['error']}")
                else:
                    pan_details = extracted_pan_data.get("data", {})

                    # Check if all required fields have valid data
                    required_fields = ["name", "fathers_name", "date_of_birth", "pan_no"]
                    if all(pan_details.get(field) for field in required_fields):
                        st.session_state.pan_data = pan_details
                        st.success("PAN Data Extracted Successfully!")
                    else:
                        st.error("Failed to extract PAN details. Please check the image quality.")

            else:
                st.error(f"Error {response.status_code}: {response.text}")

        except requests.exceptions.RequestException as e:
            st.error(f"Server Error: {str(e)}")


    # 🔥 If PAN data is extracted, show editable fields
    if st.session_state.pan_data:
        st.subheader("Edit Extracted PAN Details")

        pan_data = st.session_state.pan_data  # Retrieve extracted data

        name = st.text_input("Full Name", pan_data.get("name", ""))
        fathers_name = st.text_input("Father's Name", pan_data.get("fathers_name", ""))
        date_of_birth = st.text_input("Date of Birth", pan_data.get("date_of_birth", ""))
        pan_no = st.text_input("PAN Number", pan_data.get("pan_no", ""))

        if st.button("Save to Database"):
            save_payload = {
                "name": name.strip(),
                "fathers_name": fathers_name.strip(),
                "date_of_birth": date_of_birth.strip(),
                "pan_no": pan_no.strip()
            }

            # Debugging: Show JSON before sending
            st.write("📤 Sending JSON Data:", save_payload)

            headers = {"Content-Type": "application/json"}

            try:
                save_response = requests.post(
                    "http://127.0.0.1:5000/save_pan",
                    data=json.dumps(save_payload),  
                    headers=headers
                )

                if save_response.status_code == 200:
                    st.success("PAN Data Saved Successfully!")
                else:
                    st.error(f"Error {save_response.status_code}: {save_response.text}")

            except requests.exceptions.RequestException as e:
                st.error(f"Request Error: {str(e)}")
