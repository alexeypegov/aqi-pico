import sys
import time
from secrets import AQI_TOKEN, PASSWORD, SSID

import ntptime
from machine import Timer
from uio import StringIO

from config import OFF_HOUR, ON_HOUR, TIME_ZONE_OFFSET_SEC, WIFI_COUNTRY
from led_rgb import Matrix
from wifi import Wifi, http_get_json

last_time_sync = None
last_data_sync = None
data = None
show_temp = False
sleeping = False

wifi = Wifi(SSID, PASSWORD, WIFI_COUNTRY)
matrix = Matrix()

crashed = False


def get_trace(ex):
    s = StringIO()
    sys.print_exception(ex, s)
    return s.getvalue()


def write_stacktrace(e):
    f = open(f"stacktrace-{time.time()}.log", "w")
    f.write(get_trace(e))
    f.close()


def local_time(secs=time.time(), utc_offset_sec=TIME_ZONE_OFFSET_SEC):
    return secs + utc_offset_sec


def format_secs(secs=local_time()):
    t = time.localtime(secs)
    return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"


def log(msg):
    print(f"{format_secs()} {msg}")


def next_time_sync_at(sync_interval_min=24 * 60):
    global last_time_sync
    return 0 if last_time_sync is None else last_time_sync + sync_interval_min * 60


def next_data_sync_at(sync_interval_min=30):
    global last_data_sync
    return 0 if last_data_sync is None else last_data_sync + sync_interval_min * 60


def should_sync_data():
    return next_data_sync_at() < local_time()


def should_sync_time():
    return next_time_sync_at() < local_time()


def sync_time():
    global last_time_sync
    if not should_sync_time():
        return

    log("syncing time...")
    (year_b4, month_b4, day_b4, hour_b4, minute_b4, second_b4, _, _) = time.localtime()

    try:
        ntptime.settime()
        (year, month, day, hour, minute, second, _, _) = time.localtime()
        last_time_sync = local_time()
        log(
            f"time synced ok, {year_b4}-{month_b4}-{day_b4} {hour_b4}:{minute_b4}:{second_b4} -> {year}-{month}-{day} {hour}:{minute}:{second}, next sync at {format_secs(next_time_sync_at())}"
        )
    except Exception as e:
        log(f"failed to sync time: {e}")


def parse_aqi_data(data):
    aqi = data.get("data", {}).get("aqi", -1)
    temp = round(data.get("data", {}).get("iaqi", {}).get("t", {}).get("v", -99))
    return (aqi, temp)


def sync_data():
    if not should_sync_data():
        return

    log("syncing data...")
    global data, last_data_sync
    (ok, result) = http_get_json(
        f"https://api.waqi.info/feed/here/?token={AQI_TOKEN}", parse_aqi_data
    )
    if ok:
        last_data_sync = local_time()
        log(f"data synced ok, next sync at {format_secs(next_data_sync_at())}")
        data = result
    else:
        log(f"data sync failed, value='{data}'")


def handle_exception(ex):
    global matrix, crashed
    write_stacktrace(ex)
    matrix.clear()
    matrix.draw_value(":(", matrix.RED)
    matrix.write()
    crashed = True


def sync_all():
    try:
        sync_time()
        sync_data()
    except Exception as ex:
        handle_exception(ex)


def get_info(data):
    global show_temp, matrix
    (aqi, temp) = data

    if show_temp:
        if temp < 0:
            return (temp, matrix.BLUE, True)
        elif temp < 5:
            return (temp, matrix.CYAN, True)
        elif temp < 15:
            return (temp, matrix.WHITE, True)
        elif temp < 25:
            return (temp, matrix.YELLOW, True)
        elif temp < 35:
            return (temp, matrix.ORANGE, True)
        else:
            return (temp, matrix.RED, True)
    else:
        if aqi < 50:
            return (aqi, matrix.GREEN, False)
        elif aqi < 100:
            return (aqi, matrix.YELLOW, False)
        elif aqi < 150:
            return (aqi, matrix.ORANGE, False)
        elif aqi < 200:
            return (min(aqi, 199), matrix.RED, False)
        else:
            return (":(", matrix.VIOLET, False)


def show_count(x):
    global matrix

    matrix.clear()
    if x >= 0:
        matrix.draw_value(x, matrix.WHITE)
    else:
        matrix.draw_value(":(", matrix.YELLOW)
    matrix.write()


def do_update(
    _=None, retries=3, on_retry=lambda _: None, show_start=ON_HOUR, show_end=OFF_HOUR
):
    global sleeping, data, show_temp, matrix, wifi

    if wifi.busy:
        log("wifi is busy, skipping...")
        return

    t = time.localtime(local_time())
    current_year = t[0]
    current_hour = t[3]
    if current_year > 2021:  # initially it is 2021.01.01
        if current_hour >= show_start and current_hour < show_end:
            if sleeping:
                sleeping = False
        elif not sleeping:
            sleeping = True
            matrix.clear()
            matrix.write()

    if sleeping:
        log(f"sleeping {show_end} <= {current_hour} < {show_start}...")
        return

    if should_sync_data() or should_sync_time():
        (ok, _) = wifi.with_connection(
            sync_all, on_retry=on_retry, max_retries=retries, log=log
        )
        if not ok:
            log("unable to connect to wifi, will retry in next cycle...")

    if data is None:
        return

    try:
        (v, color, show_sign) = get_info(data)
        matrix.clear()
        matrix.draw_value(v, color, show_sign=show_sign)
        show_temp = not show_temp
        matrix.write()
    except Exception as ex:
        handle_exception(ex)


def start(screen_update_secs=20):
    global crashed

    do_update(retries=10, on_retry=show_count)

    timer = Timer(-1)
    timer.init(
        period=screen_update_secs * 1000, mode=Timer.PERIODIC, callback=do_update
    )

    while True:
        if crashed:
            timer.deinit()
            break
        time.sleep(0.5)


if __name__ == "__main__":
    log("Starting app, waiting 3 sec for interrupt...")
    matrix.draw_value(":)", matrix.WHITE)
    matrix.write()

    time.sleep(3)

    start()
