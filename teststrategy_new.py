import os, re, json
import streamlit as st
import pandas as pd
import numpy as np
import graphviz, plotly.express as px
from datetime import datetime
from streamlit_tree_select import tree_select            # NEW
from projectdetail import DATA_TIES, REPORTS_ROOT

@st.cache_data(show_spinner=False)
def _load_csvs(root):
    strat = pd.read_csv(os.path.join(root, "TestStrategy.csv"))
    fac   = pd.read_csv(os.path.join(root, "TestFacilities.csv"))
    equip = pd.read_csv(os.path.join(root, "TestEquipment.csv"))
    return strat, fac, equip
   

STANDARD_MSG = "{}.json data is not available – upload it via **Edit Data**"

def render() -> None:
    """
    Dynamic Test‑Strategy view (metrics · graph · timeline · table).
    Facility names, tests, cases – all come from user CSV.
    """
    folder = REPORTS_ROOT
    if not all(os.path.exists(os.path.join(folder, f"{n}.csv"))
               for n in ("TestStrategy","TestFacilities","TestEquipment")):
        st.info(STANDARD_MSG.format("TestStrategy / TestFacilities / TestEquipment"))
        return

    strategy, facilities, equipments = _load_csvs(folder)

    # ---------- Standard tidy‑up (unchanged) ----------------------------- #
    for df in (strategy, facilities, equipments):
        df.columns = (df.columns.str.replace(r"\s{2,}", " ", regex=True)
                                 .str.replace(r"(?<!^)(?=[A-Z])", " ", regex=True)
                                 .str.strip())
    
    # -------------- SETTINGS DRAWER ------------------------------------- #
    with st.sidebar:
        st.markdown("### ⚙️ Test‑Strategy Settings")
        st.caption("Un‑check any tests or cases you want to exclude.")
        
        tree_data = []
        for t, sub in strategy.groupby("Test"):
            children = [{"value": f"{t}/{c}", "label": c}
                        for c in sorted(sub["Test Case"].unique())]
            tree_data.append({"value": t, 
                              "label": t, 
                              "children": children
                              })
        sel = tree_select(
            tree_data,
            checked = [node["value"] for node in tree_data] + 
                      [c["value"] for n in tree_data for c in n["children"]],          # everything pre‑checked
            expand_on_click=True,
            only_leaf_checkboxes=False,
        )

        kept = set(sel["checked"])                                   # ids of kept nodes

    # -------------- FILTER DATA ----------------------------------------- #
    def _row_keep(row):
        tid = row["Test"]
        cid = f"{row['Test']}/{row['Test Case']}"
        return (tid in kept) or (cid in kept)

    parent_map = dict(
        zip(strategy["Test Case"], strategy["Occurs Before"])   # includes rows you later hid
    )
    filtered = strategy[strategy.apply(_row_keep, axis=1)].copy()
    kept_cases = set(filtered["Test Case"])

    def _next_kept(case):
        nxt = parent_map.get(case)              # first hop (may be None)
        while nxt is not None and nxt not in kept_cases:
            nxt = parent_map.get(nxt)           # keep hopping until we land on a kept node
        return nxt                              # can be None if we reached the tail
    filtered["Occurs Before"] = filtered["Test Case"].map(_next_kept)

    # ---------- Quick metrics -----------------------------------------------
    filtered["Duration Value"] = pd.to_numeric(filtered["Duration Value"], errors="coerce")
    test_case_durations = filtered.groupby("Test Case")["Duration Value"].max()

    # Build execution sequence (same algorithm as before, but dynamic)
    link = filtered[["Test Case", "Occurs Before"]].dropna()
    parent = dict(zip(link["Test Case"], link["Occurs Before"]))
    head = (set(parent.keys()) - set(parent.values())).pop()

    order = []
    while head:
        order.append(head)
        head = parent.get(head)

    facilities_seq = filtered.set_index("Test Case").loc[order, "Facility"].tolist()

    # Count facility changes for travel time
    loc_change = sum(
        1 for a, b in zip(facilities_seq[:-1], facilities_seq[1:]) if a != b
    )

    total_duration = test_case_durations.sum() + loc_change * 6

    cols = st.columns([0.4, 0.7])

    with cols[0]:
        colm = st.columns(3)
        colm[0].metric("Total Test Duration", f"{int(total_duration)} days")
        colm[1].metric("Total Test Cases", filtered["Test Case"].nunique())
        colm[2].metric(label="Total Tests", value=filtered["Test"].nunique(), delta_color="inverse")
        colm[0].metric("Total Facilities",  facilities["Test Facility"].nunique())
        colm[1].metric(label="Total Test Equipment", value=equipments["Equipment"].nunique(), delta_color="inverse")
        if "Test Procedure" in filtered.columns:
            colm[2].metric(label="Total Test Procedures", value=filtered["Test Procedure"].nunique(), delta_color="inverse")
    # with cols[1]:
    #     issuesinfo(project, "test_strategy")

    st.divider()


    # ─── all helper calls stay the same, but pass `filtered`
    # ---------- Graph view ---------------------------------------------------
    # make_graph_view(filtered)
    # ---------- Sequence / timeline view ------------------------------------
    make_sequence_view(filtered, order, test_case_durations, total_duration)
    # ---------- Table explorer ----------------------------------------------
    make_table_view(filtered)

