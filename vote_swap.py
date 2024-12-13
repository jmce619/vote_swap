import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# ---------------------------
# Load Data
# ---------------------------
house_results = pd.read_csv('./house_results_2024.csv')
map_gdf = gpd.read_file("map_gdf_shapefile.shp")

house_results['GEOID'] = house_results['GEOID'].astype(str)
map_gdf['GEOID'] = map_gdf['GEOID'].astype(str)

map_gdf = map_gdf.to_crs(epsg=4326)
# ---------------------------
# Helper Functions
# ---------------------------

def recalculate_winners(results_df):
    grouped = results_df.groupby('GEOID', as_index=False).apply(lambda df: df.assign(total_votes=df['votes'].sum())).reset_index(drop=True)
    idx = grouped.groupby('GEOID')['votes'].idxmax()
    winners = grouped.loc[idx].rename(columns={
        'candidate':'winner_candidate',
        'party':'winner_party',
        'votes':'winner_votes'
    })
    winners['winner_percentage'] = (winners['winner_votes'] / winners['total_votes']) * 100
    merged = grouped.merge(
        winners[['GEOID', 'winner_candidate', 'winner_party', 'winner_votes', 'winner_percentage']],
        on='GEOID', how='left'
    )
    return merged

def get_fill_color(party, winner_percentage):
    base_colors = {
        'Democrat': (0, 0, 255),
        'Republican': (255, 0, 0)
    }
    r, g, b = base_colors.get(party, (128,128,128))
    intensity = max(0.3, min(winner_percentage/100, 1.0))
    r = int(r * intensity + (1 - intensity) * 255)
    g = int(g * intensity + (1 - intensity) * 255)
    b = int(b * intensity + (1 - intensity) * 255)
    return f"rgba({r},{g},{b},{intensity})"

def create_figure(gdf):
    fig = go.Figure()
    for _, row in gdf.iterrows():
        geom = row['geometry']
        if geom is None:
            continue
        polygons = [geom] if geom.geom_type == 'Polygon' else list(geom)
        for polygon in polygons:
            lons, lats = polygon.exterior.xy
            fig.add_trace(go.Scattermapbox(
                fill="toself",
                lon=list(lons),
                lat=list(lats),
                mode='none',
                fillcolor=row['fill_color'],
                line=dict(color='black', width=1),
                hoverinfo='text',
                text=(
                    f"GEOID: {row['GEOID']}<br>"
                    f"Party: {row['winner_party']}<br>"
                    f"Votes: {row['winner_votes']}<br>"
                    f"Percentage: {row['winner_percentage']:.1f}%"
                )
            ))
    fig.update_layout(
        width=1000,
        height=800,
        mapbox_style="white-bg",
        mapbox_zoom=3,
        mapbox_center={"lat": 37.0902, "lon": -95.7129},
        margin={"r":0,"t":0,"l":0,"b":0}
    )
    return fig

# ---------------------------
# Streamlit App
# ---------------------------

st.title("US House Election Vote Redistribution")

all_parties = sorted(house_results['party'].unique().tolist())

from_parties = st.multiselect("From Party(ies)", options=all_parties, default=[])
to_party = st.selectbox("To Party", options=[p for p in all_parties if p not in from_parties])

# Initial calculation
initial_results = recalculate_winners(house_results)
initial_map_gdf = map_gdf.merge(
    initial_results[['GEOID','winner_party','winner_votes','winner_percentage','total_votes']].drop_duplicates('GEOID'),
    on='GEOID', how='left'
)
initial_map_gdf['fill_color'] = initial_map_gdf.apply(lambda r: get_fill_color(r['winner_party'], r['winner_percentage']), axis=1)

# Draw initial figure
initial_fig = create_figure(initial_map_gdf)

# Create a placeholder for when the button is not yet clicked
redistribution_clicked = st.button("Redistribute Votes")

if redistribution_clicked:
    # Perform redistribution
    redistributed = house_results.copy()
    for geoid_val in redistributed['GEOID'].unique():
        df_dist = redistributed[redistributed['GEOID'] == geoid_val]
        # Sum from_parties votes
        from_votes = df_dist[df_dist['party'].isin(from_parties)]['votes'].sum()
        # Set from_parties votes to 0
        redistributed.loc[(redistributed['GEOID'] == geoid_val) & 
                          (redistributed['party'].isin(from_parties)), 'votes'] = 0

        # Add these votes to the to_party
        if not ((redistributed['GEOID'] == geoid_val) & (redistributed['party'] == to_party)).any():
            example_row = df_dist.iloc[0].copy()
            example_row['party'] = to_party
            example_row['candidate'] = f"{to_party} Candidate"
            example_row['votes'] = from_votes
            redistributed = pd.concat([redistributed, pd.DataFrame([example_row])], ignore_index=True)
        else:
            redistributed.loc[(redistributed['GEOID'] == geoid_val) & 
                              (redistributed['party'] == to_party), 'votes'] += from_votes

    updated_results = recalculate_winners(redistributed)
    updated_map_gdf = map_gdf.merge(
        updated_results[['GEOID','winner_party','winner_votes','winner_percentage','total_votes']].drop_duplicates('GEOID'),
        on='GEOID', how='left'
    )
    updated_map_gdf['fill_color'] = updated_map_gdf.apply(lambda r: get_fill_color(r['winner_party'], r['winner_percentage']), axis=1)

    updated_fig = create_figure(updated_map_gdf)

    # Now show both maps in separate tabs
    tab1, tab2 = st.tabs(["Original Map", "Redistributed Map"])
    with tab1:
        st.plotly_chart(initial_fig, use_container_width=True)
    with tab2:
        st.plotly_chart(updated_fig, use_container_width=True)

else:
    # Before redistribution, just show the original map
    st.plotly_chart(initial_fig, use_container_width=True)
