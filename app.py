import os
import pandas as pd
import streamlit as st
from projectdetail import VIEW_OPTIONS, DATA_TIES, replace_data
import homepage
import architecture
import requirements
import testfacility
# import teststrategy
import teststrategy_new
# import testresults
# import issueswarnings


st.set_page_config(page_title="TnE Management", page_icon="🪄", layout="wide")


def show_tab(tab_name):
    """
    Dispatch each tab to its own view module.
    """
    if tab_name == "Home Page":
        homepage.render()
        return
    
    if tab_name == "Architecture":
        architecture.render()
        return
    
    if tab_name == "Test Facilities":
        testfacility.render()
        return

    if tab_name == "Requirements":
        requirements.render()
        return

    if tab_name == "Test Strategy":
        teststrategy_new.render()
        return


def main():
    col1, col2 = st.columns([0.9, 0.15])
    with col1:
        st.header("Test and Evaluation Dashboard", divider='violet')
    with col2:
        if st.button("🪄 Edit Data", type='primary'):
            replace_data() 
    VIEWTABS = st.tabs(VIEW_OPTIONS)
    for i, tab in enumerate(VIEWTABS):
        with tab:
            show_tab(VIEW_OPTIONS[i])



if __name__ == "__main__":
    main()