# --------------------------------------------------------------------------- #
# Helper utilities – largely lifted from your earlier code, but made dynamic #
# --------------------------------------------------------------------------- #

def make_table_view(strategy):
    st.markdown("#### Test Strategy Explorer", True)
    subsetstrategy = strategy.drop(columns=["Test Equipment", "Occurs Before"])
    subsetstrategy = subsetstrategy.dropna(axis=1, how="all")
    # save column order for later displaying
    column_order = subsetstrategy.columns
    subsetcols = [col for col in subsetstrategy.columns if col != "Duration Value"]
    subsetstrategy = subsetstrategy.groupby(subsetcols, as_index=False)["Duration Value"].max()
    exp = st.expander("View Entire Test Strategy Table", icon="🗃️")
    exp.dataframe(subsetstrategy[column_order].drop_duplicates(), hide_index=True, use_container_width=True)

    cols = st.columns([0.1,0.9])
    with cols[0]:
        testopt = st.radio("Select Test", options=np.unique(strategy["Test"]), index=0)

        caseopts = strategy[strategy["Test"] == testopt]["Test Case"].value_counts().index.tolist() + ["All"]
        testcaseopt = st.radio("Select Test Case", options=caseopts, index=0)

    with cols[1]:
        if testcaseopt == "All":
            selectedstrategy = strategy[strategy["Test"] == testopt]
        else:
            selectedstrategy = strategy[(strategy["Test"] == testopt) & (strategy["Test Case"] == testcaseopt)]
        st.dataframe(selectedstrategy.drop_duplicates(), hide_index=True, use_container_width=True, height=280)

def make_graph_view(strategy: pd.DataFrame) -> None:
    st.markdown("#### Test Strategy Structure")
    dot = graphviz.Digraph(strict=True)

    for _, row in strategy.iterrows():
        s, t, c = row["Test Strategy"], row["Test"], row["Test Case"]
        if pd.notna(s): dot.node(s)
        if pd.notna(t):
            dot.node(t)
            dot.edge(s, t, label="has test")
        if pd.notna(c):
            dot.node(c, shape="box")
            dot.edge(t, c, label="has test case")

    st.graphviz_chart(dot, use_container_width=True)


def make_sequence_view(strategy, exec_order, duration_dict, total_duration):
    st.markdown("#### Execution Sequence")
    # Build timeline rows
    tl_rows = []
    current_start = pd.to_datetime("2025-01-01")  # any anchor is fine
    prev_facility = None

    durations = duration_dict.to_dict()

    for test in exec_order:
        fac = strategy.loc[strategy["Test Case"] == test, "Facility"].iloc[0]

        # Add a 6‑day transit block if facility changes
        if prev_facility and fac != prev_facility:
            transit_finish = current_start + pd.Timedelta(days=5)
            for f in (prev_facility, fac):
                tl_rows.append(
                    {"Facility": f, "Test Case": "Transit",
                     "Start": current_start, "Finish": transit_finish}
                )
            current_start = transit_finish
        # Normal test row
        dur = durations[test] if durations[test] > 1 else durations[test] + .90
        finish = current_start + pd.Timedelta(days=dur)
        tl_rows.append(
            {"Facility": fac, "Test Case": test,
             "Start": current_start, "Finish": finish}
        )
        current_start = finish
        prev_facility = fac

    tl_df = pd.DataFrame(tl_rows)

    fig = px.timeline(
        tl_df, x_start="Start", x_end="Finish",
        y="Facility", color="Test Case", text="Test Case",
        color_discrete_sequence=px.colors.qualitative.Plotly,
        color_discrete_map={"Transit": "#e4e6eb"},
    )
    # Format X axis as "Day N"
    x_end = int(6 * (total_duration // 6) + 8)
    fig.update_layout(
        bargap=0, showlegend=False,
        xaxis=dict(
            title_text="Day Count",
            tickmode="array",
            tickvals=[pd.to_datetime("2025-01-01") + pd.Timedelta(days=i)
                      for i in range(0, x_end, 6)],
            ticktext=[f"Day {i}" for i in range(0, x_end, 6)],
            range=[pd.to_datetime("2025-01-01"),
                   pd.to_datetime("2025-01-01") + pd.Timedelta(days=x_end)],
        ),
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
