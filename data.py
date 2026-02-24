import os, json
import streamlit as st
import pandas as pd
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email_validator import validate_email, EmailNotValidError
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from datetime import datetime

st.set_page_config(page_title="Blood Bank Donor Dashboard", page_icon="🩸", layout="wide")

st.image(r"images\blood_donation.png",
    caption="Save lives. Share hope.",
    use_column_width=True
)

# --- Google Sheets Connection ---
def get_gsheet_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]

    try:
        if "GCP_SERVICE_ACCOUNT" in st.secrets:
            # ✅ Streamlit secrets section is already a dict
            creds_dict = dict(st.secrets["GCP_SERVICE_ACCOUNT"])
        else:
            load_dotenv()
            creds_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
            if not creds_json:
                st.error("❌ No GCP credentials found in secrets or .env")
                return None
            creds_dict = json.loads(creds_json)

        # Fix private key formatting
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ Failed to connect to Google Sheets: {e}")
        return None
# print("Preview:", repr(creds_dict["private_key"][:100]))

client = get_gsheet_client()
if client:
    workbook = client.open_by_url(
        "https://docs.google.com/spreadsheets/d/1lUw3SaVTnzaiJAn9O5hQV_QQhkvHBt7aIDOt9Wc7aM4/edit?usp=sharing"
    )
    sheet = workbook.sheet1          # Donor data
    log_sheet = workbook.get_worksheet(1)  # Sheet2 for download logs
else:
    sheet, log_sheet = None, None

# --- Donor Functions ---
def add_donor(name, age, blood_group, contact, location):
    if sheet:
        sheet.append_row([name, age, blood_group, contact, location])

def get_donors():
    if not sheet:
        return pd.DataFrame(columns=["name", "age", "blood_group", "contact", "location"])
    values = sheet.get_all_values()
    expected_headers = ["name", "age", "blood_group", "contact", "location"]
    if len(values) > 1:
        return pd.DataFrame(values[1:], columns=expected_headers)
    return pd.DataFrame(columns=expected_headers)

def update_donor(row_index, new_values):
    if sheet:
        sheet.update(f"A{row_index}:E{row_index}", [new_values])

def delete_donor(row_index):
    if sheet:
        sheet.delete_rows(row_index)

def log_download(email, blood_group, locations):
    if log_sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([email, blood_group, ", ".join(locations) if locations else "All", timestamp])

