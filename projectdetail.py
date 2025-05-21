import streamlit as st
import pandas as pd
import os
import shutil
from jsontocsv import json_to_csv

VIEW_OPTIONS = [
    "Home Page",
    "Architecture",
    "Test Facilities",
    "Requirements",
    "Test Strategy",
    # "Test Results",
    # "Warnings/Issues",
]
REPORTS_ROOT = "reports"                           #  ./reports/…
DATA_TIES = {
    "Home Page": ["TripleCount"],
    "Test Facilities": ["TestFacilities", "TestEquipment", "TestPersonnel"],
    "Requirements": ["Requirements"],
    "Architecture": ["SystemArchitecture", "MissionArchitecture"],
    "Test Strategy": ["TestStrategy", "TestEquipment", "TestFacilities"],
    "Test Results": ["TestResults"],
    # (Warnings/Issues pulls from these same files, so no separate entry needed)
}

@st.dialog("Select a tab below and replace its data")
def replace_data():
    """
    • Upload required JSON for selected tabs – auto‑converted to CSV
    • De‑select existing files to delete them
    """
    folder = REPORTS_ROOT
    tabs = VIEW_OPTIONS

    st.markdown("### Select tab(s) you want to modify")
    sel_tabs = st.multiselect("Tabs", options=tabs)

    # --------------------------------------- current & required filenames
    req_json = {f"{tie}.json" for tab in sel_tabs for tie in DATA_TIES[tab]}
    existing_json = {f for f in os.listdir(folder) if f.endswith(".json")}
    existing_csv  = {f for f in os.listdir(folder) if f.endswith(".csv")}

    # --------------------------------------- DELETE (un‑tick to remove)
    to_keep = st.multiselect(
        "Files already present (de-select a file to delete it from tab's storage)",
        options=sorted(existing_json & req_json),
        default=sorted(existing_json & req_json),
    )
    st.caption(":red[Do not use the deselect option, if you just want to replace a file.]")
    st.caption(":orange[To update an existing file, just upload a new version below]")
    to_delete = (existing_json & req_json) - set(to_keep)
    if to_delete:
        st.warning(f"These files will be **deleted** on save: {', '.join(to_delete)}")

    # --------------------------------------- UPLOAD
    new_files = st.file_uploader(
        "Upload the JSON files listed below",
        type="json", accept_multiple_files=True,
        key=f"uploader_project_id" 
    )

    # ------------- save uploads (JSON + converted CSV)
    uploaded_names = set()                       # keep track of just‑uploaded names
    for f in new_files:
        json_out = f.name.split(".json")[0].strip().translate({ord(ch): None for ch in '0123456789'}).strip() + ".json"
        path_json = os.path.join(folder, json_out)
        with open(path_json, "wb") as out:
            out.write(f.getbuffer())
        csv_out = f.name.split(".json")[0].strip().translate({ord(ch): None for ch in '0123456789'}).strip() + ".csv"
        json_to_csv(json_file_object=f.getvalue(),
                    csv_output_path=os.path.join(folder, csv_out))
        st.success(f"Saved {json_out} converted and saved")
        uploaded_names.add(json_out)
    
    # ------------------- MISSING / COMPLETE STATUS ---------------------------
    # What will remain after this dialog *if* the user clicks "Save Changes"
    future_present = (existing_json - to_delete) | uploaded_names
    missing_files  = sorted(req_json - future_present)

    if sel_tabs:                                 # only show feedback if a tab was chosen
        if missing_files:
            st.warning(f"Missing required files: {', '.join(missing_files)}")
        else:
            st.success("🎉 All required files are present!")

    # ------------- commit deletes
    if st.button("Save Changes"):
        for filename in to_delete:
            for ext in (".json", ".csv"):
                p = os.path.join(folder, filename.replace(".json", ext))
                if os.path.exists(p):
                    os.remove(p)
        st.rerun()