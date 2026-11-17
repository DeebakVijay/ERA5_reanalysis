ERA5 REANALYSIS HOURLY DOWNLOADER

Main script:
    DownloadERA5reanalysis.py

Configuration:
    Dowload_ERA5_reanalysis_config.py

Output:

    ERA5_reanalysis/
    |
    |-- data/
    |     |-- ERA5_Single_YYYY_MM_DD.grib
    |     |-- ERA5_Pressure_YYYY_MM_DD.grib
    |
    |-- logs/
          |-- YYYYMMDD_domain.png
          |-- YYYYMMDD_ERA5_download.log

Each daily file contains all configured UTC hours.