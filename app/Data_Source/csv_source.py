from pathlib import Path

import pandas as pd


class CSVDataSource:
    def __init__(self, data_path):
        self.data_path = Path(data_path)

    def get_data(self, source_name):
        file_path = self.data_path / f"{source_name}.csv"
        return pd.read_csv(file_path)