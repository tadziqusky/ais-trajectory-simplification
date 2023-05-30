import pandas as pd
import numpy as np
from ais_trajectory_simplification.cleaning.functions import get_azimuths_and_distance, calculate_metrics, sort_and_reset_index

class NextBetterTrajectoryCleaner:
    def __init__(self, pdf: pd.DataFrame, speed_limit_multiplier: int = 2, acceleration_limit_kn_s = 0.5):
        self.speed_service_multiplier = speed_limit_multiplier  
        self.acceleration_limit_kn_s = acceleration_limit_kn_s
        
        self.pdf = sort_and_reset_index(pdf)
        self.pdf = calculate_metrics(self.pdf)
        self.pdf['no_of_cleaned_positions_since_prev_pos'] = 0

        self.index_column_name = self.pdf.index.name
        self.pdf = self.pdf.reset_index()
        self.index_loc = self.pdf.columns.get_loc(self.index_column_name)
        self.latitude_loc = self.pdf.columns.get_loc('latitude')
        self.longitude_loc = self.pdf.columns.get_loc('longitude')
        self.position_timestamp_loc = self.pdf.columns.get_loc('position_timestamp')
        self.speed_reference_kn_loc = self.pdf.columns.get_loc('speed_reference_kn')
        self.time_since_prev_pos_s_loc = self.pdf.columns.get_loc('time_since_prev_pos_s')
        self.distance_since_prev_pos_m_loc = self.pdf.columns.get_loc('distance_since_prev_pos_m')
        self.speed_since_prev_pos_kn_loc = self.pdf.columns.get_loc('speed_since_prev_pos_kn')
        self.acceleration_kn_loc = self.pdf.columns.get_loc('acceleration_kn_s')
        self.bearing_since_prev_pos_deg_loc = self.pdf.columns.get_loc('bearing_since_prev_pos_deg')
        self.no_of_cleaned_positions_since_prev_pos_loc = self.pdf.columns.get_loc('no_of_cleaned_positions_since_prev_pos')
        
    def _speed_over_max(self, speed_since_prev_pos_kn, speed_reference_kn):
        return speed_since_prev_pos_kn > self.speed_service_multiplier * speed_reference_kn
    
    def _acceleration_over_limit(self, acceleration_knots_s):
        return abs(acceleration_knots_s) > self.acceleration_limit_kn_s
        
    def _is_outlier(self, position):
        is_speed_over_max = self._speed_over_max(position[self.speed_since_prev_pos_kn_loc], position[self.speed_reference_kn_loc])
        is__acceleration_over_limit = self._acceleration_over_limit(position[self.acceleration_kn_loc])
        
        return any([is_speed_over_max, is__acceleration_over_limit])
    
    def _next_is_better(self, pdf_arr, i) -> int:
        lookup_limit = 4
        speed_change_limit = 2
        previous_position = pdf_arr[i-1] 
        current_position = pdf_arr[i]
        current_speed_difference = abs(current_position[self.speed_since_prev_pos_kn_loc] - previous_position[self.speed_since_prev_pos_kn_loc])
        if current_speed_difference > speed_change_limit:
            for j in range(1, min(lookup_limit, len(pdf_arr) - i)):
                candidate_position = self._calculate_from_new_previous_position(pdf_arr[i+j].copy(), previous_position)
                candidate_speed_difference = abs(candidate_position[self.speed_since_prev_pos_kn_loc] - previous_position[self.speed_since_prev_pos_kn_loc])
                
                if (candidate_speed_difference - current_speed_difference) < -2:
                    return True
            
        return False
            
    def _calculate_from_new_previous_position(self, position, prev_position):
        position[self.bearing_since_prev_pos_deg_loc], back_azimuth, position[self.distance_since_prev_pos_m_loc] = get_azimuths_and_distance(
            prev_position[self.longitude_loc], prev_position[self.latitude_loc], position[self.longitude_loc], position[self.latitude_loc]
        )
        if position[self.bearing_since_prev_pos_deg_loc] < 0:
            position[self.bearing_since_prev_pos_deg_loc] + 360

        position[self.time_since_prev_pos_s_loc] = (
            position[self.position_timestamp_loc] - prev_position[self.position_timestamp_loc]) / np.timedelta64(1, 's')
        position[self.speed_since_prev_pos_kn_loc] = (
            position[self.distance_since_prev_pos_m_loc] / position[self.time_since_prev_pos_s_loc]) * (3600 / 1852)
        position[self.acceleration_kn_loc] = (
            (position[self.speed_since_prev_pos_kn_loc] - prev_position[self.speed_since_prev_pos_kn_loc]) / position[self.time_since_prev_pos_s_loc]) 
        
        position[self.no_of_cleaned_positions_since_prev_pos_loc] = position[self.index_loc] - prev_position[self.index_loc] - 1

        return position
        
    def clean_trajectory(self):
        # start with index 1 to allow step back if index 1 is outlier
        pdf_arr = self.pdf.to_numpy()
        i = 1
        iterator_end = len(pdf_arr)
        while i < iterator_end:
            is_outlier = self._is_outlier(pdf_arr[i])
            is_better_to_take_next = self._next_is_better(pdf_arr, i)
            if (is_outlier or is_better_to_take_next):
                pdf_arr = np.delete(pdf_arr, i, axis=0)
                iterator_end = len(pdf_arr)
                if i < iterator_end:
                    pdf_arr[i] = self._calculate_from_new_previous_position(pdf_arr[i], pdf_arr[i-1])
                    
            else:
                i = i + 1

        clean_pdf_arr = pdf_arr
        result_pdf = pd.DataFrame(clean_pdf_arr, columns=self.pdf.columns).astype(self.pdf.dtypes.to_dict())
        result_pdf = result_pdf.set_index(self.index_column_name)

        return result_pdf