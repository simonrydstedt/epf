"""Created on Wed Sep 21 07:32:53 2022 @author: simon.
This script is used to load the data.

Three types of data or loaded and transformed. First
the electricity consumption data from Svenska Kraftnät (SVK) is scraped via their website. This is done
for the whole range 2019-2022.
Second, the wind power data is loaded and transformed. This is done through excel files sent by
SVK. Data for 2019 and 2020 comes in to separete files, both containing 5min data which is transformed
into hourly data. Data for 2021-01 to 2022-11 come in one file with hourly data, and data for
2022-12 come in one file with hourly data.
Finally, the day-ahead electricity price data is loaded, this comes from multiple excel files
provided by Nordpool.
Since the consumption data is scraped from a website, it takes long time to load. There are two
options here. Either run this whole script, which will take some time, or load some (or all) the
DataFrames via the provided DataFrames. They can be loaded with the commands below.
For example, instead of loading the consumption data the:
df_consumption.read_pickle(const.DATA_DIR / "df_consumption") command can be used, then SECTION 1 below
can be skipped.
"""

import datetime as dt
import json
import os
import sys
from datetime import timedelta
from itertools import product
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

from src import constants as const
from src.epf import util

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

data_path = root_dir.parent / "data"
print(data_path)


# # Path where the excel files, and provided DataFrames are placed.
# path = r"C:\Users\simon\OneDrive\Documents\Skola\HT22\EPF_project\data"
# df_consumption = pd.read_pickle(const.DATA_DIR / "df_consumption")
# df_wind = pd.read_pickle(const.DATA_DIR / "df_wind")
# # DataFrames containing consumption + wind + DA prices
# dff = pd.read_pickle(const.DATA_DIR / "df")
# # Same as above but also containing dummies for hour, day and week
# df_dummies = pd.read_pickle(const.DATA_DIR / "df_dummies")

################################# SECTION 1 - CONSUMPTION ###################################
#############################################################################################
#############################################################################################


"""
Web-scraping module which is used to collect the data which is found on
the https://www.svk.se/om-kraftsystemet/kontrollrummet/ website under
"Förbrukning i Sverige". The data is collected from for different JSON
files, one for each price zone.
"""

##################################################################


def read_svk_data(
    start_date: dt.datetime, end_date: dt.datetime, force_run: bool = False
):
    svk_data = const.DATA_DIR / "df_consumption"
    if svk_data.exists() and not force_run:
        print(f"{svk_data} already exists, won't run web scarping.")
    else:
        parsing_range_svk = [
            (start_date + timedelta(n)).strftime("%Y-%m-%d")
            for n in range((end_date - start_date).days)
        ]

        ##################################################################

        base_url = "https://www.svk.se/services/controlroom/v2/situation?date="
        consumption_data = {
            area: {
                date: [
                    {
                        "ts": dt.datetime.fromtimestamp(
                            item["x"] / 1000, tz=ZoneInfo(key="Europe/Stockholm")
                        ),
                        "value": item["y"],
                    }
                    for item in json.loads(
                        urlopen(f"{base_url}{date}&biddingArea={area}").read()
                    )["Data"][0]["data"]
                ]
                for date in parsing_range_svk
            }
            for area in const.BIDDING_AREAS
        }
        import time

        # Check data for missing values.
        util.check_for_missing_data(consumption_data)

        # Add/remove DST points.
        for dates in consumption_data.values():
            for date, points in dates.items():
                if len(points) > 24:
                    util.rm_dst_point(points)
                elif len(points) < 24:
                    util.add_dst_point(points, shift=True)
                else:
                    continue
        util.check_for_missing_data(consumption_data)

        time.sleep(3)

    ########################################## SECTION 2 - WIND ###########################################
    #######################################################################################################
    #######################################################################################################

    """
    The following section is used to transform the wind prognosis data that has been provided
    in excel files by SVK.
    """

    """
    The data for 2019 and 2020 comes in 5min intervals, so it has to be tranformed into hourly data.
    There are two separete scripts, one for 2020 and one for 2019. 2019 contains some
    missing values on 2019-02-10 which are filled using linear interpolation.
    The first lines from each year are removing superflous columns and grouping the 
    date by hour. The following for loop is sorting the data into 4 dataframes based
    on the price zone. The second for loop is merging each dataframe with the datetime
    column. 

    Finally, the data is merged.
    """


