import os
import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(layout="wide", page_title="WHO COVID‑19 — Health Analytics Dashboard")


@st.cache_data
def load_data():
    """Load WHO data with a few fallbacks to avoid FileNotFound on Streamlit Cloud.

    Order of attempts:
    1. Local filename in working directory
    2. File next to this script (repo root when deployed)
    3. URL from environment variable DATA_URL
    4. Raw GitHub URL for this repo (useful if you keep the CSV in the repo)

    If all attempts fail, show a friendly message in the app and stop.
    """
    filename = "WHO-COVID-19-global-data.csv"

    # 1) Try local working directory
    try_paths = [filename]

    # 2) Try file located next to this script (common when deployed)
    try_paths.append(os.path.join(os.path.dirname(__file__), filename))

    # 3) Try environment override (useful for deployments)
    env_url = os.environ.get("DATA_URL")
    if env_url:
        try_paths.append(env_url)

    # try each path/URL
    for p in try_paths:
        try:
            df = pd.read_csv(p, parse_dates=["Date_reported"]) if p.startswith("http") else pd.read_csv(p, parse_dates=["Date_reported"])
            df.columns = [c.strip() for c in df.columns]
            return df
        except FileNotFoundError:
            # try next path
            continue
        except Exception as e:
            # If it's a URL/network or parse issue, show it so it's easier to debug
            st.error(f"Error reading data from {p}: {e}")
            st.stop()

    # 4) Final fallback: try raw file from this GitHub repo (update if you moved the CSV)
    github_raw = "https://raw.githubusercontent.com/Tomifemme/dashboard/main/WHO-COVID-19-global-data.csv"
    try:
        df = pd.read_csv(github_raw, parse_dates=["Date_reported"])
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception:
        st.error(
            "Data file 'WHO-COVID-19-global-data.csv' not found.\n"
            "Fix options:\n"
            " - Add the CSV to the repository root and push to GitHub.\n"
            " - Set the DATA_URL environment variable to a public CSV URL.\n"
            " - Use Streamlit's file uploader to upload the CSV at runtime.\n"
        )
        st.info("If you want, I can add the CSV file to the repo for you. Or set DATA_URL in Streamlit Cloud settings.")
        st.stop()

