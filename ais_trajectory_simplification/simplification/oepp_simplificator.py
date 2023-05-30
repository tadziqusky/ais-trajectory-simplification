import pandas as pd
import numpy as np
from ais_trajectory_simplification.cleaning.functions import get_azimuths_and_distance, calculate_metrics, sort_and_reset_index


class OEPPSimplificator:
    def __init__(self, pdf: pd.DataFrame, speed_limit_multiplier: int = 2):
        self.speed_service_multiplier = speed_limit_multiplier

        self.pdf = sort_and_reset_index(pdf)
        self.pdf = calculate_metrics(self.pdf)
        self.pdf['no_of_cleaned_positions_since_prev_pos'] = 0

        self.index_column_name = self.pdf.index.name
        self.pdf = self.pdf.reset_index()
        self.index_loc = self.pdf.columns.get_loc(self.index_column_name)
        self.latitude_loc = self.pdf.columns.get_loc('latitude')
        self.longitude_loc = self.pdf.columns.get_loc('longitude')
        self.prev_pos_latitude_loc = self.pdf.columns.get_loc(
            'prev_pos_latitude')
        self.prev_pos_longitude_loc = self.pdf.columns.get_loc(
            'prev_pos_longitude')
        self.position_timestamp_loc = self.pdf.columns.get_loc(
            'position_timestamp')
        self.prev_pos_position_timestamp_loc = self.pdf.columns.get_loc(
            'prev_pos_position_timestamp')
        self.speed_reference_kn_loc = self.pdf.columns.get_loc(
            'speed_reference_kn')
        self.time_since_prev_pos_s_loc = self.pdf.columns.get_loc(
            'time_since_prev_pos_s')
        self.distance_since_prev_pos_m_loc = self.pdf.columns.get_loc(
            'distance_since_prev_pos_m')
        self.speed_since_prev_pos_kn_loc = self.pdf.columns.get_loc(
            'speed_since_prev_pos_kn')
        self.prev_speed_since_prev_pos_kn_loc = self.pdf.columns.get_loc(
            'prev_speed_since_prev_pos_kn')
        self.acceleration_kn_s_loc = self.pdf.columns.get_loc(
            'acceleration_kn_s')
        self.bearing_since_prev_pos_deg_loc = self.pdf.columns.get_loc(
            'bearing_since_prev_pos_deg')
        self.no_of_cleaned_positions_since_prev_pos_loc = self.pdf.columns.get_loc(
            'no_of_cleaned_positions_since_prev_pos')

    def _is_stop(self, pdf, stop_max_distance_m):
        bearing, back_azimuth, distance_m = get_azimuths_and_distance(
            min(pdf[:, self.longitude_loc]), min(pdf[:, self.latitude_loc]), max(
                pdf[:, self.longitude_loc]), max(pdf[:, self.latitude_loc])
        )

        return distance_m < stop_max_distance_m

    def _is_bearing_straight(self, pdf_arr, max_heading_deviation_deg, max_speed_deviation_kn):
        bearing_arr = pdf_arr[:, self.bearing_since_prev_pos_deg_loc]
        heading_min_deg = min(bearing_arr)
        heading_max_deg = max(bearing_arr)

        if (heading_min_deg - max_heading_deviation_deg) <= 0 and (heading_max_deg + max_heading_deviation_deg) >= 360:
            if any((bearing_arr <= 360 - max_heading_deviation_deg) & (bearing_arr >= max_heading_deviation_deg)):
                return False
            heading_min_deg = bearing_arr[bearing_arr >
                                          360 - max_heading_deviation_deg].min() - 360
            heading_max_deg = bearing_arr[bearing_arr <
                                          max_heading_deviation_deg].max()

        heading_deviation_deg = heading_max_deg - heading_min_deg
        proper_heading_deviation = heading_deviation_deg <= max_heading_deviation_deg

        speed_range = max(pdf_arr[:, self.speed_since_prev_pos_kn_loc]
                          ) - min(pdf_arr[:, self.speed_since_prev_pos_kn_loc])
        proper_speed_limit = speed_range <= max_speed_deviation_kn
        return proper_heading_deviation and proper_speed_limit

    def _calculate_from_new_previous_position(self, position, prev_position):
        position[self.bearing_since_prev_pos_deg_loc], back_azimuth, position[self.distance_since_prev_pos_m_loc] = get_azimuths_and_distance(
            prev_position[self.longitude_loc], prev_position[self.latitude_loc], position[self.longitude_loc], position[self.latitude_loc])
        if position[self.bearing_since_prev_pos_deg_loc] < 0:
            position[self.bearing_since_prev_pos_deg_loc] + 360

        position[self.time_since_prev_pos_s_loc] = (
            position[self.position_timestamp_loc] - prev_position[self.position_timestamp_loc]) / np.timedelta64(1, 's')
        position[self.speed_since_prev_pos_kn_loc] = (
            position[self.distance_since_prev_pos_m_loc] / position[self.time_since_prev_pos_s_loc]) * (3600 / 1852)

        position[self.no_of_cleaned_positions_since_prev_pos_loc] = position[self.index_loc] - \
            prev_position[self.index_loc] - 1

        return position

    def simplify_trajectory(self, stop_max_distance_m, max_heading_deviation_deg, max_speed_deviation_kn):
        pdf_arr = self.pdf.to_numpy()
        min_segment_size = 4
        i = min_segment_size
        segment_start = 0
        iterator_end = len(pdf_arr)
        while segment_start + i <= iterator_end:
            segment_pdf = pdf_arr[segment_start:segment_start+i]
            is_stop = self._is_stop(segment_pdf, stop_max_distance_m)
            is_bearing_straight = self._is_bearing_straight(
                segment_pdf, max_heading_deviation_deg, max_speed_deviation_kn)

            if ((not is_stop) and (not is_bearing_straight)) or (segment_start + i) == iterator_end:
                if i > min_segment_size:
                    pdf_arr = np.delete(pdf_arr, np.s_[segment_start+1:segment_start+i-2], axis=0)
                    pdf_arr[segment_start+1] = self._calculate_from_new_previous_position(pdf_arr[segment_start+1], pdf_arr[segment_start])
                    segment_start = segment_start + 1
                    iterator_end = len(pdf_arr)
                    i = min_segment_size
                else:
                    segment_start = segment_start + 1
                    i = min_segment_size
            else:
                i = i + 1

        clean_pdf_arr = pdf_arr
        result_pdf = pd.DataFrame(clean_pdf_arr, columns=self.pdf.columns).astype(
            self.pdf.dtypes.to_dict())
        result_pdf = result_pdf.drop(
            result_pdf.columns[
                [
                    self.prev_pos_latitude_loc,
                    self.prev_pos_longitude_loc,
                    self.prev_pos_position_timestamp_loc,
                    self.prev_speed_since_prev_pos_kn_loc,
                    self.acceleration_kn_s_loc,
                    self.bearing_since_prev_pos_deg_loc,
                ]
            ],
            axis=1
        )
        result_pdf = result_pdf.set_index(self.index_column_name)

        return result_pdf
