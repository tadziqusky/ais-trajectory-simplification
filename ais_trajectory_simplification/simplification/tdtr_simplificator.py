import pandas as pd
import numpy as np
from ais_trajectory_simplification.cleaning.functions import get_azimuths_and_distance, calculate_metrics, sort_and_reset_index
from geopy import distance
from sortedcontainers import SortedList


class TDTRSimplificator:
    def __init__(self, pdf: pd.DataFrame):
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

    def simplify_trajectory(self, epsilon_m):
        points = self.pdf.to_numpy()
        selected_points_positions = SortedList([0, len(points) - 1])  # , key=lambda x: x[0])
        start_point_position = 0
        while start_point_position < len(selected_points_positions) - 1:
            (farthest_point, distance) = self.find_farthest_point(
                points[selected_points_positions[start_point_position]:selected_points_positions[start_point_position+1]+1])
            if distance > epsilon_m:
                idx = np.where(points[:, self.index_loc] == farthest_point[self.index_loc])[0][0]
                selected_points_positions.add(idx)
            else:
                start_point_position = start_point_position + 1
                while (start_point_position < len(selected_points_positions) - 1) and (selected_points_positions[start_point_position] + 1 == selected_points_positions[start_point_position+1]):
                    start_point_position = start_point_position + 1

        # add also no_of_cleaned_positions_since_prev_pos
        simplified_pdf_arr = points[selected_points_positions, :]
        result_pdf = pd.DataFrame(simplified_pdf_arr, columns=self.pdf.columns).astype(
            self.pdf.dtypes.to_dict())
        result_pdf = result_pdf.drop(
            result_pdf.columns[
                [
                    self.prev_pos_latitude_loc,
                    self.prev_pos_longitude_loc,
                    self.prev_pos_position_timestamp_loc,
                    self.time_since_prev_pos_s_loc,
                    self.distance_since_prev_pos_m_loc,
                    self.speed_since_prev_pos_kn_loc,
                    self.prev_speed_since_prev_pos_kn_loc,
                    self.acceleration_kn_s_loc,
                    self.bearing_since_prev_pos_deg_loc,
                    self.prev_speed_since_prev_pos_kn_loc
                ]
            ],
            axis=1
        )
        result_pdf = result_pdf.set_index(self.index_column_name)
        result_pdf = calculate_metrics(result_pdf)

        return result_pdf

    def find_farthest_point(self, points: np.ndarray):
        start_point = points[0]
        end_point = points[-1]
        perpendicular_distance_f = self.sed_distance_from_line(start_point, end_point)
        farthest_point = max(points[1:-1], default=-1, key=perpendicular_distance_f)
        if isinstance(farthest_point, int):
            return (None, 0)
        else:
            return (farthest_point, perpendicular_distance_f(farthest_point))

    def sed_distance_from_line(self, start_point, end_point):
        def distance_from_line_wrapper_m(point):
            ratio = (point[self.position_timestamp_loc] - start_point[self.position_timestamp_loc]) / (end_point[self.position_timestamp_loc] - start_point[self.position_timestamp_loc])
            perpendicular_point = self.sed_point_on_line(
                start_point[self.longitude_loc],
                start_point[self.latitude_loc],
                end_point[self.longitude_loc],
                end_point[self.latitude_loc],
                ratio)
            return distance.distance((perpendicular_point[1], perpendicular_point[0]), (point[self.latitude_loc], point[self.longitude_loc])).m

        return distance_from_line_wrapper_m


    def sed_point_on_line(self, x1, y1, x2, y2, ratio):
        dx = (x2 - x1) * ratio
        dy = (y2 - y1) * ratio

        x = x1 + dx
        y = y1 + dy
        return x, y
