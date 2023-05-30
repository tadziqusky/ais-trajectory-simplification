import pandas as pd
import numpy as np
from ais_trajectory_simplification.cleaning.functions import calculate_metrics, sort_and_reset_index


class DownsamplingSimplificator:
    def __init__(self, pdf: pd.DataFrame):
        self.pdf = sort_and_reset_index(pdf)
        self.pdf 

    def simplify_trajectory(self, downsampling_sec):
        result_pdf = self.pdf.copy()
        # result_pdf['position_timestamp'] = result_pdf['position_timestamp'].dt.tz_convert(None)

        result_pdf['time_group'] = np.floor(
            (result_pdf['position_timestamp'] - pd.Timestamp("1970-01-01")) / pd.Timedelta(f"{downsampling_sec}s")).astype('int')

        # last should have different value
        result_pdf.loc[result_pdf['position_timestamp'] ==
                       result_pdf['position_timestamp'].max(), 'time_group'] = 99999999

        result_pdf = result_pdf.groupby('time_group').first()
        result_pdf = result_pdf.sort_values('position_timestamp')
        result_pdf = result_pdf.reset_index(drop=True)
        result_pdf.index.name = "index"
        
        result_pdf = calculate_metrics(result_pdf)
        return result_pdf
