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
import requests

# Load single theme
with open("assets/theme.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# st.markdown(
#     """
#     <div class="banner">
#         <img src="https://raw.githubusercontent.com/amjadlalkodithodika/blooddonor/main/Blood%20Drop.png" alt="Logo">
#         <div>
#             <h1>Donor Dashboard</h1>
#             <p>Connecting lives through generosity</p>
#         </div>
#     </div>
#     """,
#     unsafe_allow_html=True
# )

st.markdown(
    """
    <div class="banner">
        <img src="https://raw.githubusercontent.com/amjadlalkodithodika/blooddonor/main/Blood%20Drop.png" alt="Logo">
        <div>
            <h1>Blood Donor Dashboard</h1>
            <p>Save lives. Share hope.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)



st.set_page_config(page_title="Blood Bank Donor Dashboard", page_icon="🩸", layout="wide")

# st.image(
#     r"C:\Users\amjad\OneDrive\sql+python\Blood Bank\images\blood_donation.png",
#     caption="Save lives. Share hope.",
#     use_column_width=True
# )

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

        # ❌ Removed st.success
        # ✅ Let the form show brown_success via session_state
        st.session_state["email_sent_success"] = True

    except EmailNotValidError as e:
        brown_error(f"⚠️ Invalid email address: {e}")
    except Exception as e:
        brown_error(f"⚠️ Failed to send email: {e}")
        
# --- Tabs ---
tab1, tab2, tab3,= st.tabs(["Donors", "Charts", "My Details"])

# --- Custom brown-themed alerts ---
def brown_success(msg):
    st.markdown(
        f"""
        <div style="
            background-color:#C8E6C9;  /* light green background */
            border-left: 5px solid #2E7D32; /* dark green accent */
            padding: 0.8em;
            margin: 0.5em 0;
            color:#4e342e; /* coffee brown text */
            font-weight:600;
        ">
            ✅ {msg}
        </div>
        """,
        unsafe_allow_html=True
    )

def brown_error(msg):
    st.markdown(
        f"""
        <div style="
            background-color:#FFCDD2;  /* light red background */
            border-left: 5px solid #B71C1C; /* dark red accent */
            padding: 0.8em;
            margin: 0.5em 0;
            color:#4e342e; /* coffee brown text */
            font-weight:600;
        ">
            ❌ {msg}
        </div>
        """,
        unsafe_allow_html=True
    )

def brown_warning(msg):
    st.markdown(
        f"""
        <div style="
            background-color:#FFF9C4;  /* light yellow background */
            border-left: 5px solid #FBC02D; /* dark yellow accent */
            padding: 0.8em;
            margin: 0.5em 0;
            color:#4e342e; /* coffee brown text */
            font-weight:600;
        ">
            ⚠️ {msg}
        </div>
        """,
        unsafe_allow_html=True
    )


with tab1:
    st.subheader("➕ Add Donor")

    # Reset donor form if flagged
    if st.session_state.get("reset_donor_form", False):
        st.session_state["donor_name"] = ""
        st.session_state["donor_age"] = ""
        st.session_state["donor_bg"] = "Select your blood group"
        st.session_state["donor_contact"] = ""
        st.session_state["donor_location"] = ""
        st.session_state["reset_donor_form"] = False

    with st.form("add_donor_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Name", placeholder="Enter full name", key="donor_name")
            age_input = st.text_input("Age", placeholder="Enter age in years", key="donor_age")
            location = st.text_input("Location", placeholder="Enter city or area", key="donor_location")

        with col2:
            blood_group = st.selectbox(
                "Blood Group",
                ["Select your blood group", "A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"],
                key="donor_bg"
            )
            contact = st.text_input("Contact Number", placeholder="Enter 10-digit phone number", key="donor_contact")

        submitted = st.form_submit_button("Add Donor")

        if submitted:
            # --- Validation ---
            if not name or not age_input or blood_group == "Select your blood group" or not contact or not location:
                brown_error("Please fill in all fields before submitting.")
            elif not name.replace(" ", "").isalpha():
                brown_error("Name must contain only letters and spaces (no numbers).")
            elif not location.replace(" ", "").isalpha():
                brown_error("Location must contain only letters and spaces (no numbers).")
            elif not age_input.isdigit():
                brown_error("Age must be an integer.")
            else:
                age = int(age_input)
                if age < 18 or age > 65:
                    brown_error("Donor age must be between 18 and 65 years.")
                elif not contact.isdigit() or len(contact) != 10:
                    brown_error("Contact number must be exactly 10 digits and contain only numbers.")
                else:
                    df = get_donors()
                    duplicate = df[(df["name"].str.lower() == name.strip().lower()) & (df["contact"] == contact.strip())]

                    if not duplicate.empty:
                        brown_warning("This donor is already added.")
                    else:
                        try:
                            next_row = len(sheet.get_all_values()) + 1
                            sheet.update(
                                f"A{next_row}:E{next_row}",
                                [[name.strip().title(), age, blood_group, contact.strip(), location.strip().title()]]
                            )
                            brown_success("Donor added successfully!")   # ✅ unified
                            st.session_state["reset_donor_form"] = True
                        except Exception as e:
                            brown_error(f"Failed to add donor: {e}")
                              
                    st.rerun()

    # --- Donor List ---
    df = get_donors()
    st.subheader("📋 Donor List")

    if not df.empty:
        df.columns = [col.upper() for col in df.columns]
        df = df.reset_index(drop=True)
        df.index = range(1, len(df) + 1)
        df.index.name = "INDEX"

        df["CONTACT"] = df["CONTACT"].apply(lambda x: str(x)[:-4] + "****" if len(str(x)) > 4 else "****")

        blood_filter = st.selectbox("Filter by Blood Group", ["All"] + sorted(df["BLOOD_GROUP"].unique()))

        if blood_filter != "All":
            filtered_df = df[df["BLOOD_GROUP"] == blood_filter]
        else:
            filtered_df = df

        # ✅ Responsive dataframe without toolbar
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=False,        # keep index visible
            column_config={}         # disables toolbar options
        )
    else:
        st.info("No donors available yet.")

    # --- Download via Email ---
    st.subheader("📧 Download via Email")

    df = get_donors()
    blood_groups = sorted(df["blood_group"].dropna().unique()) if not df.empty else []
    locations = sorted(df["location"].dropna().unique()) if not df.empty else []

    # Reset download form if flagged (same as Add Donor logic)
    if st.session_state.get("reset_download_form", False):
        st.session_state["download_email"] = ""
        st.session_state["download_bg"] = "All"
        st.session_state["download_locations"] = []
        st.session_state["download_confirm"] = False
        st.session_state["reset_download_form"] = False

    with st.form("download_email_form"):
        email_address = st.text_input("Recipient Email", placeholder="Enter your Email", key="download_email")
        blood_group = st.selectbox("Blood Group", ["All"] + blood_groups, key="download_bg")
        selected_locations = st.multiselect("Select Locations", ["All Locations"] + locations, key="download_locations")
        confirm_send = st.checkbox("✅ I want to receive the donor list via email", key="download_confirm")
        submitted_download = st.form_submit_button("Send Download")

    # --- Handle form submission ---
    if submitted_download:
        if not email_address:
            brown_error("Please provide a valid email address.")
        elif not confirm_send:
            brown_warning("Please tick the checkbox to confirm sending the donor list.")
        elif not email_address.endswith("@gmail.com"):
            brown_warning("It is not a valid email. Please enter a Gmail address ending with '@gmail.com'.")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            filtered_df = df.copy()
            if blood_group != "All":
                filtered_df = filtered_df[df["blood_group"] == blood_group]

            if "All Locations" not in selected_locations:
                if selected_locations:
                    filtered_df = filtered_df[filtered_df["location"].isin(selected_locations)]

            csv_data = filtered_df.to_csv(index=False)

            try:
                send_email(email_address, csv_data)
                brown_success("Email sent successfully!")
                # ✅ Flag reset for next rerun (same as Add Donor)
                st.session_state["reset_download_form"] = True
            except Exception as e:
                brown_error(f"Failed to send donor list: {e}")

            # Silent logging
            row_data = [
                email_address,
                blood_group,
                ", ".join(selected_locations) if selected_locations else "All Locations",
                timestamp,
            ]
            next_row = len(log_sheet.get_all_values()) + 1
            log_sheet.update(f"A{next_row}:D{next_row}", [row_data])

    # --- Donor Management Section ---
    st.subheader("🛠 Donor Management")
    if "manage_open" not in st.session_state:
        st.session_state.manage_open = False

    with st.expander("Open Donor Management", expanded=st.session_state.manage_open):
        df = get_donors()

        # Reset index to start from 1
        df = df.reset_index(drop=True)
        df.index = range(1, len(df) + 1)
        df.index.name = "INDEX"

        row_index = st.number_input("Row number (first donor = 1)", min_value=1, step=1)
        action = st.radio("Action", ["Update", "Delete"])

        # --- Update Donor ---
        if action == "Update":
            if not df.empty and row_index <= len(df):
                donor = df.loc[row_index]

                # Mask contact number for privacy
                donor_display = donor.copy()
                donor_display["contact"] = str(donor_display["contact"])[:-4] + "****"

                st.write("📋 Current Donor Details:")
                st.table(pd.DataFrame(donor_display).transpose())

                new_name = st.text_input("Name", value=donor["name"], key="update_name")
                new_age = st.text_input("Age", value=str(donor["age"]), key="update_age")
                new_blood = st.selectbox(
                    "Blood Group",
                    ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"],
                    index=["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"].index(donor["blood_group"]),
                    key="update_blood"
                )
                new_contact = st.text_input("Contact", value=donor["contact"], key="update_contact")
                new_location = st.text_input("Location", value=donor["location"], key="update_location")

                if st.button("✏️ Apply Update"):
                    if new_name.replace(" ", "").isalpha() and new_age.isdigit() and new_contact.isdigit() and new_location.replace(" ", "").isalpha():
                        if not (18 <= int(new_age) <= 65):
                            st.error("⚠️ Age must be between 18 and 65.")
                        elif len(new_contact) != 10:
                            st.error("⚠️ Contact number must be exactly 10 digits.")
                        else:
                            duplicate = df[(df["name"].str.lower() == new_name.lower()) & (df["contact"] == new_contact)]
                            if not duplicate.empty and not (donor["name"].lower() == new_name.lower() and donor["contact"] == new_contact):
                                st.error("⚠️ Another donor already exists with the same name and phone number!")
                            else:
                                # Update
                                update_donor(row_index + 1, [new_name.strip().title(), int(new_age), new_blood, new_contact.strip(), new_location.strip().title()])
                                brown_success("Donor updated successfully!")   # ✅ unified
                                for key in ["update_name","update_age","update_blood","update_contact","update_location"]:
                                    if key in st.session_state:
                                        del st.session_state[key]
                                st.session_state.manage_open = False
                                st.rerun()
                    else:
                        st.error("⚠️ Please provide valid update values.")
            else:
                st.warning("⚠️ Invalid donor index selected.")

        # --- Delete Donor ---
        if action == "Delete":
            if not df.empty and row_index <= len(df):
                donor = df.loc[row_index]

                # Mask contact number for privacy
                donor_display = donor.copy()
                donor_display["contact"] = str(donor_display["contact"])[:-4] + "****"

                st.error("❌ Are you sure you want to delete this donor?")
                st.table(pd.DataFrame(donor_display).transpose())

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Confirm Delete"):
                        # Delete
                        delete_donor(row_index + 1)
                        brown_success("Donor deleted successfully!")   # ✅ unified
                        st.session_state.manage_open = False
                        st.rerun()
                with col2:
                    if st.button("❌ Cancel"):
                        st.info("ℹ️ Delete action cancelled.")
                        st.session_state.manage_open = False
            else:
                st.warning("⚠️ Invalid donor index selected.")

# --- Charts Tab ---
with tab2:
    st.header("Donor Visualizations")
    df = get_donors()

    if not df.empty:
        # Shared brown palette
        brown_palette = ["#4e342e", "#6d4c41", "#8d6e63", "#a1887f"]

        # Donor Count by Blood Group (Bar Chart)
        fig_bar = px.bar(df, x="blood_group", title="Donor Count by Blood Group", color_discrete_sequence=brown_palette)
        fig_bar.update_layout(
            paper_bgcolor="rgba(78, 52, 46, 0.1)",   # transparent coffee brown outer background
            plot_bgcolor="rgba(0,0,0,0)",            # fully transparent inner background
            title={"x":0.5, "xanchor":"center", "font":{"color":"#4e342e"}},
            xaxis={
                "title":{"font":{"color":"#4e342e"}},
                "tickfont":{"color":"#4e342e"},
                "showgrid":False
            },
            yaxis={
                "title":{"font":{"color":"#4e342e"}},
                "tickfont":{"color":"#4e342e"},
                "showgrid":False
            },
            font={"color":"#4e342e", "family":"Segoe UI"},
            legend={"font":{"color":"#4e342e"}}
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

        # Blood Group Distribution (Pie Chart)
        fig_pie = px.pie(df, names="blood_group", title="Blood Group Distribution", hole=0.3, color_discrete_sequence=brown_palette)
        fig_pie.update_layout(
            paper_bgcolor="rgba(78, 52, 46, 0.1)",
            plot_bgcolor="rgba(0,0,0,0)",
            title={"x":0.5, "xanchor":"center", "font":{"color":"#4e342e"}},
            font={"color":"#4e342e", "family":"Segoe UI"},
            legend={"font":{"color":"#4e342e"}}
        )
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

        # Age Distribution of Donors (Histogram)
        fig_hist = px.histogram(df, x="age", nbins=10, title="Age Distribution of Donors", color_discrete_sequence=brown_palette)
        fig_hist.update_layout(
            paper_bgcolor="rgba(78, 52, 46, 0.1)",
            plot_bgcolor="rgba(0,0,0,0)",
            title={"x":0.5, "xanchor":"center", "font":{"color":"#4e342e"}},
            xaxis={
                "title":{"font":{"color":"#4e342e"}},
                "tickfont":{"color":"#4e342e"},
                "showgrid":False
            },
            yaxis={
                "title":{"font":{"color":"#4e342e"}},
                "tickfont":{"color":"#4e342e"},
                "showgrid":False
            },
            font={"color":"#4e342e", "family":"Segoe UI"},
            legend={"font":{"color":"#4e342e"}}
        )
        st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})

        # Age vs Blood Group (Scatter Plot)
        fig_scatter = px.scatter(df, x="age", y="blood_group", title="Age vs Blood Group", color_discrete_sequence=brown_palette)
        fig_scatter.update_traces(marker=dict(size=10))  # brown scatter points
        fig_scatter.update_layout(
            paper_bgcolor="rgba(78, 52, 46, 0.1)",
            plot_bgcolor="rgba(0,0,0,0)",
            title={"x":0.5, "xanchor":"center", "font":{"color":"#4e342e"}},
            xaxis={
                "title":{"font":{"color":"#4e342e"}},
                "tickfont":{"color":"#4e342e"},
                "showgrid":False
            },
            yaxis={
                "title":{"font":{"color":"#4e342e"}},
                "tickfont":{"color":"#4e342e"},
                "showgrid":False
            },
            font={"color":"#4e342e", "family":"Segoe UI"},
            legend={"font":{"color":"#4e342e"}}
        )
        st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})

    else:
        st.info("No donor data available for visualization.")

# --- My Details Tab ---
with tab3:
    st.header("👤 My Details")
    st.markdown("""
    ### Name: Amjad Lal K  
    **Roles:** Data Analyst & Business Analyst  
    **Location:** Malappuram, Kerala, India  
    """)

    # Create two columns for Skills and Interests
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Data Analyst Skills")
        st.markdown("""
        - Python, Pandas, NumPy, Matplotlib, Seaborn  
        - MySQL (legacy dashboards) → migrated to Google Sheets for scalable public access  
        - Excel Dashboard Design  
        - Tableau & Power BI (learning, applied to BI workflows)  
        - Machine Learning deployment with Streamlit  
        - ATS‑friendly CV design & CV Strategist  
        """)

        st.subheader("🎯 Data Analyst Interests")
        st.markdown("""
        - Building realistic datasets for ML & BI  
        - Designing immersive dashboards with Google Sheets integration  
        - Debugging and modular code design  
        - Exploring BI tools for advanced visualization  
        """)

    with col2:
        st.subheader("💼 Business Analyst Skills")
        st.markdown("""
        - Business Process Analysis & Requirement Gathering  
        - Data Visualization for decision‑making and KPI tracking  
        - Stakeholder Communication & Documentation  
        - Translating business needs into actionable insights  
        - Strategic reporting with Excel & BI tools  
        """)

        st.subheader("📌 Business Analyst Interests")
        st.markdown("""
        - Bridging technical solutions with business requirements  
        - Crafting recruiter‑friendly CVs and career storytelling  
        - Exploring BI tools for strategic analysis  
        - Designing workflows for clarity and scalability  
        """)

    # Short Bio and Connect Section
    st.markdown("""
    ### Short Bio
    Persistent, methodical, and practical — I iterate on workflows until solutions are robust and recruiter‑ready.  
    Recently migrated donor dashboards from SQL to Google Sheets, ensuring free, scalable access with full CRUD and visualization features.  
    Passionate about blending technical accuracy with engaging visuals for data and career storytelling.  
    As a Business Analyst, I focus on bridging technical solutions with business requirements, ensuring clarity, scalability, and impact.  

    ### Connect with Me
    - 🌐 [GitHub](https://github.com/amjadlalkodithodika)  
    - 📸 [Instagram](https://instagram.com/amjadlal_kodithodika)  
    - 💼 [LinkedIn](https://linkedin.com/in/amjadlalk)  
    """)

    # --- Download CV Button ---

# Raw GitHub link (for download)
cv_raw_url = "https://raw.githubusercontent.com/amjadlalkodithodika/blooddonor/main/amjadlalkodithodika.pdf"
cv_file = requests.get(cv_raw_url).content

# Blob GitHub link (for online viewing)
cv_view_url = "https://github.com/amjadlalkodithodika/blooddonor/blob/main/amjadlalkodithodika.pdf"

# Download button
st.download_button(
    label="📄 Download My CV",
    data=cv_file,
    file_name="Amjad_Lal_CV.pdf",
    mime="application/pdf",
    key="download_cv_button"
)

# View online link
st.markdown(
    f"[🔗 View CV Online]({cv_view_url})",
    unsafe_allow_html=True
)

# Disclaimer
with st.expander("⚠️ Disclaimer", expanded=False):
    st.markdown(
        """
        This donor data is displayed publicly within this application.  
        Do not misuse it or use it for false purposes.  
        The builder of this app is not responsible for any issues arising from its use.  
        Proceed at your own risk.  

        For transparency and security purposes, the application also records download history  
        and recipient email addresses when donor lists are shared.
        """,
        unsafe_allow_html=True
    )
