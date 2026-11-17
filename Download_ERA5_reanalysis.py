
"""
============================================================
ERA5 REANALYSIS HOURLY DOWNLOADER
============================================================

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

============================================================
"""


# ============================================================
# 1. IMPORT LIBRARIES
# ============================================================

import os
import time
import logging

from pathlib import Path
from datetime import datetime, date, timedelta

import cdsapi


# ============================================================
# 2. IMPORT CONFIGURATION
# ============================================================

project_root = Path(__file__).resolve().parent

import Dowload_ERA5_reanalysis_config as config


# ============================================================
# 3. DEFINE OUTPUT DIRECTORIES
# ============================================================

ERA5_data_dir = project_root / "data"

log_folder = project_root / "logs"

ERA5_data_dir.mkdir(parents=True, exist_ok=True)

log_folder.mkdir(parents=True, exist_ok=True)


# Machine execution date

RUN_DATE = datetime.now().strftime("%Y%m%d")


# Log and domain image filenames

log_file = log_folder / f"{RUN_DATE}_ERA5_download.log"

domain_file = log_folder / f"{RUN_DATE}_domain.png"


# Skip existing non-empty files

SKIP_EXISTING_FILES = True


# ============================================================
# 4. CONFIGURE LOGGING
# ============================================================

logger = logging.getLogger("ERA5_Downloader")

logger.setLevel(logging.INFO)

logger.handlers.clear()

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

file_handler = logging.FileHandler(
    log_file,
    mode="w",
    encoding="utf-8"
)

console_handler = logging.StreamHandler()

file_handler.setFormatter(formatter)

console_handler.setFormatter(formatter)

logger.addHandler(file_handler)

logger.addHandler(console_handler)


# ============================================================
# 5. DATASET CONFIGURATION
# ============================================================

dataset_single = config.dataset_single

dataset_pressure = config.dataset_pressure


# ============================================================
# 6. GENERATE DATE RANGE
# ============================================================

def generate_date_range(
    start_year, start_month, start_day,
    end_year, end_month, end_day
):

    start_date = date(
        start_year,
        start_month,
        start_day
    )

    end_date = date(
        end_year,
        end_month,
        end_day
    )

    if end_date < start_date:

        raise ValueError(
            "End date cannot precede start date."
        )

    date_list = []

    current_date = start_date

    while current_date <= end_date:

        date_list.append(current_date)

        current_date += timedelta(days=1)

    return date_list


# ============================================================
# 7. VALIDATE UTC TIME LIST
# ============================================================

def validate_times(time_list):

    validated_times = []

    for utc_time in time_list:

        parsed_time = datetime.strptime(
            utc_time,
            "%H:%M"
        )

        if parsed_time.minute != 0:

            raise ValueError(
                f"Only hourly timestamps are supported: {utc_time}"
            )

        if utc_time not in validated_times:

            validated_times.append(utc_time)

    if not validated_times:

        raise ValueError(
            "No UTC timestamps configured."
        )

    return validated_times


# ============================================================
# 8. GENERATE OUTPUT FILENAMES
# ============================================================

def generate_filename(level_type, current_date):

    date_string = current_date.strftime("%Y_%m_%d")

    if level_type == "single":

        filename = (
            f"ERA5_Single_{date_string}.grib"
        )

    elif level_type == "pressure":

        filename = (
            f"ERA5_Pressure_{date_string}.grib"
        )

    else:

        raise ValueError(
            "Unknown dataset type."
        )

    return ERA5_data_dir / filename


# ============================================================
# 9. CREATE DOMAIN MAP
# ============================================================

def create_domain_map():

    import matplotlib.pyplot as plt

    import cartopy.crs as ccrs

    import cartopy.feature as cfeature

    from matplotlib.patches import Rectangle

    north = config.North

    south = config.South

    west = config.West

    east = config.East

    if not (south < north and west < east):

        raise ValueError(
            "Invalid domain coordinates."
        )

    projection = ccrs.PlateCarree()

    fig = plt.figure(figsize=(12, 8))

    ax = fig.add_subplot(
        1, 1, 1,
        projection=projection
    )

    ax.set_extent(
        [west, east, south, north],
        crs=projection
    )

    # Land and ocean

    ax.add_feature(
        cfeature.OCEAN,
        facecolor="#DCEAF3"
    )

    ax.add_feature(
        cfeature.LAND,
        facecolor="#EEE9DC"
    )

    # Geographic boundaries

    ax.coastlines(
        resolution="110m",
        linewidth=0.8
    )

    ax.add_feature(
        cfeature.BORDERS,
        linewidth=0.6,
        edgecolor="black"
    )

    # ERA5 extraction domain

    domain_rectangle = Rectangle(
        (west, south),
        east - west,
        north - south,
        linewidth=2,
        edgecolor="red",
        facecolor="none",
        transform=projection
    )

    ax.add_patch(domain_rectangle)

    # Latitude and longitude gridlines

    gridlines = ax.gridlines(
        draw_labels=True,
        linewidth=0.5,
        color="gray",
        alpha=0.6,
        linestyle="--"
    )

    gridlines.top_labels = False

    gridlines.right_labels = False

    ax.set_title(
        "ERA5 Download Domain\n"
        f"North={north} | South={south} | "
        f"West={west} | East={east}",
        fontsize=13
    )

    fig.savefig(
        domain_file,
        dpi=250,
        bbox_inches="tight"
    )

    plt.close(fig)

    logger.info(
        "Domain figure successfully saved: %s",
        domain_file
    )