def load_wind():
    ##################################################################################3

    import csv
    import datetime as dt
    from collections import OrderedDict, defaultdict

    excel_paths = [
        const.DATA_DIR / "Vindkraftsprognos19.csv",
        const.DATA_DIR,
        "Vindkraftsprognos20.csv",
    ]
    # Initialize a nested defaultdict to hold data structured by area and date
    data_points = defaultdict(lambda: defaultdict(lambda: OrderedDict()))
    for excel_path in excel_paths:
        delimiter = ";" if "20" in excel_path else "|"
        with open(excel_path, "r") as file:
            reader = csv.reader(file, delimiter=delimiter)
            for row in reader:
                # Use the appropriate column for the timestamp and value
                timestamp = dt.datetime.strptime(
                    row[2], "%Y-%m-%d %H:%M:%S.%f"
                )  # This is the 5-minute interval
                value = float(row[4])
                area = row[3]  # This is the area key

                # Round down to the hour
                hour_key = timestamp.replace(minute=0, second=0, microsecond=0)

                # Append the value to the list for the corresponding area and date
                date_key = str(hour_key.date())  # Extract the date
                data_points[area][date_key][hour_key] = {"ts": hour_key, "value": value}

        # Convert to OrderedDict for sorting by area and date
        result = OrderedDict()
        for area, dates in data_points.items():
            result[area] = OrderedDict(sorted(dates.items()))  # Sort by date
            for date in list(
                result[area].keys()
            ):  # Use list to avoid modifying while iterating
                entries = list(result[area][date].values())
                if len(entries) < 2:  # Drop the date if it has fewer than 2 entries
                    del result[area][date]
                else:
                    result[area][date] = entries  # Convert to list of values

    util.check_for_missing_data(result)

    df_wind = pd.read_csv(
        const.DATA_DIR / "Vindkraftsprognos20.csv", sep=";", header=None
    )
    # Drop superflous columns
    df_wind.drop([0, 2], axis=1, inplace=True)
    # Make date column into datetime format
    df_wind[1] = pd.to_datetime(df_wind[1])
    # Group the 5min data into hourly data
    df_wind = df_wind.groupby([pd.Grouper(freq="H", key=1), 3]).mean().reset_index()
    # set datetime column to index
    df_wind.set_index(1, inplace=True)
    # Sort data by column 3 (Price zone)
    df_wind = df_wind.sort_values(by=[2])
    # Make some lists for the for loop
    df_list = ("df1_20", "df2_20", "df3_20", "df4_20")
    start_20 = [0, 8783, 17566, 26349]
    end_20 = [8783, 17566, 26349, 35132]

    # Create separete DFs for each price zone
    for p, i, j in zip(df_list, start_20, end_20):
        locals()[p] = df_wind.iloc[i:j]
        locals()[p].reset_index(inplace=True)
        locals()[p] = locals()[p].sort_values(by=[1])
        locals()[p] = locals()[p].rename(columns={1: "date"})

    # Create 2020 date column
    date_20 = pd.date_range(
        start="01/01/2020", end="23:00 12/31/2020", periods=24 * 366
    )
    date_20 = pd.DataFrame(date_20, columns=["date"])

    # Merge data with date column and data column
    for p, i in zip(df_list, range(1, 5)):
        locals()[p] = pd.merge(date_20, locals()[p], how="left", on="date")
        locals()[p].set_index("date", inplace=True)
        locals()[p].drop([3], axis=1, inplace=True)
        locals()[p] = locals()[p].rename(columns={4: f"SE{i}_W"})

    #############################################################################

    # Same as above but for 2019
    df_wind = pd.read_csv(
        const.DATA_DIR / "Vindkraftsprognos19.csv", sep="|", header=None
    )
    df_wind.drop([0, 2], axis=1, inplace=True)
    df_wind[1] = pd.to_datetime(df_wind[1])
    df_wind = df_wind.groupby([pd.Grouper(freq="H", key=1), 3]).mean().reset_index()
    df_wind.set_index(1, inplace=True)
    df_wind = df_wind.sort_values(by=[3])

    df_list = ("df1_19", "df2_19", "df3_19", "df4_19")
    start_19 = [0, 8748, 17502, 26256]
    end_19 = [8748, 17502, 26256, 35010]
    for p, i, j in zip(df_list, start_19, end_19):
        locals()[p] = df_wind.iloc[i:j]
        locals()[p].reset_index(inplace=True)
        locals()[p] = locals()[p].sort_values(by=[1])
        locals()[p] = locals()[p].rename(columns={1: "date"})

    date_19 = pd.date_range(
        start="01/01/2019", end="23:00 12/31/2019", periods=24 * 365
    )
    date_19 = pd.DataFrame(date_19, columns=["date"])

    for p, i in zip(df_list, range(1, 5)):
        locals()[p] = pd.merge(date_19, locals()[p], how="left", on="date")
        locals()[p].set_index("date", inplace=True)
        locals()[p].drop([3], axis=1, inplace=True)
        locals()[p] = locals()[p].rename(columns={4: f"SE{i}_W"})
        # Replace 0 values (2019-02-10 08:00) with nan to be able to interpolate
        locals()[p] = locals()[p].replace(0, np.nan)
        # Fill missing values on feb 10. 08-19 for SE1, 08-13 for rest with interpolation
        locals()[p] = locals()[p].interpolate(method="linear")

    # Combine the price zones for each year separetely
    df_wind_19 = pd.concat([df1_19, df2_19, df3_19, df4_19], axis=1)
    df_wind_20 = pd.concat([df1_20, df2_20, df3_20, df4_20], axis=1)
    # Fill empty data point 2020-03-29 02:00
    df_wind_20.fillna(935.509, inplace=True)

    # Combine 2020 and 2019
    frames = [df_wind_19, df_wind_20]
    df_wind_1920 = pd.concat(frames)

    #######################################################################################
    """
    Wind prognosis from SVK from 2021-01-01 to 2022-11-30 and from 2022-12-01 to 2022-12-31
    it comes in two separete files with hourly data. First 21/1-22/11 is loaded and tranformed
    then the file for december 2022
    """
    # 21/01 - 22/11
    # Put each Price Zone in separete DataFrames (21/01 - 22/11)
    xls_1 = pd.read_excel(
        const.DATA_DIR / "Vindkraftsprognos2101-2211.xlsx", sheet_name="SE1"
    )
    xls_2 = pd.read_excel(
        const.DATA_DIR / "Vindkraftsprognos2101-2211.xlsx", sheet_name="SE2"
    )
    xls_3 = pd.read_excel(
        const.DATA_DIR / "Vindkraftsprognos2101-2211.xlsx", sheet_name="SE3"
    )
    xls_4 = pd.read_excel(
        const.DATA_DIR / "Vindkraftsprognos2101-2211.xlsx", sheet_name="SE4"
    )

    # Merge the Price Zones into single DataFrame
    xls_12 = pd.merge(xls_1, xls_2, on="Date and Starttime")
    xls_34 = pd.merge(xls_3, xls_4, on="Date and Starttime")
    xls = pd.merge(xls_12, xls_34, on="Date and Starttime")
    # Drop superflous columns
    xls.drop(
        [
            "endtime_x_x",
            "Production MWh(MW)_x_x",
            "endtime_y_x",
            "Production MWh(MW)_y_x",
            "endtime_x_y",
            "Production MWh(MW)_x_y",
            "endtime_y_y",
            "Production MWh(MW)_y_y",
        ],
        axis=1,
        inplace=True,
    )
    # Rename columns
    xls.rename(
        columns={
            "Date and Starttime": "date",
            "Forecast MWh(MW)_x_x": "SE1_W",
            "Forecast MWh(MW)_y_x": "SE2_W",
            "Forecast MWh(MW)_x_y": "SE3_W",
            "Forecast MWh(MW)_y_y": "SE4_W",
        },
        inplace=True,
    )

    df_wind_2122 = xls.copy()
    # Extract correct date range
    df_wind_2122 = df_wind_2122.loc[
        (df_wind_2122["date"] >= "2021-01-01") & (df_wind_2122["date"] < "2022-12-01")
    ]
    # Set date column as index
    df_wind_2122.set_index("date", inplace=True)

    #####################################################################################

    # Read file for 22/12
    xls = pd.read_csv(const.DATA_DIR / "Vindkraftsprognos202212.csv", sep=";")
    xls = xls.sort_values(by=["elomrade", "DatumId", "Tid"])

    # Create list for the for loop to work
    lstt = []
    lst = list(range(744))
    for i in range(4):
        lstt.extend(lst)
    # Set list as index
    lstt = pd.DataFrame(lstt)
    xls.set_index(lstt[0], inplace=True)

    # Divide the 'varde' column into four columns, one for each price zone
    df_wind_22dec = pd.DataFrame()
    loc_1 = [0, 744, 1488, 2232]
    loc_2 = [744, 1488, 2232, 2976]
    for i, j, m in zip(range(1, 5), loc_1, loc_2):
        df_wind_22dec[i] = xls["varde"].iloc[j:m]

    # Create date column
    df_wind_22dec.set_index(
        pd.date_range(start="12/01/2022", end="23:00 12/31/2022", periods=24 * 31),
        inplace=True,
    )
    # Rename columns
    df_wind_22dec = df_wind_22dec.rename(
        columns={1: "SE1_W", 2: "SE2_W", 3: "SE3_W", 4: "SE4_W"}
    )
    # Combine the two created DataFrames
    frames = [df_wind_2122, df_wind_22dec]
    df_wind_2122 = pd.concat(frames)

    ###############################
    # Combine 2019, 2020 and 2021 and 2022
    frames = [df_wind_1920, df_wind_2122]
    df_wind = pd.concat(frames)
    df_wind.reset_index(inplace=True)
    df_wind = df_wind.rename(columns={"index": "date"})
    df_wind.to_pickle(const.DATA_DIR / "df_wind")

    del_list = [
        "date_19",
        "date_20",
        "df1_19",
        "df1_20",
        "df2_19",
        "df2_20",
        "df3_19",
        "df3_20",
        "df4_19",
        "df4_20",
        "df_list",
        "df_wind_19",
        "df_wind_1920",
        "df_wind_20",
        "df_wind_2122",
        "df_wind_22dec",
        "end_19",
        "end_20",
        "frames",
        "i",
        "j",
        "loc_1",
        "loc_2",
        "lst",
        "lstt",
        "m",
        "p",
        "start_19",
        "start_20",
        "xls",
        "xls_1",
        "xls_12",
        "xls_2",
        "xls_3",
        "xls_34",
        "xls_4",
        "i",
    ]
    for i in del_list:
        del locals()[i]

    return df_wind

    ################################# SECTION 3 -  DAY-AHEAD ##################################
    ###########################################################################################
    ###########################################################################################


