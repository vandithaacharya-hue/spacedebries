"""Mission-control dashboard for exploring the bundled satellite catalog."""

import math
from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


CATALOG_PATH = Path(__file__).with_name("satcat.csv")
REQUIRED_COLUMNS = [
    "OBJECT_NAME",
    "OBJECT_ID",
    "NORAD_CAT_ID",
    "OBJECT_TYPE",
    "OPS_STATUS_CODE",
    "OWNER",
    "LAUNCH_DATE",
    "LAUNCH_SITE",
    "DECAY_DATE",
    "PERIOD",
    "INCLINATION",
    "APOGEE",
    "PERIGEE",
    "RCS",
    "DATA_STATUS_CODE",
    "ORBIT_CENTER",
    "ORBIT_TYPE",
]


@st.cache_data(ttl="1h")
def load_catalog() -> pd.DataFrame:
    catalog = pd.read_csv(CATALOG_PATH, low_memory=False)
    validate_catalog(catalog)
    return catalog


def validate_catalog(catalog: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in catalog.columns]
    if missing:
        raise ValueError(f"Catalog is missing required columns: {', '.join(missing)}")


@st.fragment(run_every="5s")
def render_live_orbit(
    object_name: str,
    norad_id: str,
    inclination: float,
    period_minutes: float,
    mean_altitude_km: float,
) -> None:
    """Render a clearly labeled, simulated orbit visualization and telemetry."""
    now = datetime.now(timezone.utc)
    phase = now.timestamp() * (2 * math.pi / 45)
    orbit_radius = 1.5 + min(max(mean_altitude_km / 20_000, 0), 0.65)
    inclination_factor = math.sin(math.radians(inclination))

    orbit_points = []
    for step in range(181):
        angle = step * math.pi / 90
        orbit_points.append(
            {
                "x": orbit_radius * math.cos(angle),
                "y": orbit_radius * math.sin(angle) * inclination_factor,
            }
        )
    orbit = pd.DataFrame(orbit_points)
    satellite = pd.DataFrame(
        [
            {
                "x": orbit_radius * math.cos(phase),
                "y": orbit_radius * math.sin(phase) * inclination_factor,
                "object": object_name,
                "norad_id": norad_id,
            }
        ]
    )
    earth = pd.DataFrame([{"x": 0, "y": 0}])
    equator = pd.DataFrame(
        {
            "x": [-1, 1],
            "y": [0, 0],
        }
    )

    x_axis = alt.X("x:Q", axis=None, scale=alt.Scale(domain=(-2.5, 2.5)))
    y_axis = alt.Y("y:Q", axis=None, scale=alt.Scale(domain=(-2.5, 2.5)))
    chart = (
        alt.Chart(orbit)
        .mark_line(color="#1aa8cf", strokeWidth=2, opacity=0.85)
        .encode(x=x_axis, y=y_axis)
        + alt.Chart(equator)
        .mark_line(color="#5e91b6", strokeDash=[4, 5], opacity=0.45)
        .encode(x=x_axis, y=y_axis)
        + alt.Chart(earth)
        .mark_circle(size=19_000, color="#103c61", stroke="#47b8e9", strokeWidth=2)
        .encode(x=x_axis, y=y_axis)
        + alt.Chart(earth)
        .mark_text(text="EARTH", color="#dceeff", fontSize=13, fontWeight="bold")
        .encode(x=x_axis, y=y_axis)
        + alt.Chart(satellite)
        .mark_circle(size=180, color="#36e0c1", stroke="#e8fffb", strokeWidth=1.5)
        .encode(
            x=x_axis,
            y=y_axis,
            tooltip=["object:N", "NORAD ID:N"],
        )
    ).properties(height=340)
    chart = chart.configure_view(stroke=None).configure(background="transparent")

    altitude_variation = 1 + 0.008 * math.sin(phase)
    altitude = mean_altitude_km * altitude_variation
    orbital_radius_km = 6371 + max(altitude, 0)
    velocity = math.sqrt(398600.4418 / orbital_radius_km)
    velocity *= 1 + 0.002 * math.cos(phase)
    inclination_reading = inclination + 0.04 * math.sin(phase / 2)

    orbit_column, telemetry_column = st.columns([1.7, 1], gap="medium")
    with orbit_column:
        with st.container(border=True):
            st.subheader("Orbital view")
            st.caption(
                "Illustrative 2D orbit · marker and telemetry refresh every 5 seconds"
            )
            st.altair_chart(chart, alt="Illustrative orbit path around Earth")
            st.caption(f"Tracking focus: {object_name} · NORAD {norad_id}")

    with telemetry_column:
        with st.container(border=True):
            st.subheader("Telemetry")
            st.badge("Simulated feed", icon=":material/sync:", color="blue")
            st.caption(f"Updated {now.strftime('%H:%M:%S UTC')}")
            st.metric("Mean altitude", f"{altitude:,.1f} km")
            st.metric("Orbital velocity", f"{velocity:.2f} km/s")
            st.metric("Inclination", f"{inclination_reading:.2f}°")
            st.metric("Orbital period", f"{period_minutes:,.1f} min")