def preprocess(df):
    df = df.copy()
    # Ensure a valid Country column exists
    if "Country" not in df.columns:
        # try to automatically detect any column containing 'country'
        country_cols = [c for c in df.columns if "country" in c.lower()]
        if country_cols:
            df["Country"] = df[country_cols[0]]
        else:
            df["Country"] = "Unknown"
    df["Date"] = pd.to_datetime(df["Date_reported"], errors="coerce").dt.date
    for col in ["New_cases", "New_deaths", "Cumulative_cases", "Cumulative_deaths"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    # Clean Country column to prevent empty/NaN errors
    df["Country"] = df["Country"].fillna("Unknown").astype(str).str.strip()
    return df


def main():
    st.title("WHO COVID‑19 — Covid Cases Comparison")

    tab1, tab2 = st.tabs(["Dashboard", "Insights Story"])

    with tab1:
        st.markdown("""
        ### Overview  
        As a health analyst, understanding how a country’s outbreak evolves requires looking at changes from multiple angles.  
        Comparing growth rates shows how fast situations shift, trend comparisons reveal how countries differ in daily impact,  
        and the global context helps interpret whether national movements follow or diverge from worldwide patterns.
        """)

        df_raw = load_data()
        df = preprocess(df_raw)

        # Sidebar Filters
        st.sidebar.header("Global Filters")
        all_countries = sorted(df["Country"].unique())
        c1 = st.sidebar.selectbox("Primary Country", all_countries)
        c2 = st.sidebar.selectbox("Comparison Country", all_countries, index=all_countries.index("Italy") if "Italy" in all_countries else 1)
        metric = st.sidebar.selectbox("Metric", ["New_cases", "New_deaths"])
        date_min, date_max = df["Date_reported"].min(), df["Date_reported"].max()
        date_range = st.sidebar.slider("Date Range", min_value=date_min.date(), max_value=date_max.date(), value=(date_min.date(), date_max.date()))

        mask = (df["Date"] >= date_range[0]) & (df["Date"] <= date_range[1])
        df_f = df[mask]

        # Country subsets
        df_c1 = df_f[df_f["Country"] == c1]
        df_c2 = df_f[df_f["Country"] == c2]
        df_global = df_f.groupby("Date")[ ["New_cases", "New_deaths"] ].sum().reset_index()


        top_left, top_right = st.columns(2)

       #first plot
        with top_left:
            st.subheader("Growth Rate Comparison")

            # compute growth rate for both countries
            df_compare = pd.concat([
                df_c1.assign(Country=c1),
                df_c2.assign(Country=c2)
            ])

            df_gr = df_compare.copy()
            df_gr["GrowthRate"] = df_gr.groupby("Country")[metric].pct_change().fillna(0)

            chart_gr = (
                alt.Chart(df_gr)
                .mark_area(opacity=0.65)
                .encode(
                    x=alt.X("Date:T", title="Date"),
                    y=alt.Y("GrowthRate:Q", title="Growth Rate (Percent Change)"),
                    color=alt.Color(
                        "Country",
                        scale=alt.Scale(scheme="tableau10"),
                        legend=alt.Legend(orient="bottom")
                    ),
                    tooltip=["Country", "Date", "GrowthRate"]
                )
                .properties(height=320)
            )

            st.altair_chart(chart_gr, use_container_width=True)

        #second plot
        with top_right:
            st.subheader(f"Comparison: {c1} vs {c2}")

            df_compare = pd.concat([
                df_c1.assign(Country=c1),
                df_c2.assign(Country=c2)
            ])

            chart2 = (
                alt.Chart(df_compare)
                .mark_line(point=True)
                .encode(
                    x="Date:T",
                    y=alt.Y(metric, title=f"{metric.replace('_',' ').title()} (Daily Count)"),
                    color=alt.Color(
                        "Country",
                        scale=alt.Scale(scheme="tableau10"),
                        legend=alt.Legend(orient="bottom")
                    ),
                    tooltip=["Country", "Date", metric]
                )
                .properties(height=320)
            )
            st.altair_chart(chart2, use_container_width=True)

        bottom = st.container()

        #third plot
        with bottom:
            st.subheader("Global Outbreak Context")

            chart3 = (
                alt.Chart(df_global)
                .mark_area(opacity=0.4)
                .encode(
                    x="Date:T",
                    y=alt.Y(metric, title=f"Global {metric.replace('_',' ').title()} (Sum)"),
                    tooltip=["Date", metric]
                )
                .properties(height=260)
            )
            st.altair_chart(chart3, use_container_width=True)

        st.markdown("### Key Insights & Performance Interpretation")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"""
            **{c1} — Key Metrics**  
            - Peak {metric.replace('_',' ')}: **{df_c1[metric].max():,}**  
            - Average daily {metric.replace('_',' ')}: **{df_c1[metric].mean():.2f}**
            """)

        with col2:
            st.markdown(f"""
            **{c2} — Key Metrics**  
            - Peak {metric.replace('_',' ')}: **{df_c2[metric].max():,}**  
            - Average daily {metric.replace('_',' ')}: **{df_c2[metric].mean():.2f}**
            """)

        st.markdown("These values highlight where the countries differ most clearly in intensity and consistency, complementing the visual patterns above.")
       
    with tab2:
        st.header("Comparative Story & Additional Metrics")


        st.subheader("Selected Countries vs Rest of World")

        # compute rest of world by subtracting selected countries from global totals
        df_world = df_f.groupby("Date")[metric].sum().reset_index().rename(columns={metric: "WorldTotal"})
        df_two = df_compare.groupby("Date")[metric].sum().reset_index().rename(columns={metric: "TwoCountries"})

        #Combined Germany+Italy vs Rest of World (Bar Comparison)
        st.subheader("Combined Contribution vs Rest of World (Total over Selected Period)")

        total_two = df_two["TwoCountries"].sum()
        total_world = df_world["WorldTotal"].sum()
        total_rest = total_world - total_two

        df_comp = pd.DataFrame({
            "Group": [f"{c1} + {c2}", "Rest of World"],
            "Total": [total_two, total_rest]
        })

        chart_rest = (
            alt.Chart(df_comp)
            .mark_bar()
            .encode(
                x=alt.X("Group:N", title="Group"),
                y=alt.Y("Total:Q", title=f"Total {metric.replace('_',' ').title()}"),
                color=alt.Color("Group:N", scale=alt.Scale(scheme="tableau10")),
                tooltip=["Group", "Total"]
            )
            .properties(height=300)
        )

        st.altair_chart(chart_rest, use_container_width=True)

        # Case Fatality Ratio
        st.subheader("Case Fatality Ratio (CFR) Comparison")

        df_cfr = pd.concat([
            df_c1.assign(Country=c1),
            df_c2.assign(Country=c2)
        ])

        # Avoid division by zero
        df_cfr["CFR"] = df_cfr["Cumulative_deaths"] / df_cfr["Cumulative_cases"].replace({0: None})

        chart_cfr = (
            alt.Chart(df_cfr)
            .mark_line(point=True)
            .encode(
                x="Date:T",
                y=alt.Y("CFR:Q", title="Case Fatality Ratio"),
                color=alt.Color("Country", scale=alt.Scale(scheme="tableau10")),
                tooltip=["Country", "Date", "CFR"]
            )
            .properties(height=260)
        )


        st.altair_chart(chart_cfr, use_container_width=True)

        # Bar Chart for Top Countries
        st.subheader("Top Countries Ranking")

        # choose ranking metric based on sidebar selection
        rank_metric = metric  # either New_cases or New_deaths

        # compute total over selected date range
        df_rank = (
            df_f.groupby("Country")[rank_metric]
            .sum()
            .reset_index()
            .sort_values(rank_metric, ascending=False)
        )

        # take top 10 countries
        df_top = df_rank.head(10).copy()

        # ensure selected countries appear even if not top 10
        for sel in [c1, c2]:
            if sel not in df_top["Country"].values:
                sel_row = df_rank[df_rank["Country"] == sel]
                df_top = pd.concat([df_top, sel_row])

        # flag selected countries for color
        df_top["Selected"] = df_top["Country"].apply(
            lambda x: f"{x} (Selected)" if x in [c1, c2] else "Other"
        )

        chart_rank = (
            alt.Chart(df_top)
            .mark_bar()
            .encode(
                x=alt.X(rank_metric + ":Q", title=f"Total {rank_metric.replace('_',' ')}"),
                y=alt.Y("Country:N", sort="-x"),
                color=alt.Color("Selected:N", scale=alt.Scale(scheme="tableau10")),
                tooltip=["Country", rank_metric]
            )
            .properties(height=400)
        )

        st.altair_chart(chart_rank, use_container_width=True)

        st.markdown(
            f"**Conclusion:** Across the two tabs, {c1} and {c2} show distinct outbreak patterns. "
            f"{c1} may excel in stability or lower fatality, while {c2} may show stronger surges or higher variability. "
            f"These differences reflect how each country’s response and outbreak trajectory diverged over time."
        )
   
if __name__ == "__main__":
    main()