def day_ahead():
    pd.set_option("display.float_format", lambda x: "%.2f" % x)

    """
    ----- Function to extract Day-Ahead Electricty Price Data
    ----- Takes Data from all four price zones in Sweden
    ----- Takes data from January 2020 until December 2022
    """

    path = 1
    # Create empty list
    df_ = []
    # Create list to use inside "read_excel" command
    price_zones = ["lul", "sund", "sto", "mal"]
    years = ["19", "20", "21", "22"]
    data_range = [f"{zone}eur{year}.xls" for zone, year in product(price_zones, years)]

    def wrangling_func():
        for i in data_range:
            df = pd.read_excel(os.path.join(path, i))
            # drop rows 0 to 3
            df.drop(df.index[[0, 1, 2, 3]], inplace=True)
            # make first row into header
            df.columns = df.iloc[0]
            # Remove first row
            df = df[1:]
            # Change column names
            df.columns = [
                "date",
                0.0,
                1.0,
                2.0,
                "3B",
                3.0,
                4.0,
                5.0,
                6.0,
                7.0,
                8.0,
                9.0,
                10.0,
                11.0,
                12.0,
                13.0,
                14.0,
                15.0,
                16.0,
                17.0,
                18.0,
                19.0,
                20.0,
                21.0,
                22.0,
                23.0,
                "Kjøredag",
                "Daily average",
                "nan",
                "nan",
                "nan",
                "nan",
                "nan",
                "nan",
                "nan",
            ]
            # Drop columns after 26
            df = df.iloc[:, 0:26]
            # Drop 3B
            df = df.drop(["3B"], axis=1)
            # change 1 and 3 from object to float
            df[1.0] = df[1.0].astype(float)
            df[3.0] = df[3.0].astype(float)
            # change date from string to datetime
            df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d %H:%M:%S")
            # Set index to start at 0
            df = df.reset_index(drop=True)
            df = (
                df.melt("date", value_name="Price")
                .assign(
                    date=lambda x: x["date"]
                    + pd.to_timedelta(x.pop("variable").astype(float), unit="h")
                )
                .sort_values("date", ignore_index=True)
            )
            # Change from matrix to array
            df_.append(df)

    # Run function
    wrangling_func()

    ####################################################################################

    """
    ----- This segment is used to merge the files from the list df_ created above by "wrangling_func()"
    ----- The three parts combines prices from each zone from 2020, 2021 and 2022 respectively
    ----- The Last part combines all zones and all year into one DataFrame
    """
    # 2019
    # Merge zone one and two
    df_012 = pd.merge(df_[0], df_[4], on="date")
    # Merge zone three and four
    df_034 = pd.merge(df_[8], df_[12], on="date")
    # Merge the merged DataFrames from above
    df_0 = pd.merge(df_012, df_034, on="date")
    # Rename all columns
    df_0.rename(
        columns={
            "Price_x_x": "Price_REG1",
            "Price_y_x": "Price_REG2",
            "Price_x_y": "Price_REG3",
            "Price_y_y": "Price_REG4",
        },
        inplace=True,
    )
    # Filter away suoerflous obeservations at the beginning and end of the sample
    df_0 = df_0.loc[(df_0["date"] >= "2019-01-01") & (df_0["date"] < "2020-01-01")]
    # 2020
    # Merge zone one and two
    df_112 = pd.merge(df_[1], df_[5], on="date")
    # Merge zone three and four
    df_134 = pd.merge(df_[9], df_[13], on="date")
    # Merge the merged DataFrames from above
    df_1 = pd.merge(df_112, df_134, on="date")
    # Rename all columns
    df_1.rename(
        columns={
            "Price_x_x": "Price_REG1",
            "Price_y_x": "Price_REG2",
            "Price_x_y": "Price_REG3",
            "Price_y_y": "Price_REG4",
        },
        inplace=True,
    )
    # Filter away suoerflous obeservations at the beginning and end of the sample
    df_1 = df_1.loc[(df_1["date"] >= "2020-01-01") & (df_1["date"] < "2021-01-01")]
    #####################################################
    # 2021
    # Merge zone one and two
    df_212 = pd.merge(df_[2], df_[6], on="date")
    # Merge zone three and four
    df_234 = pd.merge(df_[10], df_[14], on="date")
    # Merge the merged DataFrames from above
    df_2 = pd.merge(df_212, df_234, on="date")
    # Rename all columns
    df_2.rename(
        columns={
            "Price_x_x": "Price_REG1",
            "Price_y_x": "Price_REG2",
            "Price_x_y": "Price_REG3",
            "Price_y_y": "Price_REG4",
        },
        inplace=True,
    )
    # Filter away superflous obeservations at the beginning and end of the sample
    df_2 = df_2.loc[(df_2["date"] >= "2021-01-01") & (df_2["date"] < "2022-01-01")]
    #####################################################
    # 2022
    # Merge zone one and two
    df_312 = pd.merge(df_[3], df_[7], on="date")
    # Merge zone three and four
    df_334 = pd.merge(df_[11], df_[15], on="date")
    # Merge the merged DataFrames from above
    df_3 = pd.merge(df_312, df_334, on="date")
    # Rename all columns
    df_3.rename(
        columns={
            "Price_x_x": "Price_REG1",
            "Price_y_x": "Price_REG2",
            "Price_x_y": "Price_REG3",
            "Price_y_y": "Price_REG4",
        },
        inplace=True,
    )
    # Filter away suoerflous obeservations at the beginning and end of the sample
    df_3 = df_3.loc[(df_3["date"] >= "2022-01-01") & (df_3["date"] < "2023-01-01")]
    #####################################################
    # Merge all years together
    df = pd.concat([df_0, df_1, df_2, df_3])
    df.set_index("date", inplace=True)

    ####################################################
    # Fill NaNs following the day-light savings in spring and Autumn
    df.fillna(26.98, limit=1, inplace=True)
    df.fillna(4.28, limit=1, inplace=True)
    df.fillna(18.54, limit=1, inplace=True)
    df.Price_REG1.fillna(54.01, limit=1, inplace=True)
    df.Price_REG2.fillna(54.01, limit=1, inplace=True)
    df.Price_REG3.fillna(54.01, limit=1, inplace=True)
    df.Price_REG4.fillna(76.60, limit=1, inplace=True)
    return df


