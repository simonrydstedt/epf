from src import constants as const
from src.epf import epf_load_data as eld

for i in [2019, 2020, 2021, 2022, 2023]:
    eld.read_svk_data(
        start_date=dt.datetime(i, 3, 26),
        end_date=dt.datetime(i, 4, 1),
        force_run=True,
    )

eld.load_wind(excel_path=const.DATA_DIR / "Vindkraftsprognos20.csv")