# --- Email Sending Helper ---
def send_email(recipient, csv_data):
    try:
        validate_email(recipient)

        if "EMAIL_SENDER" in st.secrets and "EMAIL_PASS" in st.secrets:
            sender = st.secrets["EMAIL_SENDER"]
            password = st.secrets["EMAIL_PASS"]
        else:
            load_dotenv()
            sender = os.getenv("EMAIL_SENDER")
            password = os.getenv("EMAIL_PASS")

        if not sender or not password:
            st.error("❌ Email credentials not found")
            return

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = "Your Donor List Download"
        msg.attach(MIMEText("Here is your requested donor list.", "plain"))
        msg.attach(MIMEApplication(csv_data, Name="donors.csv"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())

        st.success("✅ Email sent successfully!")
    except EmailNotValidError as e:
        st.error(f"⚠️ Invalid email address: {e}")
    except Exception as e:
        st.error(f"⚠️ Failed to send email: {e}")

# --- Tabs ---
tab1, tab2, tab3,= st.tabs(["Donors", "Charts", "My Details"])

# --- Donors Tab ---
with tab1:
    st.subheader("➕ Add Donor")
    with st.form("add_donor_form", clear_on_submit=True):  # auto-clear after success
        name = st.text_input("Name")
        age = st.text_input("Age")
        blood_group = st.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"])
        contact = st.text_input("Phone No")
        location = st.text_input("Location")

        # --- Pre-check validation before enabling button ---
        name_valid = bool(name and all(ch.isalpha() or ch.isspace() for ch in name))
        age_valid = age.isdigit() and 18 <= int(age) <= 65 if age else False
        blood_group_valid = bool(blood_group)
        contact_valid = contact.isdigit() and len(contact) == 10 if contact else False
        location_valid = location.isalpha() and len(location) <= 20 if location else False

        all_valid = name_valid and age_valid and blood_group_valid and contact_valid and location_valid

        # Show errors inline if fields are invalid
        if name and not name_valid:
            st.error("⚠️ Name must contain only alphabetic characters and spaces.")
        if age and not age_valid:
            st.error("⚠️ Age must be between 18 and 65.")
        if contact and not contact_valid:
            st.error("⚠️ Phone number must be exactly 10 digits.")
        if location and not location_valid:
            st.error("⚠️ Location must be alphabetic and up to 20 characters.")

        # Submit button only enabled if all fields valid
        submitted = st.form_submit_button("Add Donor", disabled=not all_valid)

    if submitted and all_valid:
        # Auto-format capitalization
        name = " ".join([part.capitalize() for part in name.strip().split()])
        location = location.strip().capitalize()

        df = get_donors()
        duplicate = df[(df["name"].str.lower() == name.lower()) & (df["contact"] == contact)]
        if not duplicate.empty:
            st.error("⚠️ Donor already exists with the same name and phone number!")
        else:
            next_row = len(sheet.get_all_values()) + 1
            sheet.update(f"A{next_row}:E{next_row}", [[name, int(age), blood_group, contact, location]])
            st.success("✅ Donor added successfully!")
            st.rerun()

    # --- Donor List ---
    df = get_donors()
    st.subheader("📋 Donor List")
    if not df.empty:
        df["contact"] = df["contact"].apply(lambda x: str(x)[:-4] + "****" if len(str(x)) > 4 else "****")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No donors available yet.")

    # --- Download via Email (stored in Sheet2/Table2 silently) ---
    st.subheader("📧 Download via Email")

    # Load donor data to populate blood group and location choices
    df = get_donors()
    blood_groups = sorted(df["blood_group"].dropna().unique()) if not df.empty else []
    locations = sorted(df["location"].dropna().unique()) if not df.empty else []

    with st.form("download_email_form", clear_on_submit=True):
        email_address = st.text_input("Recipient Email")

        # Blood group selectbox shows only available groups, plus "All"
        blood_group = st.selectbox("Blood Group", ["All"] + blood_groups)

        # Location multiselect always shown, with "All Locations" option
        selected_locations = st.multiselect("Select Locations", ["All Locations"] + locations)

        confirm_send = st.checkbox("✅ I want to receive the donor list via email")
        submitted_download = st.form_submit_button("Send Download")

    if submitted_download:
        if not email_address:
            st.error("⚠️ Please provide a valid email address.")
        elif not confirm_send:
            st.warning("⚠️ Please tick the checkbox to confirm sending the donor list.")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # --- Filter donor list based on selection ---
            filtered_df = df.copy()
            if blood_group != "All":
                filtered_df = filtered_df[filtered_df["blood_group"] == blood_group]

            # If "All Locations" is chosen, ignore other selections
            if "All Locations" not in selected_locations:
                if selected_locations:
                    filtered_df = filtered_df[filtered_df["location"].isin(selected_locations)]

            # Convert filtered donor list to CSV
            csv_data = filtered_df.to_csv(index=False)

            # Send email with filtered donor list
            try:
                send_email(email_address, csv_data)
                st.success(f"📄 Donor list for {blood_group} "
                        f"({', '.join(selected_locations) if selected_locations else 'All Locations'}) "
                        f"has been sent to {email_address}. Logged at {timestamp}.")
            except Exception as e:
                st.error(f"❌ Failed to send email: {e}")

            # --- Log request to Sheet2/Table2 ---
            row_data = [email_address,
                        blood_group,
                        ", ".join(selected_locations) if selected_locations else "All Locations",
                        timestamp]

            next_row = len(log_sheet.get_all_values()) + 1
            log_sheet.update(f"A{next_row}:D{next_row}", [row_data])

    # --- Donor Management Section ---
    st.subheader("🛠 Donor Management")
    if "manage_open" not in st.session_state:
        st.session_state.manage_open = False

    with st.expander("Open Donor Management", expanded=st.session_state.manage_open):
        row_index = st.number_input("Row number (first donor = 1)", min_value=1, step=1)
        action = st.radio("Action", ["Update", "Delete"])
        df = get_donors()

        # --- Update Donor ---
        if action == "Update":
            if not df.empty and row_index <= len(df):
                donor = df.iloc[row_index - 1]
                st.write("📋 Current Donor Details:")
                st.table(pd.DataFrame(donor).transpose())

                new_name = st.text_input("Name", value=donor["name"], key="update_name")
                new_age = st.text_input("Age", value=donor["age"], key="update_age")
                new_blood = st.selectbox("Blood Group",
                                         ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"],
                                         index=["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"].index(donor["blood_group"]),
                                         key="update_blood")
                new_contact = st.text_input("Contact", value=donor["contact"], key="update_contact")
                new_location = st.text_input("Location", value=donor["location"], key="update_location")

                if st.button("✏️ Apply Update"):
                    if new_name and new_age.isdigit() and new_contact and new_location:
                        duplicate = df[(df["name"].str.lower() == new_name.lower()) & (df["contact"] == new_contact)]
                        if not duplicate.empty and not (donor["name"].lower() == new_name.lower() and donor["contact"] == new_contact):
                            st.error("⚠️ Another donor already exists with the same name and phone number!")
                        else:
                            update_donor(row_index + 1, [new_name, int(new_age), new_blood, new_contact, new_location])
                            st.success("✅ Donor updated successfully!")
                            df = get_donors()
                            for key in ["update_name","update_age","update_blood","update_contact","update_location"]:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.session_state.manage_open = False
                    else:
                        st.error("⚠️ Please provide valid update values.")
            else:
                st.warning("⚠️ Invalid donor index selected.")

        # --- Delete Donor ---
        if action == "Delete":
            if not df.empty and row_index <= len(df):
                donor = df.iloc[row_index - 1]
                st.error("❌ Are you sure you want to delete this donor?")
                st.table(pd.DataFrame(donor).transpose())

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Confirm Delete"):
                        delete_donor(row_index + 1)
                        st.success("✅ Donor deleted successfully!")
                        df = get_donors()
                        st.session_state.manage_open = False
                with col2:
                    if st.button("❌ Cancel"):
                        st.info("ℹ️ Delete action cancelled.")
                        st.session_state.manage_open = False
            else:
                st.warning("⚠️ Invalid donor index selected.")

# Charts Tab
with tab2:
    st.header("Donor Visualizations")
    df = get_donors()
    if not df.empty:
        st.plotly_chart(px.bar(df, x="blood_group", title="Donor Count by Blood Group"), use_container_width=True)
        st.plotly_chart(px.pie(df, names="blood_group", title="Blood Group Distribution", hole=0.3), use_container_width=True)
        st.plotly_chart(px.histogram(df, x="age", nbins=10, title="Age Distribution of Donors"), use_container_width=True)
        st.plotly_chart(px.scatter(df, x="age", y="blood_group", title="Age vs Blood Group"), use_container_width=True)
# --- My Details Tab ---
with tab3:
    st.header("👤 My Details")
    st.markdown("""
    ### Name: Amjad Lal K  
    **Role:** Data Analyst  
    **Location:** Malappuram, Kerala, India  

    ### Skills
    - Python, Pandas, NumPy, Matplotlib, Seaborn  
    - MySQL (legacy dashboards) → migrated to Google Sheets for scalable public access  
    - Excel Dashboard Design  
    - Tableau & Power BI (learning)  
    - Machine Learning deployment with Streamlit  
    - ATS‑friendly CV design & CV Strategist  

    ### Interests
    - Building realistic datasets for ML & BI  
    - Designing immersive dashboards with Google Sheets integration  
    - Crafting recruiter‑friendly CVs  
    - Debugging and modular code design  

    ### Short Bio
    Persistent, methodical, and practical — I iterate on workflows until solutions are robust and recruiter‑ready.  
    Recently migrated donor dashboards from SQL to Google Sheets, ensuring free, scalable access with full CRUD and visualization features.  
    Passionate about blending technical accuracy with engaging visuals for data and career storytelling.  

    ### Connect with Me
    - 🌐 [GitHub](https://github.com/amjadlalkodithodika)  
    - 📸 [Instagram](https://instagram.com/amjadlal_kodithodika)  
    - 💼 [LinkedIn](https://linkedin.com/in/amjadlalk)  
    """)


