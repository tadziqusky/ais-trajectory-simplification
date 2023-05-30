import pandas as pd
import pyproj
import numpy as np
import folium

def get_azimuths_and_distance(start_longitude:float, start_latitude:float, end_longitude:float, end_latitude:float):
    geodesic = pyproj.Geod(ellps='WGS84')
    result = geodesic.inv(start_longitude, start_latitude, end_longitude, end_latitude)
    
    return result

def sort_and_reset_index(pdf: pd.DataFrame, sort_col:str = 'position_timestamp') -> pd.DataFrame:
    index_column_name = 'index' if pdf.index.name == None else pdf.index.name
    pdf = pdf.reset_index()
    pdf = pdf.drop_duplicates(subset = sort_col)
    # sort values descending by position_timestamp
    pdf[sort_col] = pd.to_datetime(pdf[sort_col])
    pdf = pdf.sort_values(by=[sort_col], ascending=True)
    result_pdf = pdf.set_index(index_column_name)
    
    return result_pdf

def calculate_metrics(pdf: pd.DataFrame, default_speed_reference_kn:int = 20) -> pd.DataFrame:
    pdf = sort_and_reset_index(pdf)
    # recalculation of bearing_since_prev_pos_deg
    pdf['prev_pos_latitude'] = pdf['latitude'].shift(1)
    pdf['prev_pos_longitude'] = pdf['longitude'].shift(1)
    pdf['bearing_since_prev_pos_deg'], back_azimuth, pdf['distance_since_prev_pos_m'] = get_azimuths_and_distance(
        pdf['prev_pos_longitude'], pdf['prev_pos_latitude'], pdf['longitude'], pdf['latitude']
    )
    # convert bearing_since_prev_pos_deg from -180 - +180 to 0 - 360
    pdf['bearing_since_prev_pos_deg'][pdf['bearing_since_prev_pos_deg'] < 0] += 360
    # caclulate speed and acceleration
    pdf['prev_pos_position_timestamp'] = pdf['position_timestamp'].shift(1)
    pdf['time_since_prev_pos_s'] = (
        (pdf['position_timestamp'] - pdf['prev_pos_position_timestamp']) / np.timedelta64(1, 's')
    )
    pdf['speed_since_prev_pos_kn'] = (pdf['distance_since_prev_pos_m'] / pdf['time_since_prev_pos_s']) * (3600 / 1852)
    pdf['prev_speed_since_prev_pos_kn'] = pdf['speed_since_prev_pos_kn'].shift(1)
    pdf['acceleration_kn_s'] = (
        (pdf['speed_since_prev_pos_kn'] - pdf['prev_speed_since_prev_pos_kn']) / 
        pdf['time_since_prev_pos_s']
    )
    # add speed_reference_kn if no such column exists or replace nulls
    if 'speed_reference_kn' not in pdf:
        pdf['speed_reference_kn'] = default_speed_reference_kn
    else:
        pdf['speed_reference_kn'] = pdf['speed_reference_kn'].fillna(default_speed_reference_kn)

    return pdf
    m = folium.Map(location=[positions_pdf.iloc[0]['latitude'], positions_pdf.iloc[0]['longitude']], zoom_start=7)
    color_green = "#3f9c35"
    color_red = "#eb2a34"

    color_id = 0
    route_segment = []
    for index, position in positions_pdf.iterrows():
        route_segment.append((position['latitude'], position['longitude']))

        marker_popup_html = f"""
        <table>
            <tr><td>time:&nbsp;</td><td>{position['position_timestamp']}</td></tr>
            <tr><td>distance:&nbsp;</td><td>{round(position['distance_since_prev_pos_m']/1000, 3)} km</td></tr>
            <tr><td>speed:&nbsp;</td><td>{position['speed_since_prev_pos_kn']} kn</td></tr>
            <tr><td>acceleration:&nbsp;</td><td>{position['acceleration_kn_s']} kn/s</td></tr>
            <tr><td>lat:&nbsp;</td><td>{position['latitude']}</td></tr>
            <tr><td>lng:&nbsp;</td><td>{position['longitude']}</td></tr>
        </table>
        """

        circle_html = f"""
            <svg>
                <circle cx="10" cy="10" r="5" fill="{color_green}" fill-opacity="0" stroke="{color_green}" stroke-width="4" opacity="1"/>
                <text x="16" y="16" style="font-size: 12px">{position['position_timestamp']}</text>
            </svg>"""

        if position['outlier']:
            circle_html = f"""
                <svg>
                    <circle cx="10" cy="10" r="3" fill="{color_red}" fill-opacity="1" stroke="{color_red}" stroke-width="3" opacity="1"/>
                    <text x="16" y="16" class="small">{position['position_timestamp']}</text>
                </svg>"""

        marker_icon_html = f"""
            <div style="position:relative;">
                <div style="position:absolute;">
                    {circle_html}
                </div>
            </div>
        """

        folium.Marker(
            location=[position['latitude'], position['longitude']],
            icon=folium.DivIcon(
                icon_anchor=(10, 10),
                html=marker_icon_html
            ),
            popup=folium.Popup(folium.Html(marker_popup_html, script=True), max_width=500)
        ).add_to(m)

    folium.PolyLine(
        route_segment,
        color=color_green,
        weight=6,
        opacity=0.9,
        dash_array='5 20'
    ).add_to(m)

    folium.PolyLine(
        route_segment,
        color=color_green,
        weight=5,
        opacity=0.6,
        dash_array='5 20',
        dash_offset='5'
    ).add_to(m)

    folium.PolyLine(
        route_segment,
        color=color_green,
        weight=4,
        opacity=0.3,
        dash_array='5 20',
        dash_offset='10'
    ).add_to(m)

    folium.PolyLine(
        route_segment,
        color=color_green,
        weight=7,
        opacity=0
        #         popup = folium.Popup(folium.Html(html, script=True), max_width=500)
    ).add_to(m)

    return m