def merge_data(df_consumption, df, df_wind):
    # Load the Consumption Prognosis from "Create_exogenous_varaibles"
    # df_consumption = pd.read_pickle(const.DATA_DIR / "df_consumption")
    # Merge
    df = pd.merge(df, df_consumption, on="date")
    # Load the Windpower Prognosis from "Create_exogenous_varaibles"
    df_wind = pd.read_pickle(const.DATA_DIR / "df_wind")
    # df_wind.reset_index(inplace=True)
    # df_wind.drop(["index"], axis=1, inplace=True)
    # Merge
    df = pd.merge(df, df_wind, on="date")

    # Making Columns for Hour of Week, Day of Week and Hour of Day
    df_dummies = df.copy()

    df_dummies["Hour of Week"] = (
        ((df_dummies["date"].dt.dayofweek) * 24 + 24)
        - (24 - df_dummies["date"].dt.hour)
        + 1
    )
    df_dummies["Day of Week"] = df_dummies["date"].dt.dayofweek + 1
    df_dummies["Hour of Day"] = df_dummies["date"].dt.hour + 1

    ########## Get hourly dummies #####################

    df_dummies.set_index("date", inplace=True)

    hours = pd.get_dummies(df_dummies["Hour of Day"], prefix="hour")
    df_dummies = pd.concat([df_dummies, hours], axis=1)
    del hours

    dayofweek = pd.get_dummies(df_dummies["Day of Week"], prefix="day")
    df_dummies = pd.concat(
        [
            df_dummies,
            dayofweek,
        ],
        axis=1,
    )
    del dayofweek

    del_list = [
        "data_range",
        "i",
        "df_0",
        "df_012",
        "df_034",
        "df_",
        "df_1",
        "df_112",
        "df_134",
        "df_2",
        "df_212",
        "df_234",
        "df_3",
        "df_312",
        "df_334",
        "df_consumption",
        "df_wind",
    ]
    for i in del_list:
        del locals()[i]
    del del_list
    del i

    return df_dummies

    # df.to_pickle(const.DATA_DIR / "df")
    # df_dummies.to_pickle(const.DATA_DIR / "df_dummies")