# ============================================================
# 10. COMMON CDS REQUEST PARAMETERS
# ============================================================

def generate_common_request(current_date, utc_times):

    return {

        "product_type": config.product_type,

        "year": [
            current_date.strftime("%Y")
        ],

        "month": [
            current_date.strftime("%m")
        ],

        "day": [
            current_date.strftime("%d")
        ],

        # All configured UTC hours in one request

        "time": utc_times,

        "data_format": config.data_format,

        "download_format": config.download_format,

        "area": config.area

    }


# ============================================================
# 11. DOWNLOAD ONE COMPLETE DAY
# ============================================================

def download_era5(
    client,
    level_type,
    current_date,
    utc_times
):

    output_file = generate_filename(
        level_type,
        current_date
    )

    # --------------------------------------------------------
    # Skip existing files
    # --------------------------------------------------------

    if (
        SKIP_EXISTING_FILES
        and output_file.exists()
        and output_file.stat().st_size > 0
    ):

        logger.info(
            "SKIPPED | %s | %s | %s",
            level_type.upper(),
            current_date,
            output_file.name
        )

        return "skipped", 0.0


    # --------------------------------------------------------
    # Build common request
    # --------------------------------------------------------

    common_request = generate_common_request(
        current_date,
        utc_times
    )


    # --------------------------------------------------------
    # Select dataset and variables
    # --------------------------------------------------------

    if level_type == "single":

        dataset = dataset_single

        request = {
            **common_request,

            "variable": config.variable_single
        }

    elif level_type == "pressure":

        dataset = dataset_pressure

        request = {
            **common_request,

            "variable": config.variable_pressure,

            "pressure_level": config.pressure_level
        }

    else:

        raise ValueError(
            "Unknown dataset type."
        )


    # --------------------------------------------------------
    # Prepare temporary output file
    # --------------------------------------------------------

    temporary_file = output_file.with_name(
        output_file.name + ".part"
    )

    if temporary_file.exists():

        temporary_file.unlink()


    download_start = time.perf_counter()

    logger.info("-" * 70)

    logger.info(
        "STARTING | %s | %s",
        level_type.upper(),
        current_date
    )

    logger.info(
        "UTC hours requested: %d",
        len(utc_times)
    )

    logger.info(
        "Hours: %s",
        utc_times
    )

    logger.info(
        "Dataset: %s",
        dataset
    )

    logger.info(
        "Output: %s",
        output_file
    )


    # --------------------------------------------------------
    # Start download
    # --------------------------------------------------------

    try:

        client.retrieve(
            dataset,
            request
        ).download(str(temporary_file))


        # ----------------------------------------------------
        # Validate downloaded file
        # ----------------------------------------------------

        if (
            not temporary_file.exists()
            or temporary_file.stat().st_size == 0
        ):

            raise RuntimeError(
                "Downloaded file is missing or empty."
            )


        # ----------------------------------------------------
        # Rename after successful download
        # ----------------------------------------------------

        os.replace(
            temporary_file,
            output_file
        )


        elapsed = (
            time.perf_counter() - download_start
        )

        file_size = (
            output_file.stat().st_size / (1024 ** 2)
        )


        logger.info(
            "SUCCESS | %s | %s",
            level_type.upper(),
            current_date
        )

        logger.info(
            "File: %s",
            output_file.name
        )

        logger.info(
            "File size: %.2f MB",
            file_size
        )

        logger.info(
            "Download time: %.2f minutes",
            elapsed / 60
        )

        return "success", elapsed


    except Exception:

        elapsed = (
            time.perf_counter() - download_start
        )

        logger.exception(
            "FAILED | %s | %s",
            level_type.upper(),
            current_date
        )

        if temporary_file.exists():

            try:

                temporary_file.unlink()

            except OSError:

                logger.exception(
                    "Unable to remove partial file."
                )

        return "failed", elapsed


# ============================================================
# 12. MAIN EXECUTION
# ============================================================

