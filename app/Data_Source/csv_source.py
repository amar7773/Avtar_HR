import pandas as pd

class CSVDataSource:
    def __init__(self,data_path):
        self.data_path=data_path
    def get_data(self,source_name):
        file_path=f"{self.data_path}/{source_name}.csv"
        return pd.read_csv(file_path)