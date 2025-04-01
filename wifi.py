import time
from random import randint

import network
import requests
import rp2

WLAN_STATUSES = {
    -3: "WLAN_BADAUTH: Authentication failed",
    -1: "WLAN_FAIL: Connection failed",
    -2: "WLAN_NONET: No network found",
    0: "WLAN_DOWN: No connection and no activity",
    1: "WLAN_JOIN: Connecting in progress",
    2: "WLAN_NOIP: Connected to WiFi but no IP address",
    3: "WLAN_UP: Connected with IP address (success)",
}


class Wifi:
    def __init__(self, ssid, password, country=None):
        self.ssid = ssid
        self.password = password
        self.busy = False

        if country is not None:
            rp2.country(country)

    def with_connection(
        self, callback, max_retries=3, timeout=10, on_retry=lambda _: None, log=print
    ):
        if self.busy:
            log("wifi is busy, skipping...")
            return

        log(f"wifi network country is set to {network.country()}...")

        self.busy = True
        try:
            wlan = network.WLAN(network.STA_IF)
            retry = 1

            while True:
                log(f"wifi connecting '{self.ssid}', retry={str(retry)}")

                on_retry(retry)

                if wlan.active():
                    log("wifi active, deactivating...")
                    wlan.disconnect()
                    wlan.deinit()
                    time.sleep(1)
                    wlan = network.WLAN(network.STA_IF)

                if not wlan.active():
                    log("wifi not active, activating...")
                    wlan.config(pm=0xA11140)  # turn off wireless power saving
                    wlan.active(True)
                    time.sleep(2)

                for n in wlan.scan():
                    log(f"network: {n[0]}")

                wlan.connect(self.ssid, self.password)
                max_wait = timeout
                while max_wait > 0:
                    if wlan.status() < 0 or wlan.status() >= 3:
                        break

                    log(f"wifi connecting: {WLAN_STATUSES[wlan.status()]}")
                    max_wait -= 1
                    time.sleep(1)

                if wlan.isconnected():
                    log(f"wifi connected as {wlan.ifconfig()[0]}")
                    return (True, callback())
                else:
                    if (retry + 1) <= max_retries:
                        wait = randint(1, 5)
                        log(
                            f"wifi not connected: {WLAN_STATUSES[wlan.status()]}, will retry in {wait} secs..."
                        )
                        time.sleep(wait)
                        retry += 1
                    else:
                        log(
                            f"wifi connection failed with {WLAN_STATUSES[wlan.status()]} after {retry} retries..."
                        )
                        on_retry(-1)
                        break

            return (False, WLAN_STATUSES[wlan.status()])
        finally:
            log("wifi disconnecting...")
            wlan.disconnect()
            wlan.deinit()
            self.busy = False


def http_get_json(url, callback, timeout=10):
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code != 200:
            msg = f"unable to get data from '{url}': code={response.status_code}, reason='{response.reason}', content='{response.content}'"
            response.close()
            return (False, msg)

        data = response.json()
        response.close()
        return (True, callback(data))
    except Exception as e:
        return (False, f"ERROR: unable to get data from {url}: {e}")
