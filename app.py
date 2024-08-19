import os
import json
import requests
import streamlit as st
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


def check_email(email: str) -> bool:
    url = "https://registerdisney.go.com/jgc/v8/client/TPR-DVC.WEB-PROD/guest-flow?langPref=en-US&feature=no-password-reuse"
    payload = json.dumps({"email": email})
    headers = {
        "Accept-Language": "en-US,en;q=0.5",
        "content-type": "application/json",
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    return response.json()["data"]["guestFlow"] == "LOGIN_FLOW"


def process_emails(df, progress_bar):
    email_column = next((col for col in df.columns if col.lower() == "email"), None)
    if email_column is None:
        return None

    total_emails = len(df)
    results = []
    progress = 0

    with ThreadPoolExecutor() as executor:
        future_to_email = {
            executor.submit(check_email, email): email for email in df[email_column]
        }

        for future in as_completed(future_to_email):
            result = future.result()
            results.append(result)
            progress += 1
            progress_bar.progress(progress / total_emails)

    df["registered"] = results
    return df


def process_file(file, progress_bar):
    df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)

    processed_df = process_emails(df, progress_bar)
    if processed_df is None:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_filename = f"result_{timestamp}_{file.name}"
    if not os.path.exists("results"):
        os.makedirs("results")
    processed_df.to_csv(f"results/{result_filename}", index=False)
    return result_filename


def load_history():
    if not os.path.exists("upload_history.json"):
        return []
    with open("upload_history.json", "r") as f:
        return json.load(f)


def save_to_history(filename, original_filename):
    history = load_history()
    history.append(
        {
            "filename": filename,
            "original_filename": original_filename,
            "status": "Processing",
            "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    with open("upload_history.json", "w") as f:
        json.dump(history, f)


def update_file_status(filename, status):
    history = load_history()
    for item in history:
        if item["filename"] == filename:
            item["status"] = status
    with open("upload_history.json", "w") as f:
        json.dump(history, f)


st.title("Email Checker App")

uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx"])

if uploaded_file is not None:
    st.write("Processing file...")
    progress_bar = st.progress(0)
    result_file = process_file(uploaded_file, progress_bar)

    if result_file is None:
        st.error(
            "Error: The uploaded file does not contain a column named 'email' or 'Email'. Please upload a file with an email column."
        )
    else:
        save_to_history(result_file, uploaded_file.name)
        update_file_status(result_file, "Finished")
        st.success(f"File processed successfully! Result: {result_file}")

st.subheader("Upload History")
history = load_history()

col1, col2, col3, col4 = st.columns([2, 1, 2, 1])
col1.write("**File Name**")
col2.write("**Status**")
col3.write("**Upload Date**")
col4.write("**Action**")

st.markdown("---")

for item in reversed(history):
    col1, col2, col3, col4 = st.columns([2, 1, 2, 1])

    with col1:
        st.write(item["original_filename"])
    with col2:
        st.write(item["status"])
    with col3:
        st.write(item["upload_date"])
    with col4:
        if item["status"] == "Finished":
            with open(f"results/{item['filename']}", "rb") as f:
                st.download_button(
                    label="Download",
                    data=f,
                    file_name=item["filename"],
                    mime="text/csv",
                )

    st.markdown("---")