st.set_page_config(
    page_title="OrbitWatch | Mission control",
    page_icon=":material/satellite_alt:",
    layout="wide",
)

try:
    catalog = load_catalog()
except (
    OSError,
    pd.errors.EmptyDataError,
    pd.errors.ParserError,
    UnicodeDecodeError,
    ValueError,
) as error:
    st.error(f"Could not load the bundled satellite catalog: {error}")
    st.stop()

with st.sidebar:
    st.title("OrbitWatch", anchor=False)
    st.caption("MISSION CONTROL")
    st.header("Catalog controls")
    uploaded_file = st.file_uploader(
        "Use another catalog CSV (optional)", type=["csv"]
    )
    st.caption("Bundled data is a static catalog snapshot, not a live feed.")

if uploaded_file is not None:
    try:
        catalog = pd.read_csv(uploaded_file, low_memory=False)
        validate_catalog(catalog)
    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
        ValueError,
    ) as error:
        st.error(f"Could not read the uploaded catalog CSV: {error}")
        st.stop()

with st.sidebar:
    object_types = sorted(catalog["OBJECT_TYPE"].dropna().unique().tolist())
    orbit_centers = sorted(catalog["ORBIT_CENTER"].dropna().unique().tolist())
    statuses = sorted(catalog["OPS_STATUS_CODE"].dropna().unique().tolist())
    status_options = ["Unknown", *statuses]

    selected_types = st.multiselect(
        "Object type", options=object_types, default=object_types
    )
    selected_orbit_centers = st.multiselect(
        "Orbit center", options=orbit_centers, default=orbit_centers
    )
    selected_statuses = st.multiselect(
        "Operational-status code", options=status_options, default=status_options
    )
    rows_to_show = st.slider(
        "Rows in table", min_value=10, max_value=1000, value=100, step=10
    )

status_values = catalog["OPS_STATUS_CODE"].fillna("Unknown")
visible = catalog[
    catalog["OBJECT_TYPE"].isin(selected_types)
    & catalog["ORBIT_CENTER"].isin(selected_orbit_centers)
    & status_values.isin(selected_statuses)
].copy()

st.title("Mission control", icon=":material/satellite_alt:")
header_left, header_right = st.columns([3, 1], vertical_alignment="center")
with header_left:
    st.caption("ORBITAL CATALOG · GLOBAL VIEW")
with header_right:
    st.badge("CATALOG ONLINE", icon=":material/radio_button_checked:", color="green")
    st.caption(f"UTC {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")

with st.container(horizontal=True):
    st.metric("Catalog objects", f"{len(catalog):,}", border=True)
    st.metric("Matching objects", f"{len(visible):,}", border=True)
    st.metric(
        "Debris objects",
        f"{int(visible['OBJECT_TYPE'].eq('DEB').sum()):,}",
        border=True,
    )
    st.metric(
        "Payloads",
        f"{int(visible['OBJECT_TYPE'].eq('PAY').sum()):,}",
        border=True,
    )