def main():

    total_start = time.perf_counter()


    # --------------------------------------------------------
    # Download statistics
    # --------------------------------------------------------

    statistics = {

        "single": {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "time": 0.0
        },

        "pressure": {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "time": 0.0
        }

    }


    try:

        # ----------------------------------------------------
        # Generate dates and UTC hours
        # ----------------------------------------------------

        DATE_LIST = generate_date_range(

            config.START_YEAR,
            config.START_MONTH,
            config.START_DAY,

            config.END_YEAR,
            config.END_MONTH,
            config.END_DAY

        )

        TIME_LIST = validate_times(
            config.time_list
        )


        # ----------------------------------------------------
        # Log configuration
        # ----------------------------------------------------

        logger.info("=" * 70)

        logger.info(
            "ERA5 REANALYSIS DOWNLOAD STARTED"
        )

        logger.info("=" * 70)

        logger.info(
            "Project directory: %s",
            project_root
        )

        logger.info(
            "Data directory: %s",
            ERA5_data_dir
        )

        logger.info(
            "Log directory: %s",
            log_folder
        )

        logger.info(
            "Configured dates: %s to %s",
            DATE_LIST[0],
            DATE_LIST[-1]
        )

        logger.info(
            "Number of dates: %d",
            len(DATE_LIST)
        )

        logger.info(
            "UTC timestamps per day: %d",
            len(TIME_LIST)
        )

        logger.info(
            "UTC timestamps: %s",
            TIME_LIST
        )

        logger.info(
            "Domain [N,W,S,E]: %s",
            config.area
        )

        logger.info(
            "Single-level variables: %s",
            config.variable_single
        )

        logger.info(
            "Pressure-level variables: %s",
            config.variable_pressure
        )

        logger.info(
            "Pressure levels: %s",
            config.pressure_level
        )


        # ----------------------------------------------------
        # Total planned downloads
        # ----------------------------------------------------

        total_planned = (
            len(DATE_LIST) * 2
        )

        logger.info(
            "Total planned daily files: %d",
            total_planned
        )


        # ----------------------------------------------------
        # Create domain map
        # ----------------------------------------------------

        logger.info(
            "Creating domain map..."
        )

        try:

            create_domain_map()

        except Exception:

            logger.exception(
                "Domain map creation failed. "
                "Downloads will continue."
            )


        # ----------------------------------------------------
        # Initialise CDS API
        # ----------------------------------------------------

        logger.info(
            "Initialising CDS API client..."
        )

        client = cdsapi.Client()


        # ----------------------------------------------------
        # Download loop
        #
        # One date
        #     |
        #     |-- Single-level: all hours
        #     |
        #     |-- Pressure-level: all hours
        #
        # Two requests per day.
        # ----------------------------------------------------

        request_number = 0

        for current_date in DATE_LIST:

            logger.info("")

            logger.info("=" * 70)

            logger.info(
                "PROCESSING DATE: %s",
                current_date
            )

            logger.info("=" * 70)


            for level_type in [
                "single",
                "pressure"
            ]:

                request_number += 1

                logger.info(
                    "PROGRESS: %d/%d",
                    request_number,
                    total_planned
                )

                status, elapsed = download_era5(

                    client,

                    level_type,

                    current_date,

                    TIME_LIST

                )

                statistics[level_type][status] += 1

                statistics[level_type]["time"] += elapsed


        # ----------------------------------------------------
        # FINAL SUMMARY
        # ----------------------------------------------------

        total_elapsed = (
            time.perf_counter() - total_start
        )

        logger.info("")

        logger.info("=" * 70)

        logger.info(
            "FINAL ERA5 DOWNLOAD SUMMARY"
        )

        logger.info("=" * 70)


        for level_type in [
            "single",
            "pressure"
        ]:

            result = statistics[level_type]

            logger.info(
                "%s LEVELS",
                level_type.upper()
            )

            logger.info(
                "Successful downloads: %d",
                result["success"]
            )

            logger.info(
                "Failed downloads: %d",
                result["failed"]
            )

            logger.info(
                "Skipped downloads: %d",
                result["skipped"]
            )

            logger.info(
                "Download time: %.2f minutes",
                result["time"] / 60
            )


        # ----------------------------------------------------
        # Overall statistics
        # ----------------------------------------------------

        total_success = (

            statistics["single"]["success"]

            + statistics["pressure"]["success"]

        )

        total_failed = (

            statistics["single"]["failed"]

            + statistics["pressure"]["failed"]

        )

        total_skipped = (

            statistics["single"]["skipped"]

            + statistics["pressure"]["skipped"]

        )


        logger.info("-" * 70)

        logger.info(
            "Total planned: %d",
            total_planned
        )

        logger.info(
            "Total successful: %d",
            total_success
        )

        logger.info(
            "Total failed: %d",
            total_failed
        )

        logger.info(
            "Total skipped: %d",
            total_skipped
        )

        logger.info(
            "Overall elapsed time: %.2f minutes",
            total_elapsed / 60
        )

        logger.info(
            "Data directory: %s",
            ERA5_data_dir
        )

        logger.info(
            "Log file: %s",
            log_file
        )

        logger.info(
            "Domain figure: %s",
            domain_file
        )


        # ----------------------------------------------------
        # Completion status
        # ----------------------------------------------------

        if total_failed == 0:

            logger.info(
                "ALL DOWNLOADS COMPLETED SUCCESSFULLY."
            )

        else:

            logger.warning(
                "%d DOWNLOADS FAILED. CHECK THE LOG.",
                total_failed
            )

        logger.info("=" * 70)


    except Exception:

        logger.exception(
            "FATAL ERROR: DOWNLOAD PROCESS TERMINATED."
        )

        raise


    finally:

        logger.info(
            "ERA5 DOWNLOADER EXECUTION FINISHED."
        )

        logging.shutdown()


# ============================================================
# 13. EXECUTE SCRIPT
# ============================================================

if __name__ == "__main__":

    main()