orbit_columns = ["INCLINATION", "PERIOD", "APOGEE", "PERIGEE"]
orbit_candidates = visible.copy()
for column in orbit_columns:
    orbit_candidates[column] = pd.to_numeric(
        orbit_candidates[column], errors="coerce"
    )
orbit_candidates = orbit_candidates.dropna(subset=["INCLINATION", "PERIOD"])

if orbit_candidates.empty:
    with st.container(border=True):
        st.subheader("Orbital view")
        st.info("No matching records include enough orbit data to plot.")
else:
    focus = orbit_candidates.iloc[0]
    mean_altitude = pd.Series(
        [focus["APOGEE"], focus["PERIGEE"]], dtype="float64"
    ).mean()
    if pd.isna(mean_altitude):
        mean_altitude = 0.0
    render_live_orbit(
        str(focus["OBJECT_NAME"]),
        str(focus["NORAD_CAT_ID"]),
        float(focus["INCLINATION"]),
        float(focus["PERIOD"]),
        float(mean_altitude),
    )

st.caption("LIVE GRAPHICS ARE SIMULATED · CATALOG VALUES REMAIN STATIC")
st.caption("No real-time spacecraft position or collision-risk data is provided.")

chart_columns = st.columns(2, gap="medium")
with chart_columns[0]:
    with st.container(border=True):
        st.subheader("Objects by type")
        type_counts = (
            visible["OBJECT_TYPE"]
            .value_counts()
            .rename_axis("Object type")
            .reset_index(name="Objects")
        )
        if type_counts.empty:
            st.info("No catalog records match the selected filters.")
        else:
            st.bar_chart(
                type_counts,
                x="Object type",
                y="Objects",
                alt="Number of matching catalog objects by type",
            )

with chart_columns[1]:
    with st.container(border=True):
        st.subheader("Orbit profile")
        profile = visible[["OBJECT_TYPE", "INCLINATION", "APOGEE", "PERIGEE"]].copy()
        for column in ["INCLINATION", "APOGEE", "PERIGEE"]:
            profile[column] = pd.to_numeric(profile[column], errors="coerce")
        profile["Mean altitude (km)"] = profile[["APOGEE", "PERIGEE"]].mean(axis=1)
        profile = profile.dropna(subset=["INCLINATION", "Mean altitude (km)"])
        if profile.empty:
            st.info("No matching records include altitude and inclination values.")
        else:
            if len(profile) > 2000:
                profile = profile.sample(n=2000, random_state=42)
            orbit_profile = (
                alt.Chart(profile)
                .mark_circle(size=52, opacity=0.6)
                .encode(
                    x=alt.X("INCLINATION:Q", title="Inclination (°)"),
                    y=alt.Y("Mean altitude (km):Q", title="Mean altitude (km)"),
                    color=alt.Color("OBJECT_TYPE:N", title="Object type"),
                    tooltip=[
                        alt.Tooltip("OBJECT_TYPE:N", title="Object type"),
                        alt.Tooltip("INCLINATION:Q", title="Inclination", format=".2f"),
                        alt.Tooltip(
                            "Mean altitude (km):Q",
                            title="Mean altitude",
                            format=",.1f",
                        ),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(
                orbit_profile,
                alt="Catalog objects plotted by inclination and mean altitude",
            )

with st.container(border=True):
    table_header, download_column = st.columns([3, 1], vertical_alignment="bottom")
    with table_header:
        st.subheader("Satellite catalog")
        st.caption(f"Showing up to {rows_to_show:,} of {len(visible):,} matching records")
    with download_column:
        st.download_button(
            "Download filtered catalog",
            data=visible.to_csv(index=False).encode("utf-8"),
            file_name="satcat_filtered.csv",
            mime="text/csv",
            width="stretch",
        )
    st.dataframe(
        visible.head(rows_to_show),
        hide_index=True,
        alt="Filtered satellite catalog records",
    )
